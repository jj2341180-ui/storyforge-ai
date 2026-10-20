import { Image as ImageIcon, Images, Mic, Upload, Play, Loader2, LayoutGrid, Wand2, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { Asset, Job, Project, Scene, Voice } from "../../types";
import { MOTIONS, TRANSITIONS } from "../../constants";
import { flushProject } from "../../saving";
import { Badge, EmptyState, Notice, ProgressBar, Spinner } from "../common";

export default function Storyboard({
  project,
  update,
  notify,
}: {
  project: Project;
  update: (patch: Partial<Project>) => void;
  notify: (msg: string, tone?: "ok" | "err") => void;
}) {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [busyScene, setBusyScene] = useState<string | null>(null);
  const [batch, setBatch] = useState(false);
  const [aiBusy, setAiBusy] = useState<string | null>(null);
  const [batchJob, setBatchJob] = useState<Job | null>(null);
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const batchTimer = useRef<number | null>(null);

  useEffect(() => {
    api.voices().then((r) => setVoices(r.voices)).catch(() => setVoices([]));
    return () => { if (batchTimer.current) window.clearInterval(batchTimer.current); };
  }, []);

  const assetsById = new Map(project.assets.map((a) => [a.id, a]));
  const scenes = project.scenes;

  const patchScene = (id: string, patch: Partial<Scene>) =>
    update({ scenes: scenes.map((s) => (s.id === id ? { ...s, ...patch } : s)) });

  const refresh = async () => update(await api.getProject(project.id));

  const makePlaceholder = async (sceneId: string) => {
    await flushProject(project.id);
    setBusyScene(`img-${sceneId}`);
    try {
      await api.placeholder(project.id, sceneId);
      await refresh();
      notify("Placeholder frame created");
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setBusyScene(null);
    }
  };

  const uploadImage = async (sceneId: string, file: File) => {
    setBusyScene(`img-${sceneId}`);
    try {
      const asset = await api.uploadAsset(project.id, file, "image");
      patchScene(sceneId, { image_asset_id: asset.id });
      notify("Image attached to scene");
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setBusyScene(null);
    }
  };

  const uploadAudio = async (sceneId: string, file: File) => {
    setBusyScene(`aud-${sceneId}`);
    try {
      const asset = await api.uploadAsset(project.id, file, "audio");
      patchScene(sceneId, { audio_asset_id: asset.id });
      notify("Narration audio attached");
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setBusyScene(null);
    }
  };

  const narrate = async (scene: Scene, kind: "narration" | "dialogue") => {
    await flushProject(project.id);
    const voiceId = kind === "narration" ? project.narration_voice : project.dialogue_voice;
    if (!voiceId) return notify("Choose a voice in the narration bar first", "err");
    const text = kind === "narration" ? scene.narration : scene.dialogue || "";
    if (!text.trim()) return notify("This scene has no text to narrate", "err");
    setBusyScene(`tts-${kind}-${scene.id}`);
    try {
      const r = await api.synthesize(project.id, scene.id, text, voiceId, project.speech_speed, kind);
      await refresh();
      notify(`${kind} generated (${r.duration.toFixed(1)}s, fully local)`);
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setBusyScene(null);
    }
  };

  const allPlaceholders = async () => {
    await flushProject(project.id);
    setBatch(true);
    try {
      for (const sc of scenes) {
        if (!sc.image_asset_id) await api.placeholder(project.id, sc.id);
      }
      await refresh();
      notify("All scenes now have frames");
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setBatch(false);
    }
  };

  const allNarration = async () => {
    if (!project.narration_voice) return notify("Choose a narration voice first", "err");
    await flushProject(project.id);
    setBatch(true);
    try {
      for (const sc of scenes) {
        if (sc.narration.trim()) {
          await api.synthesize(project.id, sc.id, sc.narration, project.narration_voice, project.speech_speed, "narration");
        }
      }
      await refresh();
      notify("All narration generated locally");
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setBatch(false);
    }
  };

  // Free keyless AI image for one scene (Pollinations). The scene's visual prompt is used
  // automatically, and the resulting picture is attached to the scene immediately.
  const generateAiImage = async (scene: Scene) => {
    await flushProject(project.id);
    setAiBusy(scene.id);
    try {
      await api.generateImage(project.id, {
        scene_id: scene.id,
        prompt: scene.visual_prompt || scene.heading,
        aspect: project.timeline.aspect,
        resolution: project.timeline.resolution,
      });
      await refresh();
      notify("AI image generated and attached to the scene");
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setAiBusy(null);
    }
  };

  // One button -> an original AI picture for every scene that does not have one yet.
  const generateAllAiImages = async () => {
    await flushProject(project.id);
    try {
      const job = await api.generateImagesBatch(project.id, {
        only_missing: true,
        aspect: project.timeline.aspect,
        resolution: project.timeline.resolution,
      });
      setBatchJob(job);
      batchTimer.current = window.setInterval(async () => {
        const fresh = await api.job(job.id);
        setBatchJob(fresh);
        if (fresh.status === "done" || fresh.status === "failed") {
          if (batchTimer.current) window.clearInterval(batchTimer.current);
          await refresh();
          notify(fresh.message, fresh.status === "failed" ? "err" : "ok");
        }
      }, 2000);
    } catch (e) {
      notify((e as Error).message, "err");
    }
  };

  const batchRunning = Boolean(batchJob && ["queued", "running", "finalizing"].includes(batchJob.status));
  const missingImages = scenes.filter((s) => !s.image_asset_id).length;

  if (!scenes.length) {
    return <EmptyState icon={<LayoutGrid className="w-6 h-6" />} title="Storyboard is empty" hint="Approve a script in the Story Studio first." />;
  }

  return (
    <div className="space-y-5">
      {/* Free AI image generation */}
      <div className="card p-4 md:p-5 space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[220px]">
            <h2 className="font-display text-lg text-slate-100 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-gold-400" /> AI scene images (free · no API key)
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Turns each scene's description into an original <strong className="text-slate-200">HD 1080p</strong> picture
              with the free Pollinations image model (upscaled and sharpened for video), then attaches it automatically.
              The keyless free tier allows about one image every 45 seconds, so a 5-scene batch takes roughly 4 minutes —
              progress and any quota wait are shown below. You can still replace any frame with an upload or a placeholder.
            </p>
          </div>
          <button className="btn-primary" disabled={batchRunning || Boolean(aiBusy) || missingImages === 0}
            onClick={generateAllAiImages}>
            {batchRunning ? (
              <Spinner label={batchJob?.message || "Generating…"} />
            ) : (
              <><Images className="w-4 h-4" /> Generate AI images for all scenes</>
            )}
          </button>
        </div>
        {missingImages === 0 && (
          <p className="text-xs text-emerald-400">Every scene already has an image — use a scene's AI image button to regenerate one.</p>
        )}
        {batchJob && (
          <ProgressBar value={batchJob.progress} message={batchJob.message} />
        )}
      </div>

      {/* Narration bar */}
      <div className="card p-4 flex flex-wrap items-end gap-4">
        <div className="min-w-[200px] flex-1">
          <label className="label">Narration voice</label>
          <select className="input" value={project.narration_voice || ""}
            onChange={(e) => update({ narration_voice: e.target.value || null })}>
            <option value="">— select voice —</option>
            {voices.map((v) => <option key={v.id} value={v.id}>{v.label} · {v.gender}</option>)}
          </select>
        </div>
        <div className="min-w-[200px] flex-1">
          <label className="label">Dialogue voice (separate track)</label>
          <select className="input" value={project.dialogue_voice || ""}
            onChange={(e) => update({ dialogue_voice: e.target.value || null })}>
            <option value="">— select voice —</option>
            {voices.map((v) => <option key={v.id} value={v.id}>{v.label} · {v.gender}</option>)}
          </select>
        </div>
        <div className="w-40">
          <label className="label">Speed ({project.speech_speed.toFixed(2)}x)</label>
          <input type="range" min={0.7} max={1.6} step={0.05} className="w-full"
            value={project.speech_speed}
            onChange={(e) => update({ speech_speed: Number(e.target.value) })} />
        </div>
        <button className="btn-secondary" disabled={batch} onClick={allPlaceholders}>
          {batch ? <Spinner /> : <Wand2 className="w-4 h-4" />} All placeholders
        </button>
        <button className="btn-primary" disabled={batch} onClick={allNarration}>
          {batch ? <Spinner /> : <Mic className="w-4 h-4" />} Narrate all scenes
        </button>
      </div>

      {voices.length === 0 && (
        <Notice tone="warn">
          No local Piper voice installed. You can still upload recorded narration (MP3/WAV) per scene.
          See SETUP.md for adding free offline voices.
        </Notice>
      )}

      <div className="grid md:grid-cols-2 gap-5">
        {scenes.map((sc, i) => {
          const img = sc.image_asset_id ? assetsById.get(sc.image_asset_id) : undefined;
          const audio = sc.audio_asset_id ? assetsById.get(sc.audio_asset_id) : undefined;
          const isPlaceholder = img?.source.includes("placeholder");
          return (
            <div key={sc.id} className="card overflow-hidden">
              <div className="relative aspect-video bg-ink-900">
                {img ? (
                  <img src={api.mediaUrl(img.path)} alt={sc.heading} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full grid place-items-center text-slate-600">
                    <ImageIcon className="w-10 h-10" />
                  </div>
                )}
                <div className="absolute top-2 left-2 flex gap-2">
                  <Badge tone="blue">Scene {i + 1}</Badge>
                  {isPlaceholder && <Badge tone="amber">Placeholder</Badge>}
                </div>
                {busyScene === `img-${sc.id}` && (
                  <div className="absolute inset-0 grid place-items-center bg-black/50"><Spinner /></div>
                )}
              </div>

              <div className="p-4 space-y-3">
                <input className="input font-semibold text-sm" value={sc.heading}
                  onChange={(e) => patchScene(sc.id, { heading: e.target.value })} />
                <p className="text-xs text-slate-400 line-clamp-3">{sc.narration}</p>

                <div className="flex flex-wrap gap-2">
                  <button className="btn-primary text-xs px-3 py-2" disabled={Boolean(aiBusy) || batchRunning}
                    onClick={() => generateAiImage(sc)}>
                    {aiBusy === sc.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    AI image
                  </button>
                  <button className="btn-secondary text-xs px-3 py-2" onClick={() => makePlaceholder(sc.id)}>
                    <Wand2 className="w-3.5 h-3.5" /> Placeholder
                  </button>
                  <button className="btn-secondary text-xs px-3 py-2" onClick={() => fileRefs.current[sc.id]?.click()}>
                    <Upload className="w-3.5 h-3.5" /> Upload image
                  </button>
                  <input
                    ref={(el) => { fileRefs.current[sc.id] = el; }}
                    type="file" accept="image/*" className="hidden"
                    onChange={(e) => e.target.files?.[0] && uploadImage(sc.id, e.target.files[0])}
                  />
                  <select className="input text-xs py-2 flex-1 min-w-[140px]" value={sc.image_asset_id || ""}
                    onChange={(e) => patchScene(sc.id, { image_asset_id: e.target.value || null })}>
                    <option value="">Use library image…</option>
                    {project.assets.filter((a) => a.kind === "image").map((a: Asset) => (
                      <option key={a.id} value={a.id}>{a.name.slice(0, 48)}</option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="label">Seconds</label>
                    <input type="number" min={2} max={120} className="input py-2 text-xs"
                      value={sc.duration || 5}
                      onChange={(e) => patchScene(sc.id, { duration: Number(e.target.value) })} />
                  </div>
                  <div>
                    <label className="label">Motion</label>
                    <select className="input py-2 text-xs" value={sc.motion || "zoom_in"}
                      onChange={(e) => patchScene(sc.id, { motion: e.target.value })}>
                      {MOTIONS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="label">Transition</label>
                    <select className="input py-2 text-xs" value={sc.transition || "fade"}
                      onChange={(e) => patchScene(sc.id, { transition: e.target.value })}>
                      {TRANSITIONS.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                </div>

                <div className="rounded-xl bg-ink-900 p-3 space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Mic className="w-4 h-4 text-gold-400" />
                    <span className="text-xs font-semibold text-slate-300">Local narration (Piper)</span>
                    <button className="btn-ghost text-xs px-2 py-1 ml-auto" disabled={busyScene?.startsWith(`tts-narration-${sc.id}`)}
                      onClick={() => narrate(sc, "narration")}>
                      {busyScene === `tts-narration-${sc.id}` ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Generate"}
                    </button>
                    <label className="btn-ghost text-xs px-2 py-1 cursor-pointer">
                      <Upload className="w-3.5 h-3.5" /> Recorded
                      <input type="file" accept="audio/*" className="hidden"
                        onChange={(e) => e.target.files?.[0] && uploadAudio(sc.id, e.target.files[0])} />
                    </label>
                  </div>
                  {audio && (
                    <div className="flex items-center gap-2">
                      <audio controls src={api.mediaUrl(audio.path)} className="w-full h-8" />
                    </div>
                  )}
                  {sc.dialogue && (
                    <button className="text-xs text-gold-300 hover:underline flex items-center gap-1"
                      onClick={() => narrate(sc, "dialogue")}>
                      <Play className="w-3 h-3" /> Generate separate dialogue track
                    </button>
                  )}
                  {busyScene === `aud-${sc.id}` && <Spinner label="Uploading…" />}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
