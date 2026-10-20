#!/usr/bin/env bash
# Pushes StoryForge AI to a Hugging Face Docker Space (creates the repo if missing).
# Usage: HF_USER="yourname" HF_TOKEN="hf_xxx" ./deploy/push-to-hf.sh
set -euo pipefail
cd "$(dirname "$0")/.."

: "${HF_USER:?set HF_USER}"
: "${HF_TOKEN:?set HF_TOKEN}"
SPACE_NAME="${SPACE_NAME:-storyforge}"
REMOTE="https://${HF_USER}:${HF_TOKEN}@huggingface.co/spaces/${HF_USER}/${SPACE_NAME}"
STAGE="$(mktemp -d)"

echo "==> Staging files (excluding data, dependencies, caches, large voice model)"
# Copy everything tracked-worthy, excluding heavy/regeneratable content.
tar --exclude='./.git' --exclude='./data' --exclude='**/node_modules' --exclude='**/.venv' \
    --exclude='**/__pycache__' --exclude='**/dist' --exclude='**/temp' \
    --exclude='*.onnx' --exclude='*.zip' --exclude='./docs/screenshots' \
    -cf - -C . . | tar -xf - -C "$STAGE"

# Hugging Face requires the Space config front-matter in the root README.md.
cp deploy/hf-space-README.md "$STAGE/README.md"

cd "$STAGE"
git init -q
git config user.email "storyforge@local"
git config user.name "StoryForge Deploy"
git branch -M main
git add -A
git commit -q -m "StoryForge AI - Hugging Face Space"

echo "==> Creating Space if it does not exist"
curl -s -o /dev/null -w "create-space HTTP %{http_code}\n" \
  -X POST "https://huggingface.co/api/repos/create" \
  -H "Authorization: Bearer ${HF_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"space\",\"name\":\"${SPACE_NAME}\",\"sdk\":\"docker\"}" || true

echo "==> Pushing to ${HF_USER}/${SPACE_NAME}"
git remote add origin "$REMOTE"
git push -f origin main
echo "==> Done. Space URL: https://${HF_USER}-${SPACE_NAME}.hf.space"
