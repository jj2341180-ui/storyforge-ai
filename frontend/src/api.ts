import type {
  Asset,
  Job,
  LibraryItem,
  Project,
  ProjectSummary,
  ProviderStatus,
  ScriptPack,
  Voice,
  YouTubeMetadata,
} from "./types";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: options.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") {
        detail = data.detail;
      } else if (data.detail && typeof data.detail === "object") {
        // Structured error (e.g. not_configured): show the human message, never raw JSON.
        detail = data.detail.message || data.detail.error || res.statusText;
      }
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ ok: boolean; ffmpeg: boolean; tts: boolean; version: string }>("/health"),

  listProjects: () => request<ProjectSummary[]>("/projects"),
  createProject: (name: string, mode: string) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ name, mode }) }),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  saveProject: (p: Project) =>
    request<Project>(`/projects/${p.id}`, { method: "PUT", body: JSON.stringify(p) }),
  deleteProject: (id: string) => request<{ status: string }>(`/projects/${id}`, { method: "DELETE" }),

  generateScript: (settings: Record<string, unknown>, seed?: number) =>
    request<ScriptPack>("/studio/generate-script", {
      method: "POST",
      body: JSON.stringify({ settings, seed }),
    }),
  splitScript: (raw: string) =>
    request<{ scenes: ScriptPack["scenes"] }>("/studio/split-script", {
      method: "POST",
      body: JSON.stringify({ raw }),
    }),

  uploadAsset: (pid: string, file: File, kind: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("kind", kind);
    return request<Asset>(`/projects/${pid}/assets`, { method: "POST", body: fd });
  },
  importLibrary: (pid: string, item: LibraryItem, kind: string) =>
    request<Asset>(`/projects/${pid}/library/import`, {
      method: "POST",
      body: JSON.stringify({
        url: item.url,
        name: item.title,
        kind,
        license: item.license,
        license_url: item.license_url,
        source: item.source,
        creator: item.creator,
        attribution: item.attribution,
      }),
    }),
  searchLibrary: (q: string, kind: string) =>
    request<{ results: LibraryItem[]; notice: string }>(
      `/library/search?q=${encodeURIComponent(q)}&kind=${kind}`
    ),

  placeholder: (pid: string, sceneId: string) =>
    request<Asset>(`/projects/${pid}/placeholders/${sceneId}`, { method: "POST" }),

  // Free, keyless AI text-to-image (Pollinations). One image, created synchronously.
  generateImage: (
    pid: string,
    body: { scene_id?: string | null; prompt?: string; seed?: number; aspect?: string; resolution?: string }
  ) =>
    request<Asset>(`/projects/${pid}/generate-image`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  // One AI image per scene, tracked as a background job with progress.
  generateImagesBatch: (
    pid: string,
    body: { only_missing?: boolean; aspect?: string; resolution?: string }
  ) =>
    request<Job>(`/projects/${pid}/generate-images`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  voices: () => request<{ voices: Voice[]; help: { instructions: string; voices_dir: string } }>("/tts/voices"),
  synthesize: (
    pid: string,
    sceneId: string,
    text: string,
    voiceId: string,
    speed: number,
    kind: string
  ) =>
    request<{ asset: Asset; duration: number }>(`/projects/${pid}/tts`, {
      method: "POST",
      body: JSON.stringify({ scene_id: sceneId, text, voice_id: voiceId, speed, kind }),
    }),

  providerStatus: () => request<ProviderStatus>("/providers/status"),
  generate: (
    pid: string,
    body: Record<string, unknown>
  ) => request<Job>(`/projects/${pid}/generate`, { method: "POST", body: JSON.stringify(body) }),

  render: (pid: string, resolution?: "360p" | "480p" | "720p" | "1080p") =>
    request<Job>(`/projects/${pid}/render`, {
      method: "POST",
      body: JSON.stringify(resolution ? { resolution } : {}),
    }),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  jobs: (pid?: string) => request<Job[]>(`/jobs${pid ? `?project_id=${pid}` : ""}`),
  cancelJob: (id: string) =>
    request<{ status: string }>(`/jobs/${id}/cancel`, { method: "POST" }),
  downloadUrl: (jobId: string) => `/api/jobs/${jobId}/download`,
  exportDownloadUrl: (pid: string, file: string) =>
    `/api/projects/${pid}/export-download?path=${encodeURIComponent(file)}`,
  backupUrl: (pid: string) => `/api/projects/${pid}/backup`,
  restoreBackup: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<Project>("/projects/restore", { method: "POST", body: fd });
  },

  metadata: (pid: string) => request<YouTubeMetadata>(`/projects/${pid}/metadata`),
  thumbnail: (pid: string, body: Record<string, unknown>) =>
    request<Asset>(`/projects/${pid}/thumbnail`, { method: "POST", body: JSON.stringify(body) }),

  mediaUrl: (path: string) => `/api/media?path=${encodeURIComponent(path)}`,

  // ---- YouTube Shorts studio ----
  shortsOptions: () => request<ShortsOptions>("/shorts/options"),
  createShort: (body: ShortsRequestBody) =>
    request<{ project_id: string; job_id: string }>("/shorts/create", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  cancelShort: (jobId: string) =>
    request<{ status: string }>(`/shorts/jobs/${jobId}/cancel`, { method: "POST" }),
  srtUrl: (pid: string, path: string) =>
    `/api/shorts/${pid}/srt?path=${encodeURIComponent(path)}`,
};

export interface ShortsVoicePreset {
  id: string;
  voice: string;
  label: string;
}

export interface ShortsOptions {
  durations: number[];
  aspects: string[];
  resolutions: string[];
  voice_presets: ShortsVoicePreset[];
  languages: string[];
  local_video_configured: boolean;
  hardware: {
    gpu: { name: string | null; vram_gb: string | null; driver: boolean };
    can_run_local_video: boolean;
    note: string;
  };
  providers: { id: string; name: string; configured: boolean; requires: string }[];
  honest_note: string;
}

export interface ShortsRequestBody {
  idea: string;
  seconds: number;
  aspect: string;
  resolution: string;
  narration: { enabled: boolean; voice_preset: string; custom_voice?: string; rate: number };
  audio: {
    music_enabled: boolean;
    sfx_enabled: boolean;
    narration_volume: number;
    music_volume: number;
    sfx_volume: number;
  };
  captions: { enabled: boolean; font_size: number; position: "bottom" | "top" | "middle" };
  reference_asset_id?: string | null;
  engine: "auto" | "local";
}
