#!/usr/bin/env bash
set -euo pipefail
RECIPE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$RECIPE_DIR/model-profiles.sh"
HF_CACHE="${HF_CACHE:-$HOME/.cache/huggingface}"
MODEL_PATH="/root/.cache/huggingface/hub/$MODEL_CACHE_NAME/snapshots/$MODEL_REVISION"
if [[ ! -f "$HF_CACHE/hub/$MODEL_CACHE_NAME/snapshots/$MODEL_REVISION/config.json" ]]; then
  echo "Missing checkpoint. Run QUANT=${QUANT:-exl3} $RECIPE_DIR/download.sh" >&2
  exit 1
fi
EXTRA_ARGS=()
[[ "${ENFORCE_EAGER:-0}" == 1 ]] && EXTRA_ARGS+=(--enforce-eager)
docker run -d --name "${CONTAINER_NAME:-qwen38-${QUANT:-exl3}}" \
  --gpus "device=${GPU:-0}" --ipc=host --network=host \
  -e OMP_NUM_THREADS="${CPU_THREADS:-8}" \
  -e VLLM_PLE_CPU_OFFLOAD=1 -e VLLM_PLE_OFFLOAD_READY_TIMEOUT=1800 \
  -v "$HF_CACHE:/root/.cache/huggingface:ro" \
  "${IMAGE:-qwen38-rtx:local}" "$MODEL_PATH" \
  --served-model-name "qwen38-${QUANT:-exl3}" --port "${PORT:-8001}" \
  --tensor-parallel-size 1 --distributed-executor-backend mp \
  --max-model-len "${MAX_MODEL_LEN:-262144}" \
  --max-num-seqs "${MAX_NUM_SEQS:-16}" \
  --max-num-batched-tokens "${MAX_BATCHED_TOKENS:-2048}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION:-0.94}" \
  --kv-cache-dtype fp8 \
  --speculative-config "{\"method\":\"mtp\",\"num_speculative_tokens\":${MTP_TOKENS:-3}}" \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 \
  "${EXTRA_ARGS[@]}" "$@"
