import { Clapperboard, Info, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "./api";
import Home from "./components/Home";
import DesktopStage, { isInsideDesktopFrame } from "./components/DesktopStage";
import LayoutToggle from "./components/LayoutToggle";
import Workspace from "./components/workspace/Workspace";

const STORAGE_KEY = "sf_desktop_layout";
const HINT_KEY = "sf_layout_hint_dismissed";

export default function App() {
  const inFrame = typeof window !== "undefined" && isInsideDesktopFrame();
  const [view, setView] = useState<{ name: "home" } | { name: "project"; id: string }>({ name: "home" });
  const [narrow, setNarrow] = useState(false);
  const [desktop, setDesktop] = useState(false);
  const [showHint, setShowHint] = useState(false);

  useEffect(() => {
    if (inFrame) return; // the framed desktop instance always renders the normal shell
    const isNarrow = window.innerWidth < 768;
    setNarrow(isNarrow);
    const stored = localStorage.getItem(STORAGE_KEY);
    // On phones, desktop layout is the default (the user's request); it stays switchable.
    setDesktop(isNarrow ? stored !== "0" : false);
    if (isNarrow && localStorage.getItem(HINT_KEY) !== "1") setShowHint(true);
    const onResize = () => setNarrow(window.innerWidth < 768);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [inFrame]);

  const toggleLayout = (v: boolean) => {
    setDesktop(v);
    localStorage.setItem(STORAGE_KEY, v ? "1" : "0");
  };

  const dismissHint = () => {
    setShowHint(false);
    localStorage.setItem(HINT_KEY, "1");
  };

  const newProject = async (mode: "story" | "clip" | "shorts") => {
    const name =
      mode === "clip" ? "Untitled Video Clip" : mode === "shorts" ? "YouTube Short" : "Untitled Story";
    const p = await api.createProject(name, mode);
    setView({ name: "project", id: p.id });
  };

  const goHome = () => setView({ name: "home" });

  const shell = (
    <>
      <nav className="border-b border-ink-800 bg-ink-950/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-2.5">
          <button className="flex items-center gap-2.5" onClick={goHome}>
            <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-gold-400 to-ember-500 grid place-items-center text-ink-950">
              <Clapperboard className="w-4.5 h-4.5" size={18} />
            </span>
            <span className="font-display text-lg text-slate-50">
              StoryForge <span className="text-gold-400">AI</span>
            </span>
            <span className="chip bg-ink-800 text-slate-400 hidden sm:inline-flex ml-2">local · free · open source</span>
          </button>
          {narrow && !inFrame && (
            <div className="ml-auto">
              <LayoutToggle desktop={desktop} onToggle={toggleLayout} />
            </div>
          )}
        </div>
      </nav>

      {view.name === "home" ? (
        <Home onOpen={(id) => setView({ name: "project", id })} onNew={newProject} />
      ) : (
        <Workspace projectId={view.id} onHome={goHome} />
      )}
    </>
  );

  // Portrait phone + desktop layout: host the full 1280px app in a scaled same-origin iframe.
  if (!inFrame && narrow && desktop) {
    return (
      <>
        <div className="fixed top-2 right-2 z-[80] rounded-xl bg-ink-900/95 border border-ink-700 shadow-xl">
          <LayoutToggle desktop onToggle={toggleLayout} />
        </div>
        {showHint && (
          <div className="fixed bottom-3 left-1/2 -translate-x-1/2 z-[80] w-[92vw] max-w-[340px] rounded-xl border border-gold-700/60 bg-ink-900/95 text-gold-200 text-[11px] px-3.5 py-2.5 flex items-start gap-2 shadow-xl">
            <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            <p className="flex-1">
              Desktop layout on a portrait screen — your phone stays upright. Pinch to zoom for bigger text,
              or tap the monitor icon to switch back.
            </p>
            <button onClick={dismissHint} aria-label="Dismiss hint" className="shrink-0">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
        {/* Wrapper sizes itself to the scaled frame; no forced viewport min-height. */}
        <DesktopStage />
      </>
    );
  }

  return <div className="min-h-full">{shell}</div>;
}
