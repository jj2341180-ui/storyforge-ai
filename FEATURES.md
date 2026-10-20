# Feature Status — implemented vs. awaiting configuration

Every row below is honest. “Awaiting configuration” means the code path is complete and tested
up to the boundary of a local model/service the owner must install; there is no paid fallback
and no fake button.

## Feature 1 — Two creation modes

| Requirement | Status | Evidence |
|---|---|---|
| Mode A: prompt + negative prompt inputs | ✅ Implemented | `ClipMode.tsx`, endpoint `POST /api/projects/{id}/generate` |
| Duration / resolution / aspect / quality settings | ✅ Implemented | Clip mode controls, validated in UI |
| Reference image (image-to-video) where supported | ✅ Implemented | upload + library pick, passed to adapter as `reference_image` |
| Real progress & errors, preview, save to project, regenerate | ✅ Implemented | job polling, error surfaces, result saved as project asset |
| Pluggable provider interface (no UI change to add models) | ✅ Implemented | `providers.py`: ComfyUI, Automatic1111/Forge, generic CLI |
| Hardware check + truthful “cannot run here” message | ✅ Implemented | `GET /api/providers/status`, home & clip-mode panels |
| Actual moving-clip generation on this machine | ⏳ Awaiting model | No GPU in the reference environment; requires local ComfyUI/SVD/CogVideo per SETUP.md |
| Never label a still image as video | ✅ Enforced | image results show an explicit warning, Mode B output is labeled “image-based” |
| Mode B: full story-to-video workflow (12 steps) | ✅ Implemented | story engine → storyboard → images → TTS → captions → music → FFmpeg MP4 → metadata |
| Approve/edit script & storyboard before assets | ✅ Implemented | approval gate in Story Studio; full Script & Storyboard editors |
| Automatic image-based fallback with zoom/pan/transitions | ✅ Implemented | Ken Burns `zoompan`, xfade, labeled placeholders |

## Feature 2 — Story Writing Studio

| Requirement | Status |
|---|---|
| 8 categories (fantasy, romance, horror, mystery, adventure, drama, children, short film) | ✅ `story_engine.GENRES` |
| Audience, length, language, tone, POV, scene count, 4 ending types | ✅ Studio controls + generator inputs |
| Hook, development, original dialogue, scene descriptions, ending | ✅ Verified in generated scripts |
| Short & long-form; narration-length estimate + mismatch warning | ✅ WPM estimator in UI + backend (`duration_warning`) |
| No copying of existing copyrighted works/characters | ✅ Randomized original components; originality statement attached |
| User's own complete script | ✅ Paste & auto-split into scenes with dialogue detection |

## Feature 3 — Character & visual consistency

| Requirement | Status |
|---|---|
| Per-project character library with all 8 required fields | ✅ Characters tab |
| Descriptions reused in every scene visual prompt | ✅ `story_engine` injects character block; style block reused |
| Reference images + image-to-video linkage | ✅ Upload/library link, passed to adapters |
| Honest limitation when model can't guarantee consistency | ✅ Explicit notice in Characters tab |
| Reusable location/lighting/palette/camera/effects settings | ✅ “Reusable visual style” card |

## Feature 4 — Automatic voiceover

| Requirement | Status |
|---|---|
| Genuinely free local TTS (Piper), no paid API | ✅ Verified offline WAV synthesis |
| Multiple voices, adjustable speed | ✅ Voice discovery + length-scale speed control (0.7x–1.6x) |
| Separate narration & dialogue tracks | ✅ Two voice selectors, per-scene dialogue generation |
| Scene-by-scene generation, audio preview, uploaded narration | ✅ Storyboard audio players + file upload |
| Timing information for captions | ✅ Scene durations drive weighted SRT cue timing |
| Modular design + install/language guidance | ✅ `tts.py` adapter, SETUP.md §3, `download-voices.*` |

## Feature 5 — Video editing & export

| Requirement | Status |
|---|---|
| FFmpeg assembly, scene timeline, reorder, clip replacement | ✅ Timeline tab; renderer two-pass pipeline |
| Image duration controls, transitions, narration+music, title cards, intro/outro, watermark | ✅ All wired to FFmpeg filters |
| Subtitle editing (caption override) & burn-in | ✅ Script editor override + SRT sentence chunking |
| Preview player, export progress, error recovery (real messages) | ✅ Job system with `-progress` parsing |
| MP4 H.264 + AAC, 16:9 / 9:16 / 1:1, 720p / 1080p, fast-start | ✅ Verified outputs (1280×720 & 720×1280) |
| Real download, no fake button | ✅ `GET /api/jobs/{id}/download` only exists for completed jobs |

