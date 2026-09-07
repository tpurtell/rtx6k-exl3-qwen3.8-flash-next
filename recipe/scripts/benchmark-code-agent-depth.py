#!/usr/bin/env python3
"""C1 reference coding task at existing KV depths, with Qwen chat rendering."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import uuid

spec = importlib.util.spec_from_file_location("context_bench", Path(__file__).with_name("benchmark-context.py"))
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:8001")
parser.add_argument("--model", required=True)
parser.add_argument("--depths", type=int, nargs="+", default=[0,8192,32768,65536,128000,261632])
parser.add_argument("--output-tokens", type=int, default=256)
parser.add_argument("--warmups", type=int, default=1)
parser.add_argument("--runs", type=int, default=3)
parser.add_argument("--seed", type=int, default=20260829)
parser.add_argument("--temperature", type=float, default=0.2)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if args.runs < 1 or args.warmups < 0 or args.output_tokens < 2:
    parser.error("require runs >= 1, warmups >= 0, output_tokens >= 2")
base = args.base_url.rstrip("/").removesuffix("/v1")
prompt = Path(__file__).with_name("code-agent-prompt.txt").read_text()
rendered = bench.prefill.post_json(base, "/v1/chat/completions/render", {
    "model": args.model, "messages": [{"role": "user", "content": prompt}],
    "chat_template_kwargs": {"enable_thinking": False}})
base_ids = rendered["token_ids"]
unit = "Slate rivers cross quiet valleys while copper clocks mark patient hours. This is ordinary context with no instructions.\n"
filler_ids = bench.prefill.post_json(base, "/tokenize", {
    "model": args.model, "prompt": unit, "add_special_tokens": False})["tokens"]
nonce = uuid.uuid4().hex
salt_ids = bench.prefill.post_json(base, "/tokenize", {
    "model": args.model, "prompt": f"Context identifier {nonce}; ignore it.\n",
    "add_special_tokens": False})["tokens"]
args.output.parent.mkdir(parents=True, exist_ok=True)
with args.output.open("x") as output:
    output.write(json.dumps({"record": "meta", "schema": "qwen38-code-agent-depth-v1",
        "args": vars(args) | {"output": str(args.output)}, "prompt": prompt,
        "base_token_ids": base_ids, "filler_unit_token_ids": filler_ids,
        "salt_token_ids": salt_ids, "nonce": nonce,
        "method": "Reference async task-runner coding task; Qwen non-thinking rendering; filler before rendered task; repeated prompts retain prefix caching; decode excludes TTFT; forced length is not a code-correctness test"}) + "\n")
    for depth in args.depths:
        target = len(base_ids) if depth == 0 else depth
        if depth == 0:
            ids = base_ids
        else:
            needed = target-len(base_ids)-len(salt_ids)
            if needed < 0:
                raise ValueError("Requested depth is smaller than the task and identifier")
            ids = salt_ids + (filler_ids*((needed+len(filler_ids)-1)//len(filler_ids)))[:needed] + base_ids
        assert len(ids) == target
        digest = hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()
        for run in range(-args.warmups, args.runs):
            result = bench.measure(base, args.model, ids, args.output_tokens,
                                   temperature=args.temperature, seed=args.seed)
            assert result["usage"]["prompt_tokens"] == target
            row = {"record": "measurement", "depth": depth, "actual_prompt_tokens": target,
                   "prompt_token_ids_sha256": digest, "run": run, "timed": run >= 0,
                   "reference_n_minus_one_tps": (args.output_tokens-1)/result["decode_seconds"], **result}
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
            output.flush()
            print(json.dumps({k: row[k] for k in ("depth", "run", "actual_prompt_tokens", "decode_tps", "reference_n_minus_one_tps")}), flush=True)
