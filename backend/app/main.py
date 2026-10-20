"""StoryForge AI - local FastAPI backend. All processing runs on this machine; no paid APIs."""
from __future__ import annotations

import ctypes
import gc
import io
import json
import re
import shutil
import threading
import time
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any


def _release_memory() -> None:
    """Return freed Python/glibc heap to the OS before a memory-heavy render (small containers)."""
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from . import ai_images, database, media, metadata_gen, providers, renderer, shorts, story_engine, tts, voice_studio
from .config import AI_IMAGES_ENABLED, DATA_DIR, JOB_STALE_SECONDS, OPENVERSE, PROJECTS_DIR

app = FastAPI(title="StoryForge AI", version="1.0.0")
app.include_router(voice_studio.router)
app.include_router(shorts.router)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
database.init_db()

_RENDER_LOCK = threading.Lock()  # one render at a time - small machines thank us
_CURRENT_LOCK = threading.Lock()
_CURRENT_RENDER_JOB: str | None = None


@app.on_event("startup")
def _startup_recovery() -> None:
    """Jobs left 'running' by a dead process (OOM kill, redeploy, crash) can never resume;
    mark them failed so the UI shows the truth instead of a frozen progress bar."""
    recovered = database.reset_stale_jobs()
    cutoff = time.time() - 3600
    if PROJECTS_DIR.exists():
        for temp in PROJECTS_DIR.glob("*/temp/*"):
            try:
                if temp.is_dir() and temp.stat().st_mtime < cutoff:
                    shutil.rmtree(temp, ignore_errors=True)
            except OSError:
                pass
    if recovered:
        print(f"[startup] marked {recovered} interrupted job(s) as failed")
    threading.Thread(target=_job_watchdog, daemon=True).start()

    def _warm_voice_cache() -> None:
        # Best-effort: pre-fetch the free neural voice catalog so /shorts/options and
        # VoiceForge never wait on a live network call. Failures use the offline fallback.
        try:
            import asyncio
            from . import voice_studio
            if not voice_studio._load_cached_edge():
                data = asyncio.run(voice_studio._fetch_edge_voices_async())
                voice_studio.EDGE_CACHE.write_text(json.dumps(data))
        except Exception as exc:  # pragma: no cover - network is optional
            print(f"[startup] voice cache warm skipped: {exc}")

    threading.Thread(target=_warm_voice_cache, daemon=True).start()


def _job_watchdog() -> None:
    """Last-resort net: any active job row that stops updating is declared failed so nobody
    waits forever. FFmpeg's own idle watchdog normally fires well before this."""
    while True:
        time.sleep(20)
        try:
            now = time.time()
            for job in database.list_jobs():
                if job["status"] in ("queued", "running", "finalizing") and \
                        now - float(job["updated_at"]) > JOB_STALE_SECONDS:
                    database.update_job(
                        job["id"], status="failed",
                        message="Render stalled (no progress for 10 minutes) and was stopped. "
                                "Try the fast 480p preview or fewer scenes, then render again.",
                    )
        except Exception as exc:  # pragma: no cover - the watchdog must never die
            print("[watchdog]", exc)


# ---------------------------------------------------------------- helpers

def blank_project(name: str, mode: str) -> dict[str, Any]:
    now = time.time()
    return {
        "id": str(uuid.uuid4()), "name": name, "mode": mode,
        "created_at": now, "updated_at": now,
        "settings": {"category": "fantasy", "audience": "General", "length": 3, "language": "English",
                     "tone": "epic", "pov": "third", "sceneCount": 5, "ending": "open"},
        "script": {"title": "", "logline": "", "originality": ""},
        "scenes": [], "characters": [], "style": {},
        "assets": [], "exports": [],
        "timeline": {"aspect": "16:9", "resolution": "720p", "transition": "fade",
                     "title_card": True, "outro": False, "burn_captions": True,
                     "music_asset_id": None, "watermark_asset_id": None,
                     "watermark_position": "bottom-right"},
        "clip": {"prompt": "", "negative_prompt": "", "duration": 5, "aspect": "16:9",
                 "resolution": "720p", "quality": "standard", "reference_asset_id": None,
                 "provider_id": None, "result_asset_id": None, "target_ram_gb": 32},
        "narration_voice": None, "dialogue_voice": None, "speech_speed": 1.0,
    }


