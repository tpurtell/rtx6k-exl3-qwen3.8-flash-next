# Qwen3.8 Flash Next on one RTX PRO 6000 96 GB

A TP=1 serving recipe with host-resident token embeddings and the entire PLE
n-gram table, FP8 KV cache, vision, CUDA graphs, and tuned MTP. The configured
context is 262144 tokens and the scheduler has 16 request slots. C1 performance
is the priority for the defaults; C16 throughput tradeoffs are recorded below.

| Profile (`QUANT`) | Checkpoint | Host PLE storage | Default MTP |
|---|---|---|---:|
| `exl3` | [EXL3 K4.25](https://huggingface.co/wrldsuksgo2mars/Qwen3.8-Flash-Next-EXL3-K4.25-v1) | BF16, about 95 GiB | 3 |
| `exl3-ple8` | [EXL3 K4.25 PLE FP8](https://huggingface.co/wrldsuksgo2mars/Qwen3.8-Flash-Next-EXL3-K4.25-PLE-FP8-v1) | FP8 with shared scale, about 48 GiB | 3 |
| `nvfp4` | [NVIDIA NVFP4](https://huggingface.co/nvidia/Qwen3.8-Flash-Next-NVFP4) | FP8 with shared scale, about 48 GiB | 2 |

EXL3 requires independent K4/K5 allocation for each expert's gate, up and down
projection. The pinned B12x fork supports this geometry and preserves all 5951
experts with unequal projection tiers across target and MTP layers. The
`exl3-ple8` profile keeps those expert weights and uses NVIDIA's FP8 PLE table.
Its additional qualification is quality-only: **149/176** tool points, including
**32/38** in Hard Mode. The evaluator flags internal-data request handling and
extra tool parameters; see the [full quality report](benchmarks/PLE8-QUALITY.md).
Performance equivalence to the BF16-PLE parent has not been separately measured.

Selected-profile results on one 400 W card:

| Measurement | EXL3, MTP3 | NVFP4, MTP2 |
|---|---:|---:|
| C1 seven-workload weighted decode, tokens/s | **152.82** | **151.11** |
| C1 greedy `merge_intervals` median, tokens/s | 202.99 | 185.55 |
| C1 sampled async coding task median, tokens/s | 185.55 | 166.92 |
| C16 sampled-prose aggregate median, tokens/s | 696.96 | 930.71 |
| Full-context boundary: 261888 input + 256 output | Pass | Pass |
| API tool constraints / retrieval probes | 16/16; 6/6 | 16/16; 6/6 |

These are different workloads, not interchangeable rates. The full matrices
below include ranges, settings, contract failures, raw responses and tool scores.

## Run

The published image is
`ghcr.io/tpurtell/rtx6k-exl3-qwen3.8-flash-next:v0.1.0`
(`linux/amd64`). To use the exact qualified image without building:

```bash
export IMAGE=ghcr.io/tpurtell/rtx6k-exl3-qwen3.8-flash-next@sha256:9dab4b0b3ce01eab748f3d264cabfc206be467e596e6470b1be68a2ddcfe6840
docker pull "$IMAGE"
QUANT=exl3-ple8 bash download.sh
QUANT=exl3-ple8 GPU=0 bash start.sh
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
QUANT=exl3-ple8 GPU=0 bash start.sh
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
The native multiprocessing executor is required for the PLE offload worker.

Sixteen scheduler slots do **not** mean sixteen simultaneous 262144-token
requests fit in the KV pool. The final tests include sixteen overlapping
short-context client streams and a separate exact full-context boundary test.
Final startup KV pools were 796612 tokens for EXL3 and 686817 for NVIDIA
(3.04× and 2.62× the configured context); actual scheduling also depends on
request mix. Use the context and concurrency tables below to distinguish those cases.

## MTP tuning and C16 tradeoffs

These development comparisons use the same seven C1 workloads (three measured
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
QUANT=exl3 MTP_TOKENS=0 bash start.sh --speculative-config \
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

The performance matrices were collected before the additive FP8-PLE loader
extension. Their runtime receipts retain that image ID. The published image
keeps the measured kernels unchanged, adds the annotated `exl3-ple8` path,
and passes all 16 API checks for both original profiles:
[EXL3](benchmarks/exl3-release-api-dev14.jsonl) and
[NVIDIA](benchmarks/nvfp4-release-api-dev14.jsonl). The new profile's complete
quality suite runs on the published image.

## Reproduce qualification

Run against an otherwise idle endpoint. These scripts refuse to overwrite an
existing result directory.

```bash
QUANT=exl3 MTP_TOKENS=3 RESULT_DIR=benchmarks/my-exl3 \
  bash scripts/benchmark-suite.sh
# NVIDIA: QUANT=nvfp4 MTP_TOKENS=2, with its endpoint and a new result directory.

# Additional profile: quality only.
RESULT_DIR=benchmarks/my-exl3-ple8 bash scripts/quality-suite.sh

# Install tool-eval-bench at the recorded revision, using its uv environment.
# TOOL_EVAL_DIR points to that checkout; results also persist in its SQLite DB.
TOOL_EVAL_DIR=/path/to/tool-eval-bench RESULT_DIR=benchmarks/my-exl3 \
  MODEL=qwen38-exl3 bash scripts/tool-quality.sh
```

Tool-eval-bench is pinned at `cf54b4bfe705f12f71e8866f10730572497c8105`.
The complete reports preserve failed and partial cases. Vision and retrieval
are targeted checks, not broad capability benchmarks. Exact orchid repetition
is unreliable, and throughput figures include outputs that fail contracts.

## Final serving measurements

Generated from the linked raw receipts by `scripts/summarize-results.py`.

Each quant runs on one RTX PRO 6000 Blackwell 96 GB at a 400 W power limit. C1 is the default-selection priority. Both use FP8 KV and host token embeddings and n-gram tables. All decode rates below exclude prefill.

## Profiles

| Quant | MTP draft tokens | GPU memory fraction | Configuration |
| --- | --- | --- | --- |
| EXL3 | 3 | 0.94 | [runtime](benchmarks/exl3-final/runtime.json) |
| NVFP4 | 2 | 0.94 | [runtime](benchmarks/nvfp4-final/runtime.json) |

## Seven content workloads: C1

One warmup and three measured responses per workload, temperature zero and thinking disabled. Values are median tokens/s (minimum–maximum). The weighted blend is total post-initial-burst tokens divided by their total decode time. Rates include failed output contracts and are not successful-task throughput.

| Workload | EXL3 tokens/s | Contract | NVFP4 tokens/s | Contract |
| --- | --- | --- | --- | --- |
| code | 202.99 (202.75–207.46) | 3/3 | 185.55 (184.23–189.58) | 3/3 |
| math | 211.53 (202.29–218.04) | 3/3 | 190.53 (184.60–191.27) | 3/3 |
| fable | 120.24 (118.29–121.98) | 1/3 | 130.79 (123.27–132.18) | 0/3 |
| hello | 175.76 (173.98–179.05) | 3/3 | 149.58 (149.13–150.95) | 3/3 |
| topic | 147.88 (138.51–149.55) | 3/3 | 142.45 (137.24–149.66) | 3/3 |
| structured-json | 168.50 (165.14–172.06) | 3/3 | 161.41 (161.29–161.63) | 3/3 |
| multilingual | 125.25 (116.01–129.04) | 3/3 | 127.20 (125.90–134.39) | 2/3 |

| Quant | Weighted blend | Draft acceptance | Mean acceptance length | Raw |
| --- | --- | --- | --- | --- |
| EXL3 | 152.82 | 56.05% | 2.681 | [responses and timings](benchmarks/exl3-final/seven.jsonl) |
| NVFP4 | 151.11 | 64.44% | 2.289 | [responses and timings](benchmarks/nvfp4-final/seven.jsonl) |

The code contract checks syntax and required assertions; it does not execute the generated code. The Chinese terminology check is a literal-phrase proxy and can reject a correct paraphrase. All rejected responses remain in the raw files.

## Orchid repetition: C1

The prompt requests exactly 100 space-separated `orchid` words, with a 1500-token output cap. One warmup precedes five measured runs. Counts and contract failures are retained; a fast incorrect repetition is not a task success.

| Quant | Word counts | Exact contract | Decode tokens/s | Raw |
| --- | --- | --- | --- | --- |
| EXL3 | 750, 750, 101, 100, 102 | 1/5 | 236.03 (205.82–238.09) | [responses](benchmarks/exl3-final/orchid.jsonl) |
| NVFP4 | 102, 101, 101, 100, 101 | 1/5 | 197.95 (195.65–198.39) | [responses](benchmarks/nvfp4-final/orchid.jsonl) |

## Sampled prose: independent clients

Each client requests 256 forced output tokens at temperature 0.7 with fixed sampling seeds and thinking disabled. Two full warmups and three measurements per concurrency. Aggregate rate divides the sum of each client's N−1 tokens by the whole batch's first-to-last token window. Overlap counts come from client stream intervals, not a GPU occupancy gauge.

| Clients | EXL3 aggregate tokens/s | Overlap | NVFP4 aggregate tokens/s | Overlap |
| --- | --- | --- | --- | --- |
| 1 | 111.70 (107.79–116.80) | 1–1 | 113.24 (112.45–117.52) | 1–1 |
| 2 | 191.37 (190.78–197.22) | 2–2 | 213.17 (209.52–214.76) | 2–2 |
| 4 | 347.87 (337.22–358.47) | 4–4 | 365.63 (339.10–370.64) | 4–4 |
| 8 | 532.66 (518.22–536.03) | 8–8 | 620.24 (606.62–622.41) | 8–8 |
| 16 | 696.96 (673.69–703.47) | 16–16 | 930.71 (915.42–956.41) | 16–16 |

Raw: [EXL3](benchmarks/exl3-final/clients.json), [NVFP4](benchmarks/nvfp4-final/clients.json).

## Prefill matrix: C1

Exact prompt lengths, unique first cache blocks and three measurements after a warmup at each depth. Effective prompt tokens/s includes server tokenization and the handoff of the first output token; it is not isolated GPU prefill time.

| Prompt tokens | EXL3 tokens/s | EXL3 TTFT, s | NVFP4 tokens/s | NVFP4 TTFT, s |
| --- | --- | --- | --- | --- |
| 2048 | 7046.6 (7036.5–7058.2) | 0.291 (0.290–0.291) | 10432.6 (10396.8–10440.6) | 0.196 (0.196–0.197) |
| 8192 | 7513.1 (7503.0–7517.6) | 1.090 (1.090–1.092) | 11072.0 (11069.3–11085.0) | 0.740 (0.739–0.740) |
| 32768 | 7452.9 (7452.3–7454.0) | 4.397 (4.396–4.397) | 10900.3 (10892.9–10908.5) | 3.006 (3.004–3.008) |
| 65536 | 7261.8 (7255.0–7270.7) | 9.025 (9.014–9.033) | 10535.6 (10528.5–10551.3) | 6.220 (6.211–6.225) |
| 128000 | 6965.5 (6956.1–6968.6) | 18.376 (18.368–18.401) | 9952.9 (9941.4–9962.2) | 12.861 (12.849–12.875) |
| 261632 | 6472.0 (6469.7–6480.1) | 40.425 (40.375–40.440) | 8967.4 (8959.7–8982.5) | 29.176 (29.127–29.201) |

Raw: [EXL3](benchmarks/exl3-final/prefill.json), [NVFP4](benchmarks/nvfp4-final/prefill.json).

## Context and decode scaling: C1

Synthetic filler followed by 256 forced output tokens. One warmup and three measurements at each depth; median (minimum–maximum). This measures serving capacity and speed, not long-context reasoning quality.

| Prompt tokens | EXL3 decode tokens/s | EXL3 TTFT, s | NVFP4 decode tokens/s | NVFP4 TTFT, s |
| --- | --- | --- | --- | --- |
| 2048 | 216.74 (153.01–224.41) | 0.304 (0.298–0.305) | 155.04 (142.64–189.43) | 0.206 (0.206–0.207) |
| 8192 | 219.86 (217.52–220.13) | 1.114 (1.110–1.117) | 147.89 (140.88–191.44) | 0.755 (0.752–0.758) |
| 32768 | 219.54 (211.66–223.77) | 4.460 (4.457–4.462) | 192.36 (192.16–193.06) | 3.055 (3.053–3.058) |
| 65536 | 220.39 (220.12–220.72) | 9.142 (9.137–9.143) | 193.20 (191.47–193.29) | 6.309 (6.307–6.319) |
| 131072 | 219.82 (218.19–221.66) | 18.998 (18.977–18.999) | 193.55 (193.44–194.84) | 13.349 (13.347–13.357) |
| 261632 | 224.17 (221.72–226.40) | 40.586 (40.571–40.632) | 196.69 (196.09–197.54) | 29.303 (29.295–29.306) |

Raw: [EXL3](benchmarks/exl3-final/context.jsonl), [NVFP4](benchmarks/nvfp4-final/context.jsonl).

## Reference coding task: C1 across KV depths

The async task-runner prompt is identical to the reference recipe. Qwen's native non-thinking template replaces GLM's template. Temperature is 0.2, with a fixed seed and 256 forced output tokens. One warmup precedes three measurements per depth. Prompts repeat to retain existing KV; these TTFTs are not uncached prefill measurements. Rates use the reference's N−1 token convention; raw receipts also retain the rate excluding the whole initial SSE burst. The fixed token cap is not a generated-code correctness test.

| Prompt depth | EXL3 decode tokens/s | NVFP4 decode tokens/s |
| --- | --- | --- |
| Task only | 185.55 (185.06–185.95) | 166.92 (166.08–171.40) |
| 8192 | 185.51 (181.73–190.09) | 173.65 (170.58–174.45) |
| 32768 | 183.37 (167.16–188.15) | 166.82 (166.40–169.35) |
| 65536 | 182.49 (177.04–193.39) | 165.82 (165.53–176.76) |
| 128000 | 186.82 (186.38–190.87) | 169.31 (169.25–170.33) |
| 261632 | 190.37 (190.17–197.46) | 177.83 (164.82–178.54) |

Raw: [EXL3](benchmarks/exl3-final/code-agent.jsonl), [NVFP4](benchmarks/nvfp4-final/code-agent.jsonl).

EXL3 also returned all 256 requested tokens after a 261888-token prompt at the exact 262144-token boundary: [receipt](benchmarks/exl3-final/context-boundary.jsonl).

NVFP4 also returned all 256 requested tokens after a 261888-token prompt at the exact 262144-token boundary: [receipt](benchmarks/nvfp4-final/context-boundary.jsonl).

## Functional and tool checks

| Quant | API tool choices | Numbered images per request | 8K/240K retrieval |
| --- | --- | --- | --- |
| EXL3 | 16/16 | 1: pass, 4: pass, 16: pass | 6/6 |
| NVFP4 | 16/16 | 1: pass, 4: pass, 16: pass | 6/6 |

| Quant | Full suite points | Score /100 | Hard Mode points | Raw |
| --- | --- | --- | --- | --- |
| EXL3 | 152/176 | 86 | 32/38 | [full tool traces](benchmarks/exl3-final/tools.md) |
| NVFP4 | 149/176 | 85 | 29/38 | [full tool traces](benchmarks/nvfp4-final/tools.md) |

API checks cover required/named/auto/none choices, thinking on/off and streaming/non-streaming. Retrieval places a random key early, midway and late in 8192- and 240000-token filler archives. Image checks read ordered numbers from 1, 4 and 16 images; they are smoke tests, not broad vision evaluation.

Tool-eval-bench is pinned at `cf54b4bfe705f12f71e8866f10730572497c8105`. The full 88-case suite includes 19 Hard Mode scenarios, with thinking enabled, temperature zero, one trial, eight parallel cases and at most eight turns. The linked reports retain failures and partial scores.


## EXL3 with FP8 PLE: quality-only qualification

`exl3-ple8` uses the same MTP3 setting as EXL3, FP8 KV, and host token embeddings and PLE storage. Its pinned checkpoint is `888306bd3996d6317758c07df50622829259ad17`. No performance matrix was run for this profile; incidental request timings in raw quality receipts are not evidence of performance equivalence.

| Check | Result | Evidence |
|---|---|---|
| Required/named/auto/none tool API | 16/16 | [api-tools.jsonl](benchmarks/exl3-ple8-final/api-tools.jsonl) |
| Seven content contracts | 18/21 | [seven.jsonl](benchmarks/exl3-ple8-final/seven.jsonl) |
| Exact 100-word orchid | 2/5 | [orchid.jsonl](benchmarks/exl3-ple8-final/orchid.jsonl) |
| Numbered-image requests | 1: pass, 4: pass, 16: pass | [vision.json](benchmarks/exl3-ple8-final/vision.json) |
| 8K/240K early/middle/late retrieval | 6/6 | [retrieval.jsonl](benchmarks/exl3-ple8-final/retrieval.jsonl) |
| Full 88-case tool suite | 149/176 points; 85/100 | [tools.md](benchmarks/exl3-ple8-final/tools.md) |
| Hard Mode subset (19 cases) | 32/38 points | [tools.json](benchmarks/exl3-ple8-final/tools.json) |

Orchid word counts: 100, 101, 100, 750, 750.

Content checks use three responses per workload at temperature zero without thinking; orchid uses five responses. Tool-eval-bench uses the same pinned 88-case suite, thinking enabled, one trial and eight parallel cases as the other profiles. These are not controlled perplexity/KL comparisons or a proof of unchanged model quality. The content contracts include literal wording proxies; all failed and partial results remain available for inspection.

Runtime and memory observations: [runtime.json](benchmarks/exl3-ple8-final/runtime.json).

Evaluator-flagged cases:

- TC-33 (Hallucination Resistance): Did not appropriately handle the request for internal data.
- TC-42 (Extra Parameter Injection): Injected extra parameters despite additionalProperties: false.
