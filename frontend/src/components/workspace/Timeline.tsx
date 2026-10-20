import { ArrowDown, ArrowUp, ChevronRight, Clapperboard, GripVertical } from "lucide-react";
import { api } from "../../api";
import type { Project } from "../../types";
import { ASPECTS, RESOLUTIONS, TRANSITIONS, WATERMARK_POSITIONS } from "../../constants";
import { Badge, EmptyState, Notice } from "../common";

export default function Timeline({
  project,
  update,
  go,
}: {
  project: Project;
  update: (patch: Partial<Project>) => void;
  go: (tab: string) => void;
  notify: (msg: string, tone?: "ok" | "err") => void;
}) {
  const tl = project.timeline;
  const setTl = (patch: Partial<Project["timeline"]>) => update({ timeline: { ...tl, ...patch } });
  const assetsById = new Map(project.assets.map((a) => [a.id, a]));

  const move = (i: number, dir: -1 | 1) => {
    const scenes = [...project.scenes];
    const j = i + dir;
    if (j < 0 || j >= scenes.length) return;
    [scenes[i], scenes[j]] = [scenes[j], scenes[i]];
    update({ scenes });
  };

  const setSceneImage = (sceneId: string, assetId: string) =>
    update({ scenes: project.scenes.map((s) => (s.id === sceneId ? { ...s, image_asset_id: assetId || null } : s)) });

  if (!project.scenes.length) {
    return <EmptyState icon={<GripVertical className="w-6 h-6" />} title="Timeline is empty" hint="Approve a script first." />;
  }

  return (
    <div className="space-y-6">
      {/* Global render settings */}
      <div className="card p-5 space-y-4">
        <h2 className="font-display text-xl text-slate-100 flex items-center gap-2">
          <Clapperboard className="w-5 h-5 text-gold-400" /> Export format & timeline settings
        </h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="label">Aspect preset</label>
            <select className="input" value={tl.aspect} onChange={(e) => setTl({ aspect: e.target.value as Project["timeline"]["aspect"] })}>
              {ASPECTS.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Resolution</label>
            <select className="input" value={tl.resolution} onChange={(e) => setTl({ resolution: e.target.value as "720p" | "1080p" })}>
              {RESOLUTIONS.map((r) => <option key={r}>{r}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Default transition</label>
            <select className="input" value={tl.transition} onChange={(e) => setTl({ transition: e.target.value })}>
              {TRANSITIONS.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Watermark position</label>
            <select className="input" value={tl.watermark_position} onChange={(e) => setTl({ watermark_position: e.target.value })}>
              {WATERMARK_POSITIONS.map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>
        </div>
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="label">Background music / ambience (loop, auto-ducked)</label>
            <select className="input" value={tl.music_asset_id || ""} onChange={(e) => setTl({ music_asset_id: e.target.value || null })}>
              <option value="">No music</option>
              {project.assets.filter((a) => a.kind === "audio").map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Watermark / channel logo (image)</label>
            <select className="input" value={tl.watermark_asset_id || ""} onChange={(e) => setTl({ watermark_asset_id: e.target.value || null })}>
              <option value="">No watermark</option>
              {project.assets.filter((a) => a.kind === "image").map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          {[
            ["title_card", "Intro title card"],
            ["outro", "Outro card"],
            ["burn_captions", "Burn in captions"],
          ].map(([key, label]) => (
            <label key={key} className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" className="accent-gold-400 w-4 h-4"
                checked={Boolean(tl[key as keyof typeof tl])}
                onChange={(e) => setTl({ [key]: e.target.checked } as Partial<Project["timeline"]>)} />
              {label}
            </label>
          ))}
        </div>
      </div>

      {/* Scene timeline */}
      <div className="card p-5">
        <h2 className="font-display text-xl text-slate-100 mb-4">Scene timeline ({project.scenes.length})</h2>
        <div className="space-y-2">
          {project.scenes.map((sc, i) => {
            const img = sc.image_asset_id ? assetsById.get(sc.image_asset_id) : null;
            const audio = sc.audio_asset_id ? assetsById.get(sc.audio_asset_id) : null;
            return (
              <div key={sc.id} className="flex items-center gap-3 bg-ink-900 rounded-xl p-2.5">
                <div className="flex flex-col">
                  <button className="text-slate-500 hover:text-gold-300" onClick={() => move(i, -1)}><ArrowUp className="w-4 h-4" /></button>
                  <button className="text-slate-500 hover:text-gold-300" onClick={() => move(i, 1)}><ArrowDown className="w-4 h-4" /></button>
                </div>
                <div className="w-20 h-12 rounded-lg overflow-hidden bg-ink-800 shrink-0">
                  {img ? <img src={api.mediaUrl(img.path)} className="w-full h-full object-cover" alt="" /> : <div className="w-full h-full grid place-items-center text-slate-600 text-xs">no img</div>}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-200 truncate">{sc.heading}</p>
                  <div className="flex gap-2 mt-1">
                    {img?.source.includes("placeholder") ? <Badge tone="amber">placeholder</Badge> : img ? <Badge tone="green">image</Badge> : <Badge tone="red">no image</Badge>}
                    {audio ? <Badge tone="blue">narration</Badge> : <Badge tone="neutral">no audio</Badge>}
                    <span className="text-xs text-slate-500">{sc.duration || 5}s · {sc.motion || "zoom_in"} · {sc.transition || tl.transition}</span>
                  </div>
                </div>
                <select className="input py-1.5 text-xs w-44 hidden md:block" value={sc.image_asset_id || ""}
                  onChange={(e) => setSceneImage(sc.id, e.target.value)}>
                  <option value="">Replace clip…</option>
                  {project.assets.filter((a) => a.kind === "image").map((a) => <option key={a.id} value={a.id}>{a.name.slice(0, 38)}</option>)}
                </select>
              </div>
            );
          })}
        </div>
        <button className="btn-primary w-full mt-4" onClick={() => go("export")}>
          Continue to Preview & Export <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      <Notice tone="info">
        Rendering uses local FFmpeg: Ken Burns motion on every still, xfade transitions, mixed narration and music,
        burned-in subtitles, then H.264 video with AAC audio in a fast-start MP4. Image-based videos are clearly
        placeholders until you add real images — they are not presented as AI-generated moving clips.
      </Notice>
    </div>
  );
}
