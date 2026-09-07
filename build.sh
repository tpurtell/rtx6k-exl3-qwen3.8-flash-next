#!/usr/bin/env bash
set -euo pipefail
RECIPE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
docker build --progress=plain --tag "${IMAGE:-qwen38-rtx:local}" "$RECIPE_DIR"
