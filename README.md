# StoryForge AI — Free, Local-First AI Story Video Creator

Turn original fantasy, romance, horror and other story ideas into cinematic videos for
YouTube and YouTube Shorts — **with zero paid services, no API keys, no credit card and no
subscription**. Everything that can run locally does run locally.

## YouTube Shorts studio (v1.8)

Tap **Create YouTube Short**, type one idea (e.g. *"a girl discovers a baby dragon"*), and the
app builds a complete 15/30/45/60-second vertical MP4: hook-first story, AI scene images with
cinematic motion, neural narration (six narrator personas, on/off switch), per-scene synthesized
sound effects, royalty-free background music that ducks under the voice, burned-in captions with
a separate SRT download, and volume controls for every stem.

- **Free server path (works today, no GPU):** AI-generated images + camera motion. Exports are
  labeled `image-motion (free, no GPU)` — never passed off as diffusion video.
- **Real character-movement path (free, own GPU):** point `STORYFORGE_COMFY_URL` and
  `STORYFORGE_COMFY_WORKFLOW` at a local ComfyUI running LTX-Video / Wan 2.1 / SVD / AnimateDiff
  (all free open weights, 8–24 GB VRAM). The same Shorts button then renders true text-to-video
  or image-to-video clips; see [`docs/comfyui-workflows/`](./docs/comfyui-workflows).
- Narration uses the same free neural engine as VoiceForge, with the offline Piper voice as
  automatic fallback. Sound effects and music are synthesized locally, so they are royalty-free
  by construction — no audio downloads, no attribution requirements.

## Also included: VoiceForge — free AI voice studio

An ElevenLabs-style voice product with no paid tier and no account, served at **`/voice/`**
(and linked from the StoryForge home screen):

- **322 neural voices in ~90 languages** via a free public service (`edge-tts`, no API key) — search, preview and pick by language/gender
- **Multi-voice Studio**: up to 10 parts, each with its own narrator, joined into one MP3 (podcast/audiobook style)
- Speed and pitch controls, live character counter, background jobs with progress
- **Always works**: if the neural service is unreachable, generation automatically falls back to the bundled offline Piper voice, with an honest engine badge on every file; set `STORYFORGE_VOICE_ENGINE=piper` to force fully-offline operation
- History with inline players and one-tap MP3 download; all errors are plain language, never raw JSON

```
storyforge-ai/
├── backend/          FastAPI service: story engine, Piper TTS, FFmpeg renderer, model adapters
│   ├── app/
│   │   ├── main.py            REST API + optional static hosting of the built frontend
│   │   ├── voice_studio.py    VoiceForge: free neural TTS, multi-voice studio, offline fallback
│   │   ├── story_engine.py    offline original-script generator (8 genre packs)
│   │   ├── tts.py             Piper local neural TTS adapter
│   │   ├── media.py           Pillow placeholder frames, title cards, thumbnails
│   │   ├── renderer.py        FFmpeg pipeline (Ken Burns, xfade, captions, mix, H.264/AAC)
│   │   ├── providers.py       pluggable ComfyUI / A1111 / CLI video-model adapters + HW check
│   │   ├── metadata_gen.py    YouTube titles, description, hashtags, chapters
│   │   ├── database.py        SQLite projects & background jobs
│   │   └── config.py          paths and optional env-var configuration
│   ├── voices/               Piper *.onnx voice files (one English voice bundled; add more with download-voices.sh)
│   ├── requirements.txt
│   ├── e2e_test.py           API end-to-end test
│   ├── ui_test.py            Playwright browser test
│   └── verify_visuals.py     9:16 / caption / scene-count verification
├── frontend/         React 18 + TypeScript + Tailwind + Vite (dark cinematic UI)
├── voice-studio/     VoiceForge React 18 + TypeScript + Vite app (built into frontend/dist/voice)
└── data/             created at runtime: SQLite DB, project media, exports (local only)
```

## What works out of the box (verified, no configuration)

