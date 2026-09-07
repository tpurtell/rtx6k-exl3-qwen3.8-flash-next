#!/usr/bin/env python3
"""Check exact-key retrieval at several locations in a long synthetic archive."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import uuid


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


prefill = module("prefill", "benchmark-prefill.py")
workloads = module("workloads", "benchmark-workloads.py")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--model", required=True)
    parser.add_argument("--filler-tokens", type=int, nargs="+", default=[8192, 131072, 240000])
    parser.add_argument("--positions", type=float, nargs="+", default=[0.05, 0.5, 0.95])
    parser.add_argument("--seed", type=int, default=787)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(not 0 <= position <= 1 for position in args.positions):
        parser.error("positions must be between zero and one")
    args.base_url = args.base_url.rstrip("/").removesuffix("/v1")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    passed = True
    with args.output.open("x") as output:
        output.write(json.dumps({"record": "meta", "schema": "qwen38-context-retrieval-v1",
                                 "args": vars(args) | {"output": str(args.output)},
                                 "method": "one synthetic key per prompt; positions are character fractions of filler; actual prompt length comes from server usage"}) + "\n")
        for depth in args.filler_tokens:
            for position in args.positions:
                nonce = uuid.uuid4().hex
                key = hashlib.sha256(f"{args.seed}:{depth}:{position}".encode()).hexdigest()[:20]
                filler = prefill.exact_prompt(args.base_url, args.model, depth, nonce)
                offset = round(len(filler) * position)
                prompt = (
                    "Read this archive and find its ARCHIVE_VERIFICATION_KEY.\n"
                    + filler[:offset] + f"\nARCHIVE_VERIFICATION_KEY = {key}\n"
                    + filler[offset:]
                    + "\nEnd of archive. Return only the exact ARCHIVE_VERIFICATION_KEY, without explanation."
                )
                result = workloads.request(args.base_url, args.model, prompt, 128)
                correct = result["content"].strip() == key
                passed &= correct
                row = {"record": "measurement", "filler_tokens": depth,
                       "position_fraction": position, "character_offset": offset,
                       "nonce": nonce, "expected_key": key,
                       "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                       "passed": correct, **result}
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
                output.flush()
                print(json.dumps({"filler_tokens": depth, "position": position,
                                  "prompt_tokens": result["usage"]["prompt_tokens"],
                                  "passed": correct, "response": result["content"]}), flush=True)
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
