import { Search, Trash2, Upload, Music4, Image as ImageIcon, Film, ExternalLink } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "../../api";
import type { LibraryItem, Project } from "../../types";
import { Badge, EmptyState, Notice, Spinner } from "../common";

export default function Library({
  project,
  update,
  notify,
}: {
  project: Project;
  update: (patch: Partial<Project>) => void;
  notify: (msg: string, tone?: "ok" | "err") => void;
}) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("image");
  const [results, setResults] = useState<LibraryItem[]>([]);
  const [notice, setNotice] = useState("");
  const [searching, setSearching] = useState(false);
  const [importing, setImporting] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "image" | "audio" | "video">("all");
  const uploadRef = useRef<HTMLInputElement>(null);

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const r = await api.searchLibrary(query, kind);
      setResults(r.results);
      setNotice(r.notice);
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setSearching(false);
    }
  };

  const importItem = async (item: LibraryItem) => {
    setImporting(item.id);
    try {
      const asset = await api.importLibrary(project.id, item, kind);
      update({ assets: [...project.assets, asset] });
      notify("Imported with license info stored");
    } catch (e) {
      notify((e as Error).message, "err");
    } finally {
      setImporting(null);
    }
  };

  const upload = async (files: FileList | null) => {
    if (!files) return;
    const added = [];
    for (const file of Array.from(files)) {
      const k = file.type.startsWith("audio") ? "audio" : file.type.startsWith("video") ? "video" : "image";
      try {
        added.push(await api.uploadAsset(project.id, file, k));
      } catch (e) {
        notify((e as Error).message, "err");
      }
    }
    if (added.length) {
      update({ assets: [...project.assets, ...added] });
      notify(`${added.length} file(s) added to project`);
    }
  };

  const remove = (id: string) => update({ assets: project.assets.filter((a) => a.id !== id) });

  const shown = project.assets.filter((a) => filter === "all" || a.kind === filter);
  const iconFor = (k: string) => (k === "audio" ? <Music4 className="w-4 h-4" /> : k === "video" ? <Film className="w-4 h-4" /> : <ImageIcon className="w-4 h-4" />);

  return (
    <div className="space-y-6">
      <Notice tone="warn">
        Only import media you have the rights to use. Openverse aggregates Creative Commons and public-domain
        material, but each item's license and attribution requirements differ — they are stored with every
        imported asset. Never assume “publicly viewable” means free for commercial use.
      </Notice>

      {/* Upload + free search */}
      <div className="grid lg:grid-cols-2 gap-5">
        <div className="card p-5 space-y-3">
          <h2 className="font-display text-lg text-slate-100 flex items-center gap-2"><Upload className="w-5 h-5 text-gold-400" /> Your uploads</h2>
          <p className="text-sm text-slate-400">Images, audio (music, SFX, recorded narration) and video clips. Stored in the local project folder.</p>
          <input ref={uploadRef} type="file" multiple accept="image/*,audio/*,video/*" className="hidden"
            onChange={(e) => upload(e.target.files)} />
          <button className="btn-primary w-full" onClick={() => uploadRef.current?.click()}>
            <Upload className="w-4 h-4" /> Upload media
          </button>
          <div className="flex gap-2 flex-wrap">
            {(["all", "image", "audio", "video"] as const).map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={`chip border capitalize ${filter === f ? "bg-gold-400 text-ink-950 border-gold-400" : "bg-ink-800 border-ink-600"}`}>
                {f}
              </button>
            ))}
          </div>
        </div>

        <div className="card p-5 space-y-3">
          <h2 className="font-display text-lg text-slate-100 flex items-center gap-2"><Search className="w-5 h-5 text-gold-400" /> Free licensed media (Openverse)</h2>
          <div className="flex gap-2">
            <select className="input w-32" value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="image">Images</option>
              <option value="audio">Audio</option>
            </select>
            <input className="input" placeholder="e.g. misty forest, thunderstorm…" value={query}
              onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} />
            <button className="btn-secondary" onClick={search} disabled={searching}>
              {searching ? <Spinner /> : <Search className="w-4 h-4" />}
            </button>
          </div>
          {notice && <p className="text-xs text-amber-300">{notice}</p>}
          <p className="text-xs text-slate-500">
            Privacy: your search terms are sent to the public Openverse catalog (no account, no API key). All
            imported files are downloaded and stored inside your local project folder.
          </p>
          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {results.map((item) => (
              <div key={item.id} className="flex gap-3 items-center bg-ink-900 rounded-xl p-2">
                {item.thumbnail ? (
                  <img src={item.thumbnail} className="w-16 h-16 object-cover rounded-lg" alt={item.title} />
                ) : (
                  <div className="w-16 h-16 grid place-items-center bg-ink-800 rounded-lg"><Music4 className="w-5 h-5 text-slate-500" /></div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-200 truncate">{item.title}</p>
                  <p className="text-xs text-slate-500 truncate">{item.creator} · {item.source}</p>
                  <Badge tone="blue">{item.license || "CC"}</Badge>
                </div>
                <button className="btn-secondary text-xs px-3 py-2" disabled={importing === item.id} onClick={() => importItem(item)}>
                  {importing === item.id ? <Spinner /> : "Import"}
                </button>
              </div>
            ))}
            {!results.length && !searching && <p className="text-sm text-slate-500">Search the free library to see results here.</p>}
          </div>
        </div>
      </div>

      {/* Project assets */}
      <h2 className="font-display text-xl text-slate-100">Project assets ({shown.length})</h2>
      {shown.length === 0 ? (
        <EmptyState icon={<ImageIcon className="w-6 h-6" />} title="No assets yet" hint="Upload files or import free licensed media above." />
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {shown.map((a) => (
            <div key={a.id} className="card overflow-hidden">
              <div className="aspect-video bg-ink-900 grid place-items-center">
                {a.kind === "image" ? (
                  <img src={api.mediaUrl(a.path)} className="w-full h-full object-cover" alt={a.name} />
                ) : a.kind === "audio" ? (
                  <audio controls src={api.mediaUrl(a.path)} className="w-[90%]" />
                ) : (
                  <video controls src={api.mediaUrl(a.path)} className="w-full h-full object-cover" />
                )}
              </div>
              <div className="p-3 space-y-1.5">
                <p className="text-sm font-medium text-slate-200 truncate flex items-center gap-1.5">{iconFor(a.kind)} {a.name}</p>
                <p className="text-[11px] text-slate-400">Source: {a.source}</p>
                <p className="text-[11px] text-slate-500 break-words">License: {a.license || "n/a"}</p>
                <div className="flex gap-2 pt-1">
                  <button className="btn-ghost text-xs px-2 py-1 text-red-400" onClick={() => remove(a.id)}>
                    <Trash2 className="w-3.5 h-3.5" /> Remove
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <p className="text-xs text-slate-500 flex items-center gap-1">
        <ExternalLink className="w-3 h-3" /> StoryForge never scrapes YouTube or other platforms; it only uses uploads and authorized open catalogs.
      </p>
    </div>
  );
}
