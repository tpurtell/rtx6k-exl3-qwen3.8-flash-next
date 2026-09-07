#!/usr/bin/env python3
"""Render the final benchmark tables directly from complete raw receipts."""
import argparse
import json
import os
from pathlib import Path
import statistics

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--exl3", type=Path, required=True)
parser.add_argument("--nvfp4", type=Path, required=True)
parser.add_argument("--mmap", type=Path, help="New mmap-enabled EXL3 PLE8 qualification; original profiles retain their existing receipts")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
roots = {"EXL3": args.exl3, "NVFP4": args.nvfp4}
if args.mmap:
    roots["EXL3 PLE8 mmap"] = args.mmap
lines = ["# Final serving measurements", "",
         "Generated from the linked raw receipts by `scripts/summarize-results.py`.", "",
         "Each quant runs on one RTX PRO 6000 Blackwell 96 GB at a 400 W power limit. "
         "C1 is the default-selection priority. All use FP8 KV and host token embeddings. "
         "The mmap profile reads PLE rows from checkpoint-backed mappings; the original "
         "profiles retain resident host tables. All decode rates below exclude prefill.", ""]
if args.mmap:
    lines += ["EXL3 and NVFP4 columns retain the v0.1.0 measurements; only the mmap-enabled "
              "EXL3 PLE8 column is newly benchmarked. The EXL3 baseline also has a different "
              "PLE storage precision, so this is not a controlled mmap-on/off ablation. "
              "The mmap run uses existing Linux page cache and benchmark warmups; it is "
              "not a cold-disk or constrained-RAM test.", ""]

def read(root, name):
    path = root / name
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text().splitlines() if line]
    return json.loads(path.read_text())

def timed(rows):
    return [r for r in rows if r.get("record") == "measurement" and r.get("timed")]

def link(label, root, name):
    path = os.path.relpath(root / name, args.output.parent)
    return f"[{label}]({path})"

def table(headers, rows):
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    lines.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    lines.append("")

def spread(values, digits=2):
    return f"{statistics.median(values):.{digits}f} ({min(values):.{digits}f}–{max(values):.{digits}f})"

def weighted(rows):
    return sum(r["decode_tokens"] for r in rows) / sum(r["decode_seconds"] for r in rows)

lines += ["## Profiles", ""]
profile_rows = []
for name, root in roots.items():
    runtime = read(root, "runtime.json")
    argv = runtime["args"]
    spec = json.loads(argv[argv.index("--speculative-config")+1])
    memory = argv[argv.index("--gpu-memory-utilization")+1]
    env = runtime["selected_environment"]
    mmap = "VLLM_PLE_MMAP=1" in env
    if name == "EXL3 PLE8 mmap":
        assert mmap and "VLLM_PLE_CPU_OFFLOAD=0" in env
        assert any("PLE mmap:" in line and "attached" in line for line in runtime["selected_startup_lines"])
    serial = next((v.split("=",1)[1] for v in env if v.startswith("VLLM_PLE_MMAP_SERIAL=")), "—") if mmap else "—"
    profile_rows.append([name, spec["num_speculative_tokens"], memory,
                         "mmap" if mmap else "resident", serial,
                         link("runtime", root, "runtime.json")])
table(["Profile", "MTP draft tokens", "GPU memory fraction", "PLE storage", "Serial threshold", "Configuration"], profile_rows)

lines += ["## Seven content workloads: C1", "",
          "One warmup and three measured responses per workload, temperature zero and "
          "thinking disabled. Values are median tokens/s (minimum–maximum). The weighted "
          "blend is total post-initial-burst tokens divided by their total decode time. "
          "Rates include failed output contracts and are not successful-task throughput.", ""]
seven = {name: timed(read(root, "seven.jsonl")) for name, root in roots.items()}
cases = ("code", "math", "fable", "hello", "topic", "structured-json", "multilingual")
workload_rows = []
for case in cases:
    row = [case]
    for name in roots:
        samples = [r for r in seven[name] if r["case"] == case]
        assert len(samples) == 3, (name, case, len(samples))
        passed = sum(r["contract"]["quality_contract_passed"] for r in samples)
        row += [spread([r["decode_tps"] for r in samples]), f"{passed}/3"]
    workload_rows.append(row)
table(["Workload"] + [h for n in roots for h in (n+" tokens/s", "Contract")], workload_rows)
table(["Quant", "Weighted blend", "Draft acceptance", "Mean acceptance length", "Raw"], [
    [name, f"{weighted(seven[name]):.2f}",
     f"{next(r for r in read(root, 'seven.jsonl') if r['record']=='mtp_after')['timed_suite_delta']['acceptance_rate']*100:.2f}%",
     f"{next(r for r in read(root, 'seven.jsonl') if r['record']=='mtp_after')['timed_suite_delta']['mean_acceptance_length']:.3f}",
     link("responses and timings", root, "seven.jsonl")]
    for name, root in roots.items()])
