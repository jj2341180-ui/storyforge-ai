#!/usr/bin/env bash
# Download free, offline Piper TTS voices into backend/voices.
# Browse all voices: https://huggingface.co/rhasspy/piper-voices/tree/main
set -euo pipefail
cd "$(dirname "$0")/voices"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main"

# Default set: one feminine + one masculine English voice (each ~60 MB, low quality, fast on CPU).
VOICES=(
  "en/en_US/amy/low/en_US-amy-low"
  "en/en_US/lessac/low/en_US-lessac-low"
)

for v in "${VOICES[@]}"; do
  name="$(basename "$v")"
  for ext in onnx onnx.json; do
    if [ ! -f "$name.$ext" ]; then
      echo "Downloading $name.$ext …"
      curl -L --fail -o "$name.$ext" "$BASE/$v.$ext"
    fi
  done
done

# Add more voices by appending entries, for example:
#   "en/en_GB/alan/medium/en_GB-alan-medium"
#   "es/es_MX/clauc/medium/es_MX-clauc-medium"
#   "fr/fr_FR/siwis/medium/fr_FR-siwis-medium"
echo "Done. Restart the backend; voices appear automatically in the Storyboard."
