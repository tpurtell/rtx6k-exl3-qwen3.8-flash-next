#!/usr/bin/env bash
set -euo pipefail
RECIPE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$RECIPE_DIR/model-profiles.sh"
HF_CACHE="${HF_CACHE:-$HOME/.cache/huggingface}"
RUNTIME_CACHE="${RUNTIME_CACHE:-$HOME/.cache/qwen38-rtx/${QUANT:-exl3}}"
mkdir -p "$RUNTIME_CACHE"
MODEL_PATH="/root/.cache/huggingface/hub/$MODEL_CACHE_NAME/snapshots/$MODEL_REVISION"
if [[ ! -f "$HF_CACHE/hub/$MODEL_CACHE_NAME/snapshots/$MODEL_REVISION/config.json" ]]; then
  echo "Missing checkpoint. Run QUANT=${QUANT:-exl3} $RECIPE_DIR/download.sh" >&2
  exit 1
fi
EXTRA_ARGS=()
[[ "${ENFORCE_EAGER:-0}" == 1 ]] && EXTRA_ARGS+=(--enforce-eager)
if [[ "${MTP_TOKENS:-3}" != 0 ]]; then
  EXTRA_ARGS+=(--speculative-config "{\"method\":\"mtp\",\"num_speculative_tokens\":${MTP_TOKENS:-3}}")
fi
docker run -d --name "${CONTAINER_NAME:-qwen38-${QUANT:-exl3}}" \
  --gpus "device=${GPU:-0}" --ipc=host --network=host \
  -e OMP_NUM_THREADS="${CPU_THREADS:-8}" \
  -e CUDA_CACHE_PATH=/root/.cache/cuda \
  -e TRITON_CACHE_DIR=/root/.cache/triton \
  -e VLLM_PLE_CPU_OFFLOAD=1 -e VLLM_PLE_OFFLOAD_READY_TIMEOUT=1800 \
  -v "$RUNTIME_CACHE:/root/.cache" \
  -v "$HF_CACHE:/root/.cache/huggingface:ro" \
  "${IMAGE:-qwen38-rtx:local}" "$MODEL_PATH" \
  --served-model-name "qwen38-${QUANT:-exl3}" --port "${PORT:-8001}" \
  --tensor-parallel-size 1 --distributed-executor-backend mp \
  --max-model-len "${MAX_MODEL_LEN:-262144}" \
  --max-num-seqs "${MAX_NUM_SEQS:-16}" \
  --max-num-batched-tokens "${MAX_BATCHED_TOKENS:-2048}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION:-0.94}" \
  --kv-cache-dtype fp8 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 \
  "${EXTRA_ARGS[@]}" "$@"
