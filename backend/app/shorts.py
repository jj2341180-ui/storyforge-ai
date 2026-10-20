"""YouTube Shorts orchestrator — one idea becomes a finished vertical MP4.

Pipeline (every stage reports progress into the existing job table):
  idea -> compact hook-first story -> visual prompts -> images (free keyless model,
  honest placeholder fallback) -> per-scene clips -> neural narration (edge-tts with
  Piper offline fallback) -> synthesized SFX + royalty-free music bed with automatic
  ducking -> burned captions / SRT export -> one downloadable MP4.

Real AI video models (SVD / LTX-Video / Wan / AnimateDiff) are free open weights but need
an NVIDIA GPU; when a local ComfyUI/CLI provider IS configured, scenes are rendered by that
real text/image-to-video model instead of the image-motion fallback. Every export records
per-scene which engine actually made it, so the UI never mislabels a moving still as a
diffusion video.
"""
from __future__ import annotations

import json
import os
import random
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import ai_images, audio_fx, database, media, providers, renderer, voice_studio
from .config import FFMPEG, FFMPEG_THREADS, PROJECTS_DIR, X264_INTERIM_PRESET, X264_PRESET

router = APIRouter(prefix="/api/shorts", tags=["shorts"])

# ---------------------------------------------------------------- constants

# Target length -> (number of scenes, seconds per scene). Totals are exact 15/30/45/60.
DURATION_PLANS: dict[int, tuple[int, float]] = {
    15: (3, 5.0),
    30: (5, 6.0),
    45: (6, 7.5),
    60: (8, 7.5),
}
VALID_ASPECTS = {"9:16", "16:9", "1:1"}
VALID_RESOLUTIONS = {"360p", "480p", "720p"}

# Six narrator personas requested for the studio, mapped onto verified free neural voices.
VOICE_PRESETS: dict[str, dict[str, str]] = {
    "male_narrator": {"voice": "en-US-GuyNeural", "label": "Male narrator"},
    "female_narrator": {"voice": "en-US-AriaNeural", "label": "Female narrator"},
    "deep_cinematic": {"voice": "en-US-ChristopherNeural", "label": "Deep cinematic voice"},
    "friendly_story": {"voice": "en-US-JennyNeural", "label": "Friendly storytelling voice"},
    "energetic_shorts": {"voice": "en-US-MichelleNeural", "label": "Exciting, energetic Shorts voice"},
    "calm_mysterious": {"voice": "en-GB-SoniaNeural", "label": "Calm, mysterious voice"},
}

MOTIONS = ("zoom_in", "pan_right", "zoom_out", "pan_left")
_CANCELLED: set[str] = set()
_CANCEL_LOCK = threading.Lock()

# --------------------------------------------------------------- compact story writer

_HAIR = ("dark braided hair", "curly chestnut hair", "short black hair", "long auburn hair", "silver-streaked hair")
_OUTFIT = ("a teal travelling cloak", "a worn leather jacket", "a simple white tunic and boots",
           "a hooded indigo coat", "a practical green ranger outfit")
_FACE = ("expressive amber eyes", "kind brown eyes", "bright green eyes", "steady gray eyes")

# Narration lines stay <=10 words so even a 5-second scene (11-word cap) never clips a
# sentence mid-phrase. {name} is the protagonist's generated name; visuals carry the idea.
_BEATS: list[tuple[str, str, str]] = [
    # (beat label, narration template, visual action template)
    ("hook", "Nobody believed {name}'s story, until it came true.",
     "wide establishing shot, {prot_desc} in {place}, cinematic lighting"),
    ("discovery", "Then {name} discovered what everyone had missed.",
     "{prot_desc} discovering {idea_core}, close-up reaction, wonder in their eyes"),
    ("rise-1", "Every step pulled {name} deeper into the unknown.",
     "{prot_desc} walking forward, natural arm and leg movement, environment passing by"),
    ("rise-2", "Strange signs proved this was only the beginning.",
     "tracking shot following {prot_desc}, glowing details, moving background elements"),
    ("challenge", "When danger came, {name} chose to stand and fight.",
     "{prot_desc} running with determination, dynamic motion, hair and clothes moving"),
    ("climax", "Everything came down to one breathless choice.",
     "dramatic low angle, {prot_desc} standing firm, wind, smoke and light effects"),
    ("resolve-1", "That single choice changed {name} forever.",
     "soft sunrise lighting, {prot_desc} looking into the distance, gentle camera push"),
    ("resolve-2", "And the next chapter was already beginning.",
     "silhouette of {prot_desc} against a vast sky, slow zoom out"),
]

