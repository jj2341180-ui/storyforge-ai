export interface Scene {
  id: string;
  heading: string;
  narration: string;
  dialogue?: string;
  visual_prompt: string;
  notes?: string;
  duration?: number;
  image_asset_id?: string | null;
  audio_asset_id?: string | null;
  dialogue_audio_asset_id?: string | null;
  transition?: string;
  motion?: string;
  caption_text?: string;
}

export interface Character {
  id: string;
  name: string;
  age_range: string;
  appearance: string;
  hair: string;
  eyes: string;
  clothing: string;
  personality: string;
  features: string;
  ref_asset_id?: string | null;
}

export interface Asset {
  id: string;
  kind: "image" | "audio" | "video";
  name: string;
  path: string;
  source: string;
  license: string;
  created_at: number;
}

export interface TimelineSettings {
  aspect: "16:9" | "9:16" | "1:1";
  resolution: "720p" | "1080p";
  transition: string;
  title_card: boolean;
  outro: boolean;
  burn_captions: boolean;
  music_asset_id: string | null;
  watermark_asset_id: string | null;
  watermark_position: string;
}

export interface ExportRecord {
  job_id: string;
  created_at: number;
  file: string;
  duration: number;
  width: number;
  height: number;
  aspect: string;
  resolution: string;
  scene_timings?: { scene_id: string; heading: string; start: number; end: number }[];
  used_placeholders?: string[];
}

export interface Project {
  id: string;
  name: string;
  mode: "story" | "clip" | "shorts";
  created_at: number;
  updated_at: number;
  settings: Record<string, string | number>;
  script: { title: string; logline: string; originality?: string };
  scenes: Scene[];
  characters: Character[];
  style: Record<string, string>;
  assets: Asset[];
  exports: ExportRecord[];
  timeline: TimelineSettings;
  clip: {
    prompt: string;
    negative_prompt: string;
    duration: number;
    aspect: string;
    resolution: string;
    quality: string;
    reference_asset_id: string | null;
    provider_id: string | null;
    result_asset_id: string | null;
    target_ram_gb: number;
  };
  narration_voice: string | null;
  dialogue_voice: string | null;
  speech_speed: number;
}

export interface ProjectSummary {
  id: string;
  name: string;
  mode: string;
  created_at: number;
  updated_at: number;
  scene_count: number;
  exports: ExportRecord[];
}

export interface Job {
  id: string;
  project_id: string;
  kind: string;
  status: "queued" | "running" | "finalizing" | "done" | "failed";
  progress: number;
  message: string;
  result: Record<string, unknown> | null;
  created_at: number;
  updated_at: number;
  file_exists?: boolean;
}

export interface Voice {
  id: string;
  label: string;
  language: string;
  gender: string;
  engine: string;
}

export interface ProviderInfo {
  id: string;
  name: string;
  kind: string;
  configured: boolean;
  requires: string;
  docs: string;
  cost: string;
  selectable: boolean;
}

export interface ProviderStatus {
  hardware: {
    cpu_cores: number;
    ram_gb: number;
    gpu: { name: string | null; vram_gb: string | null; driver: boolean };
    disk_free_gb: number;
    can_run_local_video: boolean;
    note: string;
  };
  providers: ProviderInfo[];
  ram_options_gb: number[];
  any_configured: boolean;
  honest_alternative: string;
}

export interface ScriptPack {
  title: string;
  logline: string;
  scenes: Scene[];
  characters: Character[];
  style: Record<string, string>;
  narration_words: number;
  estimated_seconds: number;
  duration_warning: string | null;
  originality: string;
  seed: number;
}

export interface LibraryItem {
  id: string;
  title: string;
  creator: string;
  url: string;
  thumbnail: string;
  license: string;
  license_url: string;
  source: string;
  kind: string;
  attribution: string;
}

export interface YouTubeMetadata {
  title_options: string[];
  description: string;
  keywords: string[];
  hashtags: string[];
  chapters: string[];
  pinned_comment: string;
  disclaimer: string;
}