def _safe_media_path(raw: str) -> Path:
    p = Path(raw).resolve()
    if not str(p).startswith(str(DATA_DIR.resolve())):
        raise HTTPException(403, "Path outside data directory")
    if not p.exists():
        raise HTTPException(404, "File not found")
    return p


def _register_asset(project: dict[str, Any], path: str, kind: str, name: str,
                    source: str, license_info: str = "") -> dict[str, Any]:
    asset = {
        "id": str(uuid.uuid4()), "kind": kind, "name": name, "path": path,
        "source": source, "license": license_info, "created_at": time.time(),
    }
    project.setdefault("assets", []).append(asset)
    return asset


# ---------------------------------------------------------------- system / projects

@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "version": app.version, "ffmpeg": Path(renderer.FFMPEG).exists(),
            "tts": tts.tts_available(), "data_dir": str(DATA_DIR)}


@app.get("/api/projects")
def get_projects() -> list[dict[str, Any]]:
    return database.list_projects()


@app.post("/api/projects")
def create_project(payload: dict[str, Any]) -> dict[str, Any]:
    p = blank_project(payload.get("name", "Untitled Project"), payload.get("mode", "story"))
    return database.save_project(p)


@app.get("/api/projects/{pid}")
def get_project(pid: str) -> dict[str, Any]:
    p = database.get_project(pid)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


@app.put("/api/projects/{pid}")
def update_project(pid: str, payload: dict[str, Any]) -> dict[str, Any]:
    existing = database.get_project(pid)
    if not existing:
        raise HTTPException(404, "Project not found")
    payload["id"] = pid
    payload.setdefault("created_at", existing.get("created_at"))
    return database.save_project(payload)


@app.delete("/api/projects/{pid}")
def remove_project(pid: str) -> dict[str, str]:
    database.delete_project(pid)
    folder = PROJECTS_DIR / pid
    if folder.exists():
        for f in sorted(folder.rglob("*"), reverse=True):
            if f.is_file():
                f.unlink()
        for d in sorted(folder.rglob("*"), reverse=True):
            if d.is_dir():
                d.rmdir()
        folder.rmdir()
    return {"status": "deleted"}


# ---------------------------------------------------------------- media files

@app.get("/api/media")
def serve_media(path: str) -> FileResponse:
    return FileResponse(str(_safe_media_path(path)))


@app.post("/api/projects/{pid}/assets")
async def upload_asset(pid: str, file: UploadFile = File(...), kind: str = Form("image"),
                       source: str = Form("User upload"),
                       license_info: str = Form("User-provided - you hold the rights")) -> dict[str, Any]:
    project = database.get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")
    ext = Path(file.filename or "asset").suffix.lower()[:10] or ".bin"
    dest_dir = PROJECTS_DIR / pid / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex}{ext}"
    with open(dest, "wb") as f:
        f.write(await file.read())
    asset = _register_asset(project, str(dest), kind, file.filename or dest.name, source, license_info)
    database.save_project(project)
    return asset


# ---------------------------------------------------------------- free-asset library (Openverse)