_NAMES = {
    "she": ("Aria", "Zara", "Maya", "Lena", "Nia"),
    "he": ("Kael", "Jude", "Omar", "Elias", "Theo"),
    "it": ("Pip", "Ember", "Pico", "Boba", "Momo"),
    "they": ("Wren", "Sage", "Ash", "Rio", "Nova"),
}

_PLACES = ("an ancient forest", "a rain-slicked city street", "a forgotten temple",
           "a windswept cliff above the sea", "a quiet village at dawn", "a glowing cavern")


def _words_cap(seconds: float) -> int:
    # ~2.4 spoken words per second leaves breathing room inside each scene.
    return max(8, int(seconds * 2.3))


def _clip_words(text: str, cap: int) -> str:
    words = text.split()
    if len(words) <= cap:
        return text
    clipped = " ".join(words[:cap]).rstrip(",;:")
    return clipped + "."


def _detect_prot(idea: str) -> tuple[str, str]:
    low = idea.lower()
    def has(*words: str) -> bool:
        return any(re.search(rf"\b{re.escape(w)}\b", low) for w in words)
    if has("girl", "woman", "lady", "she", "daughter", "princess", "mother", "witch"):
        return "she", "a young woman"
    if has("boy", "man", "guy", "he", "son", "prince", "father", "wizard", "king"):
        return "he", "a young man"
    if has("dragon", "creature", "animal", "fox", "cat", "bird", "dog", "wolf", "monster"):
        return "it", "a small creature"
    return "they", "a brave traveler"


