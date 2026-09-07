#!/usr/bin/env bash
# Quality-only qualification for the additional EXL3 FP8-PLE checkpoint.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
MODEL="${MODEL:-qwen38-exl3-ple8}"
RESULT_DIR="${RESULT_DIR:?Set a new result directory}"
[[ ! -e "$RESULT_DIR" ]] || { echo "Results already exist: $RESULT_DIR" >&2; exit 1; }
mkdir -p "$RESULT_DIR"
COMMON=(--base-url "$BASE_URL" --model "$MODEL")
python3 "$SCRIPT_DIR/test-api-tool-constraints.py" "${COMMON[@]}" --output "$RESULT_DIR/api-tools.jsonl"
python3 "$SCRIPT_DIR/test-vision-vllm.py" "${COMMON[@]}" --image-counts 1 4 16 --output "$RESULT_DIR/vision.json"
# Preserve responses and incidental request timings; do not infer performance equivalence.
python3 "$SCRIPT_DIR/benchmark-workloads.py" "${COMMON[@]}" --suite seven --runs 3 --warmups 0 --output "$RESULT_DIR/seven.jsonl"
python3 "$SCRIPT_DIR/benchmark-workloads.py" "${COMMON[@]}" --suite orchid --runs 5 --warmups 0 --output "$RESULT_DIR/orchid.jsonl"
python3 "$SCRIPT_DIR/test-context-retrieval.py" "${COMMON[@]}" --filler-tokens 8192 240000 --positions 0.05 0.5 0.95 --output "$RESULT_DIR/retrieval.jsonl"
# Run the pinned full tool-eval-bench suite separately, including Hard Mode.