@app.get("/api/library/search")
def library_search(q: str, kind: str = "image", page_size: int = 12) -> dict[str, Any]:
    # Openverse: free, keyless search for CC-licensed media. Never scrapes platforms.
    endpoint = f"{OPENVERSE}/v1/{'images' if kind == 'image' else 'audio'}/"
    url = f"{endpoint}?{urllib.parse.urlencode({'q': q, 'page_size': page_size})}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "StoryForgeAI/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
    except Exception as exc:
        raise HTTPException(502, f"Free library unreachable right now: {exc}. You can still upload your own files.")
    results = []
    for item in data.get("results", []):
        results.append({
            "id": item.get("id"),
            "title": item.get("title", "Untitled"),
            "creator": item.get("creator", "Unknown"),
            "url": item.get("url"),
            "thumbnail": item.get("thumbnail"),
            "license": item.get("license", "").upper(),
            "license_url": item.get("license_url", ""),
            "source": item.get("source", "openverse"),
            "kind": kind,
            "attribution": item.get("attribution", ""),
        })
    return {"results": results, "notice": "Verify each item's license and attribution before publishing."}


class ImportBody(BaseModel):
    url: str
    name: str
    kind: str = "image"
    license: str = ""
    license_url: str = ""
    source: str = "Openverse"
    creator: str = ""
    attribution: str = ""


