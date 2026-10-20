# StoryForge AI — Setup Guide (Windows & Linux)

Everything here is free and open source. No credit card, paid account or subscription is needed
at any point. Commands starting with `$` run in a terminal (Linux/macOS) or PowerShell (Windows).

## 1. Prerequisites

| Component | Version | Notes |
|---|---|---|
| Python | 3.10–3.13 | [python.org](https://www.python.org/downloads/) — on Windows check “Add python.exe to PATH” |
| Node.js | 18+ (20 recommended) | [nodejs.org](https://nodejs.org/) LTS installer |
| FFmpeg | 6.x / 7.x | **Optional manual install** — the Python dependency `imageio-ffmpeg` bundles a static build automatically |
| Disk | ~3 GB | voices, models you choose to add, and rendered videos |

### Installing system FFmpeg manually (optional)

- **Windows:** `winget install Gyan.FFmpeg` (or download from ffmpeg.org and add `bin` to PATH).
- **Debian/Ubuntu:** `sudo apt install ffmpeg`
- **Fedora:** `sudo dnf install ffmpeg`
- StoryForge uses the bundled static FFmpeg if no system binary is found.

## 2. Backend setup

### Linux / macOS

```bash
cd storyforge-ai/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Windows (PowerShell)

```powershell
cd storyforge-ai\backend
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks the venv, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## 3. Voice models for Piper TTS (free, offline)

One English voice (`en_US-amy-low`, feminine) is bundled in `backend/voices/`, so narration
works immediately. Add more voices (a second English voice, 20+ languages, multiple qualities)
with the included downloader:

```bash
# Linux/macOS
cd backend && ./download-voices.sh
# Windows
cd backend && download-voices.bat
```

Or install manually:

1. Browse <https://huggingface.co/rhasspy/piper-voices/tree/main>
2. Download **both** the `*.onnx` and the `*.onnx.json` file for a voice, e.g.
   `en/en_GB/alan/medium/en_GB-alan-medium.onnx(+.json)`
3. Place both files in `backend/voices/` (or a folder set via `STORYFORGE_VOICES`)
4. Restart the backend — the voice appears automatically in the Storyboard.

No network is used during synthesis; Piper runs entirely on CPU.

## 4. Run the application

### Development mode (hot reload, two processes)

```bash
# terminal 1 — API on :8000
cd backend && source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# terminal 2 — UI on :5173 (proxies /api to :8000)
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. On Windows use `.venv\Scripts\activate` instead.

### Single-process mode (recommended for everyday use)

```bash
cd frontend && npm install && npm run build
cd ../backend && source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The backend detects `frontend/dist` and serves the whole app at <http://localhost:8000>.

Convenience scripts: `./start-all.sh` (Linux/macOS), `start-all.bat` (Windows).

## 5. Optional local AI image/video models

StoryForge never requires these. Without them you still get full script → narration →
image-based MP4 export. If your hardware supports it:

### ComfyUI (text-to-video / image-to-video: SVD, AnimateDiff, CogVideo)

1. Install ComfyUI from <https://github.com/comfyanonymous/ComfyUI> and your chosen model.
2. Start it with the API enabled (default port 8188).
3. Export an API-format workflow JSON for your SVD/AnimateDiff graph.
4. Point StoryForge at it:
   - Linux: `export STORYFORGE_COMFY_URL=http://127.0.0.1:8188`
   - Windows PowerShell: `$env:STORYFORGE_COMFY_URL="http://127.0.0.1:8188"`
5. Restart the backend — the provider shows **Connected** on the home screen and in Mode A.

### Automatic1111 / Forge / SD.Next (local still images)

Start the WebUI with `--api`, then set `STORYFORGE_A1111_URL=http://127.0.0.1:7860`.
Generated stills can be animated through Mode B's Ken Burns pipeline.

### Generic CLI wrapper

Set `STORYFORGE_VIDEO_CMD` to any command template, for example:

```
STORYFORGE_VIDEO_CMD='python /opt/cogvideo/run.py --prompt "{prompt}" --output "{out}"'
```

`{image}` is substituted with a reference image path when provided.

## 6. Your first video (5-minute walkthrough)

1. Open the app → **Create a Story Video**.
2. Pick a category, tone, scene count and ending → **Generate original script**.
3. Review/regenerate, then **Approve & build storyboard**. Edit any narration or visual prompt.
4. Open **Storyboard** → choose a narration voice → **All placeholders** → **Narrate all scenes**.
   Replace placeholders with your own images or Openverse imports whenever you like.
5. Open **Timeline** → choose 16:9/9:16/1:1, 720p/1080p, transitions, music, captions, watermark.
6. **Preview & Export** → **Render video with FFmpeg** → watch progress → **Download MP4**.
7. Generate the thumbnail and YouTube metadata on the same page.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| “No local Piper voice installed” | Put `*.onnx` + `*.onnx.json` in `backend/voices/` and restart |
| Render fails with FFmpeg error | The job panel shows the real FFmpeg message; check disk space and that images/audio exist |
| Provider shows “Not configured” | Set the env var from section 5 and restart; verify the model server URL in a browser |
| Port already in use | start uvicorn/vite on another port and set Vite proxy target via `STORYFORGE_API` |
| Windows: long renders feel slow | close other apps; use 720p and fewer scenes; 1080p needs more RAM |
| Openverse search unavailable | network issue or catalog downtime — uploads and all other features keep working |

## 7b. Real AI video for Shorts (free open-weights models, own GPU)

The hosted/free path makes Shorts from AI images with cinematic motion and labels them
`image-motion`. To get true character movement (walking, running, interacting), run a free
open-weights video model locally with ComfyUI:

1. Install [ComfyUI](https://github.com/comfyanonymous/ComfyUI) on a machine with an NVIDIA GPU (8–24 GB VRAM).
2. Add a video model — recommended starting points: **LTX-Video 2B** (fast, ~8 GB), **Wan 2.1**
   T2V, **Stable Video Diffusion** for image-to-video, or **AnimateDiff**.
3. Load the model's example workflow, confirm it runs once, then Save (API Format).
4. Copy a template from `docs/comfyui-workflows/`, align its node ids with your export, keeping
   the `{prompt} {seed} {frames} {fps} {duration} {image}` placeholders.
5. Export the variables and restart StoryForge:
   - Linux: `export STORYFORGE_COMFY_URL=http://127.0.0.1:8188` and
     `export STORYFORGE_COMFY_WORKFLOW=/path/to/your-workflow.template.json`
   - Windows PowerShell: the same two names with `$env:...="..."`
6. In **Create YouTube Short**, the status card switches to "Local video model connected" and
   scenes render via the diffusion model; Clip Mode gains the same connection.

If ComfyUI is stopped, generation falls back to image-motion with a plain status message — no
errors are hidden and no still image is mislabeled as video.

## 8. VoiceForge voice studio (free, no account)

VoiceForge is built into the same server. Once the app is running, open
**`http://localhost:8000/voice/`** (or tap **VoiceForge — Free AI Voice Studio** on the home
screen). It needs no API key: neural voices stream from a free public service, and the bundled
Piper voice is used automatically when that service cannot be reached.

- Single-speech text-to-speech: up to 5,000 characters, speed/pitch controls, MP3 download
- Multi-voice Studio: up to 10 parts with different narrators, joined into one MP3
- Generated audio lives in `data/voice/` (history JSON + `audio/*.mp3`), deleted from the History tab
- Force fully-offline operation (air-gapped machines): set `STORYFORGE_VOICE_ENGINE=piper`
- Self-hosters behind a strict firewall must allow outbound HTTPS to `*.speech.platform.bing.com`
  for neural voices; without it, everything still works via Piper

## 9. Where your data lives

```
data/
├── storyforge.db                 # projects, settings, job history (SQLite)
├── voice/                        # VoiceForge: history.json + audio/*.mp3
└── projects/<project-id>/
    ├── assets/ images/ audio/ generated/   # your media + generated narration/frames
    ├── temp/render_*/                     # per-render working files (safe to delete)
    └── exports/                           # final MP4s and thumbnails
```

Delete a project from the UI to remove its database row and media folder. Nothing is uploaded
to the cloud.