def write_short(idea: str, scene_count: int, scene_dur: float, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    idea_clean = " ".join(idea.strip().split())
    idea_core = idea_clean.rstrip(".!")[:120] or "an impossible discovery"
    title = " ".join(idea_clean.split()[:8]).title()[:70] or "Untitled Short"
    pronoun, prot_noun = _detect_prot(idea)
    name = rng.choice(_NAMES[pronoun])
    prot_desc = (f"{prot_noun} named {name} with {rng.choice(_HAIR)}, {rng.choice(_FACE)}, "
                 f"wearing {rng.choice(_OUTFIT)}")
    place = rng.choice(_PLACES)
    style = {
        "location": place,
        "lighting": rng.choice(("golden hour light", "moonlit blue lighting", "soft overcast light", "warm sunset glow")),
        "palette": rng.choice(("teal and amber", "deep indigo and gold", "emerald and bronze", "muted earth tones")),
        "camera": "shallow depth of field, cinematic 35mm look",
        "effects": "subtle film grain, consistent character and wardrobe across every shot",
    }
    # A short idea can be spoken directly in the discovery beat; long ideas stay visual-only.
    idea_spoken = idea_core if len(idea_core.split()) <= 7 else None
    scenes: list[dict[str, Any]] = []
    for i in range(scene_count):
        label, narr_t, vis_t = _BEATS[min(i, len(_BEATS) - 1)]
        narration = narr_t.format(name=name)
        if label == "discovery" and idea_spoken:
            candidate = f"Then {name} discovered {idea_spoken.lower()}."
            if len(candidate.split()) <= _words_cap(scene_dur):
                narration = candidate
        visual = (f"{vis_t.format(prot_desc=prot_desc, idea_core=idea_core, place=place)}. "
                  f"Same character every scene: {prot_desc}. Setting: {place}. "
                  f"Style: {style['lighting']}, {style['palette']}, {style['camera']}.")
        scenes.append({
            "id": uuid.uuid4().hex,
            "beat": label,
            "heading": f"Scene {i+1}",
            "narration": narration,
            "visual_prompt": visual,
            "motion": MOTIONS[i % len(MOTIONS)],
        })
    return {
        "title": title,
        "idea": idea_clean,
        "prot_desc": prot_desc,
        "place": place,
        "style": style,
        "scenes": scenes,
        "scene_dur": scene_dur,
    }


# ---------------------------------------------------------------- request models

class NarrationCfg(BaseModel):
    enabled: bool = True
    voice_preset: str = "female_narrator"
    custom_voice: str = ""          # explicit edge/piper voice id overrides the preset
    rate: int = Field(default=0, ge=-50, le=100)


class AudioCfg(BaseModel):
    music_enabled: bool = True
    sfx_enabled: bool = True
    narration_volume: float = Field(default=1.0, ge=0, le=2)
    music_volume: float = Field(default=0.5, ge=0, le=2)
    sfx_volume: float = Field(default=0.7, ge=0, le=2)


class CaptionCfg(BaseModel):
    enabled: bool = True
    font_size: int = Field(default=18, ge=10, le=36)
    position: str = "bottom"       # bottom | top | middle


class ShortBody(BaseModel):
    idea: str
    seconds: int = 30
    aspect: str = "9:16"
    resolution: str = "480p"
    narration: NarrationCfg = NarrationCfg()
    audio: AudioCfg = AudioCfg()
    captions: CaptionCfg = CaptionCfg()
    reference_asset_id: str | None = None
    engine: str = "auto"           # auto | local (force real provider when configured)


# ---------------------------------------------------------------- helpers

def _job_update(jid: str, pct: float, msg: str) -> None:
    database.update_job(jid, progress=round(pct, 4), message=msg,
                        status="finalizing" if pct >= 1 else "running")


def _is_cancelled(jid: str) -> bool:
    with _CANCEL_LOCK:
        return jid in _CANCELLED


def _run_video(cmd: list[str], timeout: int = 600) -> None:
    proc = __import__("subprocess").run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"video encoding failed: {proc.stderr[-400:]}")


def _ken_burns_clip(image: Path, out: Path, width: int, height: int, dur: float,
                    motion: str, fps: int) -> None:
    frames = max(1, int(dur * fps))
    z, x, y = renderer._zoom_expr(motion, frames)
    vf = (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
          f"crop={width}:{height},setsar=1,"
          f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={width}x{height}:fps={fps},"
          f"fps={fps},format=yuv420p")
    _run_video([FFMPEG, "-hide_banner", "-nostdin", "-y", "-loop", "1", "-i", str(image),
                "-t", f"{dur:.3f}", "-vf", vf, "-r", str(fps),
                "-threads", str(FFMPEG_THREADS), "-preset", X264_INTERIM_PRESET,
                "-crf", "26", "-an", "-pix_fmt", "yuv420p", str(out)])


def _resolve_voice(cfg: NarrationCfg) -> tuple[dict[str, str], str]:
    voice_id = cfg.custom_voice or VOICE_PRESETS.get(cfg.voice_preset, VOICE_PRESETS["female_narrator"])["voice"]
    voice = voice_studio.find_voice(voice_id)
    if not voice:  # preset id missing from this catalog: fall back to Aria, then anything
        voice = voice_studio.find_voice("en-US-AriaNeural") or voice_studio.catalog()["voices"][0]
    return voice, voice["id"]


