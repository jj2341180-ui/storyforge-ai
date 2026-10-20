import { ArrowLeft, Cpu, Film, Image as ImageIcon, RefreshCw, Sparkles, Upload, Wand2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { Job, Project, ProviderInfo, ProviderStatus } from "../../types";
import { ASPECTS, RAM_OPTIONS_GB, RESOLUTIONS } from "../../constants";
import { flushProject } from "../../saving";
import { Badge, EmptyState, Notice, ProgressBar, Spinner } from "../common";

const CLIP_MIN_SECONDS = 2;
const CLIP_MAX_SECONDS = 30;

export default function ClipMode({
  project,
  update,
  notify,
  onHome,
}: {
  project: Project;
  update: (patch: Partial<Project>) => void;
  notify: (msg: string, tone?: "ok" | "err") => void;
  onHome: () => void;
}) {
  const [status, setStatus] = useState<ProviderStatus | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [blocked, setBlocked] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const timer = useRef<number | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const clip = project.clip;

  useEffect(() => {
    api.providerStatus().then(setStatus);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, []);

  const setClip = (patch: Partial<Project["clip"]>) => update({ clip: { ...clip, ...patch } });
  const configuredProviders = status?.providers.filter((p) => p.configured) ?? [];
  const selectedProvider: ProviderInfo | undefined =
    status?.providers.find((p) => p.id === clip.provider_id);
  const result = project.assets.find((a) => a.id === clip.result_asset_id) || null;
  const refAsset = project.assets.find((a) => a.id === clip.reference_asset_id) || null;

  const setDuration = (raw: number) => {
    if (Number.isNaN(raw)) return setClip({ duration: CLIP_MIN_SECONDS });
    setClip({ duration: Math.max(CLIP_MIN_SECONDS, Math.min(CLIP_MAX_SECONDS, Math.round(raw))) });
  };

  const uploadRefImage = async (file: File) => {
    setUploading(true);
    try {
      const asset = await api.uploadAsset(project.id, file, "image");
      update({ assets: [...project.assets, asset] });
      setClip({ reference_asset_id: asset.id });
      notify("Reference image attached (image-to-video)");
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setUploading(false);
    }
  };

  const generate = async () => {
    if (!clip.prompt.trim()) return notify("Enter a scene prompt first", "err");
    if (!clip.provider_id) return notify("Choose a provider first — every adapter is selectable, even before setup", "err");
    // Pre-flight: on the phone/free host none of the local adapters can run. Explain in plain
    // language with the free alternative instead of surfacing a raw server JSON error.
    if (selectedProvider && !selectedProvider.configured) {
      setBlocked(selectedProvider.id);
      return;
    }
    await flushProject(project.id);
    setBlocked(null);
    try {
      const j = await api.generate(project.id, {
        provider_id: clip.provider_id,
        prompt: clip.prompt,
        negative_prompt: clip.negative_prompt,
        duration: Math.max(CLIP_MIN_SECONDS, Math.min(CLIP_MAX_SECONDS, clip.duration || 5)),
        aspect: clip.aspect,
        resolution: clip.resolution,
        reference_asset_id: clip.reference_asset_id,
        target_ram_gb: clip.target_ram_gb ?? 32,
      });
      setJob(j);
      timer.current = window.setInterval(async () => {
        const fresh = await api.job(j.id);
        setJob(fresh);
        if (fresh.status === "done" || fresh.status === "failed") {
          if (timer.current) window.clearInterval(timer.current);
          if (fresh.status === "done") {
            const updated = await api.getProject(project.id);
            update(updated);
            notify("Local model finished generating");
          } else {
            notify(fresh.message || "Generation failed", "err");
          }
        }
      }, 2000);
    } catch (e) {
      setBlocked(clip.provider_id);
      notify((e as Error).message, "err");
    }
  };

  const running = job && ["queued", "running", "finalizing"].includes(job.status);

  return (
    <div className="space-y-6">
      <Notice tone="info">
        <strong>Mode A — Text-to-Video.</strong> This drives a real local video diffusion model through a pluggable
        provider adapter. StoryForge never sends prompts to a paid service and never labels a still image as a video clip.
      </Notice>

      {/* Hardware / providers */}
      <div className="card p-5 space-y-3">
        <h2 className="font-display text-xl text-slate-100 flex items-center gap-2">
          <Cpu className="w-5 h-5 text-gold-400" /> Local model status
        </h2>
        {!status ? (
          <Spinner label="Checking hardware and providers…" />
        ) : (
          <>
            <div className="flex flex-wrap gap-3 text-sm">
              <Badge tone={status.hardware.can_run_local_video ? "green" : "red"}>
                {status.hardware.gpu.name ? `GPU: ${status.hardware.gpu.name} (${status.hardware.gpu.vram_gb} GB VRAM)` : "No GPU detected"}
              </Badge>
              <Badge tone="neutral">{status.hardware.ram_gb} GB RAM</Badge>
              <Badge tone="neutral">{status.hardware.disk_free_gb} GB free disk</Badge>
            </div>
            <p className="text-sm text-slate-400">{status.hardware.note}</p>
            <p className="text-xs text-slate-400">
              Every adapter below is <strong className="text-slate-200">selectable</strong> in the Provider dropdown. A connected
              adapter runs immediately; selecting one that still needs setup returns its exact setup steps instead of a fake result.
            </p>
            <div className="space-y-2">
              {status.providers.map((p) => (
                <div key={p.id} className="rounded-xl bg-ink-900 p-3 text-sm">
                  <div className="flex items-center gap-2 flex-wrap">
                    {p.configured ? <Badge tone="green">Connected</Badge> : <Badge tone="amber">Setup needed · selectable</Badge>}
                    <span className="font-medium">{p.name}</span>
                    <span className="text-xs text-slate-500">· {p.cost}</span>
                  </div>
                  {!p.configured && <p className="text-xs text-slate-400 mt-1.5">{p.requires}</p>}
                </div>
              ))}
            </div>
            {!status.any_configured && (
              <Notice tone="warn">
                <p>{status.honest_alternative}</p>
                <p className="pt-1">
                  You can still pick any provider below to see its requirements. Setup instructions for ComfyUI / Automatic1111
                  adapters are in <strong>SETUP.md</strong>. The rest of StoryForge (script, narration, free AI scene images,
                  image-based MP4 export) works fully without a local video model.
                </p>
              </Notice>
            )}
          </>
        )}
      </div>

      {/* Prompt */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="card p-5 space-y-4">
          <h2 className="font-display text-xl text-slate-100 flex items-center gap-2">
            <Wand2 className="w-5 h-5 text-gold-400" /> Scene prompt
          </h2>
          <textarea
            className="input min-h-[150px]"
            placeholder="Generate a cinematic fantasy scene of a young woman standing in a ruined dragon kingdom at night…"
            value={clip.prompt}
            onChange={(e) => setClip({ prompt: e.target.value })}
          />
          <div>
            <label className="label">Negative prompt (optional)</label>
            <textarea className="input min-h-[70px]" placeholder="blurry, distorted faces, watermark, text, low quality…"
              value={clip.negative_prompt} onChange={(e) => setClip({ negative_prompt: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Provider (all adapters selectable)</label>
              <select className="input" value={clip.provider_id || ""}
                onChange={(e) => { setClip({ provider_id: e.target.value || null }); setBlocked(null); }}>
                <option value="">— choose a provider —</option>
                {status?.providers.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}{p.configured ? " · connected" : " · setup needed"}</option>
                ))}
              </select>
              {selectedProvider && !selectedProvider.configured && (
                <p className="text-xs text-amber-300/90 mt-1.5">
                  Not connected — {selectedProvider.requires}
                </p>
              )}
            </div>
            <div>
              <label className="label">Duration (seconds, 2–30)</label>
              <input type="number" min={CLIP_MIN_SECONDS} max={CLIP_MAX_SECONDS} className="input"
                value={Math.max(CLIP_MIN_SECONDS, Math.min(CLIP_MAX_SECONDS, clip.duration || 5))}
                onChange={(e) => setDuration(Number(e.target.value))} />
            </div>
            <div>
              <label className="label">Target system RAM (planning)</label>
              <select className="input" value={clip.target_ram_gb ?? 32}
                onChange={(e) => setClip({ target_ram_gb: Number(e.target.value) })}>
                {(status?.ram_options_gb ?? RAM_OPTIONS_GB).map((gb) => (
                  <option key={gb} value={gb}>{gb} GB</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Aspect ratio</label>
              <select className="input" value={clip.aspect} onChange={(e) => setClip({ aspect: e.target.value })}>
                {ASPECTS.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Resolution / quality</label>
              <select className="input" value={clip.resolution} onChange={(e) => setClip({ resolution: e.target.value })}>
                {RESOLUTIONS.map((r) => <option key={r}>{r}</option>)}
              </select>
            </div>
          </div>

          <div className="rounded-xl bg-ink-900 p-3">
            <label className="label">Reference image (image-to-video, where supported)</label>
            <div className="flex items-center gap-3">
              {refAsset ? (
                <img src={api.mediaUrl(refAsset.path)} className="w-20 h-12 object-cover rounded-lg" alt="reference" />
              ) : (
                <div className="w-20 h-12 grid place-items-center bg-ink-800 rounded-lg text-slate-600"><ImageIcon className="w-5 h-5" /></div>
              )}
              <select className="input text-xs py-2 flex-1" value={clip.reference_asset_id || ""}
                onChange={(e) => setClip({ reference_asset_id: e.target.value || null })}>
                <option value="">Choose library image…</option>
                {project.assets.filter((a) => a.kind === "image").map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
              <button className="btn-secondary text-xs px-3 py-2" onClick={() => uploadRef.current?.click()} disabled={uploading}>
                {uploading ? <Spinner /> : <Upload className="w-3.5 h-3.5" />}
              </button>
              <input ref={uploadRef} type="file" accept="image/*" className="hidden"
                onChange={(e) => e.target.files?.[0] && uploadRefImage(e.target.files[0])} />
            </div>
          </div>

          <button className="btn-primary w-full" onClick={generate} disabled={Boolean(running)}>
            {running ? <Spinner label="Generating with local model…" /> : <><Sparkles className="w-4 h-4" /> Generate clip</>}
          </button>
          {job && (
            <div className="space-y-2">
              <ProgressBar value={job.progress} message={job.message} />
              {job.status === "failed" && (
                <div className="rounded-xl bg-red-950/50 border border-red-900 p-3 text-sm text-red-200 whitespace-pre-wrap">{job.message}</div>
              )}
            </div>
          )}
          {blocked && selectedProvider && (
            <div className="rounded-xl bg-amber-950/40 border border-amber-900 p-4 text-sm space-y-3">
              <div className="flex items-start justify-between gap-3">
                <p className="font-semibold text-amber-200">
                  “{selectedProvider.name}” needs your own computer with a GPU
                </p>
                <button onClick={() => setBlocked(null)} aria-label="Dismiss" className="shrink-0 text-amber-300/70 hover:text-amber-200">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <p className="text-amber-100/80">
                This provider is a local video model (8–24 GB NVIDIA VRAM recommended). It cannot run on a phone or on
                the free server, so no moving clip can be generated from here without that hardware.
              </p>
              <p className="text-amber-100/80">{selectedProvider.requires}</p>
              <div className="rounded-lg bg-ink-900/70 p-3 text-slate-300">
                <p className="font-medium text-slate-100 mb-1">Free option that works on this phone:</p>
                <p>
                  Story Video mode turns free AI scene images into a complete MP4 with Ken Burns motion, transitions,
                  narration and captions — no GPU or paid service. Go back to the home screen and choose
                  “Create a Story Video”.
                </p>
              </div>
              <button className="btn-secondary w-full" onClick={onHome}>
                <ArrowLeft className="w-4 h-4" /> Back to Home — use Story Video mode
              </button>
            </div>
          )}
        </div>

        {/* Result */}
        <div className="card p-5 space-y-3">
          <h2 className="font-display text-xl text-slate-100 flex items-center gap-2">
            <Film className="w-5 h-5 text-gold-400" /> Result preview
          </h2>
          {!result ? (
            <EmptyState icon={<Film className="w-6 h-6" />} title="No clip generated yet"
              hint="Pick any provider above. Connected adapters produce moving video here; adapters still needing setup return their setup steps. In Story Video mode you can also generate free AI scene images without any local model." />
          ) : (
            <div className="space-y-3">
              {result.kind === "video" ? (
                <video controls src={api.mediaUrl(result.path)} className="w-full rounded-xl bg-black" />
              ) : (
                <>
                  <img src={api.mediaUrl(result.path)} className="w-full rounded-xl" alt="generated still" />
                  <Notice tone="warn">This is a generated <strong>still image</strong>, not a video clip — use Mode B's image-based motion workflow to animate it.</Notice>
                </>
              )}
              <p className="text-xs text-slate-400">Saved to this project · source: {result.source}</p>
              <button className="btn-secondary w-full" onClick={generate} disabled={Boolean(running)}>
                <RefreshCw className="w-4 h-4" /> Regenerate / edit prompt
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