| Capability | Status | How |
|---|---|---|
| Original story generation (8 genres, audience, tone, POV, endings, 3–10 scenes) | ✅ Fully working | Offline template engine, randomized per seed |
| Paste-your-own-script splitting into scenes | ✅ Fully working | Scene headings / blank lines / `Name: dialogue` |
| Script & storyboard editing, scene reordering, duration/motion/transition controls | ✅ Fully working | React UI + autosave to SQLite |
| Character & visual-style consistency library | ✅ Fully working | Descriptions baked into every scene prompt |
| Local neural voiceover, multiple voices, speed control, narration + dialogue tracks, preview | ✅ Fully working | Piper TTS, fully offline |
| User-uploaded narration / images / video | ✅ Fully working | Stored in local project folder |
| Free licensed media search (CC images/audio) with license & attribution stored | ✅ Fully working | Openverse keyless API |
| Captions, timed and burned in (sentence-level cues), editable per scene | ✅ Fully working | FFmpeg subtitles filter + SRT |
| Title cards, intro/outro, background music ducking, watermark/logo | ✅ Fully working | FFmpeg |
| Ken Burns zoom/pan motion, xfade transitions, image-based cinematic MP4 | ✅ Fully working | FFmpeg libx264 + AAC, 720p/1080p, 16:9 / 9:16 / 1:1 |
| Real render queue, live progress, error messages, downloadable MP4 | ✅ Fully working | SQLite jobs + `-progress` parsing |
| Thumbnail generator (title text, placement, small-size preview, PNG export) | ✅ Fully working | Pillow |
| YouTube metadata: 3 titles, description, keywords, hashtags, chapters, pinned comment | ✅ Fully working | Offline rules |
| Mode A text-to-video / image-to-video **provider framework** | ⚙️ Adapter ready, awaits a local model | ComfyUI / A1111 / generic CLI — see below |

## What is *not* claimed (honest limitations)

- **This repository does not download or run a video diffusion model by default.** On a machine
  without a capable GPU, Mode A shows the real hardware/adapter status and points you to Mode B.
- A still image is **never** presented as a generated video clip. Image-based videos are labeled
  *“Image-based cinematic video (Ken Burns)”* and placeholder frames carry a visible red tag.
- There is no guarantee of unlimited cloud compute, free AI video generation, rankings, views,
  monetization or copyright clearance. Placeholders are original generated art, but must be
  replaced or explicitly accepted before publishing.
- Realistic synthetic content may require disclosure in YouTube's upload tools.

## Hardware requirements

| Workload | Minimum | Comfortable |
|---|---|---|
| Story writing, TTS, image-based 720p rendering (default Free Mode) | 2 CPU cores, 2 GB RAM, ~3 GB disk | 4 cores, 4 GB RAM |
| 1080p renders / long videos | 4 cores, 4 GB RAM | 8 GB RAM |
| Local Stable Diffusion **images** (A1111/Forge) | NVIDIA GPU, 4–8 GB VRAM | 8 GB VRAM |
| Local **video** diffusion (SVD, AnimateDiff, CogVideo via ComfyUI) | NVIDIA GPU, 8 GB VRAM, 16 GB RAM | 12–24 GB VRAM, 32 GB RAM |

CPU-only video diffusion is technically possible but can take hours per clip — the app detects
the hardware and tells you the truth instead of pretending otherwise.

## Quick start

Full OS-specific instructions are in [SETUP.md](./SETUP.md). Short version:

```bash
# 1. backend
cd backend
python3 -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. frontend (development)
cd ../frontend
npm install
npm run dev                     # open http://localhost:5173
```

Single-process option after `npm run build`: the backend automatically serves `frontend/dist`
at <http://localhost:8000>.

## Connecting a local video/image model (all free, all optional)

Set environment variables before starting the backend — no code changes, no paid services:

| Variable | Purpose |
|---|---|
| `STORYFORGE_COMFY_URL` | e.g. `http://127.0.0.1:8188` — ComfyUI with SVD/AnimateDiff/CogVideo nodes |
| `STORYFORGE_A1111_URL` | e.g. `http://127.0.0.1:7860` — Automatic1111 / Forge / SD.Next image API |
| `STORYFORGE_VIDEO_CMD` | generic CLI template using `{prompt}`, `{out}`, optional `{image}` |
| `STORYFORGE_FFMPEG` | force a specific FFmpeg binary (otherwise system PATH, then bundled static build) |
| `STORYFORGE_DATA` | relocate the local data directory |
| `STORYFORGE_VOICES` | folder containing Piper `*.onnx` voices |

## Testing

```bash
# API workflow: story -> script -> placeholders -> Piper narration -> MP4 -> metadata
cd backend && python e2e_test.py

# 9:16 Shorts, caption chunking, scene-count correctness
python verify_visuals.py

# Full browser workflow with Playwright/Chromium
python ui_test.py
```

## Privacy & content responsibility

- Projects, scripts, media and exports stay in `data/` on your machine by default.
- The only outbound call in Free Mode is the optional Openverse media search (search terms only;
  no account, no personal data). Piper, FFmpeg, rendering and storage never leave the computer.
- Write original stories. The engine generates randomized, original plots and does not reproduce
  copyrighted books, films or distinctive characters.
- Check every imported asset's license; attribution info is stored with the asset.