def _real_provider_clip(prompt: str, out_mp4: Path, dur: float, seed: int,
                        reference_image: str | None) -> str | None:
    """Render via a configured free local model. Returns engine label, or None if no
    provider is configured (caller then uses the honest image-motion fallback)."""
    status = providers.provider_status()
    if not status["any_configured"]:
        return None
    cli = providers.get_provider("cli")
    if cli and cli.configured():
        cli.generate(prompt, str(out_mp4), reference_image=reference_image or "")
        return "local-video-model (CLI)"
    comfy = providers.get_provider("comfyui")
    if comfy and comfy.configured():
        workflow_file = os.environ.get("STORYFORGE_COMFY_WORKFLOW", "").strip()
        if not workflow_file or not Path(workflow_file).exists():
            return None
        template = json.loads(Path(workflow_file).read_text())
        substitutions = {
            "{prompt}": prompt.replace('"', "'"),
            "{seed}": str(seed),
            "{duration}": f"{dur:.1f}",
            "{frames}": str(int(dur * 24)),
            "{fps}": "24",
            "{image}": reference_image or "",
        }
        def substitute(node: Any) -> Any:
            if isinstance(node, str):
                for k, v in substitutions.items():
                    node = node.replace(k, v)
                return node
            if isinstance(node, list):
                return [substitute(x) for x in node]
            if isinstance(node, dict):
                return {k: substitute(v) for k, v in node.items()}
            return node
        comfy.generate(prompt, str(out_mp4), workflow_json=substitute(template),
                       reference_image=reference_image, seed=seed, duration=dur)
        return "local-video-model (ComfyUI)"
    return None


# ---------------------------------------------------------------- main pipeline

def create_short(body: ShortBody) -> dict[str, str]:
    idea = (body.idea or "").strip()
    if not idea:
        raise HTTPException(400, "Enter an idea first — for example: a girl discovers a baby dragon.")
    if len(idea) > 500:
        raise HTTPException(400, "Keep the idea under 500 characters.")
    if body.seconds not in DURATION_PLANS:
        raise HTTPException(400, "Pick a duration of 15, 30, 45 or 60 seconds.")
    if body.aspect not in VALID_ASPECTS:
        raise HTTPException(400, "Aspect must be 9:16, 16:9 or 1:1.")
    if body.resolution not in VALID_RESOLUTIONS:
        raise HTTPException(400, "Resolution must be 360p, 480p or 720p.")
    if body.captions.position not in ("bottom", "top", "middle"):
        raise HTTPException(400, "Caption position must be bottom, top or middle.")
    if not (10 <= body.captions.font_size <= 36):
        raise HTTPException(400, "Caption font size must be between 10 and 36.")

    seed = int(time.time() * 1000) % 1_000_000
    project = {
        "id": uuid.uuid4().hex,
        "name": "",
        "mode": "shorts",
        "created_at": time.time(),
        "updated_at": time.time(),
        "settings": {"category": "fantasy", "language": "English"},
        "scenes": [],
        "assets": [],
        "exports": [],
        "shorts_config": body.model_dump(),
    }
    project["name"] = "Short: " + " ".join(idea.split()[:6])[:60]
    database.save_project(project)
    job = database.create_job(project["id"], "shorts")
    _run_pipeline(job["id"], project["id"], body, seed)
    return {"project_id": project["id"], "job_id": job["id"]}


def _run_pipeline(jid: str, pid: str, body: ShortBody, seed: int) -> None:
    threading.Thread(target=_pipeline_worker, args=(jid, pid, body, seed), daemon=True).start()


