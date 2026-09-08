#!/usr/bin/env bash
# Native build/run defaults for RTX SM120 and Spark SM121.
case "$(uname -m)" in
  aarch64|arm64)
    DEFAULT_EXL3_MTP_TOKENS=2
    DEFAULT_B12X_VOCAB=1
    PLATFORM_KIND=spark
    DEFAULT_IMAGE=spark-exl3-qwen3.8-flash-next:local
    DEFAULT_RELEASE_IMAGE=ghcr.io/tpurtell/spark-exl3-qwen3.8-flash-next@sha256:67f7b104711451878e5af188195c7ac675e79246aab65ff36bb9919bcdffeb33
    DEFAULT_GPU_MEMORY_UTILIZATION=0.7
    DEFAULT_CUTE_DSL_ARCH=sm_121a
    ;;
  x86_64|amd64)
    DEFAULT_EXL3_MTP_TOKENS=3
    DEFAULT_B12X_VOCAB=0
    PLATFORM_KIND=rtx
    DEFAULT_IMAGE=qwen38-rtx:local
    DEFAULT_RELEASE_IMAGE=ghcr.io/tpurtell/rtx6k-exl3-qwen3.8-flash-next@sha256:0f3fdb9e1073446ca756db7541bbcfe943a7e5c43aa97e85cbcba982d82b7516
    DEFAULT_GPU_MEMORY_UTILIZATION=0.94
    DEFAULT_CUTE_DSL_ARCH=sm_120a
    ;;
  *) echo "Unsupported architecture: $(uname -m)" >&2; exit 2 ;;
esac
