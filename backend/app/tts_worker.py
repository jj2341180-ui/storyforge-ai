"""Subprocess TTS worker.

Piper/onnxruntime reserves a large CPU memory arena (~200 MB) that is never returned to the
OS while the parent process lives. On 512 MB containers that leaves too little room for
FFmpeg renders, so constrained deployments run synthesis here: the worker loads the voice,
writes the WAV, prints a JSON result line, and exits — giving every byte back immediately.

Invocation:  python -m app.tts_worker '{"text": "...", "model": "/path/voice.onnx",
                                        "out": "/path/out.wav", "speed": 1.0}'
"""
from __future__ import annotations

import json
import sys
import wave


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m app.tts_worker <json-args>", file=sys.stderr)
        return 2
    args = json.loads(sys.argv[1])
    try:
        from piper import PiperVoice
        from piper.config import SynthesisConfig
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"error": f"Piper unavailable: {exc}"}))
        return 1

    length_scale = max(0.6, min(1.8, 1.0 / max(0.5, min(2.0, float(args.get("speed", 1.0))))))
    voice = PiperVoice.load(args["model"])
    with wave.open(args["out"], "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit PCM
        wav_file.setframerate(voice.config.sample_rate)
        voice.synthesize_wav(
            args["text"], wav_file,
            syn_config=SynthesisConfig(length_scale=length_scale),
            set_wav_format=False,
        )
    with wave.open(args["out"], "rb") as w:
        duration = w.getnframes() / float(w.getframerate())
    print(json.dumps({"ok": True, "duration": round(duration, 3),
                      "sample_rate": voice.config.sample_rate}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
