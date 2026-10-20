# Running StoryForge AI in Chrome, Edge, Firefox or on your phone

StoryForge is a **local-first web app**: a small Python server renders videos and a web UI
opens in any modern browser. Nothing is Chrome-specific — Chrome, Edge, Firefox, Safari and
mobile browsers all work, because it is a standard website served over HTTP.

> ⚠️ The Arena sandbox preview is temporary. To open StoryForge in your own browser you must
> run the project on your own computer (or a free cloud server — see section 5).

---

## 1. Run it on your own computer (recommended, zero cost)

### Windows

1. Install **Python 3.11+** from python.org (tick “Add python.exe to PATH”) and **Node.js 18+**
   from nodejs.org (LTS installer).
2. Copy the whole `storyforge-ai` folder to your PC (you can skip `node_modules`, `.venv`
   and `data/` — they are recreated automatically).
3. Double-click **`start-all.bat`** the first time. It will:
   - create the Python virtual environment and install backend dependencies (includes a bundled
     FFmpeg, so no separate FFmpeg install is required);
   - run `npm install` and build the frontend;
   - start the server.
4. Open **http://localhost:8000** in Chrome (or any browser). That's the whole app in one process.

### macOS / Linux

```bash
cd storyforge-ai
./start-all.sh            # creates .venv, installs deps, builds UI, serves on :8000
# then open http://localhost:8000
```

### Two-process development mode (optional, hot reload)

```bash
./start-dev.sh            # API on :8000, Vite dev server on :5173 -> open http://localhost:5173
```

### Make it feel like a desktop app in Chrome

Chrome menu (⋮) → **Cast, save, and share → Install page as app…** (or
**More tools → Create shortcut → tick “Open as window”**). You get a StoryForge icon in your
taskbar/Start menu that opens without the browser toolbar. Edge has the same “Install this site
as an app” option.

---

## 2. Start it automatically every time the computer boots

### Windows (no command line needed)

1. Press `Win + R`, type `shell:startup`, press Enter — the Startup folder opens.
2. Right-drag `start-all.bat` into that folder → **Create shortcuts here**.
3. It now launches on every login. A small terminal window stays open; closing it stops the app.

Alternative: Task Scheduler → Create Task → trigger **At startup** → action runs
`start-all.bat` → tick “Run whether user is logged on or not” for true background operation.

### Linux (systemd)

A ready template is in `deploy/storyforge.service`. Install it:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/storyforge.service ~/.config/systemd/user/
# edit the two paths inside if your project is not in ~/storyforge-ai
systemctl --user daemon-reload
systemctl --user enable --now storyforge
loginctl enable-linger "$USER"      # keep it running even when you log out
```

Check status with `systemctl --user status storyforge`; logs with `journalctl --user -u storyforge -f`.

### macOS

System Settings → General → Login Items → add the terminal command, or create a LaunchAgent
plist. The simplest everyday option: run `./start-all.sh` in a Terminal window and keep it in the Dock.

---

## 3. Open it from your phone, tablet or another computer (same Wi-Fi)

The servers already listen on `0.0.0.0`, so no code change is needed.

1. Find the host computer's local IP:
   - Windows: `ipconfig` → IPv4 Address, e.g. `192.168.1.42`
   - Mac/Linux: `ip addr` (or `ifconfig`) → look for `192.168.x.x`
2. On the other device's browser (same network): **http://192.168.1.42:8000**
3. First connection on Windows may prompt a firewall dialog — click **Allow access** for
   private networks. If no prompt appears, add a rule manually in an Administrator PowerShell:

   ```powershell
   New-NetFirewallRule -DisplayName "StoryForge 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
   ```

Bookmark it on the phone and use “Add to Home screen” for an app icon. This only works at
home/on the same network — see section 4 for anywhere-access.

---

## 4. Access it securely from anywhere (free)

The app has **no login screen**, so never open port 8000 directly to the public internet.
Use a private tunnel instead:

### Easiest: Tailscale (free for personal use)

1. Install Tailscale on the host computer and on your phone/laptop, log in with the same account.
2. The host gets a private IP (e.g. `100.x.x.x`) or a MagicDNS name like `my-pc.tail-xxxx.ts.net`.
3. Open `http://100.x.x.x:8000` from anywhere. Traffic is end-to-end encrypted and only your
   own devices can reach it — no port forwarding, no public exposure.

### Alternative: Cloudflare Tunnel (gives an https:// URL)

`cloudflared tunnel --url http://localhost:8000` creates a public HTTPS address. Lock it down
with a Cloudflare Access email/Google login policy so only you can open it.

---

## 5. Run it 24/7 without keeping your PC on — free cloud options

The default Mode B pipeline (script → Piper narration → FFmpeg MP4) runs on a 2 GB RAM machine,
so small free servers work. **No free cloud tier includes a GPU**, so Mode A's local video
diffusion models still need your own NVIDIA GPU — cloud access changes where the UI runs, not
that hardware requirement.

| Option | Free tier reality | Good for |
|---|---|---|
| **Oracle Cloud Always Free** | Ampere A1 VM, up to 4 cores / 24 GB RAM, free indefinitely (capacity permitting) | Best zero-cost always-on host; runs the full Mode B pipeline |
| **Google Cloud e2-micro** | One small VM free in specific US regions + 90-day trial credit; modest RAM | Light use; check current terms, they change |
| An old laptop at home | Free, yours already | Best privacy; pair with Tailscale for remote access |

Hardening checklist for any cloud host:

- do **not** open port 8000 in the cloud firewall; reach it only via Tailscale or an
  authenticated Cloudflare Tunnel;
- keep the OS patched; the app stores everything in its local `data/` folder;
- expect renders to be slower on a small shared CPU (a 1-minute 720p video takes a few minutes).

---

## 6. Troubleshooting browser access

| Symptom | Fix |
|---|---|
| `localhost` refused / “can't connect” | The server isn't running — start `start-all.bat`/`start-all.sh` and check the terminal for errors |
| Works on the PC but not on the phone | Different Wi-Fi, or firewall blocked port 8000 (see section 3) |
| Port already in use | Stop the other service, or run uvicorn/vite on another port |
| Page loads but projects/narration fail | Backend isn't running or a proxy blocked `/api`; in single-process mode (8000) UI and API share one origin |
| Voice missing | Run `backend/download-voices.bat` (Windows) or `./download-voices.sh` |
| Arena preview shows “Preview Unavailable” | Open the preview entry from inside the Arena chat; Arena previews aren't standalone public URLs |

## 7. What runs where — quick reference

```
Your browser (Chrome/Edge/Firefox/Safari, any device)
        │  http://host:8000  (relative /api calls, same origin)
        ▼
FastAPI + FFmpeg + Piper + SQLite  ──►  local data/ folder on the host machine
(localhost, LAN IP, Tailscale IP, or Cloudflare Tunnel — never a raw public port)
```
