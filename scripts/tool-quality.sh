#!/usr/bin/env bash
# Persist the complete pinned 88-case suite, including all 19 Hard Mode cases.
set -euo pipefail
TOOL_EVAL_DIR="${TOOL_EVAL_DIR:?Set path to tool-eval-bench checkout with its uv environment}"
EXPECTED=cf54b4bfe705f12f71e8866f10730572497c8105
[[ $(git -C "$TOOL_EVAL_DIR" rev-parse HEAD) == "$EXPECTED" ]] || { echo "Expected tool-eval-bench $EXPECTED" >&2; exit 1; }
RESULT_DIR="$(realpath "${RESULT_DIR:?Set existing qualification result directory}")"
[[ ! -e "$RESULT_DIR/tools.json" ]] || { echo "Tools result already exists" >&2; exit 1; }
BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
BASE_URL="${BASE_URL%/}"
BASE_URL="${BASE_URL%/v1}"
cd "$TOOL_EVAL_DIR"
.venv/bin/tool-eval-bench run --model "${MODEL:?Set served model alias}" \
  --backend vllm --base-url "$BASE_URL/v1" --hardmode --parallel 8 \
  --timeout 900 --max-turns 8 --trials 1 --temperature 0 \
  --reference-date 2026-09-07 \
  --backend-kwargs '{"chat_template_kwargs":{"enable_thinking":true}}' \
  --json-file "$RESULT_DIR/tools.json" --no-live
python3 - "$RESULT_DIR" <<'PY'
import json, shutil, sys
from pathlib import Path
root = Path(sys.argv[1])
result = json.loads((root / 'tools.json').read_text())
assert result['status'] == 'completed' and result['total_scenarios'] == 88
shutil.copyfile(result['report_path'], root / 'tools.md')
PY
