import { Sparkles, Wand2, FileText, AlertTriangle, Info } from "lucide-react";
import { useState } from "react";
import { api } from "../../api";
import type { Project, ScriptPack } from "../../types";
import { AUDIENCES, ENDINGS, GENRES, LENGTHS, POVS, TONES } from "../../constants";
import { Badge, Notice, Spinner } from "../common";

export default function Studio({
  project,
  update,
  go,
  notify,
}: {
  project: Project;
  update: (patch: Partial<Project>) => void;
  go: (tab: string) => void;
  notify: (msg: string, tone?: "ok" | "err") => void;
}) {
  const [busy, setBusy] = useState(false);
  const [pack, setPack] = useState<ScriptPack | null>(null);
  const [rawScript, setRawScript] = useState("");
  const [splitting, setSplitting] = useState(false);
  const s = project.settings;

  const setSetting = (k: string, v: string | number) => update({ settings: { ...project.settings, [k]: v } });

  const generate = async (seed?: number) => {
    setBusy(true);
    try {
      const result = await api.generateScript(project.settings, seed);
      setPack(result);
      notify("Original script generated locally");
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  const accept = () => {
    if (!pack) return;
    update({
      script: { title: pack.title, logline: pack.logline, originality: pack.originality },
      scenes: pack.scenes,
      characters: pack.characters,
      style: pack.style,
      name: project.name.startsWith("Untitled") ? pack.title : project.name,
    });
    notify("Script & storyboard saved — review and edit before rendering", "ok");
    go("script");
  };

  const acceptOwnScript = async () => {
    if (!rawScript.trim()) return;
    setSplitting(true);
    try {
      const { scenes } = await api.splitScript(rawScript);
      const visual = scenes.map((sc) => ({
        ...sc,
        visual_prompt: `Cinematic scene, ${sc.heading}. ${sc.narration.slice(0, 160)} Film still, dramatic lighting, no text, no watermark.`,
      }));
      update({
        scenes: visual,
        script: { ...project.script, title: project.script.title || project.name },
      });
      notify(`Your script was split into ${visual.length} scenes`, "ok");
      go("script");
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setSplitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <Notice tone="info">
        <p>
          Everything here runs offline: original randomized genre writing, local Piper narration and local FFmpeg
          rendering. No existing books, films or copyrighted characters are used.
        </p>
      </Notice>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Settings */}
        <div className="card p-5 space-y-4">
          <h2 className="font-display text-xl text-gold-300 flex items-center gap-2">
            <Sparkles className="w-5 h-5" /> Story setup
          </h2>
          <div>
            <label className="label">Story category</label>
            <select className="input" value={String(s.category)} onChange={(e) => setSetting("category", e.target.value)}>
              {GENRES.map((g) => <option key={g.id} value={g.id}>{g.label}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Target audience</label>
              <select className="input" value={String(s.audience)} onChange={(e) => setSetting("audience", e.target.value)}>
                {AUDIENCES.map((a) => <option key={a}>{a}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Narration language</label>
              <input className="input" value={String(s.language)} onChange={(e) => setSetting("language", e.target.value)} />
            </div>
            <div>
              <label className="label">Video length target</label>
              <select className="input" value={Number(s.length)} onChange={(e) => setSetting("length", Number(e.target.value))}>
                {LENGTHS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Number of scenes</label>
              <input type="number" min={3} max={10} className="input" value={Number(s.sceneCount)}
                onChange={(e) => setSetting("sceneCount", Math.max(3, Math.min(10, Number(e.target.value))))} />
            </div>
            <div>
              <label className="label">Tone & atmosphere</label>
              <select className="input" value={String(s.tone)} onChange={(e) => setSetting("tone", e.target.value)}>
                {TONES.map((t) => <option key={t} className="capitalize">{t}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Narration perspective</label>
              <select className="input" value={String(s.pov)} onChange={(e) => setSetting("pov", e.target.value)}>
                {POVS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="label">Ending</label>
            <div className="flex flex-wrap gap-2">
              {ENDINGS.map((en) => (
                <button key={en.id} onClick={() => setSetting("ending", en.id)}
                  className={`chip border ${s.ending === en.id ? "bg-gold-400 text-ink-950 border-gold-400" : "bg-ink-800 border-ink-600 text-slate-300"}`}>
                  {en.label}
                </button>
              ))}
            </div>
          </div>
          <button className="btn-primary w-full" disabled={busy} onClick={() => generate()}>
            {busy ? <Spinner label="Writing an original story…" /> : <><Wand2 className="w-4 h-4" /> Generate original script</>}
          </button>
          {pack && (
            <button className="btn-secondary w-full" disabled={busy} onClick={() => generate(pack.seed + 1)}>
              Regenerate with a new variation
            </button>
          )}
        </div>

        {/* Result / own script */}
        <div className="space-y-6">
          {pack ? (
            <div className="card p-5 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <h3 className="font-display text-2xl text-slate-50">{pack.title}</h3>
                <Badge tone="green">Original</Badge>
              </div>
              <p className="text-sm text-slate-300 italic">{pack.logline}</p>
              {pack.duration_warning && (
                <Notice tone="warn"><AlertTriangle className="w-4 h-4" /> {pack.duration_warning}</Notice>
              )}
              <div className="flex gap-4 text-sm text-slate-400">
                <span>{pack.narration_words} narration words</span>
                <span>~{Math.floor(pack.estimated_seconds / 60)}m {pack.estimated_seconds % 60}s estimated</span>
                <span>{pack.scenes.length} scenes</span>
              </div>
              <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
                {pack.scenes.map((sc, i) => (
                  <div key={sc.id} className="rounded-lg bg-ink-900 p-3 text-sm">
                    <p className="text-gold-300 font-semibold text-xs mb-1">{sc.heading}</p>
                    <p className="text-slate-300">{sc.narration}</p>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <button className="btn-primary flex-1" onClick={accept}>Approve & build storyboard</button>
                <button className="btn-secondary" onClick={() => setPack(null)}>Discard</button>
              </div>
              <p className="text-[11px] text-slate-500">{pack.originality}</p>
            </div>
          ) : (
            <div className="card p-5 space-y-3">
              <h3 className="font-display text-xl text-slate-100 flex items-center gap-2">
                <FileText className="w-5 h-5 text-gold-400" /> Or paste your own script
              </h3>
              <p className="text-sm text-slate-400">
                Separate scenes with blank lines, or start each with “Scene …”. Lines like <code className="text-gold-300">Name: dialogue</code> are
                detected automatically.
              </p>
              <textarea
                className="input min-h-[220px] font-mono text-xs leading-relaxed"
                placeholder={"Scene 1 - The Arrival\nThe harbor vanished into fog as Mira stepped off the boat.\nMira: Tell me this is the right address."}
                value={rawScript}
                onChange={(e) => setRawScript(e.target.value)}
              />
              <button className="btn-secondary w-full" disabled={splitting || !rawScript.trim()} onClick={acceptOwnScript}>
                {splitting ? <Spinner label="Splitting into scenes…" /> : "Split my script into scenes"}
              </button>
            </div>
          )}
          <Notice tone="info">
            <Info className="w-4 h-4" />
            Approve or edit everything before generating assets. You stay in control of the script, characters and visuals.
          </Notice>
        </div>
      </div>
    </div>
  );
}
