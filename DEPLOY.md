# Getting StoryForge onto your phone or any browser — the complete picture

## The one thing to understand first

StoryForge has two parts: a **server** (Python + FFmpeg + Piper, does the rendering) and a
**web interface** (what you see in the browser). A phone — especially an iPhone — cannot run
the rendering server as a normal app. So the server always runs *somewhere*, and your
phone/browser connects to it:

```
Phone / laptop browser  ──http──►  StoryForge server (your PC, or a free cloud host)
```

There are three realistic, zero-cost ways to make that happen, easiest first.

---

## Option 1 — Your own computer + installable browser app (best for most people)

1. Install Python 3.11+ and Node 18+ (Windows/Mac installers from python.org and nodejs.org).
2. Put the `storyforge-ai` folder on that computer and run `start-all.bat` (Windows) or
   `./start-all.sh` (Mac/Linux).
3. On that computer's Chrome/Edge open `http://localhost:8000`, then install it as an app
   (address-bar install icon, or menu → Install page as app).
4. To use it **from your phone**: install the free **Tailscale** app on both devices (same
   free account), then open `http://<computer-tailscale-ip>:8000` in the phone browser and use
   Add to Home Screen. Full steps and firewall rules are in `ACCESS-GUIDE.md` §3–4.

Pros: free forever, fully private, fastest renders, survives reboots with auto-start.
Requires: the computer to be on when you use the app.

---

## Option 2 — Hugging Face Docker Space (free public URL, opens on any phone)

This gives you an `https://your-name-storyforge.hf.space` address that works from any browser,
no computer needed. Free tier, no card required.

1. Create a free account at huggingface.co.
2. Create a **new Space** → SDK choose **Docker** → blank.
3. Upload the whole `storyforge-ai` project (drag-and-drop works), including the `Dockerfile`
   at the root.
4. Edit the Space's `README.md` so it starts with this block, then save:

```yaml
---
title: StoryForge AI
emoji: 🎬
colorFrom: gray
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---
```

5. The Space builds automatically (first build ~10–20 min) and then shows your running app.
6. Open that URL on your phone → Chrome menu **Install app** / Safari **Share → Add to Home Screen**.

Honest limitations of the free tier:

- The Space **sleeps after inactivity** (first visit after sleep waits ~1–2 min to wake).
- Its disk is **ephemeral**: projects and exports may be lost when the Space restarts. Treat it
  as a rendering service — download every MP4 you want to keep.
- No GPU on free Spaces: Mode A video models won't run; Mode B (the full script→narration→
  image-based MP4 pipeline) works fine on the free CPU.
- The Space URL is public. Do not put private stories on it unless you set the Space visibility
  to Private in Space settings.

The same `Dockerfile` works on **Render.com** (Web Service → Docker, free instance, it
injects `$PORT` automatically) and **Fly.io** (`fly launch --dockerfile`).

---

## Option 3 — Always-on free cloud VM (persistent, most capable)

Oracle Cloud's **Always Free** Ampere VM (up to 4 cores / 24 GB RAM) runs 24/7 at no charge
(signup needs a card for identity, it is not charged while you stay within Always-Free limits).

1. Create an Ubuntu 22.04/24.04 Ampere A1 instance.
2. Install Docker (`curl -fsSL https://get.docker.com | sh`), copy the project over, then:
   ```bash
   docker build -t storyforge .
   docker run -d --name storyforge -p 8000:7860 \
     -v storyforge-data:/app/data --restart unless-stopped storyforge
   ```
3. Do **not** open port 8000 to the whole internet. Install Tailscale inside the VM and connect
   from your phone/laptop over the private Tailscale IP (or use a Cloudflare Tunnel with an
   access policy if you want an https URL).
4. The named volume (`storyforge-data`) keeps all projects, voices and exports across restarts.

This is the closest thing to a permanently installed version that remains completely free and
under your control.

---

## Can I run it directly ON the phone?

- **Android (advanced):** yes, via Termux — install Python, FFmpeg and Piper inside Termux,
  copy the project, run the backend, and open `http://localhost:8000` in Chrome. Expect slow
  renders on phone hardware; detailed Termux recipes are best attempted after Option 1 works.
- **iPhone / iPad:** no. iOS does not allow this kind of background server. Use Option 2 or 3
  and open the hosted URL in Safari, then Add to Home Screen.

## Why the Arena sandbox can't be the permanent install

Arena sandboxes are disposable: background processes and installed packages are removed when
the environment resets (this has happened repeatedly during development). Source files and the
`data/` folder survive, which is why `restore-and-start.sh` can rebuild the runtime in one
command — but anything meant to live for days or weeks belongs in Option 1, 2 or 3 above.

## AI scene images (free, keyless)

The Storyboard can turn each scene's description into an original picture without any API
key, via Pollinations' anonymous image endpoint. Each generated frame is stored with its
source and a license note. The free tier is throttled to about **one image every 45 seconds
per server IP**, so batch generation runs sequentially with live "waiting for quota"
progress — a 5-scene batch takes roughly 4 minutes. Related settings:

| Variable | Default | Purpose |
|---|---|---|
| `STORYFORGE_AI_IMAGES` | `1` | Set `0` to disable AI image generation entirely |
| `STORYFORGE_AI_IMAGE_BASE` | `https://image.pollinations.ai` | Point at a compatible/self-hosted endpoint |

If an image cannot be produced (quota outage, network block), the scene keeps its previous
frame or placeholder and the job reports exactly which scenes failed — nothing is faked.

## Memory-tuning environment variables (small cloud containers)

Free PaaS containers (Render free = 512 MB RAM, a fraction of a vCPU) need the memory-safe
defaults already baked into the Dockerfile and `render.yaml`:

| Variable | Container default | Purpose |
|---|---|---|
| `STORYFORGE_TTS_SUBPROCESS` | `1` | Runs Piper/onnxruntime in a child process that exits, returning its ~200 MB arena before video rendering |
| `STORYFORGE_FFMPEG_THREADS` | `1` | Single-threaded x264/filters: lower peak RSS on shared CPUs |
| `MALLOC_ARENA_MAX` | `2` | Stops glibc creating one malloc arena per CPU core |
| `STORYFORGE_X264_PRESET` | `veryfast` | Set `ultrafast` on even smaller hosts (faster, lower memory, larger files) |
| `STORYFORGE_DATA` | `/app/data` | Where projects/exports live; mount a volume to persist |

Measured peak on a 512 MB-class host during a full 720p story render: ~340 MB combined
(API ~90 MB, FFmpeg ~250 MB, transient TTS worker included), leaving comfortable headroom.
Local PC installs leave these unset and use the faster in-process defaults.

## Quick decision guide

| Your situation | Choose |
|---|---|
| You have a laptop/PC and want it free & private | Option 1 (+ Tailscale for phone) |
| No computer, only a phone/tablet | **Render free web service via GitHub** (this repo's `render.yaml`; sleeps after 15 min, ephemeral disk) — Hugging Face Docker Spaces now require a paid PRO plan |
| Want it on 24/7 with saved projects | Option 3 (Oracle free VM + Tailscale) |
| Android power user, no other hardware | Termux (advanced) |
