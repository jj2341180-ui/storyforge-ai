# Real AI video on your own hardware — free open-weights setup

The free hosted server has no GPU, so true character-movement video (walking, running,
interacting, moving hair/cloth/water) runs on **your own computer** with free, open-source
models. There is no paid API and no API key.

## What you need

- An NVIDIA GPU with **8–24 GB VRAM** (16 GB+ recommended for 720p)
- Windows or Linux; latest NVIDIA driver
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) running locally (default port 8188)

## Recommended free models

| Model | Use | VRAM | License |
|---|---|---|---|
| **LTX-Video 2B** (`ltx-video-2b-v0.9.5`) | fast text-to-video, real motion | ~8 GB | open weights (see model card) |
| **Wan 2.1 T2V 1.3B/14B** | high-quality text-to-video | 8–24 GB | Apache-2.0 |
| **Stable Video Diffusion (SVD/SVD-XT)** | image-to-video from an uploaded frame | ~10 GB | Stability community license |
| **AnimateDiff** | motion modules on Stable Diffusion checkpoints | ~8 GB | open weights |

## Connect StoryForge (two environment variables)

```bash
# Linux/macOS
export STORYFORGE_COMFY_URL=http://127.0.0.1:8188
export STORYFORGE_COMFY_WORKFLOW=/path/to/ltx-video-t2v.template.json
```

```powershell
# Windows PowerShell
$env:STORYFORGE_COMFY_URL="http://127.0.0.1:8188"
$env:STORYFORGE_COMFY_WORKFLOW="C:\path\to\ltx-video-t2v.template.json"
```

## Workflow files in this folder

- `ltx-video-t2v.template.json` — text-to-video starting point
- `svd-i2v.template.json` — image-to-video starting point (uses your uploaded reference image)

### Making the templates match your ComfyUI install

1. In ComfyUI, load the model's official example workflow and confirm it runs once manually.
2. Enable **Settings → Enable Dev mode options**, then **Save (API Format)**.
3. Open the saved JSON and copy its node ids/structure over the template, keeping these
   placeholder strings exactly as written — StoryForge replaces them at generation time:
   - `{prompt}` — the scene description
   - `{seed}` — per-scene seed for reproducibility
   - `{frames}` / `{fps}` / `{duration}` — clip length
   - `{image}` — only for image-to-video; replaced after the reference frame uploads
4. Point `STORYFORGE_COMFY_WORKFLOW` at your finished file and restart StoryForge.

## What happens when it's connected

- **YouTube Shorts** scenes call ComfyUI for real diffusion video instead of the image-motion
  fallback; every export lists the engine used per scene.
- **Clip Mode** uses the same connection for single text-to-video or image-to-video clips.
- If ComfyUI is stopped or unreachable, the app keeps working with the free image-motion path
  and says so plainly — it never pretends a still image is a diffusion video.

### Reaching ComfyUI from the hosted site (advanced, optional)

The free Render server cannot see `127.0.0.1` on your PC. To use your GPU from the hosted app,
expose ComfyUI with a tunnel (e.g. Cloudflare Tunnel) and set `STORYFORGE_COMFY_URL` to the
tunnel URL on your own deployment, or simply run StoryForge locally (see `SETUP.md`) where
both run on the same machine.