lines += ["The code contract checks syntax and required assertions; it does not execute "
          "the generated code. The Chinese terminology check is a literal-phrase proxy "
          "and can reject a correct paraphrase. All rejected responses remain in the raw files.", ""]

lines += ["## Orchid repetition: C1", "",
          "The prompt requests exactly 100 space-separated `orchid` words, with a "
          "1500-token output cap. One warmup precedes five measured runs. Counts and "
          "contract failures are retained; a fast incorrect repetition is not a task success.", ""]
orchid_rows = []
for name, root in roots.items():
    samples = timed(read(root, "orchid.jsonl"))
    assert len(samples) == 5
    orchid_rows.append([name, ", ".join(str(r["contract"]["occurrences"]) for r in samples),
        f"{sum(r['contract']['pass'] for r in samples)}/5",
        spread([r["decode_tps"] for r in samples]), link("responses", root, "orchid.jsonl")])
table(["Quant", "Word counts", "Exact contract", "Decode tokens/s", "Raw"], orchid_rows)

lines += ["## Sampled prose: independent clients", "",
          "Each client requests 256 forced output tokens at temperature 0.7 with fixed "
          "sampling seeds and thinking disabled. Two full warmups and three "
          "measurements per concurrency. Aggregate rate divides the sum of each client's "
          "N−1 tokens by the whole batch's first-to-last token window. Overlap counts "
          "come from client stream intervals, not a GPU occupancy gauge.", ""]
clients = {name: read(root, "clients.json") for name, root in roots.items()}
client_rows = []
for concurrency in (1, 2, 4, 8, 16):
    row = [concurrency]
    for name in roots:
        point = next(p for p in clients[name]["points"] if p["concurrency"] == concurrency)
        runs = point["runs"]
        assert len(runs) == 3
        overlap = [r["peak_overlapping_stream_intervals"] for r in runs]
        row += [spread([r["decode_tokens_per_second"] for r in runs]), f"{min(overlap)}–{max(overlap)}"]
    client_rows.append(row)
table(["Clients"] + [h for n in roots for h in (n+" aggregate tokens/s", "Overlap")], client_rows)
lines += ["Raw: " + ", ".join(link(name, root, "clients.json") for name, root in roots.items()) + ".", ""]

lines += ["## Prefill matrix: C1", "",
          "Exact prompt lengths, unique first cache blocks and three measurements after "
          "a warmup at each depth. Effective prompt tokens/s includes server tokenization "
          "and the handoff of the first output token; it is not isolated GPU prefill time.", ""]
prefill = {name: read(root, "prefill.json") for name, root in roots.items()}
prefill_rows = []
for depth in (2048, 8192, 32768, 65536, 128000, 261632):
    row = [depth]
    for name in roots:
        point = next(p for p in prefill[name]["points"] if p["prompt_tokens"] == depth)
        row += [spread([r["effective_prompt_tokens_per_second"] for r in point["runs"]], 1),
                spread([r["ttft_seconds"] for r in point["runs"]], 3)]
    prefill_rows.append(row)
table(["Prompt tokens"] + [h for n in roots for h in (n+" tokens/s", n+" TTFT, s")], prefill_rows)
lines += ["Raw: " + ", ".join(link(name, root, "prefill.json") for name, root in roots.items()) + ".", ""]

lines += ["## Context and decode scaling: C1", "",
          "Synthetic filler followed by 256 forced output tokens. One warmup and three "
          "measurements at each depth; median (minimum–maximum). This measures serving "
          "capacity and speed, not long-context reasoning quality.", ""]
context = {name: timed(read(root, "context.jsonl")) for name, root in roots.items()}
context_rows = []
for depth in (2048, 8192, 32768, 65536, 131072, 261632):
    row = [depth]
    for name in roots:
        samples = [r for r in context[name] if r["depth"] == depth]
        assert len(samples) == 3
        row += [spread([r["decode_tps"] for r in samples]), spread([r["ttft_seconds"] for r in samples], 3)]
    context_rows.append(row)
table(["Prompt tokens"] + [h for n in roots for h in (n+" decode tokens/s", n+" TTFT, s")], context_rows)
lines += ["Raw: " + ", ".join(link(name, root, "context.jsonl") for name, root in roots.items()) + ".", ""]
lines += ["## Reference coding task: C1 across KV depths", "",
          "The async task-runner prompt is identical to the reference recipe. Qwen's "
          "native non-thinking template replaces GLM's template. Temperature is 0.2, "
          "with a fixed seed and 256 forced output tokens. One warmup precedes three "
          "measurements per depth. Prompts repeat to retain existing KV; these TTFTs "
          "are not uncached prefill measurements. Rates use the reference's N−1 token "
          "convention; raw receipts also retain the rate excluding the whole initial "
          "SSE burst. The fixed token cap is not a generated-code correctness test.", ""]
