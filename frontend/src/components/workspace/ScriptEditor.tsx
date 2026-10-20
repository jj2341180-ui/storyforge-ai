import { Clock, FileEdit, Trash2, Plus } from "lucide-react";
import type { Project, Scene } from "../../types";
import { EmptyState, Notice, Badge } from "../common";
import { NARRATION_WPM } from "../../constantsClient";

export default function ScriptEditor({
  project,
  update,
}: {
  project: Project;
  update: (patch: Partial<Project>) => void;
  notify: (msg: string, tone?: "ok" | "err") => void;
}) {
  const scenes = project.scenes;

  const words = scenes.reduce((n, s) => n + `${s.narration} ${s.dialogue || ""}`.split(/\s+/).filter(Boolean).length, 0);
  const estSec = Math.round((words / NARRATION_WPM) * 60);
  const targetSec = Number(project.settings.length || 3) * 60;
  const mismatch = Math.abs(estSec - targetSec) > Math.max(20, targetSec * 0.25);

  const patchScene = (id: string, patch: Partial<Scene>) =>
    update({ scenes: scenes.map((s) => (s.id === id ? { ...s, ...patch } : s)) });

  const removeScene = (id: string) => update({ scenes: scenes.filter((s) => s.id !== id) });

  const addScene = () =>
    update({
      scenes: [
        ...scenes,
        {
          id: crypto.randomUUID(),
          heading: `Scene ${scenes.length + 1} - New scene`,
          narration: "",
          dialogue: "",
          visual_prompt: "",
          notes: "",
        },
      ],
    });

  if (!scenes.length) {
    return (
      <EmptyState
        icon={<FileEdit className="w-6 h-6" />}
        title="No script yet"
        hint="Generate an original script in the Story Studio, or paste your own."
      />
    );
  }

  return (
    <div className="space-y-5">
      <div className="card p-5 grid sm:grid-cols-3 gap-4">
        <div className="sm:col-span-2">
          <label className="label">Title</label>
          <input className="input" value={project.script.title}
            onChange={(e) => update({ script: { ...project.script, title: e.target.value } })} />
          <label className="label mt-3">Logline</label>
          <textarea className="input min-h-[70px]" value={project.script.logline}
            onChange={(e) => update({ script: { ...project.script, logline: e.target.value } })} />
        </div>
        <div className="rounded-xl bg-ink-900 p-4 space-y-2 text-sm">
          <p className="flex items-center gap-2 text-slate-300"><Clock className="w-4 h-4 text-gold-400" /> Narration estimate</p>
          <p className="text-2xl font-display text-slate-100">{Math.floor(estSec / 60)}m {estSec % 60}s</p>
          <p className="text-slate-400">{words} words · target {Math.floor(targetSec / 60)}m</p>
          {mismatch ? (
            <Badge tone="red">Duration mismatch</Badge>
          ) : (
            <Badge tone="green">Within target range</Badge>
          )}
        </div>
      </div>

      {mismatch && (
        <Notice tone="warn">
          The narration length doesn't match your target duration. Add or remove scenes/text, or change the length
          target in the Story Studio before rendering.
        </Notice>
      )}

      {scenes.map((sc, i) => (
        <div key={sc.id} className="card p-5 space-y-3">
          <div className="flex items-center gap-3">
            <span className="chip bg-ink-700 text-gold-300">#{i + 1}</span>
            <input className="input flex-1 font-semibold" value={sc.heading}
              onChange={(e) => patchScene(sc.id, { heading: e.target.value })} />
            <button className="btn-ghost p-2 text-red-400 hover:bg-red-950" onClick={() => removeScene(sc.id)} title="Delete scene">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
          <div>
            <label className="label">Narration</label>
            <textarea className="input min-h-[110px] leading-relaxed" value={sc.narration}
              onChange={(e) => patchScene(sc.id, { narration: e.target.value })} />
          </div>
          <div>
            <label className="label">Dialogue (one “Name: line” per row)</label>
            <textarea className="input min-h-[70px] font-mono text-xs" value={sc.dialogue || ""}
              onChange={(e) => patchScene(sc.id, { dialogue: e.target.value })} />
          </div>
          <div>
            <label className="label">Visual prompt (feeds image / video models)</label>
            <textarea className="input min-h-[90px] text-xs" value={sc.visual_prompt}
              onChange={(e) => patchScene(sc.id, { visual_prompt: e.target.value })} />
          </div>
          <div>
            <label className="label">Caption override (blank = use narration; burned into the video)</label>
            <input className="input text-sm" placeholder="Custom subtitle text for this scene…"
              value={sc.caption_text || ""}
              onChange={(e) => patchScene(sc.id, { caption_text: e.target.value })} />
          </div>
          <div>
            <label className="label">Director notes</label>
            <input className="input text-sm" value={sc.notes || ""}
              onChange={(e) => patchScene(sc.id, { notes: e.target.value })} />
          </div>
        </div>
      ))}

      <button className="btn-secondary w-full" onClick={addScene}>
        <Plus className="w-4 h-4" /> Add scene
      </button>
    </div>
  );
}
