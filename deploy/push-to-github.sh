#!/usr/bin/env bash
# Creates (if needed) and pushes StoryForge AI to a GitHub repository.
# Usage: GH_USER="yourname" GH_TOKEN="ghp_xxx" [GH_REPO="storyforge-ai"] ./deploy/push-to-github.sh
set -euo pipefail
cd "$(dirname "$0")/.."

: "${GH_USER:?set GH_USER}"
: "${GH_TOKEN:?set GH_TOKEN}"
GH_REPO="${GH_REPO:-storyforge-ai}"
STAGE="$(mktemp -d)"

echo "==> Staging source (no data, dependencies, caches or voice models)"
tar --exclude='./.git' --exclude='./data' --exclude='**/node_modules' --exclude='**/.venv' \
    --exclude='**/__pycache__' --exclude='**/dist' --exclude='**/temp' \
    --exclude='*.onnx' --exclude='*.zip' --exclude='./docs/screenshots' \
    -cf - -C . . | tar -xf - -C "$STAGE"

cd "$STAGE"
git init -q
git config user.email "storyforge@local"
git config user.name "StoryForge Deploy"
git branch -M main
git add -A
git commit -q -m "StoryForge AI - permanent free deployment"

echo "==> Creating GitHub repository ${GH_USER}/${GH_REPO} (public)"
curl -s -o /tmp/gh-create.json -w "create-repo HTTP %{http_code}\n" \
  -X POST "https://api.github.com/user/repos" \
  -H "Authorization: Bearer ${GH_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -d "{\"name\":\"${GH_REPO}\",\"private\":false,\"description\":\"Free local-first AI story-to-video creator\"}" || true
cat /tmp/gh-create.json | head -c 300; echo

git remote add origin "https://${GH_USER}:${GH_TOKEN}@github.com/${GH_USER}/${GH_REPO}.git"
echo "==> Pushing"
git push -f origin main
echo "==> Done: https://github.com/${GH_USER}/${GH_REPO}"
