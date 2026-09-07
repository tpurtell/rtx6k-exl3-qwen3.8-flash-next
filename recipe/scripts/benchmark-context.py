#!/usr/bin/env python3
"""Measure C1 decode scaling after exact-length, uncached synthetic prompts."""
import argparse
import importlib.util
import json
from pathlib import Path
import time
import urllib.request
import uuid

spec = importlib.util.spec_from_file_location("prefill", Path(__file__).with_name("benchmark-prefill.py"))
prefill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prefill)


def measure(base, model, prompt, output_tokens):
    payload = {"model": model, "prompt": prompt, "temperature": 0,
               "max_tokens": output_tokens, "min_tokens": output_tokens,
               "ignore_eos": True, "stream": True,
               "stream_options": {"include_usage": True}, "return_token_ids": True}
    req = urllib.request.Request(base.rstrip("/") + "/v1/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    chunks, usage, content = [], None, ""
    with urllib.request.urlopen(req, timeout=3600) as response:
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
                content += choice.get("text") or ""
                if choice.get("token_ids"):
                    chunks.append({"seconds": observed, "token_ids": choice["token_ids"]})
    count = sum(len(chunk["token_ids"]) for chunk in chunks)
    if not chunks or not usage or count != output_tokens or count != usage["completion_tokens"]:
        raise RuntimeError(f"Incomplete token evidence: {count=}, {usage=}")
    seconds = chunks[-1]["seconds"] - chunks[0]["seconds"]
    decode_tokens = count - len(chunks[0]["token_ids"])
    return {"usage": usage, "content": content, "chunks": chunks,
            "ttft_seconds": chunks[0]["seconds"], "decode_seconds": seconds,
            "decode_tokens": decode_tokens,
            "decode_tps": decode_tokens / seconds if seconds else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--model", required=True)
    parser.add_argument("--depths", type=int, nargs="+", default=[2048, 8192, 32768, 65536, 131072, 261632])
    parser.add_argument("--output-tokens", type=int, default=256)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.runs < 1 or args.warmups < 0 or args.output_tokens < 2:
        parser.error("require runs >= 1, warmups >= 0 and output tokens >= 2")
    args.base_url = args.base_url.rstrip("/").removesuffix("/v1")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        output.write(json.dumps({"record": "meta", "schema": "qwen38-context-v1",
                                 "args": vars(args) | {"output": str(args.output)},
                                 "workload": "C1 forced-length raw completion; synthetic filler; not a quality test"}) + "\n")
        for depth in args.depths:
            for run in range(-args.warmups, args.runs):
                nonce = uuid.uuid4().hex
                prompt = prefill.exact_prompt(args.base_url, args.model, depth, nonce)
                result = measure(args.base_url, args.model, prompt, args.output_tokens)
                if result["usage"]["prompt_tokens"] != depth:
                    raise RuntimeError("Server prompt-token count differs from requested depth")
                row = {"record": "measurement", "depth": depth, "run": run,
                       "timed": run >= 0, "nonce": nonce, **result}
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
                output.flush()
                print(json.dumps({k: row[k] for k in ("depth", "run", "ttft_seconds", "decode_tps")}), flush=True)


if __name__ == "__main__":
    main()
