#!/usr/bin/env bash
# Install the pinned native image under the same local name used by build/start.
set -euo pipefail
RECIPE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$RECIPE_DIR/platform-config.sh"
SOURCE_IMAGE="${RELEASE_IMAGE:-$DEFAULT_RELEASE_IMAGE}"
docker pull "$SOURCE_IMAGE"
docker tag "$SOURCE_IMAGE" "${IMAGE:-$DEFAULT_IMAGE}"
