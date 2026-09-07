#!/usr/bin/env bash
case "${QUANT:-exl3}" in
  exl3)
    MODEL_REPO=wrldsuksgo2mars/Qwen3.8-Flash-Next-EXL3-K4.25-v1
    MODEL_REVISION=73a050c27b8c488c65acd6d1c74e45ff02be5fab
    ;;
  nvfp4)
    MODEL_REPO=nvidia/Qwen3.8-Flash-Next-NVFP4
    MODEL_REVISION=2061e0b0c5d92bdf7c8fbd4241bbc2af239d7e2d
    ;;
  *) echo "QUANT must be exl3 or nvfp4" >&2; exit 2 ;;
esac
MODEL_CACHE_NAME="models--${MODEL_REPO//\//--}"
