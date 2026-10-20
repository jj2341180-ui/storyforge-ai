import { ArrowLeft, CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { Project } from "../../types";
import { registerFlusher, unregisterFlusher } from "../../saving";
import { Toast, useToast } from "../common";
import Studio from "./Studio";
import ScriptEditor from "./ScriptEditor";
import Storyboard from "./Storyboard";
import Characters from "./Characters";
import Library from "./Library";
import Timeline from "./Timeline";
import ExportPanel from "./ExportPanel";
import ClipMode from "./ClipMode";
import ShortsStudio from "./ShortsStudio";
import WizardNav, { ClipNav } from "./WizardNav";

const TABS = [
  { id: "studio", label: "Story Studio" },
  { id: "script", label: "Script" },
  { id: "storyboard", label: "Storyboard" },
  { id: "characters", label: "Characters" },
  { id: "library", label: "Asset Library" },
  { id: "timeline", label: "Timeline" },
  { id: "export", label: "Preview & Export" },
];

export default function Workspace({ projectId, onHome }: { projectId: string; onHome: () => void }) {
  const [project, setProject] = useState<Project | null>(null);
  const [tab, setTab] = useState("studio");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const first = useRef(true);
  const latest = useRef<Project | null>(null);
  const timer = useRef<number | null>(null);
  const { toast, show } = useToast();

  useEffect(() => {
    api.getProject(projectId).then((p) => {
      setProject(p);
      latest.current = p;
    });
  }, [projectId]);

  const persist = async (p: Project) => {
    if (timer.current) window.clearTimeout(timer.current);
    setSaveState("saving");
    try {
      const saved = await api.saveProject(p);
      latest.current = saved;
      setSaveState("saved");
    } catch (e) {
      show(`Save failed: ${(e as Error).message}`, "err");
    }
  };

  // Register an immediate-save callback for panels about to call scene-dependent APIs.
  useEffect(() => {
    if (!project) return;
    registerFlusher(project.id, async () => {
      if (latest.current) await persist(latest.current);
    });
    return () => unregisterFlusher(project.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id]);

  useEffect(() => {
    if (!project || first.current) {
      if (project) first.current = false;
      return;
    }
    latest.current = project;
    setSaveState("saving");
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => persist(project), 800);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project]);

  if (!project) {
    return (
      <div className="h-full grid place-items-center">
        <Loader2 className="w-7 h-7 animate-spin text-gold-400" />
      </div>
    );
  }

  const update = (patch: Partial<Project>) =>
    setProject((p) => (p ? { ...p, ...patch } : p));

  return (
    <div className="min-h-full flex flex-col">
      <header className="sticky top-0 z-40 bg-ink-950/90 backdrop-blur border-b border-ink-800">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-3">
          <button className="btn-ghost p-2" onClick={onHome} title="Back home">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <input
            className="bg-transparent font-display text-lg text-slate-100 focus:outline-none focus:text-gold-300 min-w-0 flex-1"
            value={project.name}
            onChange={(e) => update({ name: e.target.value })}
          />
          <span className="hidden sm:flex items-center gap-1.5 text-xs text-slate-400">
            {saveState === "saving" ? (
              <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Saving…</>
            ) : saveState === "saved" ? (
              <><CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Saved locally</>
            ) : null}
          </span>
        </div>
        {project.mode === "story" && (
          <nav className="max-w-7xl mx-auto px-4 pb-2 flex gap-1 overflow-x-auto">
            {TABS.map((t) => (
              <button key={t.id} className={`tab ${tab === t.id ? "tab-active" : ""}`} onClick={() => setTab(t.id)}>
                {t.label}
              </button>
            ))}
          </nav>
        )}
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
        {project.mode === "clip" ? (
          <ClipMode project={project} update={update} notify={show} onHome={onHome} />
        ) : project.mode === "shorts" ? (
          <ShortsStudio project={project} update={update} onHome={onHome} />
        ) : (
          <>
            {tab === "studio" && <Studio project={project} update={update} go={setTab} notify={show} />}
            {tab === "script" && <ScriptEditor project={project} update={update} notify={show} />}
            {tab === "storyboard" && <Storyboard project={project} update={update} notify={show} />}
            {tab === "characters" && <Characters project={project} update={update} notify={show} />}
            {tab === "library" && <Library project={project} update={update} notify={show} />}
            {tab === "timeline" && <Timeline project={project} update={update} go={setTab} notify={show} />}
            {tab === "export" && <ExportPanel project={project} update={update} notify={show} />}
          </>
        )}
      </main>

      {project.mode === "clip" ? (
        <ClipNav onHome={onHome} />
      ) : (
        <WizardNav
          steps={TABS}
          currentId={tab}
          onGo={setTab}
          onHome={onHome}
          nextDisabled={tab === "studio" && project.scenes.length === 0}
          nextHint="Generate or paste a script on this page first, then continue"
        />
      )}
      <Toast toast={toast} />
    </div>
  );
}
