#!/usr/bin/env bash
set -euo pipefail
RECIPE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$RECIPE_DIR/platform-config.sh"
docker build --progress=plain --build-arg CUTE_DSL_ARCH="$DEFAULT_CUTE_DSL_ARCH" --build-arg B12X_VOCAB="$DEFAULT_B12X_VOCAB" --tag "${IMAGE:-$DEFAULT_IMAGE}" "$RECIPE_DIR"