## Feature 6 — Thumbnails & YouTube metadata

| Requirement | Status |
|---|---|
| Original thumbnail concept, image choice, title text & placement | ✅ Pillow generator, 3 placements, custom background |
| Small-size preview + PNG export | ✅ Export panel |
| 3 titles, description, keywords, hashtags, chapters, pinned comment | ✅ `metadata_gen.py`, copy-to-clipboard UI |
| No ranking/view/monetization/copyright promises | ✅ Disclaimer shown in-app and in output |

## Feature 7 — Free-asset library

| Requirement | Status |
|---|---|
| User images/audio/video upload with source & license stored | ✅ Asset records carry source/license fields |
| Optional free legal-media integration (keyless Openverse CC catalog) | ✅ Search + import with attribution persisted |
| No platform scraping; “public ≠ free commercial use” warning | ✅ In-app notices; only uploads + authorized catalog |

## Feature 8 — Local-first architecture

| Requirement | Status |
|---|---|
| React + TypeScript + Tailwind frontend | ✅ Vite build, strict TS passes |
| Python FastAPI local service | ✅ All processing endpoints |
| FFmpeg, SQLite metadata, local project folders | ✅ `data/projects/<id>/…`, `storyforge.db` |
| Modular AI adapters, keys never in frontend | ✅ Env-var configured adapters; no key handling in UI |
| Frontend vs local service distinction documented | ✅ README architecture + SETUP dev/single-process modes |
| Windows & Linux setup incl. limited-hardware guidance | ✅ SETUP.md, `.sh`/`.bat` scripts, hardware table |

## Feature 9 — User interface

| Requirement | Status |
|---|---|
| Exact home headline & subtitle, 4 primary actions | ✅ `Home.tsx` |
| Prompt/script editors, storyboard, characters, library, timeline, preview, export | ✅ Seven workspace tabs |
| Modern dark cinematic responsive UI (phone + desktop) | ✅ Tailwind responsive grids, tested at 1440px; mobile breakpoints included |
| All controls perform real actions | ✅ Every button calls an API or mutates persisted state; Playwright test passes |
| Obvious Back / Next navigation on every page (phone-friendly wizard) | ✅ `WizardNav.tsx`: step indicator, tap dots, labeled Back/Next buttons under every step; clip mode has its own Back-to-Home bar; Next is disabled with a hint until a script exists |
| All Mode A providers selectable even before setup | ✅ No disabled options in the Provider dropdown; selecting an unconfigured adapter returns its exact setup requirements (503) instead of hiding it |
| Target system RAM planning selector, 32–72 GB | ✅ Clip mode dropdown: 32 / 40 / 48 / 56 / 64 / 72 GB; selection is stored and compared with the host's real RAM in the job result |

## Feature 19 — YouTube Shorts studio: one idea → finished narrated MP4 (v1.8)