@app.post("/api/projects/{pid}/library/import")
def library_import(pid: str, body: ImportBody) -> dict[str, Any]:
    project = database.get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")
    ext = ".jpg" if body.kind == "image" else ".mp3"
    dest_dir = PROJECTS_DIR / pid / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex}{ext}"
    try:
        req = urllib.request.Request(body.url, headers={"User-Agent": "StoryForgeAI/1.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            dest.write_bytes(r.read())
    except Exception as exc:
        raise HTTPException(502, f"Download failed: {exc}")
    license_info = f"{body.license} | {body.license_url} | by {body.creator} | via {body.source}"
    asset = _register_asset(project, str(dest), body.kind, body.name, body.source, license_info)
    database.save_project(project)
    return asset


# ---------------------------------------------------------------- story studio

class ScriptRequest(BaseModel):
    settings: dict[str, Any]
    seed: int | None = None


@app.post("/api/studio/generate-script")
def generate_script(req: ScriptRequest) -> dict[str, Any]:
    return story_engine.generate_story(req.settings, req.seed)


class SplitRequest(BaseModel):
    raw: str


@app.post("/api/studio/split-script")
def split_script(req: SplitRequest) -> dict[str, Any]:
    scenes = story_engine.split_script(req.raw)
    if not scenes:
        raise HTTPException(400, "No scenes could be parsed. Separate scenes with blank lines or 'Scene' headings.")
    return {"scenes": scenes}


@app.post("/api/projects/{pid}/placeholders/{scene_id}")
def make_placeholder_asset(pid: str, scene_id: str) -> dict[str, Any]:
    project = database.get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")
    scene = next((s for s in project.get("scenes", []) if s["id"] == scene_id), None)
    if not scene:
        raise HTTPException(404, "Scene not found")
    path = media.create_placeholder(pid, scene_id, scene.get("visual_prompt", scene.get("heading", "")),
                                    project.get("style", {}),
                                    project["timeline"].get("aspect", "16:9"),
                                    project["timeline"].get("resolution", "720p"),
                                    label=scene.get("heading"))
    asset = _register_asset(project, path, "image", f"Placeholder - {scene.get('heading', scene_id)[:60]}",
                            "StoryForge auto placeholder",
                            "Generated locally - labeled placeholder; replace before publishing")
    scene["image_asset_id"] = asset["id"]
    database.save_project(project)
    return asset


# ---------------------------------------------------------------- AI text-to-image (free, keyless)

class GenerateImageBody(BaseModel):
    scene_id: str | None = None
    prompt: str = ""
    seed: int | None = None
    aspect: str = "16:9"
    resolution: str = "720p"


@app.post("/api/projects/{pid}/generate-image")
def generate_one_ai_image(pid: str, body: GenerateImageBody) -> dict[str, Any]:
    if not AI_IMAGES_ENABLED:
        raise HTTPException(503, "AI image generation is disabled on this server (STORYFORGE_AI_IMAGES=0).")
    project = database.get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")
    scene = None
    if body.scene_id:
        scene = next((s for s in project.get("scenes", []) if s["id"] == body.scene_id), None)
        if not scene:
            raise HTTPException(404, "Scene not found")
    prompt = (body.prompt or "").strip() or (
        scene.get("visual_prompt") or scene.get("heading", "") if scene else ""
    )
    if not prompt:
        raise HTTPException(400, "Enter a prompt for the AI image.")
    out = PROJECTS_DIR / pid / "ai_images" / f"ai_{uuid.uuid4().hex[:10]}.jpg"
    try:
        info = ai_images.generate_ai_image(
            prompt, out, aspect=body.aspect, resolution=body.resolution,
            seed=body.seed, style=project.get("style", {}), deadline_seconds=200.0,
        )
    except RuntimeError as exc:
        raise HTTPException(
            503,
            "The free image service is busy right now (one image per ~45s). Wait a minute and "
            f"tap AI image again, or use a placeholder/upload. Detail: {exc}",
        )
    heading = (scene.get("heading", "") if scene else "") or prompt[:40]
    asset = _register_asset(project, info["path"], "image", f"AI image - {heading[:50]}",
                            ai_images.AI_IMAGE_SOURCE, ai_images.AI_IMAGE_LICENSE)
    if scene is not None:
        scene["image_asset_id"] = asset["id"]
    database.save_project(project)
    return asset


class BatchImageBody(BaseModel):
    only_missing: bool = True
    aspect: str | None = None
    resolution: str | None = None


@app.post("/api/projects/{pid}/generate-images")
def generate_all_ai_images(pid: str, body: BatchImageBody) -> dict[str, Any]:
    """Batch-generate one AI image per scene (small thread pool, progress tracked as a job)."""
    if not AI_IMAGES_ENABLED:
        raise HTTPException(503, "AI image generation is disabled on this server (STORYFORGE_AI_IMAGES=0).")
    project = database.get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")
    scenes = list(project.get("scenes", []))
    if body.only_missing:
        scenes = [s for s in scenes if not s.get("image_asset_id")]
    if not scenes:
        raise HTTPException(400, "No scenes need images (all already have one).")
    aspect = body.aspect or project["timeline"].get("aspect", "16:9")
    resolution = body.resolution or project["timeline"].get("resolution", "720p")
    job = database.create_job(pid, "generate-images")
    style = project.get("style", {})
    total = len(scenes)
    errors: list[str] = []

    def worker() -> None:
        # Sequential on purpose: the keyless free tier allows ~1 image per 45s per IP, so
        # parallel requests would all be rejected. Each scene's wait is shown in the job log.
        database.update_job(job["id"], status="running", progress=0.01,
                            message=f"Generating {total} AI images — free tier allows one every ~45s")
        for index, scene in enumerate(scenes, start=1):
            prompt = scene.get("visual_prompt") or scene.get("heading") or scene.get("narration", "")[:160]
            try:
                out = PROJECTS_DIR / pid / "ai_images" / f"ai_{uuid.uuid4().hex[:10]}.jpg"

                def progress_cb(msg: str, index=index) -> None:
                    database.update_job(job["id"], status="running",
                                        progress=round((index - 1) / total, 4), message=msg)

                info = ai_images.generate_ai_image(prompt, out, aspect=aspect, resolution=resolution,
                                                    style=style, progress_cb=progress_cb)
                asset = _register_asset(project, info["path"], "image",
                                        f"AI image - {scene.get('heading', 'scene')[:50]}",
                                        ai_images.AI_IMAGE_SOURCE, ai_images.AI_IMAGE_LICENSE)
                scene["image_asset_id"] = asset["id"]
                database.save_project(project)
                database.update_job(job["id"], status="running", progress=round(index / total, 4),
                                    message=f"Generated {index}/{total} scene images")
            except Exception as exc:  # keep going; report per-scene failures honestly
                errors.append(f"{scene.get('heading', 'scene')}: {exc}")
                database.update_job(job["id"], status="running", progress=round(index / total, 4),
                                    message=f"Scene {index} failed ({len(errors)}); continuing")
        if errors:
            database.update_job(
                job["id"], status="done", progress=1.0,
                message=f"{total - len(errors)}/{total} images generated; some failed",
                result=json.dumps({"errors": errors[:5]}),
            )
        else:
            database.update_job(job["id"], status="done", progress=1.0,
                                message=f"All {total} AI images generated",
                                result=json.dumps({"images": total}))

    threading.Thread(target=worker, daemon=True).start()
    return job


# ---------------------------------------------------------------- TTS

@app.get("/api/tts/voices")
def voices() -> dict[str, Any]:
    return {"voices": tts.list_voices(), "help": tts.voice_install_help()}


class TTSBody(BaseModel):
    scene_id: str
    text: str
    voice_id: str
    speed: float = 1.0
    kind: str = "narration"  # narration | dialogue


@app.post("/api/projects/{pid}/tts")
def synthesize_scene(pid: str, body: TTSBody) -> dict[str, Any]:
    project = database.get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")
    scene = next((s for s in project.get("scenes", []) if s["id"] == body.scene_id), None)
    if not scene:
        raise HTTPException(404, "Scene not found")
    out = PROJECTS_DIR / pid / "audio" / f"{body.scene_id}_{body.kind}_{uuid.uuid4().hex[:6]}.wav"
    try:
        info = tts.synthesize(body.text, body.voice_id, out, body.speed)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    asset = _register_asset(project, info["path"], "audio",
                            f"{body.kind.title()} - {scene.get('heading', body.scene_id)[:50]}",
                            "Piper local TTS", "Generated locally, no external service")
    if body.kind == "dialogue":
        scene["dialogue_audio_asset_id"] = asset["id"]
    else:
        scene["audio_asset_id"] = asset["id"]
        scene["duration"] = max(float(scene.get("duration") or 0), info["duration"] + 0.5)
    database.save_project(project)
    return {"asset": asset, "duration": info["duration"]}


# ---------------------------------------------------------------- metadata / thumbnail

@app.get("/api/projects/{pid}/metadata")
def project_metadata(pid: str) -> dict[str, Any]:
    project = database.get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")
    timings = None
    if project.get("exports"):
        timings = project["exports"][-1].get("scene_timings")
    return metadata_gen.generate_metadata(project, timings)


class ThumbBody(BaseModel):
    title: str
    background_asset_id: str | None = None
    placement: str = "bottom"
    aspect: str = "16:9"


@app.post("/api/projects/{pid}/thumbnail")
def make_thumbnail(pid: str, body: ThumbBody) -> dict[str, Any]:
    project = database.get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")
    background = None
    if body.background_asset_id:
        asset = next((a for a in project.get("assets", []) if a["id"] == body.background_asset_id), None)
        if asset:
            background = asset["path"]
    path = media.create_thumbnail(pid, body.title, background, body.placement, body.aspect)
    asset = _register_asset(project, path, "image", f"Thumbnail - {body.title[:40]}",
                            "StoryForge local thumbnail", "Original generated image")
    database.save_project(project)
    return asset


# ---------------------------------------------------------------- model providers (Mode A)

@app.get("/api/providers/status")
def provider_status() -> dict[str, Any]:
    return providers.provider_status()


class GenerateBody(BaseModel):
    provider_id: str
    prompt: str
    negative_prompt: str = ""
    duration: int = 5
    aspect: str = "16:9"
    resolution: str = "720p"
    reference_asset_id: str | None = None
    target_ram_gb: int | None = None  # planning selector (32-72 GB); checked against host hardware


# Local diffusion clips are short by nature; this also catches typos like 6000 seconds.
CLIP_MIN_SECONDS, CLIP_MAX_SECONDS = 2, 30


@app.post("/api/projects/{pid}/generate")
def provider_generate(pid: str, body: GenerateBody) -> dict[str, Any]:
    project = database.get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")
    if not body.prompt.strip():
        raise HTTPException(400, "Enter a scene prompt first.")
    body.duration = max(CLIP_MIN_SECONDS, min(CLIP_MAX_SECONDS, int(body.duration or 5)))
    status = providers.provider_status()
    provider = providers.get_provider(body.provider_id)
    if not provider:
        raise HTTPException(400, "Unknown provider")
    if not provider.configured():
        info = provider.status()
        raise HTTPException(
            503,
            {
                "error": "not_configured",
                "message": (
                    f"{info['name']} runs on your own computer with a suitable NVIDIA GPU "
                    f"(8-24 GB VRAM); it cannot run on this phone or the free server. "
                    f"For videos that work right now with no hardware, use Story Video mode: "
                    f"free AI scene images with Ken Burns motion, narration and captions, exported as MP4."
                ),
                "requires": info.get("requires", ""),
                "provider": info,
                "alternative": status["honest_alternative"],
            },
        )
    job = database.create_job(pid, f"generate-{provider.kind}")

    def worker() -> None:
        database.update_job(job["id"], status="running", progress=0.02, message="Starting local model")
        try:
            with _RENDER_LOCK:
                out_dir = PROJECTS_DIR / pid / "generated"
                out_dir.mkdir(parents=True, exist_ok=True)
                ext = ".png" if provider.kind == "image" else ".mp4"
                out = out_dir / f"{uuid.uuid4().hex}{ext}"
                ref = None
                if body.reference_asset_id:
                    ref = next((a["path"] for a in project.get("assets", [])
                                if a["id"] == body.reference_asset_id), None)
                provider.generate(body.prompt, str(out), negative_prompt=body.negative_prompt,
                                  reference_image=ref, duration=body.duration)
                asset = _register_asset(project, str(out), "video" if ext == ".mp4" else "image",
                                        f"Generated {provider.name[:40]}", provider.name,
                                        "Locally generated - verify model license")
                if ext == ".mp4":
                    project["clip"]["result_asset_id"] = asset["id"]
                if body.target_ram_gb:
                    project["clip"]["target_ram_gb"] = body.target_ram_gb
                database.save_project(project)
            ram_note = None
            if body.target_ram_gb:
                actual = status["hardware"]["ram_gb"]
                ram_note = (f"Target RAM {body.target_ram_gb} GB selected; this host has {actual} GB. "
                            + ("Hardware meets the selected plan."
                               if actual >= body.target_ram_gb
                               else "Run this adapter on a workstation meeting the selected RAM."))
            database.update_job(job["id"], status="done", progress=1.0, message="Complete",
                                result=json.dumps({"asset_id": asset["id"], "ram_note": ram_note}))
        except Exception as exc:  # surface real errors, never fake success
            database.update_job(job["id"], status="failed", progress=0, message=str(exc)[:1200])

    threading.Thread(target=worker, daemon=True).start()
    return job


# ---------------------------------------------------------------- render pipeline

class RenderBody(BaseModel):
    # Optional per-render override: "360p"/"480p" produce a fast draft preview without changing
    # the project's saved resolution; "720p"/"1080p" match the timeline setting.
    resolution: str | None = None


@app.post("/api/projects/{pid}/render")
def start_render(pid: str, body: RenderBody | None = None) -> dict[str, Any]:
    global _CURRENT_RENDER_JOB
    project = database.get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")
    if not project.get("scenes"):
        raise HTTPException(400, "Add at least one scene before rendering.")
    # Fail fast instead of queueing a zombie behind a stuck render (the old behavior left
    # users staring at a 0% job that could never start).
    if not _RENDER_LOCK.acquire(blocking=False):
        raise HTTPException(
            409,
            "Another video is already rendering on this free server. Wait for it to finish "
            "or press Cancel render, then start again.",
        )
    override = (body.resolution if body and body.resolution in ("360p", "480p", "720p", "1080p") else None)
    kind = "render-preview" if override in media.PREVIEW_RESOLUTIONS else "render"
    job = database.create_job(pid, kind)
    with _CURRENT_LOCK:
        _CURRENT_RENDER_JOB = job["id"]

    def worker() -> None:
        try:
            fresh = database.get_project(pid)

            def cb(pct: float, msg: str) -> None:
                database.update_job(job["id"], progress=round(pct, 4), message=msg,
                                    status="running" if pct < 1 else "finalizing")

            database.update_job(job["id"], status="running", progress=0.01,
                                message="Preparing fast preview" if override == "480p" else "Preparing render")
            _release_memory()
            result = renderer.render_project(fresh, cb, resolution_override=override)
            fresh.setdefault("exports", []).append({
                "job_id": job["id"], "created_at": time.time(), **result,
            })
            database.save_project(fresh)
            database.update_job(job["id"], status="done", progress=1.0,
                                message=f"MP4 ready - {result['duration']}s",
                                result=json.dumps(result))
        except renderer.RenderCancelled:
            database.update_job(job["id"], status="failed", progress=0,
                                message="Render cancelled.")
        except Exception as exc:
            database.update_job(job["id"], status="failed", progress=0,
                                message=str(exc)[:1500])
        finally:
            with _CURRENT_LOCK:
                _CURRENT_RENDER_JOB = None
            try:
                _RENDER_LOCK.release()
            except RuntimeError:
                pass

    threading.Thread(target=worker, daemon=True).start()
    return job


@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: str) -> dict[str, str]:
    job = database.get_job(jid)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] not in ("queued", "running", "finalizing"):
        raise HTTPException(400, "This job is not running.")
    with _CURRENT_LOCK:
        current = _CURRENT_RENDER_JOB
    if current == jid:
        # Kills the active FFmpeg process group; the worker thread marks the job failed.
        renderer.request_cancel()
        return {"status": "cancelling"}
    # No live worker owns this row (rare restart race): settle it directly.
    database.update_job(jid, status="failed", message="Render cancelled.")
    return {"status": "cancelled"}


