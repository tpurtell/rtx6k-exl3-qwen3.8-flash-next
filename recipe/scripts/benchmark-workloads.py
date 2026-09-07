#!/usr/bin/env python3
"""Stream seven semantic workloads or orchid repeats with auditable client timings."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import statistics
import sys
import time
import urllib.request

spec = importlib.util.spec_from_file_location("contracts", Path(__file__).with_name("test-content-vllm.py"))
contracts = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = contracts
spec.loader.exec_module(contracts)


def request(base, model, prompt, max_tokens):
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "temperature": 0, "max_tokens": max_tokens,
               "chat_template_kwargs": {"enable_thinking": False},
               "stream": True, "stream_options": {"include_usage": True},
               "return_token_ids": True}
    started = time.perf_counter()
    req = urllib.request.Request(base.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    chunks, content, usage, finish = [], "", None, None
    with urllib.request.urlopen(req, timeout=900) as response:
        for line in response:
            if not line.startswith(b"data:"):
                continue
            raw = line[5:].strip()
            if raw == b"[DONE]":
                break
            event = json.loads(raw)
            observed = time.perf_counter() - started
            if event.get("usage"):
                usage = event["usage"]
            for choice in event.get("choices", []):
                delta = choice.get("delta", {})
                content += delta.get("content") or ""
                ids = choice.get("token_ids")
                if ids:
                    chunks.append({"seconds": observed, "token_ids": ids})
                finish = choice.get("finish_reason") or finish
    elapsed = time.perf_counter() - started
    count = sum(len(chunk["token_ids"]) for chunk in chunks)
    if not chunks or not usage or count != usage["completion_tokens"]:
        raise RuntimeError(f"Incomplete token timing evidence: stream={count}, usage={usage}")
    duration = chunks[-1]["seconds"] - chunks[0]["seconds"]
    # Exclude all tokens delivered in the initial speculative burst. Also
    # retain the conventional N-1 measure for comparison with reference runs.
    decode_tokens = count - len(chunks[0]["token_ids"])
    return {"content": content, "usage": usage, "finish_reason": finish,
            "elapsed_seconds": elapsed, "ttft_seconds": chunks[0]["seconds"],
            "decode_seconds": duration, "decode_tokens": decode_tokens,
            "decode_tps": decode_tokens / duration if duration > 0 else None,
            "n_minus_one_tps": (count - 1) / duration if duration > 0 else None,
            "chunks": chunks}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--model", required=True)
    parser.add_argument("--suite", choices=("seven", "orchid"), required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--seed", type=int, default=787)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.runs < 1 or args.warmups < 0:
        parser.error("runs must be positive and warmups nonnegative")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cases = contracts.CASES if args.suite == "seven" else {
        "orchid": contracts.PromptCase("repeat", 'Repeat only the single word "orchid" exactly 100 times, separated by spaces. Do not add any other text.', 1500)}
    records = []
    with args.output.open("x") as destination:
        destination.write(json.dumps({"record": "meta", "schema": "qwen38-workloads-v1",
                                     "args": vars(args) | {"output": str(args.output)},
                                     "timing": "client SSE chunks; decode excludes initial burst; raw token IDs retained"}) + "\n")
        for run in range(-args.warmups, args.runs):
            for name, case in cases.items():
                nonce = hashlib.sha256(f"{args.seed}:{run}:{name}".encode()).hexdigest()[:16]
                prompt = f"Nonce {nonce}; ignore this identifier.\n{case.prompt}"
                result = request(args.base_url, args.model, prompt, case.max_tokens)
                if name == "orchid":
                    words = result["content"].strip().split()
                    contract = {"pass": words == ["orchid"] * 100,
                                "occurrences": len(re.findall(r"\borchid\b", result["content"]))}
                else:
                    contract = contracts.validate_case_content(name, result["content"])
                row = {"record": "measurement", "run": run, "timed": run >= 0,
                       "case": name, "prompt": prompt, "contract": contract, **result}
                destination.write(json.dumps(row, ensure_ascii=False) + "\n")
                destination.flush()
                if run >= 0:
                    records.append(row)
                print(json.dumps({"run": run, "case": name, "contract": contract,
                                  "decode_tps": result["decode_tps"]}), flush=True)
        total_seconds = sum(row["decode_seconds"] for row in records)
        summary = {"record": "summary", "weighted_decode_tps":
                   sum(row["decode_tokens"] for row in records) / total_seconds if total_seconds else None,
                   "median_tps_by_case": {name: (statistics.median(values) if values else None)
                       for name in cases
                       for values in [[row["decode_tps"] for row in records
                                       if row["case"] == name and row["decode_tps"] is not None]]}}
        destination.write(json.dumps(summary) + "\n")


if __name__ == "__main__":
    main()
