#!/usr/bin/env bash
# Native build/run defaults for RTX SM120 and Spark SM121.
case "$(uname -m)" in
  aarch64|arm64)
    DEFAULT_EXL3_MTP_TOKENS=2
    DEFAULT_B12X_VOCAB=1
    PLATFORM_KIND=spark
    DEFAULT_IMAGE=spark-exl3-qwen3.8-flash-next:local
    DEFAULT_RELEASE_IMAGE=ghcr.io/tpurtell/spark-exl3-qwen3.8-flash-next@sha256:0e17cebbff2a95de615f4c1f68ba4e16ad07710164e82c0bf90f044216e8cbd3
    DEFAULT_GPU_MEMORY_UTILIZATION=0.7
    DEFAULT_CUTE_DSL_ARCH=sm_121a
    ;;
  x86_64|amd64)
    DEFAULT_EXL3_MTP_TOKENS=3
    DEFAULT_B12X_VOCAB=0
    PLATFORM_KIND=rtx
    DEFAULT_IMAGE=qwen38-rtx:local
    DEFAULT_RELEASE_IMAGE=ghcr.io/tpurtell/rtx6k-exl3-qwen3.8-flash-next@sha256:bb252820ade1b6aa1316c45485186db90fe67f1d7ea48826169bf92f634d2e73
    DEFAULT_GPU_MEMORY_UTILIZATION=0.94
    DEFAULT_CUTE_DSL_ARCH=sm_120a
    ;;
  *) echo "Unsupported architecture: $(uname -m)" >&2; exit 2 ;;
esac
