import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  Sparkles,
  Square,
  Volume2,
  Wand2,
} from "lucide-react";
import { api, type ShortsOptions, type ShortsRequestBody } from "../../api";
import type { Job, Project } from "../../types";
import { Toast, useToast } from "../common";

type ShortResult = {
  file: string;
  srt?: string;
  title?: string;
  duration?: number;
  width?: number;
  height?: number;
  aspect?: string;
  resolution?: string;
  video_engines?: string[];
  real_video_used?: boolean;
  narration_engines?: string[];
  voice?: string;
  sfx_presets?: string[];
  music_mood?: string | null;
  kind?: string;
};

const IDEA_EXAMPLES = [
  "A 30-second fantasy story about a girl who discovers a baby dragon in an enchanted forest",
  "A detective cat solves a midnight bakery heist in a rainy city",
  "A lonely robot finds a glowing flower on an abandoned space station",
];

function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!on)}
      className={`flex items-center justify-between w-full rounded-xl border px-3.5 py-3 text-sm font-medium transition ${
        on ? "border-gold-500/60 bg-gold-400/10 text-slate-100" : "border-ink-700 bg-ink-900 text-slate-400"
      }`}
      aria-pressed={on}
    >
      <span>{label}</span>
      <span
        className={`ml-3 inline-flex h-6 w-11 shrink-0 items-center rounded-full px-0.5 transition ${
          on ? "bg-gold-400 justify-end" : "bg-ink-700 justify-start"
        }`}
      >
        <span className="h-5 w-5 rounded-full bg-white shadow" />
      </span>
    </button>
  );
}

function VolumeRow({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-slate-400 mb-1">
        <span className="flex items-center gap-1.5"><Volume2 className="w-3.5 h-3.5" />{label}</span>
        <span className="text-slate-200 font-semibold">{Math.round(value * 100)}%</span>
      </div>
      <input
        type="range" min={0} max={1.5} step={0.05} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-gold-400"
      />
    </div>
  );
}

