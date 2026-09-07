# Qwen3.8 Flash Next on RTX PRO 6000 and DGX Spark

A TP=1 SM12x serving recipe with host-resident token embeddings and mmap-backed PLE
n-gram tables, FP8 KV cache, vision, CUDA graphs, and tuned MTP. The configured
context is 262144 tokens and the scheduler has 16 request slots. C1 performance
is the priority for the defaults; C16 throughput tradeoffs are recorded below.

| Profile (`QUANT`) | Checkpoint | PLE table format | Default MTP |
|---|---|---|---:|
| `exl3` | [EXL3 K4.25](https://huggingface.co/wrldsuksgo2mars/Qwen3.8-Flash-Next-EXL3-K4.25-v1) | BF16, about 95 GiB | 3 |
| `exl3-ple8` | [EXL3 K4.25 PLE FP8](https://huggingface.co/wrldsuksgo2mars/Qwen3.8-Flash-Next-EXL3-K4.25-PLE-FP8-v1) | FP8 with shared scale, about 48 GiB | 3 |
| `nvfp4` | [NVIDIA NVFP4](https://huggingface.co/nvidia/Qwen3.8-Flash-Next-NVFP4) | FP8 with shared scale, about 48 GiB | 2 |

EXL3 requires independent K4/K5 allocation for each expert's gate, up and down
projection. The pinned B12x fork supports this geometry and preserves all 5951
experts with unequal projection tiers across target and MTP layers. The
`exl3-ple8` profile keeps those expert weights and uses NVIDIA's FP8 PLE table.
The shipping default is **`exl3` with mmap enabled**, retaining the original
BF16 PLE table. Choose `exl3-ple8` to save about 47.7 GiB of checkpoint payload,
reduce download/storage requirements, or fit more PLE rows in the available
file cache on a lower-RAM system. Its FP8 PLE table is approximately half the
size of the BF16 table. This preference change does not add a new measurement
of the default profile.

The `exl3-ple8` profile now has a full benchmark matrix with **mmap enabled**
in v0.2.0, including the quality checks in the main tables below.
The original EXL3/NVIDIA performance columns below are unchanged historical
results, not new runs. They differ in quantization and PLE precision from the
mmap profile; this is not a controlled mmap-on/off comparison.

Selected-profile results on one 400 W card:

| Measurement | EXL3 resident, MTP3 (v0.1.0) | NVFP4 resident, MTP2 (v0.1.0) | EXL3 PLE8 mmap, MTP3 |
|---|---:|---:|---:|
| C1 seven-workload weighted decode, tokens/s | **152.82** | **151.11** | **147.78** |
| C1 greedy `merge_intervals` median, tokens/s | 202.99 | 185.55 | 197.74 |
| C1 sampled async coding task median, tokens/s | 185.55 | 166.92 | 183.45 |
| C16 sampled-prose aggregate median, tokens/s | 696.96 | 930.71 | 659.75 |
| Full-context boundary: 261888 input + 256 output | Pass | Pass | Pass |
| API tool constraints / retrieval probes | 16/16; 6/6 | 16/16; 6/6 | 16/16; 6/6 |

These are different workloads, not interchangeable rates. The full matrices
below show medians, settings, contract failures and tool points. Linked raw
receipts retain individual measurements; the [detailed report](benchmarks/RESULTS.md)
also includes measurement ranges. Tool evaluation uses C8 (eight concurrent cases);
its points are not presented as a normalized comparison score.

## Platforms

`bash build.sh` and `bash start.sh` detect the host architecture automatically:
arm64 selects DGX Spark SM121 settings; x86_64 selects RTX SM120 settings.
Both default to the original EXL3 K4.25 checkpoint with BF16 PLE and mmap.
Spark caps GPU memory utilization at **0.7** to leave unified memory available
for checkpoint pages and the host. A lower value is configurable.

Spark qualification and tuning are in progress on the `spark` branch. The
existing RTX measurements below remain unchanged; no Spark numbers are claimed
until its full default-profile qualification completes.

## Run

The published image is
`ghcr.io/tpurtell/rtx6k-exl3-qwen3.8-flash-next:v0.2.0`
(`linux/amd64`). To use the exact qualified image without building:

```bash
export IMAGE=ghcr.io/tpurtell/rtx6k-exl3-qwen3.8-flash-next@sha256:bb252820ade1b6aa1316c45485186db90fe67f1d7ea48826169bf92f634d2e73
docker pull "$IMAGE"
bash download.sh
GPU=0 bash start.sh
```

Install Docker with NVIDIA GPU access. All reported measurements use one RTX
PRO 6000 Blackwell 96 GB at **400 W**, driver 595.71.05, and a Threadripper 9970X
host with 183 GiB RAM. Each target/draft token embedding adds approximately
1.184 GiB of host storage beyond the PLE table. Leave additional RAM for model
loading, the server and the operating system; 95/48 GiB are table sizes, not
whole-server RAM requirements. Checkpoint weights are downloaded separately.

```bash
# Build from the repository root, or use the published image below.
bash build.sh
QUANT=exl3 bash download.sh
QUANT=exl3 GPU=0 bash start.sh
curl http://127.0.0.1:8001/health

# Stop before switching models to release the host tables.
QUANT=exl3 bash stop.sh
QUANT=exl3-ple8 bash download.sh
QUANT=exl3-ple8 GPU=0 PLE_MMAP=1 bash start.sh
# NVIDIA: use QUANT=nvfp4 for download.sh, start.sh and stop.sh.
```

The OpenAI-compatible endpoint is `http://127.0.0.1:8001/v1`, with served
aliases `qwen38-exl3`, `qwen38-exl3-ple8` and `qwen38-nvfp4`. Tool calls use
`qwen3_coder`; reasoning uses `qwen3`. Send
`"chat_template_kwargs":{"enable_thinking":false}` for the non-thinking mode
used in performance tests. The full tool-quality suite uses thinking enabled.

`GPU`, `PORT`, `CONTAINER_NAME`, `HF_CACHE`, `RUNTIME_CACHE`, `CPU_THREADS`,
`MAX_MODEL_LEN`, `MAX_NUM_SEQS`, `MAX_BATCHED_TOKENS`,
`GPU_MEMORY_UTILIZATION` and `MTP_TOKENS` can override the defaults.
`MTP_TOKENS=0` disables speculation. Runtime/compiler caches persist under
`~/.cache/qwen38-rtx/<profile>`; checkpoint caches are mounted read-only.
The launcher uses the native multiprocessing executor. Resident mode needs
its PLE offload worker; mmap gathers rows directly in the model worker.

Sixteen scheduler slots do **not** mean sixteen simultaneous 262144-token
requests fit in the KV pool. The final tests include sixteen overlapping
short-context client streams and a separate exact full-context boundary test.
Measured startup KV pools were 796612 tokens for resident EXL3, 686817 for
resident NVIDIA and 880600 for EXL3 PLE8 mmap (3.04×, 2.62× and 3.36× the
configured context); actual scheduling also depends on
request mix. Use the context and concurrency tables below to distinguish those cases.

## Optional mmap PLE (v0.2.0)

`PLE_MMAP=1` is the shipping default and works with **all three profiles**.
It reads the PLE table through read-only checkpoint mappings and replaces the
resident PLE subprocess. Set `PLE_MMAP=0` to use the resident host table instead.
Token embeddings remain in host RAM in either mode.
Mmap maps the selected checkpoint's actual table dtype, including BF16 for
`exl3` and FP8 plus its scalar scale for `exl3-ple8` and `nvfp4`.

```bash
GPU=0 bash start.sh  # default: exl3, BF16 PLE, mmap enabled
QUANT=exl3-ple8 GPU=0 bash start.sh  # FP8 PLE, smaller checkpoint/cache footprint
# Run one model at a time; use stop.sh with the same QUANT before switching.
# PLE_MMAP=0 opts into the resident table with any profile.
```

The launcher supports `PLE_MMAP_WORKERS=32`, `PLE_MMAP_CHUNK=2048`,
`PLE_MMAP_PREWARM=0`, `PLE_MMAP_READAHEAD=2048`, `PLE_MMAP_PINNED=0` and
`PLE_MMAP_SERIAL=128`. When running the image directly, use the corresponding
`VLLM_PLE_MMAP*` environment variables. `VLLM_PLE_MMAP=1` takes precedence
over the image's resident-worker setting. Model Runner V2 and PP=1 are required.

The serial threshold bypasses thread-pool dispatch for at most 128 distinct
rows. We selected it for C1: the three-run blend measured 147.94 tokens/s
versus 138.30 with the PR's SERIAL=0 default. Larger gathers still use the
thread pool. Targeted readahead is enabled globally with a 2,048-range limit,
selected from the Spark tuning runs. It asks Linux to fetch the current step's
PLE file ranges before the gather; it does not predict future tokens or preload
the entire table. If the coalesced range count exceeds the limit, that step's
hints are skipped. Set `PLE_MMAP_READAHEAD=0` to disable the hints. Historical
RTX results below retain their measured readahead-zero configuration; this
default change does not introduce new RTX measurements.

This ports [PR #54129](https://github.com/vllm-project/vllm/pull/54129) at a pinned
commit after review, with fixes for approximate/broadcast scale comparisons
and non-finite scales. **218 tests pass**, followed by byte-exact checks on
real checkpoint shard boundaries and changed-row CUDA graph replay. The
[review and evidence](docs/mmap-review.md) explain the port and test adaptations.

Mapped pages may accumulate in Linux's file cache, but remain clean and
reclaimable. An initial snapshot showed about 2.3 GiB resident across the
47.68 GiB table mappings, with no anonymous or dirty PLE mapping pages. This
is not a fixed memory limit. Benchmarks use an ext4 filesystem on a Samsung
9100 PRO 4TB NVMe, the existing OS page cache and explicit warmups; they do
not establish cold-disk throughput or a minimum host-RAM requirement.

## MTP tuning and C16 tradeoffs

These v0.1.0 resident-mode development comparisons use the same seven C1 workloads (three measured
responses each). C8/C16 are shorter probes: 128 forced prose tokens, one measured
batch after warmup. They are distinct from the final 256-token, three-run client
matrix below. Small differences between runs are not a statistical proof of
superiority; defaults use the best observed mixed C1 result.

| Quant | Draft policy | C1 weighted blend, tokens/s | C8 aggregate | C16 aggregate |
|---|---|---:|---:|---:|
| EXL3 | Off | 92.76 | 465.99 | 762.88 |
| EXL3 | 1 | 131.54 | 561.14 | 861.92 |
| EXL3 | 2 | 149.16 | 532.52 | 718.39 |
| EXL3 | **3, default** | **152.97** | — | — |
| EXL3 | 4 | 150.63 | 408.90 | 486.12 |
| EXL3 | Adaptive 3 → 1 | 150.71 | 516.51 | 792.07 |
| NVFP4 | Off | 96.38 | 500.96 | 855.50 |
| NVFP4 | 1 | 130.35 | 597.43 | 915.16 |
| NVFP4 | **2, default** | **152.40** | 552.95 | 881.49 |
| NVFP4 | 3 | 149.46 | 549.68 | 544.11 |
| NVFP4 | Adaptive 2 → 1 | 146.04 | 585.89 | 858.97 |

Adaptive policies use the longer draft for 1–4 scheduled requests and one draft
token for 5–16. Neither improved the observed C1 blend. MTP1 is a measured option
for higher C16 throughput at a substantial C1 cost. The MTP4 EXL3 and MTP3 NVIDIA
C16 probes reached only 14 and 13 overlapping streams, respectively.

To reproduce the EXL3 adaptive comparison, suppress the automatic static
configuration and supply the measured scheduler policy explicitly:

```bash
QUANT=exl3 PLE_MMAP=0 MTP_TOKENS=0 bash start.sh --speculative-config \
  '{"method":"mtp","num_speculative_tokens":3,"num_speculative_tokens_per_batch_size":[[1,4,3],[5,16,1]]}'
```

For code-heavy C1 traffic, EXL3 MTP4 reached 217.18 tokens/s on the greedy
`merge_intervals` workload, versus approximately 203–206 with MTP3. NVIDIA
MTP3 reached 202.67 versus 182.82 with MTP2. These are workload-specific options:
set `MTP_TOKENS=4` or `3` respectively. They are not the separate sampled async
coding task reported below. Full tuning receipts and exceptions are in the
[qualification ledger](docs/qualification.md) and [raw benchmarks](benchmarks).

## Kernel choices

- **EXL3 mixed MoE:** B12x, including the Qwen H2560/I640 projection planner fix
  pushed to the [fork](https://github.com/tpurtell/sparkinfer-glmrt/commit/c76a40ee684cb3ef7d2c223d56a9b9cff25a3a1e).
- **QSA attention:** B12x sparse attention with FP8 cache descales and native
  cache writes/index selection. Numerical and mutable CUDA-graph tests cover
  the actual integration. There is no full-model BF16-KV quality control.
- **NVIDIA MoE:** native FlashInfer CUTLASS. Precise B12x won isolated component
  timings but lost the end-to-end C1 blend, 136.74 versus 152.40 tokens/s.
  `B12X_NVFP4=1` retains the tested optional bridge; it is off by default.
- **Vocabulary projection:** native. B12x improved the isolated M1 projection
  but did not improve the mixed C1 blend. `B12X_VOCAB=1` is optional and off.
- **HC and GDN:** native. HC packing costs erased the small component advantage;
  GDN was slower at tested small batches and failed a B16 mutable-graph numerical
  check. The reproducer and failure remain in the repository.

The [Dockerfile](Dockerfile) pins the base image and B12x revision. The
[patches](patches) also handle EXL3 MTP layer mapping, NVIDIA's FP8 draft weights,
FP8 PLE storage, exact host token embeddings and required/named tool constraints.
[Provenance](PROVENANCE.md) distinguishes borrowed benchmark contracts from new
integration work. Model licenses apply separately from the recipe's [license](LICENSE).

The v0.1.0 runtime receipts retain the original image IDs. The follow-on
release adds optional mmap support and its reviewed validation fixes. Only
mmap-enabled `exl3-ple8` receives a new full qualification; the other profile
settings remain available and their historical evidence is retained.

## Reproduce qualification

Run against an otherwise idle endpoint. These scripts refuse to overwrite an
existing result directory.

```bash
# With the mmap-enabled exl3-ple8 server already running:
QUANT=exl3-ple8 MTP_TOKENS=3 RESULT_DIR=benchmarks/my-mmap \
  bash scripts/benchmark-suite.sh
# NVIDIA: QUANT=nvfp4 MTP_TOKENS=2, with its endpoint and a new result directory.

# Install tool-eval-bench at the recorded revision, using its uv environment.
# TOOL_EVAL_DIR points to that checkout; results also persist in its SQLite DB.
TOOL_EVAL_DIR=/path/to/tool-eval-bench RESULT_DIR=benchmarks/my-mmap \
  MODEL=qwen38-exl3-ple8 bash scripts/tool-quality.sh
```

Tool-eval-bench is pinned at `cf54b4bfe705f12f71e8866f10730572497c8105`.
The complete reports preserve failed and partial cases. Vision and retrieval
are targeted checks, not broad capability benchmarks. Exact orchid repetition
is unreliable, and throughput figures include outputs that fail contracts.


## Final serving measurements

Generated from the linked raw receipts by `scripts/summarize-results.py`.

Each quant runs on one RTX PRO 6000 Blackwell 96 GB at a 400 W power limit. C1 is the default-selection priority. All use FP8 KV and host token embeddings. The mmap profile reads PLE rows from checkpoint-backed mappings; the original profiles retain resident host tables. All decode rates below exclude prefill.

EXL3 and NVFP4 columns retain the v0.1.0 measurements; only the mmap-enabled EXL3 PLE8 column is newly benchmarked. The EXL3 baseline also has a different PLE storage precision, so this is not a controlled mmap-on/off ablation. The mmap run uses existing Linux page cache and benchmark warmups; it is not a cold-disk or constrained-RAM test.

## Profiles

| Profile | MTP draft tokens | GPU memory fraction | PLE storage | Serial threshold | Configuration |
| --- | --- | --- | --- | --- | --- |
| EXL3 | 3 | 0.94 | resident | — | [runtime](benchmarks/exl3-final/runtime.json) |
| NVFP4 | 2 | 0.94 | resident | — | [runtime](benchmarks/nvfp4-final/runtime.json) |
| EXL3 PLE8 mmap | 3 | 0.94 | mmap | 128 | [runtime](benchmarks/exl3-ple8-mmap-final/runtime.json) |

## Seven content workloads: C1

One warmup and three measured responses per workload, temperature zero and thinking disabled. Values are median tokens/s. The weighted blend is total post-initial-burst tokens divided by their total decode time. Rates include failed output contracts and are not successful-task throughput.

| Workload | EXL3 tokens/s | Contract | NVFP4 tokens/s | Contract | EXL3 PLE8 mmap tokens/s | Contract |
| --- | --- | --- | --- | --- | --- | --- |
| code | 202.99 | 3/3 | 185.55 | 3/3 | 197.74 | 3/3 |
| math | 211.53 | 3/3 | 190.53 | 3/3 | 203.70 | 3/3 |
| fable | 120.24 | 1/3 | 130.79 | 0/3 | 117.36 | 1/3 |
| hello | 175.76 | 3/3 | 149.58 | 3/3 | 175.71 | 3/3 |
| topic | 147.88 | 3/3 | 142.45 | 3/3 | 138.57 | 3/3 |
| structured-json | 168.50 | 3/3 | 161.41 | 3/3 | 187.19 | 3/3 |
| multilingual | 125.25 | 3/3 | 127.20 | 2/3 | 112.99 | 2/3 |

| Quant | Weighted blend | Draft acceptance | Mean acceptance length | Raw |
| --- | --- | --- | --- | --- |
| EXL3 | 152.82 | 56.05% | 2.681 | [responses and timings](benchmarks/exl3-final/seven.jsonl) |
| NVFP4 | 151.11 | 64.44% | 2.289 | [responses and timings](benchmarks/nvfp4-final/seven.jsonl) |
| EXL3 PLE8 mmap | 147.78 | 52.55% | 2.576 | [responses and timings](benchmarks/exl3-ple8-mmap-final/seven.jsonl) |

The code contract checks syntax and required assertions; it does not execute the generated code. The Chinese terminology check is a literal-phrase proxy and can reject a correct paraphrase. All rejected responses remain in the raw files.

## Orchid repetition: C1

The prompt requests exactly 100 space-separated `orchid` words, with a 1500-token output cap. One warmup precedes five measured runs. Counts and contract failures are retained; a fast incorrect repetition is not a task success.

| Quant | Word counts | Exact contract | Decode tokens/s | Raw |
| --- | --- | --- | --- | --- |
| EXL3 | 750, 750, 101, 100, 102 | 1/5 | 236.03 | [responses](benchmarks/exl3-final/orchid.jsonl) |
| NVFP4 | 102, 101, 101, 100, 101 | 1/5 | 197.95 | [responses](benchmarks/nvfp4-final/orchid.jsonl) |
| EXL3 PLE8 mmap | 100, 101, 100, 750, 750 | 2/5 | 231.43 | [responses](benchmarks/exl3-ple8-mmap-final/orchid.jsonl) |

## Sampled prose: independent clients

Each client requests 256 forced output tokens at temperature 0.7 with fixed sampling seeds and thinking disabled. Two full warmups and three measurements per concurrency. Aggregate rate divides the sum of each client's N−1 tokens by the whole batch's first-to-last token window. Overlap counts come from client stream intervals, not a GPU occupancy gauge.

| Clients | EXL3 aggregate tokens/s | Overlap | NVFP4 aggregate tokens/s | Overlap | EXL3 PLE8 mmap aggregate tokens/s | Overlap |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 111.70 | 1 | 113.24 | 1 | 99.18 | 1 |
| 2 | 191.37 | 2 | 213.17 | 2 | 162.30 | 2 |
| 4 | 347.87 | 4 | 365.63 | 4 | 306.38 | 4 |
| 8 | 532.66 | 8 | 620.24 | 8 | 493.19 | 8 |
| 16 | 696.96 | 16 | 930.71 | 16 | 659.75 | 16 |

Raw: [EXL3](benchmarks/exl3-final/clients.json), [NVFP4](benchmarks/nvfp4-final/clients.json), [EXL3 PLE8 mmap](benchmarks/exl3-ple8-mmap-final/clients.json).

## Prefill matrix: C1

Exact prompt lengths, unique first cache blocks and three measurements after a warmup at each depth. Effective prompt tokens/s includes server tokenization and the handoff of the first output token; it is not isolated GPU prefill time.

| Prompt tokens | EXL3 tokens/s | EXL3 TTFT, s | NVFP4 tokens/s | NVFP4 TTFT, s | EXL3 PLE8 mmap tokens/s | EXL3 PLE8 mmap TTFT, s |
| --- | --- | --- | --- | --- | --- | --- |
| 2048 | 7046.6 | 0.291 | 10432.6 | 0.196 | 6888.2 | 0.297 |
| 8192 | 7513.1 | 1.090 | 11072.0 | 0.740 | 7432.7 | 1.102 |
| 32768 | 7452.9 | 4.397 | 10900.3 | 3.006 | 7411.3 | 4.421 |
| 65536 | 7261.8 | 9.025 | 10535.6 | 6.220 | 7226.0 | 9.069 |
| 128000 | 6965.5 | 18.376 | 9952.9 | 12.861 | 6933.4 | 18.461 |
| 261632 | 6472.0 | 40.425 | 8967.4 | 29.176 | 6452.9 | 40.545 |

Raw: [EXL3](benchmarks/exl3-final/prefill.json), [NVFP4](benchmarks/nvfp4-final/prefill.json), [EXL3 PLE8 mmap](benchmarks/exl3-ple8-mmap-final/prefill.json).

## Context and decode scaling: C1

Synthetic filler followed by 256 forced output tokens. One warmup and three measurements at each depth; median. This measures serving capacity and speed, not long-context reasoning quality.

| Prompt tokens | EXL3 decode tokens/s | EXL3 TTFT, s | NVFP4 decode tokens/s | NVFP4 TTFT, s | EXL3 PLE8 mmap decode tokens/s | EXL3 PLE8 mmap TTFT, s |
| --- | --- | --- | --- | --- | --- | --- |
| 2048 | 216.74 | 0.304 | 155.04 | 0.206 | 190.00 | 0.305 |
| 8192 | 219.86 | 1.114 | 147.89 | 0.755 | 219.37 | 1.127 |
| 32768 | 219.54 | 4.460 | 192.36 | 3.055 | 216.10 | 4.493 |
| 65536 | 220.39 | 9.142 | 193.20 | 6.309 | 215.01 | 9.292 |
| 131072 | 219.82 | 18.998 | 193.55 | 13.349 | 217.44 | 19.031 |
| 261632 | 224.17 | 40.586 | 196.69 | 29.303 | 220.81 | 40.749 |

Raw: [EXL3](benchmarks/exl3-final/context.jsonl), [NVFP4](benchmarks/nvfp4-final/context.jsonl), [EXL3 PLE8 mmap](benchmarks/exl3-ple8-mmap-final/context.jsonl).

## Reference coding task: C1 across KV depths

The async task-runner prompt is identical to the reference recipe. Qwen's native non-thinking template replaces GLM's template. Temperature is 0.2, with a fixed seed and 256 forced output tokens. One warmup precedes three measurements per depth. Prompts repeat to retain existing KV; these TTFTs are not uncached prefill measurements. Rates use the reference's N−1 token convention; raw receipts also retain the rate excluding the whole initial SSE burst. The fixed token cap is not a generated-code correctness test.

| Prompt depth | EXL3 decode tokens/s | NVFP4 decode tokens/s | EXL3 PLE8 mmap decode tokens/s |
| --- | --- | --- | --- |
| Task only | 185.55 | 166.92 | 183.45 |
| 8192 | 185.51 | 173.65 | 185.42 |
| 32768 | 183.37 | 166.82 | 180.28 |
| 65536 | 182.49 | 165.82 | 176.87 |
| 128000 | 186.82 | 169.31 | 184.41 |
| 261632 | 190.37 | 177.83 | 183.27 |

Raw: [EXL3](benchmarks/exl3-final/code-agent.jsonl), [NVFP4](benchmarks/nvfp4-final/code-agent.jsonl), [EXL3 PLE8 mmap](benchmarks/exl3-ple8-mmap-final/code-agent.jsonl).

EXL3 also returned all 256 requested tokens after a 261888-token prompt at the exact 262144-token boundary: [receipt](benchmarks/exl3-final/context-boundary.jsonl).

NVFP4 also returned all 256 requested tokens after a 261888-token prompt at the exact 262144-token boundary: [receipt](benchmarks/nvfp4-final/context-boundary.jsonl).

EXL3 PLE8 mmap also returned all 256 requested tokens after a 261888-token prompt at the exact 262144-token boundary: [receipt](benchmarks/exl3-ple8-mmap-final/context-boundary.jsonl).

## Functional and tool checks

| Quant | API tool choices | Numbered images per request | 8K/240K retrieval |
| --- | --- | --- | --- |
| EXL3 | 16/16 | 1: pass, 4: pass, 16: pass | 6/6 |
| NVFP4 | 16/16 | 1: pass, 4: pass, 16: pass | 6/6 |
| EXL3 PLE8 mmap | 16/16 | 1: pass, 4: pass, 16: pass | 6/6 |

| Quant | Full suite points | Hard Mode points | Raw |
| --- | --- | --- | --- |
| EXL3 | 152/176 | 32/38 | [full tool traces](benchmarks/exl3-final/tools.md) |
| NVFP4 | 149/176 | 29/38 | [full tool traces](benchmarks/nvfp4-final/tools.md) |
| EXL3 PLE8 mmap | 146/176 | 27/38 | [full tool traces](benchmarks/exl3-ple8-mmap-final/tools.md) |

API checks cover required/named/auto/none choices, thinking on/off and streaming/non-streaming. Retrieval places a random key early, midway and late in 8192- and 240000-token filler archives. Image checks read ordered numbers from 1, 4 and 16 images; they are smoke tests, not broad vision evaluation.

Tool-eval-bench is pinned at `cf54b4bfe705f12f71e8866f10730572497c8105`. Results are earned/possible points from a C8 run (eight concurrent cases), not a normalized score for comparison with other execution setups. The full 88-case suite includes 19 Hard Mode scenarios, with thinking enabled, temperature zero, one trial, eight parallel cases and at most eight turns. The linked reports retain failures and partial scores.

## mmap memory snapshot

Captured after the performance/retrieval suite, before the full tool evaluation. These are process mapping observations, not a working-set ceiling or a low-RAM test. Linux can retain and reclaim clean checkpoint pages as workloads change.

| Checkpoint mappings | Mapped GiB | Resident mapped GiB | Anonymous mapped GiB | Dirty mapped GiB |
| --- | --- | --- | --- | --- |
| 128 | 47.68 | 19.45 | 0.00 | 0.00 |

The backing filesystem is ext4 on a Samsung 9100 PRO 4TB NVMe. PREWARM, READAHEAD and PINNED are off; the run uses the existing file cache and the warmups specified above. [Full memory and storage receipt](benchmarks/exl3-ple8-mmap-final/memory.json).