def _enrich_job(job: dict[str, Any]) -> dict[str, Any]:
    """Tell the UI whether a finished render's MP4 still exists on disk. The free host's
    disk is cleared on every redeploy/restart, so a done job can outlive its file."""
    result = job.get("result")
    if isinstance(result, dict) and result.get("file"):
        try:
            job["file_exists"] = Path(result["file"]).exists()
        except OSError:
            job["file_exists"] = False
    return job


@app.get("/api/jobs")
def all_jobs(project_id: str | None = None) -> list[dict[str, Any]]:
    return [_enrich_job(j) for j in database.list_jobs(project_id)]


@app.get("/api/jobs/{jid}")
def job_status(jid: str) -> dict[str, Any]:
    job = database.get_job(jid)
    if not job:
        raise HTTPException(404, "Job not found")
    return _enrich_job(job)


@app.get("/api/jobs/{jid}/download")
def job_download(jid: str) -> FileResponse:
    job = database.get_job(jid)
    if not job or job["status"] != "done" or not job.get("result"):
        raise HTTPException(404, "No completed output for this job")
    path = _safe_media_path(job["result"]["file"])
    return FileResponse(str(path), filename=path.name, media_type="video/mp4")


@app.get("/api/projects/{pid}/export-download")
def export_download(pid: str, path: str) -> FileResponse:
    """Download one rendered MP4 with attachment headers (works for saved exports and for
    restored projects whose original job rows no longer exist)."""
    if not database.get_project(pid):
        raise HTTPException(404, "Project not found")
    target = _safe_media_path(path)
    exports_root = (PROJECTS_DIR / pid / "exports").resolve()
    if exports_root not in target.parents:
        raise HTTPException(403, "That file is not one of this project's exported videos.")
    return FileResponse(str(target), filename=target.name,
                        media_type="video/mp4",
                        headers={"Content-Disposition": f'attachment; filename="{target.name}"'})


