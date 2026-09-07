#!/usr/bin/env python3
"""Measure aggregate pure-decode throughput at selected concurrencies."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import statistics
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
import uuid


def request_once(
    base_url: str, model: str, concurrency: int, output_tokens: int, seed: int,
    nonce: str = "",
) -> dict:
    parsed = urlparse(base_url)
    connection_type = (
        http.client.HTTPSConnection
        if parsed.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = connection_type(parsed.hostname, parsed.port, timeout=3600)
    path = parsed.path.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": (
                    (f"Ignore this request identifier: {nonce}.\n" if nonce else "") +
                    "Write a long, coherent continuation about systems engineering, "
                    "without headings or a conclusion."
                ),
            }
        ],
        "chat_template_kwargs": {"enable_thinking": False},
        "n": concurrency,
        "max_tokens": output_tokens,
        "min_tokens": output_tokens,
        "ignore_eos": True,
        "temperature": 0.7,
        "seed": seed,
        "stream": True,
        "stream_options": {"include_usage": True},
        "return_token_ids": True,
        "cache_prompt": False,
    }
    started = time.perf_counter()
    connection.request(
        "POST",
        path,
        body=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    response = connection.getresponse()
    if response.status != 200:
        error = response.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {response.status}: {error}")

    token_times: list[list[float]] = [[] for _ in range(concurrency)]
    completion_tokens = None
    while True:
        raw_line = response.readline()
        if not raw_line:
            break
        observed = time.perf_counter()
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        event = json.loads(data)
        if isinstance(event.get("usage"), dict):
            completion_tokens = event["usage"].get("completion_tokens")
        for choice in event.get("choices", []):
            index = choice.get("index")
            if not isinstance(index, int) or not 0 <= index < concurrency:
                continue
            token_ids = choice.get("token_ids")
            if isinstance(token_ids, list):
                token_times[index].extend([observed] * len(token_ids))
    connection.close()

    expected = concurrency * output_tokens
    observed_tokens = sum(len(times) for times in token_times)
    if observed_tokens != expected:
        raise RuntimeError(
            f"stream exposed {observed_tokens} token IDs, expected {expected}; "
            f"usage reported {completion_tokens}"
        )
    first_token = min(times[0] for times in token_times if times)
    last_token = max(times[-1] for times in token_times if times)
    duration = last_token - first_token
    decode_tokens = sum(len(times) - 1 for times in token_times)
    return {
        "concurrency": concurrency,
        "request_nonce": nonce,
        "started_perf_seconds": started,
        "token_times_seconds": [[t - started for t in times] for times in token_times],
        "timing_convention": "sum(N-1) over global first-to-last SSE token window",
        "output_tokens_per_sequence": output_tokens,
        "completion_tokens": completion_tokens,
        "decode_tokens": decode_tokens,
        "decode_seconds": duration,
        "decode_tokens_per_second": decode_tokens / duration,
        "ttft_ms": (first_token - started) * 1000,
    }


def independent_clients(base_url, model, concurrency, output_tokens, seed):
    barrier = threading.Barrier(concurrency)
    nonce = uuid.uuid4().hex

    def worker(index):
        barrier.wait()
        return request_once(base_url, model, 1, output_tokens, seed + index,
                            nonce=f"{nonce}:{index}")

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(worker, range(concurrency)))
    first = min(r["started_perf_seconds"] + r["token_times_seconds"][0][0] for r in results)
    last = max(r["started_perf_seconds"] + r["token_times_seconds"][0][-1] for r in results)
    tokens = sum(r["decode_tokens"] for r in results)
    events = []
    for result in results:
        times = result["token_times_seconds"][0]
        start = result["started_perf_seconds"]
        events.extend(((start + times[0], 1), (start + times[-1], -1)))
    active = peak = 0
    for _, delta in sorted(events):
        active += delta
        peak = max(peak, active)
    return {"concurrency": concurrency, "request_mode": "clients",
            "peak_overlapping_stream_intervals": peak,
            "decode_tokens": tokens, "decode_seconds": last - first,
            "decode_tokens_per_second": tokens / (last - first),
            "request_results": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--profile", required=True, choices=["nvfp4", "exl3"])
    parser.add_argument("--mtp-tokens", type=int, required=True)
    parser.add_argument(
        "--mtp-policy",
        choices=["off", "static", "adaptive"],
        default="static",
    )
    parser.add_argument("--concurrency", nargs="+", type=int, default=[1, 16])
    parser.add_argument("--request-mode", choices=["continuations", "clients"], default="continuations")
    parser.add_argument("--output-tokens", type=int, default=128)
    parser.add_argument(
        "--warmup-tokens",
        type=int,
        default=0,
        help="warmup length; 0 uses --output-tokens so the full decode path is warm",
    )
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=2,
        help="full warmup requests per concurrency (two covers lazy JIT shapes)",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260828)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.concurrency) < 1 or args.output_tokens < 2:
        parser.error("concurrency must be positive and output tokens >= 2")
    runner = independent_clients if args.request_mode == "clients" else request_once

    points = []
    warmup_tokens = args.warmup_tokens or args.output_tokens
    for concurrency in args.concurrency:
        for _ in range(args.warmup_runs):
            runner(
                args.base_url, args.model, concurrency, warmup_tokens, args.seed
            )
        runs = []
        for run in range(args.runs):
            result = runner(
                args.base_url,
                args.model,
                concurrency,
                args.output_tokens,
                args.seed,
            )
            runs.append(result)
            print(
                f"{args.profile} {args.mtp_policy} MTP{args.mtp_tokens} "
                f"C{concurrency} "
                f"run {run + 1}/{args.runs}: "
                f"{result['decode_tokens_per_second']:.2f} tok/s",
                flush=True,
            )
        rates = [run["decode_tokens_per_second"] for run in runs]
        points.append(
            {
                "concurrency": concurrency,
                "aggregate_decode_tokens_per_second": {
                    "median": statistics.median(rates),
                    "min": min(rates),
                    "max": max(rates),
                },
                "runs": runs,
            }
        )

    report = {
        "schema": "qwen38-decode-concurrency.v3",
        "request_mode": args.request_mode,
        "method": (
            ("separate HTTP requests with unique prompt identifiers; " if args.request_mode == "clients"
             else "one short prompt with n parallel continuations; ") +
            "aggregate decode uses sum(N-1) over the global first-to-last SSE token window; "
            "sampling seeds are fixed per sequence"
        ),
        "model": args.model,
        "quant_profile": args.profile,
        "kv_cache_dtype": "fp8",
        "mtp_tokens": args.mtp_tokens,
        "mtp_policy": args.mtp_policy,
        "output_tokens_per_sequence": args.output_tokens,
        "warmup_runs_per_point": args.warmup_runs,
        "runs_per_point": args.runs,
        "points": points,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
