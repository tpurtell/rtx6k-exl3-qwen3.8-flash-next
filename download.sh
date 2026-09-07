#!/usr/bin/env bash
set -euo pipefail
RECIPE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$RECIPE_DIR/model-profiles.sh"
source "$RECIPE_DIR/platform-config.sh"
HF_CACHE="${HF_CACHE:-$HOME/.cache/huggingface}"
mkdir -p "$HF_CACHE"
docker run --rm --user "$(id -u):$(id -g)" \
  -e HF_HOME=/hf \
  --env MODEL_REPO="$MODEL_REPO" --env MODEL_REVISION="$MODEL_REVISION" \
  -v "$HF_CACHE:/hf" --entrypoint python3 "${IMAGE:-$DEFAULT_IMAGE}" \
  -c 'import os; from huggingface_hub import snapshot_download; print(snapshot_download(os.environ["MODEL_REPO"], revision=os.environ["MODEL_REVISION"]))'