# ---------------------------------------------------------------- project backup / restore

@app.get("/api/projects/{pid}/backup")
def project_backup(pid: str) -> StreamingResponse:
    """Download the whole project as one zip: story JSON plus every image, audio and exported
    video on disk. This is the zero-budget way to keep work permanently, because the free
    host clears its disk on every redeploy or restart."""
    project = database.get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")
    root = (PROJECTS_DIR / pid).resolve()

    def iter_zip() -> Any:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("project.json", json.dumps(project, indent=2))
            if root.exists():
                for f in sorted(root.rglob("*")):
                    if f.is_file() and "temp" not in f.relative_to(root).parts:
                        zf.write(f, str(Path("files") / f.relative_to(root)))
        buf.seek(0)
        yield from buf
        buf.close()

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project["name"])[:40] or "project"
    return StreamingResponse(
        iter_zip(), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="storyforge-{safe_name}-backup.zip"'},
    )


@app.post("/api/projects/restore")
async def restore_project(file: UploadFile = File(...)) -> dict[str, Any]:
    """Recreate a project from a backup zip: files land in a fresh project folder and every
    stored path is remapped to it."""
    raw = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise HTTPException(400, "That file is not a StoryForge backup zip.")
    if "project.json" not in zf.namelist():
        raise HTTPException(400, "Backup is missing project.json.")
    old = json.loads(zf.read("project.json"))
    old_pid = old.get("id") or "unknown"
    # The uploaded document IS the project; give it a fresh id on this server.
    project = old
    project["id"] = str(uuid.uuid4())
    now = time.time()
    project["created_at"], project["updated_at"] = now, now
    new_root = PROJECTS_DIR / project["id"]
    new_root.mkdir(parents=True, exist_ok=True)
    old_prefix = f"{PROJECTS_DIR}/{old_pid}"
    new_prefix = str(new_root)
    # Backups made on another machine (or another STORYFORGE_DATA root) store that
    # machine's absolute path, e.g. /tmp/sf-testdata/projects/<old-id>/assets/x.jpg.
    # Re-anchor any string containing the old project's projects/<id> segment to this
    # machine's project folder regardless of the original root (POSIX or Windows).
    old_project_segment = re.compile(
        r"^.*?[\\/]projects[\\/]" + re.escape(old_pid) + r"(?=[\\/]|$)"
    )
    for member in zf.namelist():
        # Zip-slip guard: only files under files/ with simple relative paths are extracted.
        if not member.startswith("files/") or member.endswith("/") or ".." in Path(member).parts:
            continue
        dest = new_root / Path(member[len("files/"):])
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out)

    def remap(value: Any) -> Any:
        if isinstance(value, str):
            remapped = value.replace(old_prefix, new_prefix)
            return old_project_segment.sub(new_prefix, remapped)
        if isinstance(value, list):
            return [remap(v) for v in value]
        if isinstance(value, dict):
            return {k: remap(v) for k, v in value.items()}
        return value

    project = remap(project)
    # Drop any export whose file did not survive in the backup.
    project["exports"] = [e for e in project.get("exports", [])
                          if isinstance(e, dict) and Path(e.get("file", "")).exists()]
    database.save_project(project)
    return project


# ---------------------------------------------------------------- optional built frontend

# In production-style use the backend can also serve the compiled React app, so a local user
# only runs one process. In development use Vite (port 5173) which proxies /api here.
_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _DIST.exists():
    from fastapi.staticfiles import StaticFiles

    # VoiceForge voice studio ships as its own small bundle under dist/voice.
    # Mounted before the SPA catch-all so /voice/* resolves to the voice app.
    _VOICE_DIST = _DIST / "voice"
    if _VOICE_DIST.exists():
        app.mount("/voice", StaticFiles(directory=str(_VOICE_DIST), html=True), name="voice-ui")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        # Never shadow API routes; serve real static files, otherwise the SPA shell.
        if full_path.startswith("api/"):
            raise HTTPException(404)
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        # The app shell must always revalidate so newly deployed bundles are never hidden
        # behind a phone's cached old index.html (hashed /assets stay cacheable).
        return FileResponse(
            str(_DIST / "index.html"),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")
