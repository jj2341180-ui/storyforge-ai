"""VoiceForge — a free AI voice studio (ElevenLabs-style, but with no paid tier).

Primary engine: edge-tts, which streams Microsoft's public neural TTS voices. It needs no
API key and no account. Offline fallback: the local Piper engine already shipped with
StoryForge, so a blocked network can never make the studio unusable.

Everything runs as short background jobs behind a single worker lock: the neural endpoint
is rate-limited per IP, and the 512 MB free host only has room for one encode at a time.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import edge_tts
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import tts
from .config import DATA_DIR, FFMPEG, FFMPEG_THREADS
from .renderer import media_duration

router = APIRouter(prefix="/api/voice", tags=["voice"])

# ---------------------------------------------------------------- storage & limits

VOICE_DIR = DATA_DIR / "voice"
AUDIO_DIR = VOICE_DIR / "audio"
TEMP_DIR = VOICE_DIR / "temp"
HISTORY_FILE = VOICE_DIR / "history.json"
EDGE_CACHE = VOICE_DIR / "edge-voices.json"
for _d in (AUDIO_DIR, TEMP_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Generous caps that still finish on a free shared CPU (the free neural endpoint streams
# roughly in real time; 5,000 characters is about six minutes of finished audio).
MAX_SPEAK_CHARS = 5_000
MAX_STUDIO_BLOCKS = 10
MAX_BLOCK_CHARS = 2_000
EDGE_TIMEOUT_SECONDS = 240

# "edge" (default) uses the free neural endpoint; "piper" forces the fully offline engine
# (also used automatically whenever the neural endpoint fails).
ENGINE = os.environ.get("STORYFORGE_VOICE_ENGINE", "edge").strip().lower()

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_work_lock = threading.Lock()      # one generation at a time, process-wide
_history_lock = threading.Lock()
_catalog_lock = threading.Lock()


# ---------------------------------------------------------------- voice catalog

def _normalize_edge_voice(raw: dict[str, Any]) -> dict[str, str]:
    friendly = (raw.get("FriendlyName") or raw.get("ShortName") or "").replace("Microsoft ", "")
    personalities = raw.get("VoiceTag", {}).get("VoicePersonalities", []) or []
    locale = raw.get("Locale", "unknown")
    return {
        "id": raw.get("ShortName", ""),
        "label": friendly.split(" Online (Natural)")[0].split(" - ")[0],
        "locale": locale,
        "lang": locale.split("-")[0],
        "region": locale.split("-")[1] if "-" in locale else "",
        "gender": (raw.get("Gender") or "Neutral").lower(),
        "personalities": ", ".join(personalities),
        "engine": "edge",
        "engine_label": "Neural voice · free",
    }


async def _fetch_edge_voices_async() -> list[dict[str, str]]:
    raw = await edge_tts.list_voices()
    return [_normalize_edge_voice(v) for v in raw if v.get("ShortName")]


def _load_cached_edge() -> list[dict[str, str]]:
    try:
        return json.loads(EDGE_CACHE.read_text())
    except Exception:
        return []


def _piper_catalog() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for v in tts.list_voices():
        out.append({
            "id": v["id"],
            "label": f"{v['label']} (offline)",
            "locale": v["language"].replace("-", "-"),
            "lang": v["language"].split("-")[0],
            "region": "",
            "gender": v.get("gender", "neutral"),
            "personalities": "",
            "engine": "piper",
            "engine_label": "Offline voice · free",
        })
    return out


def catalog() -> dict[str, Any]:
    """Full voice catalog. Neural voices are cached; failures fall back to disk/offline."""
    with _catalog_lock:
        edge_voices = _load_cached_edge()
        edge_ok = bool(edge_voices)
        if not edge_voices:
            try:
                edge_voices = asyncio.run(_fetch_edge_voices_async())
                EDGE_CACHE.write_text(json.dumps(edge_voices))
                edge_ok = True
            except Exception:
                edge_voices, edge_ok = [], False
        piper_voices = _piper_catalog()
        return {
            "voices": edge_voices + piper_voices,
            "edge_available": edge_ok,
            "forced_engine": ENGINE if ENGINE != "edge" else None,
        }


def find_voice(voice_id: str) -> dict[str, str] | None:
    for v in catalog()["voices"]:
        if v["id"] == voice_id:
            return v
    return None


# ---------------------------------------------------------------- synthesis engines

async def _edge_stream(text: str, voice_id: str, rate: int, pitch: int, out_path: Path) -> None:
    communicate = edge_tts.Communicate(
        text, voice_id, rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz",
    )
    written = 0
    with open(out_path, "wb") as fh:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
                written += len(chunk["data"])
    if written < 1024:
        raise RuntimeError("the neural voice service returned no audio")


def _piper_synth(text: str, out_mp3: Path, rate: int) -> str:
    """Render through the offline Piper engine, then transcode WAV → MP3."""
    installed = tts.list_voices()
    if not installed:
        raise RuntimeError("no offline voice is installed on this server")
    preferred = next((v["id"] for v in installed if v["id"].startswith("en_")), installed[0]["id"])
    wav_path = TEMP_DIR / f"{uuid.uuid4().hex}.wav"
    speed = max(0.5, min(2.0, 1.0 + rate / 100.0))
    try:
        tts.synthesize(text, preferred, wav_path, speed=speed)
        out_mp3.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [FFMPEG, "-hide_banner", "-nostdin", "-y", "-i", str(wav_path),
             "-threads", str(FFMPEG_THREADS), "-c:a", "libmp3lame", "-q:a", "4", str(out_mp3)],
            capture_output=True, text=True, timeout=EDGE_TIMEOUT_SECONDS,
        )
        if proc.returncode != 0 or not out_mp3.exists() or out_mp3.stat().st_size < 1024:
            raise RuntimeError("offline audio encoding failed")
    finally:
        wav_path.unlink(missing_ok=True)
    return preferred


def synth_block(text: str, voice: dict[str, str], rate: int, pitch: int,
                out_path: Path) -> str:
    """Synthesize one block. Returns the engine actually used ('edge' | 'piper')."""
    if voice["engine"] == "piper" or ENGINE == "piper":
        _piper_synth(text, out_mp3=out_path, rate=rate)
        return "piper"
    try:
        asyncio.run(asyncio.wait_for(
            _edge_stream(text, voice["id"], rate, pitch, out_path),
            timeout=EDGE_TIMEOUT_SECONDS,
        ))
        return "edge"
    except Exception as exc:  # network block, throttle, timeout — never strand the user
        if tts.tts_available():
            _piper_synth(text, out_mp3=out_path, rate=rate)
            return "piper-fallback"
        raise RuntimeError(
            "The free neural voice service could not be reached and no offline voice is "
            f"installed. Details for the server log: {exc}"
        )


# ---------------------------------------------------------------- history

def _load_history() -> list[dict[str, Any]]:
    try:
        data = json.loads(HISTORY_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_history(records: list[dict[str, Any]]) -> None:
    tmp = HISTORY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, indent=1))
    tmp.replace(HISTORY_FILE)


def _add_history(record: dict[str, Any]) -> None:
    with _history_lock:
        records = _load_history()
        records.insert(0, record)
        _save_history(records[:200])  # keep the library bounded on the small host


def _safe_name(text: str, fallback: str) -> str:
    name = (fallback or "").strip() or " ".join(text.split())[:48] or "Voice recording"
    return "".join(c for c in name if c.isalnum() or c in " .,_-()'’&").strip()[:80] or fallback


# ---------------------------------------------------------------- job machinery

def _set(job_id: str, **fields: Any) -> None:
    with _jobs_lock:
        _jobs.setdefault(job_id, {}).update(fields)


def _start_job(kind: str, worker: Any) -> str:
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {"id": job_id, "kind": kind, "status": "queued",
                         "progress": 0.0, "message": "Waiting in queue", "record": None,
                         "created_at": time.time()}

    def runner() -> None:
        with _work_lock:
            try:
                worker(job_id)
            except Exception as exc:  # plain language only; raw detail stays in the log
                _set(job_id, status="failed", message=str(exc)[:300])

    threading.Thread(target=runner, daemon=True).start()
    return job_id


def _finish(job_id: str, record: dict[str, Any]) -> None:
    _add_history(record)
    _set(job_id, status="done", progress=1.0, message="Finished", record=record)


# ---------------------------------------------------------------- request models

class SpeakBody(BaseModel):
    text: str
    voice: str
    rate: int = Field(default=0, ge=-50, le=100)
    pitch: int = Field(default=0, ge=-50, le=50)
    title: str = ""


class StudioBlock(BaseModel):
    text: str
    voice: str
    rate: int = Field(default=0, ge=-50, le=100)
    pitch: int = Field(default=0, ge=-50, le=50)


class StudioBody(BaseModel):
    title: str = ""
    blocks: list[StudioBlock]


# ---------------------------------------------------------------- endpoints

@router.get("/health")
def health() -> dict[str, Any]:
    cat = catalog()
    return {
        "status": "ok",
        "neural_voices": sum(1 for v in cat["voices"] if v["engine"] == "edge"),
        "offline_voices": sum(1 for v in cat["voices"] if v["engine"] == "piper"),
        "neural_service_reachable": cat["edge_available"],
        "forced_engine": cat["forced_engine"],
    }


@router.get("/voices")
def voices() -> dict[str, Any]:
    return catalog()


@router.post("/speak")
def speak(body: SpeakBody) -> dict[str, str]:
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "Enter some text first.")
    if len(body.text) > MAX_SPEAK_CHARS:
        raise HTTPException(400, f"That text is too long. The limit is {MAX_SPEAK_CHARS:,} characters.")
    voice = find_voice(body.voice)
    if not voice:
        raise HTTPException(400, "That voice isn't available. Pick one from the voice list.")

    def worker(job_id: str) -> None:
        _set(job_id, status="running", message=f"Speaking with {voice['label']}")
        rid = uuid.uuid4().hex
        out = AUDIO_DIR / f"{rid}.mp3"
        engine = synth_block(text, voice, body.rate, body.pitch, out)
        record = {
            "id": rid,
            "kind": "speak",
            "title": _safe_name(text, body.title),
            "voice": voice["label"],
            "voice_id": voice["id"],
            "engine": engine,
            "engine_label": "Offline fallback voice · free" if "fallback" in engine else voice["engine_label"],
            "characters": len(text),
            "duration": round(media_duration(out), 2),
            "size": out.stat().st_size,
            "file": str(out),
            "created_at": time.time(),
        }
        _finish(job_id, record)

    return {"job_id": _start_job("speak", worker)}


@router.post("/studio")
def studio(body: StudioBody) -> dict[str, str]:
    blocks = [b for b in body.blocks if (b.text or "").strip()]
    if not blocks:
        raise HTTPException(400, "Add at least one spoken line first.")
    if len(blocks) > MAX_STUDIO_BLOCKS:
        raise HTTPException(400, f"The studio allows at most {MAX_STUDIO_BLOCKS} parts in one project.")
    resolved: list[tuple[StudioBlock, dict[str, str]]] = []
    for block in blocks:
        block.text = block.text.strip()
        if len(block.text) > MAX_BLOCK_CHARS:
            raise HTTPException(400, f"One part is too long. The per-part limit is {MAX_BLOCK_CHARS:,} characters.")
        voice = find_voice(block.voice)
        if not voice:
            raise HTTPException(400, "One part uses a voice that isn't available. Pick voices from the voice list.")
        resolved.append((block, voice))

    def worker(job_id: str) -> None:
        job_temp = TEMP_DIR / job_id
        job_temp.mkdir(parents=True, exist_ok=True)
        part_files: list[Path] = []
        engines: set[str] = set()
        total = len(resolved)
        try:
            for idx, (block, voice) in enumerate(resolved, start=1):
                _set(job_id, status="running", progress=(idx - 1) / (total + 1),
                     message=f"Recording part {idx} of {total} — {voice['label']}")
                part = job_temp / f"part_{idx:02d}.mp3"
                engines.add(synth_block(block.text, voice, block.rate, block.pitch, part))
                part_files.append(part)

            _set(job_id, progress=total / (total + 1), message="Joining parts into one MP3")
            list_file = job_temp / "concat.txt"
            list_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in part_files))
            rid = uuid.uuid4().hex
            out = AUDIO_DIR / f"{rid}.mp3"
            proc = subprocess.run(
                [FFMPEG, "-hide_banner", "-nostdin", "-y", "-f", "concat", "-safe", "0",
                 "-i", str(list_file), "-threads", str(FFMPEG_THREADS),
                 "-c:a", "libmp3lame", "-q:a", "4", str(out)],
                capture_output=True, text=True, timeout=EDGE_TIMEOUT_SECONDS,
            )
            if proc.returncode != 0 or not out.exists() or out.stat().st_size < 1024:
                raise RuntimeError("joining the studio parts failed")
            engine = "edge" if engines == {"edge"} else (
                "piper" if engines <= {"piper"} else "edge+piper-fallback")
            record = {
                "id": rid,
                "kind": "studio",
                "title": _safe_name(resolved[0][0].text, body.title or "Studio project"),
                "voice": f"{total} parts · {len({v['id'] for _, v in resolved})} voices",
                "voice_id": "",
                "engine": engine,
                "engine_label": "Neural + offline voices · free" if "fallback" in engine or "+" in engine
                else ("Neural voices · free" if engine == "edge" else "Offline voices · free"),
                "characters": sum(len(b.text) for b, _ in resolved),
                "duration": round(media_duration(out), 2),
                "size": out.stat().st_size,
                "file": str(out),
                "created_at": time.time(),
            }
            _finish(job_id, record)
        finally:
            for leftover in job_temp.glob("*"):
                leftover.unlink(missing_ok=True)
            job_temp.rmdir() if job_temp.exists() else None

    return {"job_id": _start_job("studio", worker)}


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "That task isn't running anymore. Check History — finished audio is kept there.")
    return job


@router.get("/history")
def history() -> dict[str, list[dict[str, Any]]]:
    records = _load_history()
    # Honest file_exists flag: the free host's disk can be wiped by an update.
    for rec in records:
        rec["file_exists"] = Path(rec.get("file", "")).exists()
    return {"history": records}


@router.get("/audio/{record_id}")
def audio(record_id: str, download: int = 0) -> Any:
    if not record_id.replace("-", "").isalnum():
        raise HTTPException(400, "Bad audio id.")
    path = (AUDIO_DIR / f"{record_id}.mp3").resolve()
    if path.parent != AUDIO_DIR.resolve() or not path.exists():
        raise HTTPException(404, "That audio file isn't on this server anymore. Re-generate it or use a copy you downloaded.")
    record = next((r for r in _load_history() if r["id"] == record_id), None)
    filename = f"{(record or {}).get('title', 'voiceforge')}.mp3".replace('"', "")
    from fastapi.responses import FileResponse

    return FileResponse(
        str(path), media_type="audio/mpeg",
        headers={"Content-Disposition": (
            f'attachment; filename="{filename}"' if download else f'inline; filename="{filename}"')},
    )


@router.delete("/history/{record_id}")
def delete_history(record_id: str) -> dict[str, str]:
    if not record_id.replace("-", "").isalnum():
        raise HTTPException(400, "Bad audio id.")
    with _history_lock:
        records = _load_history()
        match = next((r for r in records if r["id"] == record_id), None)
        if not match:
            raise HTTPException(404, "That recording isn't in the history.")
        Path(match.get("file", "")).unlink(missing_ok=True)
        _save_history([r for r in records if r["id"] != record_id])
    return {"status": "deleted"}
