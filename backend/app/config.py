"""Global configuration and path discovery. Everything can be overridden with env vars."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent

# All user data lives locally. Override with STORYFORGE_DATA.
DATA_DIR = Path(os.environ.get("STORYFORGE_DATA", ROOT_DIR / "data"))
PROJECTS_DIR = DATA_DIR / "projects"
DB_PATH = DATA_DIR / "storyforge.db"
VOICES_DIR = Path(os.environ.get("STORYFORGE_VOICES", BACKEND_DIR / "voices"))

for _d in (DATA_DIR, PROJECTS_DIR, VOICES_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def find_ffmpeg() -> str:
    """Locate an FFmpeg binary: explicit env var, system PATH, or the imageio-ffmpeg static build."""
    env = os.environ.get("STORYFORGE_FFMPEG")
    if env and Path(env).exists():
        return env
    sys = shutil.which("ffmpeg")
    if sys:
        return sys
    try:
        import imageio_ffmpeg  # type: ignore

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if Path(exe).exists():
            return exe
    except Exception:
        pass
    return "ffmpeg"  # leave a readable error for the user later


FFMPEG = find_ffmpeg()

# Thread cap for FFmpeg's x264 encoder. Small cloud containers (e.g. Render free = 512 MB RAM,
# a fraction of a vCPU) run safest with 1 thread; override on bigger machines via env var.
FFMPEG_THREADS = int(os.environ.get("STORYFORGE_FFMPEG_THREADS", "2"))

# x264 preset: "veryfast" locally balances quality/speed; weak cloud CPUs can set "ultrafast"
# (smaller encoder context, much faster, modest quality trade-off) via STORYFORGE_X264_PRESET.
X264_PRESET = os.environ.get("STORYFORGE_X264_PRESET", "veryfast")

# Intermediate clips/joins are always re-encoded again in the final quality pass, so they use
# the fastest preset — this is the biggest single render-time saving on weak cloud CPUs.
X264_INTERIM_PRESET = os.environ.get("STORYFORGE_X264_INTERIM_PRESET", "ultrafast")

# Kill an FFmpeg child if it emits no output for this long (seconds). A healthy encode prints
# progress several times per second, so silence means a true stall — never another 30-minute hang.
FFMPEG_IDLE_TIMEOUT = int(os.environ.get("STORYFORGE_FFMPEG_IDLE_TIMEOUT", "240"))

# Hard wall-clock cap for one whole render (last-resort guard). Default 20 minutes.
RENDER_MAX_SECONDS = int(os.environ.get("STORYFORGE_RENDER_MAX_SECONDS", "1200"))

# A single FFmpeg filter graph handles up to this many clips in one process (one encode instead
# of the old O(n^2) re-encode chain). Larger projects fall back to the chunked path.
MAX_SINGLE_GRAPH_CLIPS = int(os.environ.get("STORYFORGE_MAX_GRAPH_CLIPS", "16"))

# Jobs whose row has not updated for this many seconds are declared failed by the watchdog
# (covers threads that died with the process, e.g. an OOM kill or container restart).
JOB_STALE_SECONDS = int(os.environ.get("STORYFORGE_JOB_STALE_SECONDS", "600"))

# Optional external integrations (all disabled by default, never required for export).
COMFYUI_URL = os.environ.get("STORYFORGE_COMFY_URL", "").strip()        # local ComfyUI, e.g. http://127.0.0.1:8188
A1111_URL = os.environ.get("STORYFORGE_A1111_URL", "").strip()          # local Automatic1111/Forge API
VIDEO_CLI_CMD = os.environ.get("STORYFORGE_VIDEO_CMD", "").strip()      # generic local CLI command template

# Keyless free text-to-image endpoint (Pollinations by default; swap for a compatible host).
AI_IMAGE_BASE = os.environ.get("STORYFORGE_AI_IMAGE_BASE", "https://image.pollinations.ai").rstrip("/")
AI_IMAGES_ENABLED = os.environ.get("STORYFORGE_AI_IMAGES", "1").strip().lower() not in ("0", "false", "no", "off")
OPENVERSE = "https://api.openverse.org"                                 # free CC media search, no API key

# Narration pacing estimate used for duration mismatch warnings (words per minute).
NARRATION_WPM = 145