def _pipeline_worker(jid: str, pid: str, body: ShortBody, seed: int) -> None:
    root = PROJECTS_DIR / pid
    work = root / "shorts" / jid
    work.mkdir(parents=True, exist_ok=True)
    try:
        scene_count, scene_dur = DURATION_PLANS[body.seconds]
        total = scene_count * scene_dur
        width, height = media.dimensions(body.aspect, body.resolution)
        fps = renderer.FPS if body.resolution not in media.PREVIEW_RESOLUTIONS else media.PREVIEW_FPS

        # 1 — script -----------------------------------------------------------
        _job_update(jid, 0.02, "Writing the story and hook")
        script = write_short(body.idea, scene_count, scene_dur, seed)
        project = database.get_project(pid)
        project["script"] = {"title": script["title"], "logline": script["idea"]}
        project["scenes"] = [{
            "id": s["id"], "heading": s["heading"], "narration": s["narration"],
            "visual_prompt": s["visual_prompt"], "duration": scene_dur,
        } for s in script["scenes"]]
        database.save_project(project)
        if _is_cancelled(jid):
            raise renderer.RenderCancelled()

        # 2 — images -----------------------------------------------------------
        images: list[Path] = []
        reference_path = None
        if body.reference_asset_id:
            ref = next((a for a in project.get("assets", []) if a["id"] == body.reference_asset_id), None)
            if ref and Path(ref["path"]).exists():
                reference_path = ref["path"]
        for i, scene in enumerate(script["scenes"]):
            _job_update(jid, 0.06 + 0.30 * (i / scene_count),
                        f"Creating visual {i+1} of {scene_count}")
            img = work / f"img_{i:02d}.jpg"
            if i == 0 and reference_path:
                img.write_bytes(Path(reference_path).read_bytes())
            else:
                try:
                    ai_images.generate_ai_image(
                        scene["visual_prompt"], img, aspect=body.aspect,
                        resolution=body.resolution, seed=seed + i * 7,
                        style=script["style"], deadline_seconds=240)
                except Exception:
                    fallback = media.create_placeholder(
                        pid, scene["id"], scene["visual_prompt"], script["style"],
                        body.aspect, body.resolution)
                    img.write_bytes(Path(fallback).read_bytes())
            images.append(img)
            if _is_cancelled(jid):
                raise renderer.RenderCancelled()

        # 3 — per-scene clips --------------------------------------------------
        clips: list[Path] = []
        engines: list[str] = []
        for i, scene in enumerate(script["scenes"]):
            _job_update(jid, 0.38 + 0.20 * (i / scene_count),
                        f"Building scene {i+1} of {scene_count}")
            clip = work / f"clip_{i:02d}.mp4"
            ref = reference_path if i == 0 else None
            engine = None
            if body.engine in ("auto", "local"):
                try:
                    engine = _real_provider_clip(scene["visual_prompt"], clip, scene_dur,
                                                 seed + i * 13, ref)
                except Exception as exc:
                    database.update_job(jid, message=f"Local model unavailable ({str(exc)[:80]}); using free image-motion.")
                    engine = None
            if engine is None or not clip.exists():
                _ken_burns_clip(images[i], clip, width, height, scene_dur, scene["motion"], fps)
                engines.append("image-motion (free, no GPU)")
            else:
                engines.append(engine)
            clips.append(clip)
            if _is_cancelled(jid):
                raise renderer.RenderCancelled()

        # 4 — narration --------------------------------------------------------
        voice = None
        scene_narration: list[Path | None] = []
        narration_engines: set[str] = set()
        if body.narration.enabled:
            voice, vid = _resolve_voice(body.narration)
            for i, scene in enumerate(script["scenes"]):
                _job_update(jid, 0.60 + 0.12 * (i / scene_count),
                            f"Narrating scene {i+1} of {scene_count} — {voice['label']}")
                mp3 = work / f"voice_{i:02d}.mp3"
                used = voice_studio.synth_block(scene["narration"], voice,
                                                 body.narration.rate, 0, mp3)
                narration_engines.add(used)
                scene_narration.append(mp3)
                if _is_cancelled(jid):
                    raise renderer.RenderCancelled()
        else:
            scene_narration = [None] * scene_count

        # 5 — SFX + music ------------------------------------------------------
        _job_update(jid, 0.74, "Creating sound effects and music")
        stems: list[Path] = []
        sfx_used: list[str] = []
        for i, scene in enumerate(script["scenes"]):
            sfx_path = None
            if body.audio.sfx_enabled:
                sfx_path, preset = audio_fx.sfx_for_scene(
                    scene["visual_prompt"] + " " + scene["narration"], scene_dur, seed + i)
                sfx_used.append(preset)
            stem = work / f"stem_{i:02d}.mp3"
            audio_fx.mix_scene_stem(scene_narration[i], sfx_path, stem, scene_dur,
                                    body.audio.narration_volume, body.audio.sfx_volume)
            stems.append(stem)
        music_path = None
        mood = audio_fx.detect_mood(body.idea + " " + script["place"])
        if body.audio.music_enabled:
            music_path, mood = audio_fx.music_bed(mood, total, seed)
        if _is_cancelled(jid):
            raise renderer.RenderCancelled()

        # 6 — final audio mix --------------------------------------------------
        _job_update(jid, 0.84, "Mixing narration, music and sound effects")
        final_audio = work / "audio_final.mp3"
        audio_fx.build_final_audio(
            scene_stems=stems, scene_durations=[scene_dur] * scene_count,
            music=music_path, out_path=final_audio, total_duration=total,
            narration_volume=body.audio.narration_volume,
            music_volume=body.audio.music_volume, sfx_volume=body.audio.sfx_volume,
            has_narration=body.narration.enabled)

        # 7 — captions ---------------------------------------------------------
        srt_path = root / "exports" / f"{pid[:8]}_short_{jid[:8]}.srt"
        srt_path.parent.mkdir(parents=True, exist_ok=True)
        if body.narration.enabled and body.captions.enabled:
            entries = []
            cursor = 0.0
            for i, narr in enumerate(scene_narration):
                if narr is None:
                    cursor += scene_dur
                    continue
                ndur = renderer.media_duration(narr)
                entries.append({
                    "start": cursor + 0.15,
                    "end": min(cursor + scene_dur - 0.1, cursor + 0.15 + max(1.0, ndur)),
                    "caption": script["scenes"][i]["narration"],
                })
                cursor += scene_dur
            renderer._write_srt(entries, srt_path)
        else:
            srt_path.write_text("", encoding="utf-8")

        # 8 — concat video + final encode -------------------------------------
        _job_update(jid, 0.90, "Joining scenes and burning captions")
        list_file = work / "concat.txt"
        list_file.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips))
        silent = work / "silent.mp4"
        _run_video([FFMPEG, "-hide_banner", "-nostdin", "-y", "-f", "concat",
                    "-safe", "0", "-i", str(list_file), "-c", "copy", str(silent)])

        exports = root / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        out_mp4 = exports / f"{script['title'][:40].replace(' ', '_').replace('/', '_')}_{jid[:8]}.mp4"
        preset = X264_INTERIM_PRESET if body.resolution in media.PREVIEW_RESOLUTIONS else X264_PRESET
        crf = "26" if body.resolution in media.PREVIEW_RESOLUTIONS else "23"
        cmd = [FFMPEG, "-hide_banner", "-nostdin", "-y", "-i", str(silent), "-i", str(final_audio)]
        if body.narration.enabled and body.captions.enabled and srt_path.stat().st_size > 0:
            alignment = {"bottom": 2, "middle": 5, "top": 8}[body.captions.position]
            # Escape the path for the subtitles filter and force mobile-readable styling.
            srt_esc = str(srt_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
            style = (f"FontName=DejaVu Sans,FontSize={body.captions.font_size},"
                     f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,"
                     f"Outline=2,Shadow=0,Alignment={alignment},MarginV=40")
            cmd += ["-vf", f"subtitles='{srt_esc}':force_style='{style}'"]
        cmd += ["-map", "0:v:0", "-map", "1:a:0",
                "-threads", str(FFMPEG_THREADS), "-preset", preset, "-crf", crf,
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                "-t", f"{total:.3f}", "-movflags", "+faststart", str(out_mp4)]
        _run_video(cmd, timeout=900)

        # 9 — persist result ---------------------------------------------------
        result = {
            "job_id": jid, "created_at": time.time(),
            "file": str(out_mp4), "srt": str(srt_path),
            "title": script["title"], "duration": round(renderer.media_duration(out_mp4), 2),
            "width": width, "height": height,
            "aspect": body.aspect, "resolution": body.resolution,
            "scene_timings": [{"scene_id": s["id"], "heading": s["heading"],
                               "start": round(i * scene_dur, 2),
                               "end": round((i + 1) * scene_dur, 2)}
                              for i, s in enumerate(script["scenes"])],
            "video_engines": engines,
            "real_video_used": any("local-video-model" in e for e in engines),
            "narration_engines": sorted(narration_engines),
            "voice": voice["label"] if voice else "Narration off",
            "sfx_presets": sfx_used, "music_mood": mood if body.audio.music_enabled else None,
            "kind": "shorts",
        }
        fresh = database.get_project(pid)
        fresh.setdefault("exports", []).append(result)
        database.save_project(fresh)
        database.update_job(jid, status="done", progress=1.0,
                            message=f"Short ready - {result['duration']}s MP4",
                            result=json.dumps(result))
    except renderer.RenderCancelled:
        database.update_job(jid, status="failed", progress=0, message="Short cancelled.")
    except Exception as exc:
        database.update_job(jid, status="failed", progress=0,
                            message=f"Could not finish the short: {str(exc)[:400]}")


# ---------------------------------------------------------------- endpoints

@router.get("/options")
def options() -> dict[str, Any]:
    status = providers.provider_status()
    # Use the on-disk voice cache only: this screen needs language tags, not a live
    # network fetch of all 322 voices (the presets themselves are static).
    cached = voice_studio._load_cached_edge()
    languages = sorted({v["lang"] for v in cached})[:40] if cached else ["en"]
    return {
        "durations": sorted(DURATION_PLANS),
        "aspects": sorted(VALID_ASPECTS),
        "resolutions": sorted(VALID_RESOLUTIONS),
        "voice_presets": [{"id": k, **v} for k, v in VOICE_PRESETS.items()],
        "languages": languages,
        "local_video_configured": status["any_configured"],
        "hardware": status["hardware"],
        "providers": status["providers"],
        "honest_note": (
            "Real character-movement video models (SVD, LTX-Video, Wan, AnimateDiff) are free "
            "open weights but require an NVIDIA GPU (8-24 GB VRAM) via local ComfyUI/CLI. On this "
            "free server, Shorts use AI-generated images with cinematic motion; exports are labeled "
            "per scene so the two are never confused."
        ),
    }


@router.post("/create")
def create(body: ShortBody) -> dict[str, str]:
    return create_short(body)


@router.post("/jobs/{jid}/cancel")
def cancel(jid: str) -> dict[str, str]:
    job = database.get_job(jid)
    if not job:
        raise HTTPException(404, "Job not found")
    with _CANCEL_LOCK:
        _CANCELLED.add(jid)
    renderer.request_cancel()  # kills any active clip/encode process group
    return {"status": "cancelling"}


@router.get("/{pid}/srt")
def srt_download(pid: str, path: str) -> Any:
    from fastapi.responses import FileResponse
    if not database.get_project(pid):
        raise HTTPException(404, "Project not found")
    target = Path(path).resolve()
    exports_root = (PROJECTS_DIR / pid / "exports").resolve()
    if exports_root not in target.parents or target.suffix != ".srt" or not target.exists():
        raise HTTPException(403, "That subtitle file isn't available for this project.")
    return FileResponse(str(target), media_type="application/x-subrip",
                        headers={"Content-Disposition": f'attachment; filename="{target.name}"'})