| Requirement | Status |
|---|---|
| One-prompt Shorts pipeline (15/30/45/60 s, 9:16 default, also 16:9 / 1:1) | ✅ New **Create YouTube Short** mode: idea → titled hook-first story → per-scene visual prompts → AI images → moving clips → narration → SFX → music → captions → one MP4, with 360p/480p/720p choices |
| Real AI video model integration, honestly labeled | ✅ ComfyUI adapter upgraded into a full queued client (image upload for image-to-video, `{prompt}/{seed}/{frames}/{fps}/{image}` workflow templates, history polling, video download). Free open-weights models documented: LTX-Video 2B (~8 GB VRAM), Wan 2.1, SVD, AnimateDiff (`docs/comfyui-workflows/`). When no GPU provider is connected the free server uses AI images + cinematic camera motion, and every export records per-scene `video_engines` plus an `image-motion (free, no GPU)` badge — a still is never presented as diffusion video |
| Automatic narration on every video, with off switch | ✅ On by default; a compact hook-first script is written per scene, spoken with neural voices (edge-tts, offline Piper fallback), timed to the scene timeline; toggle in the UI and `narration.enabled` in the API |
| Six requested narrator personas | ✅ Male, Female, Deep cinematic, Friendly storytelling, Exciting Shorts, Calm mysterious — mapped to verified free neural voices, with speaking-speed control; accents/languages available via the VoiceForge catalog |
| Sound effects per scene | ✅ 10 synthesized ambience presets (ocean, rain, forest/birds, city, fire, dragon, magic sparkles, action, night, wind) chosen by scene keywords; fully procedural FFmpeg synthesis = royalty-free by construction; on/off switch + volume slider |
| Background music with auto-ducking | ✅ Five moods (adventurous, suspenseful, peaceful, dramatic, emotional) generated as layered pad progressions; music automatically ducks under narration (sidechain compression), with fades and a limiter against clipping; on/off switch + volume slider |
| Subtitles / captions | ✅ Narration cues become an SRT timeline, burned into the MP4 with selectable font size (10–36) and position (top/middle/bottom); the SRT file is also downloadable separately |
| Free-host constraints respected | ✅ One render at a time, job progress for every stage, cancellation, plain-language errors (no JSON), 512 MB-safe single-encode final pass, watchdog timeouts |
| Verified | ✅ Two full local pipeline runs (15 s 9:16 with narration/SFX/music/captions; 16:9 narration-off/music-off/captions-off variant), MP4 stream inspection (H.264+AAC, exact duration), mock-ComfyUI provider contract test (upload/queue/poll/download), Playwright UI flow, backend e2e 10/10 |

## Feature 18 — VoiceForge: free ElevenLabs-style voice studio (v1.7)

A complete second product inside the same free deployment, at **`/voice/`** (linked from the StoryForge home screen). No API key, no account, no paid tier — the free guarantee is shown in the header of every screen.

| Requirement | Status |
|---|---|
| Realistic neural text-to-speech, free | ✅ 322 neural voices across ~90 locales via the free public edge-tts service (no key); every generation returns a downloadable MP3 |
| Voice library like a commercial voice product | ✅ Search/filter by language and gender, featured voices, per-voice **Preview** and **Use this voice**; each card labels engine and gender |
| Creative controls | ✅ Speed (−50%…+100%) and pitch (−50…+50 Hz) sliders; 5,000-character single-speech limit with live counter |
| Multi-voice studio (audiobook/podcast style) | ✅ Up to 10 parts, each with its own voice and speed, reorderable; parts are synthesized sequentially and joined into one MP3 with FFmpeg |
| Never blocked by network/paywall | ✅ Automatic fallback to the bundled offline Piper voice (open source) when the neural service is unreachable, with an honest engine badge on every file; `STORYFORGE_VOICE_ENGINE=piper` forces fully offline mode |
| Library & downloads | ✅ History tab with inline players, one-tap **Download MP3**, delete, and an honest `file_exists` notice when a free-host update wiped the disk |
| Phone-first, no raw errors | ✅ Portrait-first UI with big tap targets; all failures are plain-language notices (JSON never reaches the UI); background jobs with progress bar and polling |
| Safe by construction | ✅ Audio ids validated, path traversal blocked (404), bounded history (200 items), single generation lock for the 512 MB host |
| Verified | ✅ Backend: speak/studio/offline/fallback/validation/history/delete/traversal checks all pass; Playwright phone flow 19/19 with zero console errors |

## Feature 17 — v1.6 Clip Mode plain-language guidance

| Requirement | Status |
|---|---|
| Server errors must never appear as raw JSON in the phone UI | ✅ The API error parser now reads the human `message` from structured error details instead of stringifying them; Clip Mode never renders braces/JSON to the user |
| An unconfigured diffusion provider must explain what is actually required | ✅ Tapping **Generate clip** with an unconfigured provider opens a plain-language amber panel: the local video models only run on your own computer with an NVIDIA GPU (8–24 GB VRAM), with the exact setup line shown; a red status label and an inline **Not connected — …** hint appear on the provider dropdown before you tap |
| The error must offer a free one-tap path, not a dead end | ✅ The panel includes **Back to Home — use Story Video mode**, which returns to the Home screen where the free image-based **Story Video** workflow builds a real downloadable MP4 without any GPU |
| Duration typo protection | ✅ The Duration field clamps to 2–30 seconds in the UI while typing, and the server independently clamps every request (`6000` becomes `30`, `1` becomes `2`) |
| Plain bad-input responses | ✅ Empty prompt → `400 "Enter a scene prompt first."`; unknown provider → `400 "Unknown provider"`; both shown as plain text |
| Verified | ✅ Playwright phone-flow test (clamp 6000→30, inline hint, friendly panel, zero JSON anywhere, CTA returns Home, zero console errors); backend curl checks for 503/400 contracts and server-side clamping; backend e2e still 10/10 |