export default function ShortsStudio({ project, update, onHome }: {
  project: Project;
  update: (patch: Partial<Project>) => void;
  onHome: () => void;
}) {
  const { toast, show } = useToast();
  const [options, setOptions] = useState<ShortsOptions | null>(null);
  const [idea, setIdea] = useState("");
  const [seconds, setSeconds] = useState(30);
  const [aspect, setAspect] = useState("9:16");
  const [resolution, setResolution] = useState("480p");
  const [narrationOn, setNarrationOn] = useState(true);
  const [voicePreset, setVoicePreset] = useState("female_narrator");
  const [rate, setRate] = useState(0);
  const [musicOn, setMusicOn] = useState(true);
  const [sfxOn, setSfxOn] = useState(true);
  const [captionsOn, setCaptionsOn] = useState(true);
  const [fontSize, setFontSize] = useState(18);
  const [captionPos, setCaptionPos] = useState<"bottom" | "top" | "middle">("bottom");
  const [narrationVol, setNarrationVol] = useState(1.0);
  const [musicVol, setMusicVol] = useState(0.5);
  const [sfxVol, setSfxVol] = useState(0.7);
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<ShortResult | null>(null);
  const [error, setError] = useState("");
  const stopPoll = useRef<(() => void) | null>(null);

  useEffect(() => {
    api.shortsOptions().then(setOptions).catch((e) => setError(e.message));
    return () => stopPoll.current?.();
  }, []);

  const busy = job !== null && job.status !== "done" && job.status !== "failed";
  const pct = Math.round((job?.progress ?? 0) * 100);

  const start = async () => {
    setError("");
    setResult(null);
    if (!idea.trim()) {
      setError("Enter an idea first — for example: a girl discovers a baby dragon.");
      return;
    }
    const body: ShortsRequestBody = {
      idea: idea.trim(),
      seconds,
      aspect,
      resolution,
      narration: { enabled: narrationOn, voice_preset: voicePreset, rate },
      audio: {
        music_enabled: musicOn,
        sfx_enabled: sfxOn,
        narration_volume: narrationVol,
        music_volume: musicVol,
        sfx_volume: sfxVol,
      },
      captions: { enabled: captionsOn, font_size: fontSize, position: captionPos },
      reference_asset_id: null,
      engine: "auto",
    };
    try {
      const { project_id, job_id } = await api.createShort(body);
      if (project_id !== project.id) {
        show("A new Shorts project was created.");
      }
      const poll = async () => {
        try {
          const j = await api.job(job_id);
          setJob(j);
          if (j.status === "done") {
            const r = (j.result ?? null) as ShortResult | null;
            setResult(r);
            show("Your Short is ready — preview it below.");
            return;
          }
          if (j.status === "failed") {
            setError(j.message || "Generation failed. Please try again.");
            return;
          }
          stopPoll.current = setTimeout(poll, 2000) as unknown as () => void;
        } catch (e) {
          setError(e instanceof Error ? e.message : "Lost connection to the task.");
        }
      };
      poll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start generation.");
    }
  };

  const cancel = async () => {
    if (!job) return;
    try {
      await api.cancelShort(job.id);
      show("Cancelling…");
    } catch {
      /* status will settle on next poll */
    }
  };

  const priorExports = (project.exports || []).filter((e) => (e as ShortResult).kind === "shorts" || Boolean((e as ShortResult).video_engines));

  return (
    <div className="space-y-6">
      <Toast toast={toast} />

      <div className="card p-5 space-y-4">
        <h2 className="font-display text-xl text-slate-100 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-gold-400" /> YouTube Shorts generator
        </h2>
        <p className="text-sm text-slate-400">
          One idea becomes a complete vertical video: story, moving scenes, narrated voice-over, sound effects,
          background music, captions and an MP4 — fully free.
        </p>

        {options && !options.local_video_configured && (
          <div className="rounded-xl border border-amber-700/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-200 space-y-1">
            <div className="flex items-center gap-2 font-semibold">
              <AlertTriangle className="w-4 h-4" /> How the free server makes motion
            </div>
            <p>
              This server has no GPU, so Shorts use free AI-generated images with cinematic camera motion,
              labeled <strong>image-motion</strong> in every export. True character-movement diffusion models
              (LTX-Video, Wan, SVD — free, open weights) need an NVIDIA GPU (8–24 GB VRAM) on your own computer;
              connect ComfyUI and the same button renders real diffusion video instead. No paid service is involved either way.
            </p>
          </div>
        )}
        {options?.local_video_configured && (
          <div className="rounded-xl border border-emerald-700/50 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-200 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" /> Local video model connected — scenes render with real AI-generated movement.
          </div>
        )}
      </div>

      <div className="card p-5 space-y-4">
        <label className="label" htmlFor="short-idea">Your idea</label>
        <textarea
          id="short-idea"
          className="input min-h-[110px]"
          maxLength={500}
          placeholder={IDEA_EXAMPLES[0]}
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          {IDEA_EXAMPLES.map((ex) => (
            <button key={ex} type="button" className="chip bg-ink-800 border border-ink-700 text-slate-300 hover:border-gold-500/60"
              onClick={() => setIdea(ex)}>
              {ex.slice(0, 42)}…
            </button>
          ))}
        </div>

        <div className="grid sm:grid-cols-3 gap-4">
          <div>
            <label className="label">Duration</label>
            <div className="grid grid-cols-4 gap-2">
              {[15, 30, 45, 60].map((s) => (
                <button key={s} type="button" onClick={() => setSeconds(s)}
                  className={`rounded-lg py-2 text-sm font-semibold border ${
                    seconds === s ? "bg-gold-400 text-ink-950 border-gold-400" : "bg-ink-900 text-slate-300 border-ink-700"
                  }`}>
                  {s}s
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="label">Aspect ratio</label>
            <select className="input" value={aspect} onChange={(e) => setAspect(e.target.value)}>
              <option value="9:16">9:16 vertical (Shorts)</option>
              <option value="16:9">16:9 landscape</option>
              <option value="1:1">1:1 square</option>
            </select>
          </div>
          <div>
            <label className="label">Resolution</label>
            <select className="input" value={resolution} onChange={(e) => setResolution(e.target.value)}>
              <option value="360p">360p — fastest</option>
              <option value="480p">480p — balanced</option>
              <option value="720p">720p — sharper, slower</option>
            </select>
          </div>
        </div>
      </div>

      <div className="card p-5 space-y-4">
        <h3 className="font-display text-lg text-slate-100">Narration, music &amp; sound</h3>
        <div className="grid sm:grid-cols-2 gap-3">
          <Toggle on={narrationOn} onChange={setNarrationOn} label="AI narration (on by default)" />
          <Toggle on={musicOn} onChange={setMusicOn} label="Background music" />
          <Toggle on={sfxOn} onChange={setSfxOn} label="Scene sound effects" />
          <Toggle on={captionsOn} onChange={setCaptionsOn} label="Burned-in subtitles" />
        </div>

        {narrationOn && (
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Narrator voice</label>
              <select className="input" value={voicePreset} onChange={(e) => setVoicePreset(e.target.value)}>
                {(options?.voice_presets ?? []).map((v) => (
                  <option key={v.id} value={v.id}>{v.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Speaking speed: {rate === 0 ? "normal" : `${rate > 0 ? "+" : ""}${rate}%`}</label>
              <input type="range" min={-50} max={100} step={5} value={rate}
                onChange={(e) => setRate(Number(e.target.value))} className="w-full accent-gold-400 mt-3" />
            </div>
          </div>
        )}

        <div className="grid sm:grid-cols-3 gap-4">
          <VolumeRow label="Narration volume" value={narrationVol} onChange={setNarrationVol} />
          <VolumeRow label="Music volume" value={musicVol} onChange={setMusicVol} />
          <VolumeRow label="Sound effects volume" value={sfxVol} onChange={setSfxVol} />
        </div>
        <p className="text-xs text-slate-500">
          Music automatically ducks under narration, every track fades in and out, and a limiter prevents clipping.
        </p>

        {captionsOn && (
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Caption font size: {fontSize}</label>
              <input type="range" min={10} max={36} step={1} value={fontSize}
                onChange={(e) => setFontSize(Number(e.target.value))} className="w-full accent-gold-400" />
            </div>
            <div>
              <label className="label">Caption position</label>
              <select className="input" value={captionPos} onChange={(e) => setCaptionPos(e.target.value as typeof captionPos)}>
                <option value="bottom">Bottom</option>
                <option value="middle">Middle</option>
                <option value="top">Top</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/60 bg-red-950/30 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <div className="flex gap-3">
        <button className="btn-primary flex-1 py-3.5 text-base" onClick={start} disabled={busy}>
          {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Wand2 className="w-5 h-5" />}
          {busy ? "Generating…" : "Create my Short"}
        </button>
        {busy && (
          <button className="btn-secondary px-5" onClick={cancel}>
            <Square className="w-4 h-4" /> Cancel
          </button>
        )}
      </div>

      {busy && (
        <div className="card p-5 space-y-3">
          <div className="h-2.5 rounded-full bg-ink-900 overflow-hidden">
            <div className="h-full bg-gold-400 transition-all duration-500" style={{ width: `${Math.max(3, pct)}%` }} />
          </div>
          <p className="text-sm text-slate-300">{job?.message || "Starting…"} ({pct}%)</p>
          <p className="text-xs text-slate-500">
            Free image generation is rate-limited per server, so a full run can take several minutes. Leave this tab open.
          </p>
        </div>
      )}

      {job?.status === "done" && result && (
        <div className="card p-5 space-y-4">
          <h3 className="font-display text-lg text-slate-100 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-400" /> {result.title || "Your Short is ready"}
          </h3>
          <video
            className="w-full max-h-[70vh] rounded-xl bg-black"
            controls
            preload="metadata"
            src={api.mediaUrl(result.file)}
          />
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="chip bg-ink-800 border border-ink-700 text-slate-300">
              {result.width}×{result.height} · {result.aspect} · {result.resolution} · {result.duration}s
            </span>
            {(result.video_engines ?? []).every((e) => e.includes("image-motion")) ? (
              <span className="chip bg-amber-950 border border-amber-800 text-amber-200">image-motion (free, no GPU)</span>
            ) : (
              <span className="chip bg-emerald-950 border border-emerald-800 text-emerald-200">real AI video model</span>
            )}
            {result.voice && <span className="chip bg-ink-800 border border-ink-700 text-slate-300">voice: {result.voice}</span>}
            {result.music_mood && <span className="chip bg-ink-800 border border-ink-700 text-slate-300">music: {result.music_mood}</span>}
            {result.sfx_presets && <span className="chip bg-ink-800 border border-ink-700 text-slate-300">sfx: {[...new Set(result.sfx_presets)].join(", ")}</span>}
          </div>
          <div className="flex flex-wrap gap-3">
            <a className="btn-primary" href={api.exportDownloadUrl(project.id, result.file)}>
              <Download className="w-4 h-4" /> Download MP4
            </a>
            {result.srt && (
              <a className="btn-secondary" href={api.srtUrl(project.id, result.srt)}>
                <FileText className="w-4 h-4" /> Download subtitles (.srt)
              </a>
            )}
            <button className="btn-ghost" onClick={onHome}>Back to Home</button>
          </div>
        </div>
      )}

      {priorExports.length > 0 && !busy && (
        <div className="card p-5 space-y-3">
          <h3 className="font-display text-lg text-slate-100">Earlier Shorts in this project</h3>
          {priorExports.map((e) => (
            <div key={e.job_id} className="rounded-xl bg-ink-900 border border-ink-700 p-3 flex flex-wrap items-center gap-3">
              <video className="h-20 rounded-lg bg-black" preload="metadata" src={api.mediaUrl(e.file)} />
              <div className="text-sm text-slate-300 flex-1 min-w-[160px]">
                <div>{e.duration}s · {e.aspect} · {e.resolution}</div>
                {(e as ShortResult).real_video_used ? (
                  <div className="text-xs text-emerald-300">real AI video model</div>
                ) : (
                  <div className="text-xs text-amber-300">image-motion (free, no GPU)</div>
                )}
              </div>
              <a className="btn-secondary py-2" href={api.exportDownloadUrl(project.id, e.file)}>
                <Download className="w-4 h-4" /> MP4
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
