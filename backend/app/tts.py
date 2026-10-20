"""
Local text-to-speech via Piper (fully offline, open source, no API key).

Voice files (*.onnx + *.onnx.json) are discovered in VOICES_DIR. Users can drop in
any voice from https://huggingface.co/rhasspy/piper-voices - see SETUP.md
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any

from .config import VOICES_DIR

# When enabled, Piper runs in a short-lived child process so its ~200 MB onnxruntime arena
# is fully released before video rendering (needed on 512 MB containers; see tts_worker.py).
TTS_SUBPROCESS = os.environ.get("STORYFORGE_TTS_SUBPROCESS", "").strip() in ("1", "true", "yes")

# Best-effort gender hints for common Piper voices; unknown voices are labeled "neutral".
GENDER_HINTS = {
    "amy": "feminine", "hfc": "feminine", "lessac": "masculine", "joe": "masculine",
    "ryan": "masculine", "kusal": "masculine", "libritts": "neutral", "norman": "masculine",
    "danny": "masculine", "lisa": "feminine", "alan": "masculine", "kristin": "feminine",
}


def list_voices() -> list[dict[str, str]]:
    voices = []
    for onnx in sorted(VOICES_DIR.glob("*.onnx")):
        key = onnx.stem  # e.g. en_US-amy-low
        lang = key.split("-")[0].replace("_", "-")
        name = key.split("-")[1] if "-" in key else key
        quality = key.split("-")[2] if len(key.split("-")) > 2 else ""
        gender = GENDER_HINTS.get(name.split("(")[0].lower(), "neutral")
        voices.append({
            "id": key,
            "label": f"{name.replace('_', ' ').title()} ({lang}, {quality or 'custom'})",
            "language": lang,
            "gender": gender,
            "path": str(onnx),
            "engine": "piper",
        })
    return voices


def tts_available() -> bool:
    return len(list_voices()) > 0


def wav_duration(path: str | Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def synthesize(text: str, voice_id: str, out_path: Path, speed: float = 1.0) -> dict[str, Any]:
    """Synthesize WAV. speed <1 is slower, >1 faster. Returns duration info."""
    voices = {v["id"]: v for v in list_voices()}
    if voice_id not in voices:
        raise RuntimeError(f"Voice '{voice_id}' is not installed. Installed: {list_voices() or 'none'}")
    model = voices[voice_id]["path"]
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if TTS_SUBPROCESS:
        # Constrained-memory deployment: isolate onnxruntime in a process that exits.
        payload = json.dumps({"text": text, "model": model,
                              "out": str(out_path), "speed": speed})
        proc = subprocess.run(
            [sys.executable, "-m", "app.tts_worker", payload],
            capture_output=True, text=True, timeout=300,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Piper worker failed: {proc.stderr[-500:] or proc.stdout[-500:]}")
        result_line = proc.stdout.strip().splitlines()[-1]
        info = json.loads(result_line)
        if "error" in info:
            raise RuntimeError(info["error"])
        return {
            "path": str(out_path),
            "duration": round(float(info.get("duration") or wav_duration(out_path)), 3),
            "voice": voice_id,
            "speed": speed,
            "engine": "piper-local-subprocess",
        }

    try:
        from piper import PiperVoice  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Piper TTS package missing. Install with: pip install piper-tts (see SETUP.md)."
        ) from exc

    from piper.config import SynthesisConfig  # type: ignore

    voice = PiperVoice.load(model)
    # Piper length_scale: lower = faster. Clamp to a sane range.
    length_scale = max(0.6, min(1.8, 1.0 / max(0.5, min(2.0, speed))))
    with wave.open(str(out_path), "wb") as wav_file:
        # Newer Piper versions leave WAV header setup to the caller.
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit PCM
        wav_file.setframerate(voice.config.sample_rate)
        voice.synthesize_wav(
            text, wav_file,
            syn_config=SynthesisConfig(length_scale=length_scale),
            set_wav_format=False,
        )
    return {
        "path": str(out_path),
        "duration": round(wav_duration(out_path), 3),
        "voice": voice_id,
        "speed": speed,
        "engine": "piper-local",
    }


def voice_install_help() -> dict[str, Any]:
    return {
        "available": tts_available(),
        "engine": "Piper (local, open source)",
        "voices_dir": str(VOICES_DIR),
        "installed": list_voices(),
        "instructions": (
            "Download any *.onnx and *.onnx.json voice from "
            "https://huggingface.co/rhasspy/piper-voices/tree/main and place both files in the "
            "voices directory above, then restart the backend. English plus 20+ languages are available. "
            "Alternative free fallback: record/import your own narration, or preview with your browser's "
            "built-in SpeechSynthesis (no files are produced for video export)."
        ),
    }
