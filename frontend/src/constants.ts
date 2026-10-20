export const GENRES = [
  { id: "fantasy", label: "Fantasy & magical kingdoms" },
  { id: "romance", label: "Romance & enemies-to-lovers" },
  { id: "horror", label: "Horror & supernatural suspense" },
  { id: "mystery", label: "Mystery & thriller" },
  { id: "adventure", label: "Adventure & action" },
  { id: "drama", label: "Emotional drama" },
  { id: "children", label: "Children's stories" },
  { id: "shortfilm", label: "Original short films" },
];

export const AUDIENCES = ["General", "Young adults", "Adults", "Young children"];
export const TONES = ["epic", "dark", "dreamy", "cozy", "tense", "whimsical", "melancholic"];
export const ENDINGS = [
  { id: "happy", label: "Happy" },
  { id: "tragic", label: "Tragic" },
  { id: "mysterious", label: "Mysterious" },
  { id: "open", label: "Open" },
];
export const POVS = [
  { id: "third", label: "Third person" },
  { id: "first", label: "First person" },
];
export const LENGTHS = [
  { value: 1, label: "~1 min (Shorts)" },
  { value: 3, label: "~3 min" },
  { value: 5, label: "~5 min" },
  { value: 10, label: "~10 min" },
];
export const ASPECTS = [
  { id: "16:9", label: "16:9 — YouTube landscape" },
  { id: "9:16", label: "9:16 — YouTube Shorts" },
  { id: "1:1", label: "1:1 — Square" },
];
export const RESOLUTIONS = ["720p", "1080p"];
export const TRANSITIONS = ["fade", "fadeblack", "slideleft", "slideright", "wiperight", "dissolve", "circleopen", "none"];
export const MOTIONS = [
  { id: "zoom_in", label: "Slow zoom in" },
  { id: "zoom_out", label: "Slow zoom out" },
  { id: "pan_left", label: "Pan left" },
  { id: "pan_right", label: "Pan right" },
  { id: "static", label: "Static" },
];
export const WATERMARK_POSITIONS = ["top-left", "top-right", "bottom-left", "bottom-right"];

// Planning RAM for local video-diffusion workstations (Mode A adapter requirements).
export const RAM_OPTIONS_GB = [32, 40, 48, 56, 64, 72];
