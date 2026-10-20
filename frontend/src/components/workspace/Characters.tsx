import { UserPlus, Trash2, Upload, Palette } from "lucide-react";
import { useRef } from "react";
import { api } from "../../api";
import type { Character, Project } from "../../types";
import { EmptyState, Notice } from "../common";

const FIELDS: { key: keyof Character; label: string }[] = [
  { key: "name", label: "Character name" },
  { key: "age_range", label: "Age range" },
  { key: "appearance", label: "Physical appearance" },
  { key: "hair", label: "Hair" },
  { key: "eyes", label: "Eye color" },
  { key: "clothing", label: "Clothing" },
  { key: "personality", label: "Personality" },
  { key: "features", label: "Important visual features" },
];

export default function Characters({
  project,
  update,
  notify,
}: {
  project: Project;
  update: (patch: Partial<Project>) => void;
  notify: (msg: string, tone?: "ok" | "err") => void;
}) {
  const uploadRef = useRef<HTMLInputElement | null>(null);
  const targetChar = useRef<string | null>(null);

  const patchChar = (id: string, patch: Partial<Character>) =>
    update({ characters: project.characters.map((c) => (c.id === id ? { ...c, ...patch } : c)) });

  const add = () =>
    update({
      characters: [
        ...project.characters,
        {
          id: crypto.randomUUID(), name: "New character", age_range: "", appearance: "", hair: "",
          eyes: "", clothing: "", personality: "", features: "", ref_asset_id: null,
        },
      ],
    });

  const remove = (id: string) => update({ characters: project.characters.filter((c) => c.id !== id) });

  const uploadRefImage = async (cid: string, file: File) => {
    try {
      const asset = await api.uploadAsset(project.id, file, "image");
      patchChar(cid, { ref_asset_id: asset.id });
      notify("Reference image saved — use it for image-to-video when a model is connected");
    } catch (e) {
      notify((e as Error).message, "err");
    }
  };

  const setStyle = (k: string, v: string) => update({ style: { ...project.style, [k]: v } });
  const refAsset = (cid: string | null) => project.assets.find((a) => a.id === cid);

  return (
    <div className="space-y-6">
      <Notice tone="info">
        These descriptions are automatically baked into every scene's visual prompt so characters, clothing and
        locations stay consistent. Perfect frame-to-frame consistency depends on the connected model — local
        placeholders and uploaded reference images always preserve your descriptions.
      </Notice>

      <div className="flex items-center justify-between">
        <h2 className="font-display text-xl text-slate-100">Character library ({project.characters.length})</h2>
        <button className="btn-primary" onClick={add}><UserPlus className="w-4 h-4" /> Add character</button>
      </div>

      {project.characters.length === 0 && (
        <EmptyState icon={<UserPlus className="w-6 h-6" />} title="No characters yet"
          hint="Generate a script to create leads automatically, or add one manually." />
      )}

      <div className="grid lg:grid-cols-2 gap-5">
        {project.characters.map((c) => {
          const ref = refAsset(c.ref_asset_id || null);
          return (
            <div key={c.id} className="card p-5 space-y-3">
              <div className="flex gap-4">
                <div className="shrink-0">
                  <div className="w-24 h-24 rounded-xl overflow-hidden bg-ink-900 grid place-items-center text-slate-600">
                    {ref ? <img src={api.mediaUrl(ref.path)} className="w-full h-full object-cover" alt={c.name} /> : <Palette className="w-7 h-7" />}
                  </div>
                  <input
                    ref={(el) => { if (el) uploadRef.current = el; }}
                    type="file" accept="image/*" className="hidden"
                    onChange={(e) => e.target.files?.[0] && uploadRefImage(c.id, e.target.files[0])}
                  />
                  <button className="btn-ghost text-[11px] px-2 py-1 mt-1 w-full"
                    onClick={() => { targetChar.current = c.id; uploadRef.current?.click(); }}>
                    <Upload className="w-3 h-3" /> Ref image
                  </button>
                </div>
                <div className="flex-1 space-y-2">
                  {FIELDS.slice(0, 2).map((f) => (
                    <input key={f.key} className="input py-2 text-sm" placeholder={f.label}
                      value={String(c[f.key] || "")}
                      onChange={(e) => patchChar(c.id, { [f.key]: e.target.value } as Partial<Character>)} />
                  ))}
                  <select className="input py-2 text-xs" value={c.ref_asset_id || ""}
                    onChange={(e) => patchChar(c.id, { ref_asset_id: e.target.value || null })}>
                    <option value="">Link library image…</option>
                    {project.assets.filter((a) => a.kind === "image").map((a) => (
                      <option key={a.id} value={a.id}>{a.name.slice(0, 44)}</option>
                    ))}
                  </select>
                </div>
              </div>
              {FIELDS.slice(2).map((f) => (
                <input key={f.key} className="input py-2 text-sm" placeholder={f.label}
                  value={String(c[f.key] || "")}
                  onChange={(e) => patchChar(c.id, { [f.key]: e.target.value } as Partial<Character>)} />
              ))}
              <button className="btn-ghost text-red-400 text-xs px-2 py-1" onClick={() => remove(c.id)}>
                <Trash2 className="w-3.5 h-3.5" /> Remove character
              </button>
            </div>
          );
        })}
      </div>

      {/* Reusable visual style */}
      <div className="card p-5 space-y-3">
        <h2 className="font-display text-xl text-slate-100 flex items-center gap-2">
          <Palette className="w-5 h-5 text-gold-400" /> Reusable visual style
        </h2>
        <p className="text-sm text-slate-400">
          Location, lighting, color palette, camera style and effects are reused across every scene prompt.
        </p>
        <div className="grid md:grid-cols-2 gap-3">
          {[
            { key: "location", label: "Location / setting" },
            { key: "lighting", label: "Lighting" },
            { key: "palette", label: "Color palette" },
            { key: "camera", label: "Camera style" },
            { key: "effects", label: "Atmosphere & effects" },
          ].map((f) => (
            <div key={f.key}>
              <label className="label">{f.label}</label>
              <input className="input text-sm" value={project.style[f.key] || ""}
                onChange={(e) => setStyle(f.key, e.target.value)} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