## Feature 16 — v1.5 downloads & project backup

| Requirement | Status |
|---|---|
| A finished video must always have a visible Download MP4 button | ✅ The export list now merges saved exports with every finished render job, so a completed job shows a download even if the project document's export list is empty; each row has a one-tap **Download MP4** using the attachment-header endpoint `/api/projects/{id}/export-download` |
| Download the whole project anytime | ✅ **Download project backup (.zip)** on the Preview & Export tab bundles `project.json` plus every image, audio file and exported MP4 on disk; works at any time, not just after a render |
| Bring a project back | ✅ **Restore project from backup (.zip)** recreates the project under a fresh id, extracts files into its folder, remaps every stored path (including backups made on another machine or a different data folder — absolute POSIX and Windows paths are re-anchored by project id), drops exports whose files are missing, and rejects malformed zips (zip-slip guarded) |
| Honest handling of the free host's temporary disk | ✅ Jobs carry a `file_exists` flag; when a restart/update cleared an MP4 the row shows a plain-English notice instead of a broken player or a 500 error |
| Verified | ✅ Backup zip contents (JSON + 10 images + MP4), restore with path remap, wiped-file 404/flag behavior, bad-zip 400, zip-slip blocked, Playwright download flow with zero console errors, backend e2e 10/10 |

## Feature 15 — v1.4 render reliability & speed

| Requirement | Status |
|---|---|
| Renders must never hang on a frozen progress bar | ✅ Root cause fixed: the old pipeline re-encoded the growing video once per join (O(n²) work) and later joins could stall for 30+ minutes on the free CPU while queued renders waited forever on a global lock. New pipeline: per-clip normalized files → bounded group-of-three joins → one quality encode |
| Memory-safe on the 512 MB free container | ✅ No FFmpeg process opens more than three inputs; measured peak FFmpeg PSS is ~286 MB at 720p (10 scenes) / ~160 MB at 480p; the earlier all-in-one graph used 1.1–1.2 GB and would have been OOM-killed |
| Stalled-process watchdog | ✅ Any FFmpeg child silent for `STORYFORGE_FFMPEG_IDLE_TIMEOUT` (240 s default) is killed and the job fails with a clear message; hard `STORYFORGE_RENDER_MAX_SECONDS` (1200 s) wall-clock cap as last resort |
| Cancel button | ✅ `POST /api/jobs/{id}/cancel` kills the active FFmpeg process group immediately; the job settles as "Render cancelled" and the render lock frees at once |
| No zombie queued renders | ✅ Starting a render while one is active returns HTTP 409 with plain-language guidance instead of creating a 0% job that can never start |
| Recovery after restart/OOM/redeploy | ✅ On startup every unfinished job row is marked failed ("Interrupted by a server restart or update"); a 10-minute no-update watchdog catches any later stall; temp files older than an hour are swept |
| Continuous, honest progress | ✅ Per-second FFmpeg `-progress` parsing on every stage (per-clip encodes, joins, final encode); elapsed timer in the UI; truncated `.part` files are renamed to MP4 only on success so broken files never appear as exports |
| Measured speed (10 scenes, ~4 min video, 1 thread) | ✅ Fast preview is now a 360p / 20 fps draft with static framed scenes and no title card (smallest encode of the real storyboard): local ≈ 34 s; full 720p render with Ken Burns motion stays at 30 fps, local ≈ 128 s. The full video is encoded only once after per-clip work (captions/music/watermark fold into the final join); join groups adapt per resolution (360p: 6 inputs, 480p: 5, 720p: 3, 1080p: 2) with peak FFmpeg PSS ≤ ~300 MB — safe on 512 MB. Old pipeline could not finish the same video in 30+ minutes |
| UI behavior | ✅ Cancel render button + elapsed seconds under both render bars, "keep this tab open" keep-awake note, jobs reattach automatically after reload/navigation, visibility regains trigger an immediate poll, zero console errors |

