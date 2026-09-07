#!/usr/bin/env bash
# Run on an otherwise idle endpoint. Tool-eval-bench is a separate pinned suite.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
QUANT="${QUANT:?Set QUANT=exl3 or nvfp4}"
MTP_TOKENS="${MTP_TOKENS:?Set the tested maximum draft length}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
BASE_URL="${BASE_URL%/}"
BASE_URL="${BASE_URL%/v1}"
RESULT_DIR="${RESULT_DIR:?Set a new result directory}"
if [[ -e "$RESULT_DIR" ]]; then
  echo "Refusing to overwrite existing results: $RESULT_DIR" >&2
  exit 1
fi
mkdir -p "$RESULT_DIR"
MODEL="qwen38-$QUANT"
COMMON=(--base-url "$BASE_URL" --model "$MODEL")
MTP_METRICS=()
[[ "$MTP_TOKENS" != 0 ]] && MTP_METRICS+=(--collect-mtp-metrics)
python3 "$SCRIPT_DIR/test-api-tool-constraints.py" "${COMMON[@]}" --output "$RESULT_DIR/api-tools.jsonl"
python3 "$SCRIPT_DIR/test-vision-vllm.py" "${COMMON[@]}" --image-counts 1 4 16 --output "$RESULT_DIR/vision.json"
python3 "$SCRIPT_DIR/benchmark-workloads.py" "${COMMON[@]}" --suite seven --runs 3 --warmups 1 "${MTP_METRICS[@]}" --output "$RESULT_DIR/seven.jsonl"
python3 "$SCRIPT_DIR/benchmark-workloads.py" "${COMMON[@]}" --suite orchid --runs 5 --warmups 1 "${MTP_METRICS[@]}" --output "$RESULT_DIR/orchid.jsonl"
python3 "$SCRIPT_DIR/benchmark-decode.py" --base-url "$BASE_URL/v1" --model "$MODEL" --profile "$QUANT" --mtp-tokens "$MTP_TOKENS" --mtp-policy "${MTP_POLICY:-static}" --concurrency 1 2 4 8 16 --request-mode clients --output-tokens 256 --warmup-runs 2 --runs 3 --output "$RESULT_DIR/clients.json"
python3 "$SCRIPT_DIR/benchmark-prefill.py" --base-url "$BASE_URL/v1" --model "$MODEL" --profile "$QUANT" --prompt-tokens 2048 8192 32768 65536 128000 261632 --runs 3 --output "$RESULT_DIR/prefill.json"
python3 "$SCRIPT_DIR/benchmark-context.py" "${COMMON[@]}" --depths 2048 8192 32768 65536 131072 261632 --output-tokens 256 --runs 3 --warmups 1 --output "$RESULT_DIR/context.jsonl"
python3 "$SCRIPT_DIR/benchmark-context.py" "${COMMON[@]}" --depths 261888 --output-tokens 256 --runs 1 --warmups 0 --output "$RESULT_DIR/context-boundary.jsonl"
python3 "$SCRIPT_DIR/test-context-retrieval.py" "${COMMON[@]}" --filler-tokens 8192 240000 --positions 0.05 0.5 0.95 --output "$RESULT_DIR/retrieval.jsonl"
python3 "$SCRIPT_DIR/benchmark-code-agent-depth.py" "${COMMON[@]}" --output "$RESULT_DIR/code-agent.jsonl"
