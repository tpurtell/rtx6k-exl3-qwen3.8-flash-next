#!/usr/bin/env bash
set -euo pipefail
docker stop "${CONTAINER_NAME:-qwen38-${QUANT:-exl3}}"