## Feature 14 — v1.3 speed, layout & disclosure

| Requirement | Status |
|---|---|
| Faster preview/export | ✅ Two buttons: **Fast preview (480p)** draft and **Full quality render**; all intermediate clips/joins now use the ultrafast preset (only the final pass uses the quality preset) — measured ~1.6× faster previews locally |
| Desktop layout on a portrait phone (device never rotates) | ✅ `DesktopStage` renders the full 1280px app inside a same-origin scaled iframe — media queries resolve as on a real desktop (multi-column grids), while the phone stays portrait; monitor/smartphone toggle in the header remembers the choice (`sf_desktop_layout`), first-visit hint, pinch-to-zoom for larger text |
| Automatic AI/synthetic disclosure | ✅ Every generated YouTube description includes an explicit AI-ASSISTED / SYNTHETIC CONTENT DISCLOSURE block and the pinned comment carries the same notice (YouTube's own upload toggle still must be switched by the creator) |
| No stale UI after updates | ✅ `index.html` served with `Cache-Control: no-store` while hashed `/assets` stay long-cacheable |
| Earlier features not regressed | ✅ Wizard nav, selectable providers, 32–72 GB RAM selector and keyless AI images all re-verified in the v1.2 Playwright + e2e suite |

## Feature 13 — Free AI scene images (keyless)

| Requirement | Status |
|---|---|
| Generate an original picture for a scene with no reference image and no API key | ✅ `ai_images.py` → Pollinations anonymous image endpoint; per-scene **AI image** button in the Storyboard |
| Generate images for multiple/all story scenes in one action | ✅ **Generate AI images for all scenes** batch job with live progress; runs sequentially because the free tier allows ~1 image per 45 s per server IP (the wait is shown honestly) |
| HD 1080p source frames for video | ✅ Every AI image is produced/upscaled to full-HD `HD_TARGETS` (1920×1080 / 1080×1920 / 1080×1080) with LANCZOS resampling + UnsharpMask, saved as quality-92 JPEG |
| Exact project dimensions, no provider watermark | ✅ Corner logo strip cropped; HD frame downscales cleanly for 720p exports and matches 1080p 1:1 |
| Free-quota resilience | ✅ 402/429 responses are parsed for their retry delay and honored within a time budget; failures per scene are reported without faking an image |
| License/source traceability per asset | ✅ Every image registered with source "Pollinations AI (keyless free image API)" and a terms-review license note |
| Kill switch / self-host alternative | ✅ `STORYFORGE_AI_IMAGES=0` disables; `STORYFORGE_AI_IMAGE_BASE` points at any compatible endpoint |
| Placeholder/upload paths preserved | ✅ AI images sit alongside the existing Placeholder, Upload and Library options |

## Feature 10 — Honest Free Mode

| Requirement | Status |
|---|---|
| Works with zero paid APIs; export never locked behind payment | ✅ Full default pipeline is free/local |
| Disclosure of account/limit/cost before external integrations | ✅ Provider cards state cost & requirements; Openverse privacy note |
| Functional no-GPU alternative (script + TTS + images + captions + FFmpeg MP4) | ✅ Verified end-to-end on a 2-core / 2 GB RAM, no-GPU machine |
| No “unlimited free cloud AI video” claims | ✅ Explicit limitations throughout |

## Feature 11 — Privacy & content responsibility

| Requirement | Status |
|---|---|
| Local by default; external-send disclosure | ✅ Only Openverse search leaves the machine, labeled in UI |
| No unnecessary personal data | ✅ No accounts, no analytics, no telemetry |
| Synthetic-content disclosure reminder | ✅ Home footer + Export panel notice |
| Original-story encouragement over mass production | ✅ Originality statement; per-project unique seeds |

## Feature 12 — Build phases

- **Phase 1 (interface, editors, storyboard, import, local saving):** ✅ complete
- **Phase 2 (TTS, captions, FFmpeg, MP4 export):** ✅ complete and tested
- **Phase 3 (T2V/I2V adapters, hardware check, queue, errors):** ✅ framework complete; model execution ⏳ awaits a local GPU model
- **Phase 4 (characters, thumbnails, metadata, timeline controls):** ✅ complete
