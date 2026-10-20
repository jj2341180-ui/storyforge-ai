import { Clapperboard, FolderOpen, Film, PlayCircle, ShieldCheck, Cpu, Volume2, Clock, Smartphone, MonitorDown, Mic, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { ProjectSummary, ProviderStatus } from "../types";
import { Badge, Notice, Spinner, formatTime } from "./common";

export default function Home({
  onOpen,
  onNew,
}: {
  onOpen: (id: string) => void;
  onNew: (mode: "story" | "clip" | "shorts") => void;
}) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [status, setStatus] = useState<ProviderStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.listProjects(), api.providerStatus()])
      .then(([p, s]) => {
        setProjects(p);
        setStatus(s);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-full">
      {/* Hero */}
      <header className="relative overflow-hidden">
        <div className="max-w-6xl mx-auto px-5 pt-16 pb-12 text-center">
          <div className="inline-flex items-center gap-2 chip bg-ink-800 text-gold-300 border border-ink-600 mb-6">
            <ShieldCheck className="w-3.5 h-3.5" /> 100% local-first · no paid API required
          </div>
          <h1 className="font-display text-4xl md:text-6xl text-slate-50 leading-tight">
            Turn Your Stories Into <span className="text-gold-400">Cinematic YouTube Videos</span>
          </h1>
          <p className="mt-5 text-lg text-slate-400 max-w-2xl mx-auto">
            Write your story, build your scenes, add narration, and create your own video.
          </p>
          <div className="mt-9 flex flex-wrap justify-center gap-3">
            <button className="btn-primary text-base px-6 py-3" onClick={() => onNew("story")}>
              <Clapperboard className="w-5 h-5" /> Create a Story Video
            </button>
            <button className="btn-secondary text-base px-6 py-3" onClick={() => onNew("shorts")}>
              <Zap className="w-5 h-5" /> Create YouTube Short
            </button>
            <button className="btn-ghost text-base px-5 py-3 border border-ink-600" onClick={() => onNew("clip")}>
              <Film className="w-5 h-5" /> Generate a Video Clip
            </button>
            <button className="btn-ghost text-base px-5 py-3 border border-ink-600" onClick={() => onNew("story")}>
              <PlayCircle className="w-5 h-5" /> Continue a Project
            </button>
            <a className="btn-ghost text-base px-5 py-3 border border-ink-600" href="#my-videos">
              <FolderOpen className="w-5 h-5" /> Open My Videos
            </a>
            <a className="btn-secondary text-base px-6 py-3" href="/voice/" target="_blank" rel="noreferrer">
              <Mic className="w-5 h-5" /> VoiceForge — Free AI Voice Studio
            </a>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-5 pb-20 space-y-10">
        {/* Install to phone / browser */}
        <section className="card p-5 md:p-6">
          <h2 className="font-display text-xl text-slate-100 mb-4 flex items-center gap-2">
            <Smartphone className="w-5 h-5 text-gold-400" /> Install StoryForge like an app
          </h2>
          <div className="grid md:grid-cols-2 gap-4 text-sm text-slate-300">
            <div className="rounded-xl bg-ink-900 p-4 space-y-2">
              <p className="flex items-center gap-2 font-semibold text-slate-100">
                <MonitorDown className="w-4 h-4 text-gold-400" /> Computer browser (Chrome / Edge)
              </p>
              <ol className="list-decimal list-inside space-y-1 text-slate-400">
                <li>Open the StoryForge URL in Chrome or Edge.</li>
                <li>Click the install icon in the address bar, or menu ⋮ → <em>Cast, save and share → Install page as app…</em></li>
                <li>A StoryForge icon appears in your taskbar / Start menu.</li>
              </ol>
            </div>
            <div className="rounded-xl bg-ink-900 p-4 space-y-2">
              <p className="flex items-center gap-2 font-semibold text-slate-100">
                <Smartphone className="w-4 h-4 text-gold-400" /> Phone or tablet
              </p>
              <ul className="list-disc list-inside space-y-1 text-slate-400">
                <li><strong>Android / Chrome:</strong> open the URL → menu ⋮ → <em>Install app</em> or <em>Add to Home screen</em>.</li>
                <li><strong>iPhone / Safari:</strong> open the URL → Share icon → <em>Add to Home Screen</em> → Add.</li>
                <li>The server must be reachable from the device — same Wi-Fi (LAN IP) or a hosted URL / Tailscale. See ACCESS-GUIDE.md.</li>
              </ul>
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-3">
            This is a Progressive Web App: the icon opens full-screen without a browser toolbar. It is not a native
            App Store app — the rendering engine still runs on the host computer or server, which is what keeps it free.
          </p>
        </section>

        {/* Honest capability panel */}
        <section className="card p-5 md:p-6">
          <h2 className="font-display text-xl text-slate-100 mb-4 flex items-center gap-2">
            <Cpu className="w-5 h-5 text-gold-400" /> What this computer can do right now
          </h2>
          {loading || !status ? (
            <Spinner label="Checking local engines…" />
          ) : (
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-slate-400">CPU cores</span><span>{status.hardware.cpu_cores}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">System RAM</span><span>{status.hardware.ram_gb} GB</span></div>
                <div className="flex justify-between"><span className="text-slate-400">GPU</span>
                  <span>{status.hardware.gpu.name ? `${status.hardware.gpu.name} (${status.hardware.gpu.vram_gb} GB)` : "Not detected"}</span>
                </div>
                <div className="flex justify-between"><span className="text-slate-400">Free disk</span><span>{status.hardware.disk_free_gb} GB</span></div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  {status.any_configured ? <Badge tone="green">Model connected</Badge> : <Badge tone="amber">Providers selectable · setup needed</Badge>}
                  <span className="text-xs text-slate-400">text-to-video / image-to-video</span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone="green"><Volume2 className="w-3 h-3" /> Local narration ready</Badge>
                  <span className="text-xs text-slate-400">Piper TTS runs offline</span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone="green"><Clock className="w-3 h-3" /> MP4 export ready</Badge>
                  <span className="text-xs text-slate-400">FFmpeg H.264 / AAC</span>
                </div>
              </div>
            </div>
          )}
          {status && !status.hardware.can_run_local_video && (
            <div className="mt-4">
              <Notice tone="warn">
                <p>{status.hardware.note}</p>
                <p className="pt-1">{status.honest_alternative}</p>
              </Notice>
            </div>
          )}
          {status && (
            <div className="mt-4 space-y-2">
              <p className="text-xs text-slate-400">
                All three local adapters are <strong className="text-slate-200">always selectable</strong> in Generate a Video Clip,
                with target RAM plans from {Math.min(...status.ram_options_gb)} GB to {Math.max(...status.ram_options_gb)} GB.
              </p>
              {status.providers.map((p) => (
                <div key={p.id} className="flex flex-wrap items-center gap-2 text-sm border-t border-ink-700 pt-2">
                  {p.configured ? <Badge tone="green">Connected</Badge> : <Badge tone="amber">Setup needed · selectable</Badge>}
                  <span className="font-medium">{p.name}</span>
                  <span className="text-xs text-slate-500">· {p.cost}</span>
                  {!p.configured && <span className="text-xs text-slate-400 w-full md:w-auto">— {p.requires}</span>}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Projects */}
        <section id="my-videos">
          <h2 className="font-display text-2xl text-slate-100 mb-4">My Videos</h2>
          {loading ? (
            <Spinner label="Loading projects…" />
          ) : projects.length === 0 ? (
            <Notice tone="info">
              No projects yet. Start with <strong>Create a Story Video</strong> for the full story-to-MP4 workflow,
              or <strong>Generate a Video Clip</strong> for Mode A text-to-video.
            </Notice>
          ) : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((p) => (
                <button
                  key={p.id}
                  onClick={() => onOpen(p.id)}
                  className="card p-5 text-left hover:border-gold-500 transition group"
                >
                  <div className="flex items-center justify-between">
                    <Badge tone={p.mode === "clip" ? "blue" : "amber"}>
                      {p.mode === "clip" ? "Video Clip" : "Story Video"}
                    </Badge>
                    <span className="text-xs text-slate-500">{new Date(p.updated_at * 1000).toLocaleDateString()}</span>
                  </div>
                  <h3 className="mt-3 font-display text-lg text-slate-100 group-hover:text-gold-300">{p.name}</h3>
                  <p className="text-sm text-slate-400 mt-1">{p.scene_count} scenes · {p.exports.length} export(s)</p>
                  {p.exports[0] && (
                    <p className="text-xs text-emerald-400 mt-2">Last video: {formatTime(p.exports[0].duration)}</p>
                  )}
                </button>
              ))}
            </div>
          )}
        </section>

        <footer className="text-center text-xs text-slate-500 pt-6 border-t border-ink-800 space-y-1.5">
          <p>
            StoryForge AI uses original, locally generated content. Realistic synthetic scenes may require disclosure
            when uploaded to YouTube. No rankings, views, monetization or copyright clearance are guaranteed.
          </p>
          <p className="text-slate-600">StoryForge AI v1.8 · YouTube Shorts studio with AI narration, music &amp; sound effects · free forever</p>
        </footer>
      </main>
    </div>
  );
}