coding = {name: timed(read(root, "code-agent.jsonl")) for name, root in roots.items()}
coding_rows = []
for depth in (0, 8192, 32768, 65536, 128000, 261632):
    row = ["Task only" if depth == 0 else depth]
    for name in roots:
        samples = [r for r in coding[name] if r["depth"] == depth]
        assert len(samples) == 3
        row.append(spread([r["reference_n_minus_one_tps"] for r in samples]))
    coding_rows.append(row)
table(["Prompt depth"] + [n+" decode tokens/s" for n in roots], coding_rows)
lines += ["Raw: " + ", ".join(link(name, root, "code-agent.jsonl") for name, root in roots.items()) + ".", ""]
for name, root in roots.items():
    boundary = timed(read(root, "context-boundary.jsonl"))
    assert len(boundary) == 1
    usage = boundary[0]["usage"]
    assert usage["prompt_tokens"] == 261888 and usage["completion_tokens"] == 256
    lines += [f"{name} also returned all 256 requested tokens after a 261888-token prompt "
              f"at the exact 262144-token boundary: {link('receipt', root, 'context-boundary.jsonl')}.", ""]

lines += ["## Functional and tool checks", ""]
functional = []
tool_rows = []
for name, root in roots.items():
    api = [r for r in read(root, "api-tools.jsonl") if r.get("record") == "measurement"]
    vision = read(root, "vision.json")["supported_image_counts"]
    retrieval = [r for r in read(root, "retrieval.jsonl") if r.get("record") == "measurement"]
    functional.append([name, f"{sum(r['passed'] for r in api)}/{len(api)}",
        ", ".join(f"{n}: {'pass' if vision[str(n)]['passed'] else 'fail'}" for n in (1,4,16)),
        f"{sum(r['passed'] for r in retrieval)}/{len(retrieval)}"])
    tools = read(root, "tools.json")
    assert tools["status"] == "completed" and tools["total_scenarios"] == 88
    scores = tools["scores"]
    hard = next(c for c in scores["category_scores"] if c["label"] == "Hard Mode")
    tool_rows.append([name, f"{scores['total_points']}/{scores['max_points']}", scores["final_score"],
        f"{hard['earned']}/{hard['max']}", link("full tool traces", root, "tools.md")])
table(["Quant", "API tool choices", "Numbered images per request", "8K/240K retrieval"], functional)
table(["Quant", "Full suite points", "Score /100", "Hard Mode points", "Raw"], tool_rows)
lines += ["API checks cover required/named/auto/none choices, thinking on/off and "
          "streaming/non-streaming. Retrieval places a random key early, midway and late "
          "in 8192- and 240000-token filler archives. Image checks read ordered numbers "
          "from 1, 4 and 16 images; they are smoke tests, not broad vision evaluation.", "",
          "Tool-eval-bench is pinned at `cf54b4bfe705f12f71e8866f10730572497c8105`. "
          "The full 88-case suite includes 19 Hard Mode scenarios, with thinking enabled, "
          "temperature zero, one trial, eight parallel cases and at most eight turns. "
          "The linked reports retain failures and partial scores.", ""]
if args.mmap:
    memory = read(args.mmap, "memory.json")
    worker = next(p for p in memory["processes"] if p["checkpoint_mappings"])
    totals = worker["checkpoint_totals_KiB"]
    assert len(worker["checkpoint_mappings"]) == 128
    assert totals["Anonymous"] == 0
    assert totals["Shared_Dirty"] + totals["Private_Dirty"] == 0
    lines += ["## mmap memory snapshot", "",
              "Captured after the performance/retrieval suite, before the full tool evaluation. "
              "These are process mapping observations, not a working-set ceiling or a low-RAM test. "
              "Linux can retain and reclaim clean checkpoint pages as workloads change.", ""]
    table(["Checkpoint mappings", "Mapped GiB", "Resident mapped GiB", "Anonymous mapped GiB", "Dirty mapped GiB"], [[
        len(worker["checkpoint_mappings"]), f"{totals['Size']/2**20:.2f}",
        f"{totals['Rss']/2**20:.2f}", f"{totals['Anonymous']/2**20:.2f}",
        f"{(totals['Private_Dirty']+totals['Shared_Dirty'])/2**20:.2f}"]])
    lines += ["The backing filesystem is ext4 on a Samsung 9100 PRO 4TB NVMe. "
              "PREWARM, READAHEAD and PINNED are off; the run uses the existing file cache "
              "and the warmups specified above. " + link("Full memory and storage receipt", args.mmap, "memory.json") + ".", ""]

args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text("\n".join(lines) + "\n")
