# Final serving measurements

Generated from the linked raw receipts by `scripts/summarize-results.py`.

RTX profiles run on one RTX PRO 6000 Blackwell 96 GB at a 400 W power limit. The Spark profile, when present, runs on one DGX Spark GB10 with unified memory. C1 is the default-selection priority. All use FP8 KV and host token embeddings. The mmap profiles read PLE rows from checkpoint-backed mappings; the original RTX profiles retain resident host tables. All decode rates below exclude prefill.

EXL3 and NVFP4 columns retain the v0.1.0 measurements; only the mmap-enabled EXL3 PLE8 column records its v0.2.0 qualification. The RTX EXL3 baseline has a different PLE storage precision, so this is not a controlled mmap-on/off ablation. The mmap run uses existing Linux page cache and benchmark warmups; it is not a cold-disk or constrained-RAM test.

The Spark column is newly qualified on native arm64 with the original BF16 PLE checkpoint.

## Profiles

| Profile | MTP draft tokens | GPU memory fraction | PLE storage | Serial threshold | Readahead range limit | Configuration |
| --- | --- | --- | --- | --- | --- | --- |
| EXL3 | 3 | 0.94 | resident | — | — | [runtime](exl3-final/runtime.json) |
| NVFP4 | 2 | 0.94 | resident | — | — | [runtime](nvfp4-final/runtime.json) |
| EXL3 PLE8 mmap | 3 | 0.94 | mmap | 128 | 0 | [runtime](exl3-ple8-mmap-final/runtime.json) |
| EXL3 mmap Spark (BF16 PLE) | 2 | 0.7 | mmap | 128 | 2048 | [runtime](spark-final/runtime.json) |

Independent Spark suites ran on four hosts with identical image IDs, serving arguments and selected environment settings. Each measurement uses one TP=1 GB10. Dynamically profiled KV allocations and page-cache histories can differ between hosts. [Host assignments, runtime receipts and memory snapshots](spark-final/qualification-manifest.json).

## Seven content workloads: C1

One warmup and three measured responses per workload, temperature zero and thinking disabled. Values are median tokens/s (minimum–maximum). The weighted blend is total post-initial-burst tokens divided by their total decode time. Rates include failed output contracts and are not successful-task throughput.

| Workload | EXL3 tokens/s | Contract | NVFP4 tokens/s | Contract | EXL3 PLE8 mmap tokens/s | Contract | EXL3 mmap Spark (BF16 PLE) tokens/s | Contract |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| code | 202.99 (202.75–207.46) | 3/3 | 185.55 (184.23–189.58) | 3/3 | 197.74 (191.59–198.40) | 3/3 | 38.12 (38.05–38.22) | 3/3 |
| math | 211.53 (202.29–218.04) | 3/3 | 190.53 (184.60–191.27) | 3/3 | 203.70 (202.96–218.92) | 3/3 | 38.75 (38.65–39.55) | 3/3 |
| fable | 120.24 (118.29–121.98) | 1/3 | 130.79 (123.27–132.18) | 0/3 | 117.36 (116.85–120.37) | 1/3 | 26.29 (25.56–27.56) | 1/3 |
| hello | 175.76 (173.98–179.05) | 3/3 | 149.58 (149.13–150.95) | 3/3 | 175.71 (174.81–177.49) | 3/3 | 31.35 (31.25–31.37) | 3/3 |
| topic | 147.88 (138.51–149.55) | 3/3 | 142.45 (137.24–149.66) | 3/3 | 138.57 (136.73–150.36) | 3/3 | 30.37 (30.11–30.59) | 3/3 |
| structured-json | 168.50 (165.14–172.06) | 3/3 | 161.41 (161.29–161.63) | 3/3 | 187.19 (183.57–193.90) | 3/3 | 35.12 (33.17–35.65) | 3/3 |
| multilingual | 125.25 (116.01–129.04) | 3/3 | 127.20 (125.90–134.39) | 2/3 | 112.99 (111.89–113.90) | 2/3 | 24.79 (24.78–26.33) | 3/3 |

| Quant | Weighted blend | Draft acceptance | Mean acceptance length | Raw |
| --- | --- | --- | --- | --- |
| EXL3 | 152.82 | 56.05% | 2.681 | [responses and timings](exl3-final/seven.jsonl) |
| NVFP4 | 151.11 | 64.44% | 2.289 | [responses and timings](nvfp4-final/seven.jsonl) |
| EXL3 PLE8 mmap | 147.78 | 52.55% | 2.576 | [responses and timings](exl3-ple8-mmap-final/seven.jsonl) |
| EXL3 mmap Spark (BF16 PLE) | 31.11 | 62.96% | 2.259 | [responses and timings](spark-final/seven.jsonl) |

The code contract checks syntax and required assertions; it does not execute the generated code. The Chinese terminology check is a literal-phrase proxy and can reject a correct paraphrase. All rejected responses remain in the raw files.

## Orchid repetition: C1

The prompt requests exactly 100 space-separated `orchid` words, with a 1500-token output cap. One warmup precedes five measured runs. Counts and contract failures are retained; a fast incorrect repetition is not a task success.

| Quant | Word counts | Exact contract | Decode tokens/s | Raw |
| --- | --- | --- | --- | --- |
| EXL3 | 750, 750, 101, 100, 102 | 1/5 | 236.03 (205.82–238.09) | [responses](exl3-final/orchid.jsonl) |
| NVFP4 | 102, 101, 101, 100, 101 | 1/5 | 197.95 (195.65–198.39) | [responses](nvfp4-final/orchid.jsonl) |
| EXL3 PLE8 mmap | 100, 101, 100, 750, 750 | 2/5 | 231.43 (224.18–236.16) | [responses](exl3-ple8-mmap-final/orchid.jsonl) |
| EXL3 mmap Spark (BF16 PLE) | 750, 100, 100, 100, 102 | 3/5 | 41.84 (41.32–41.99) | [responses](spark-final/orchid.jsonl) |

## Sampled prose: independent clients

Each client requests 256 forced output tokens at temperature 0.7 with fixed sampling seeds and thinking disabled. Two full warmups and three measurements per concurrency. Aggregate rate divides the sum of each client's N−1 tokens by the whole batch's first-to-last token window. Overlap counts come from client stream intervals, not a GPU occupancy gauge.

| Clients | EXL3 aggregate tokens/s | Overlap | NVFP4 aggregate tokens/s | Overlap | EXL3 PLE8 mmap aggregate tokens/s | Overlap | EXL3 mmap Spark (BF16 PLE) aggregate tokens/s | Overlap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 111.70 (107.79–116.80) | 1 | 113.24 (112.45–117.52) | 1 | 99.18 (87.88–102.05) | 1 | 27.13 (25.04–27.61) | 1 |
| 2 | 191.37 (190.78–197.22) | 2 | 213.17 (209.52–214.76) | 2 | 162.30 (161.35–165.18) | 2 | 43.67 (42.31–44.65) | 2 |
| 4 | 347.87 (337.22–358.47) | 4 | 365.63 (339.10–370.64) | 4 | 306.38 (303.24–316.98) | 4 | 65.48 (63.72–67.61) | 4 |
| 8 | 532.66 (518.22–536.03) | 8 | 620.24 (606.62–622.41) | 8 | 493.19 (485.98–510.16) | 8 | 97.46 (90.22–99.77) | 8 |
| 16 | 696.96 (673.69–703.47) | 16 | 930.71 (915.42–956.41) | 16 | 659.75 (647.57–670.61) | 16 | 101.00 (98.19–101.90) | 12 |

Raw: [EXL3](exl3-final/clients.json), [NVFP4](nvfp4-final/clients.json), [EXL3 PLE8 mmap](exl3-ple8-mmap-final/clients.json), [EXL3 mmap Spark (BF16 PLE)](spark-final/clients.json).

## Prefill matrix: C1

Exact prompt lengths, unique first cache blocks and three measurements after a warmup at each depth. Effective prompt tokens/s includes server tokenization and the handoff of the first output token; it is not isolated GPU prefill time.

| Prompt tokens | EXL3 tokens/s | EXL3 TTFT, s | NVFP4 tokens/s | NVFP4 TTFT, s | EXL3 PLE8 mmap tokens/s | EXL3 PLE8 mmap TTFT, s | EXL3 mmap Spark (BF16 PLE) tokens/s | EXL3 mmap Spark (BF16 PLE) TTFT, s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2048 | 7046.6 (7036.5–7058.2) | 0.291 (0.290–0.291) | 10432.6 (10396.8–10440.6) | 0.196 (0.196–0.197) | 6888.2 (6883.2–6898.8) | 0.297 (0.297–0.298) | 1719.3 (1339.7–1731.3) | 1.191 (1.183–1.529) |
| 8192 | 7513.1 (7503.0–7517.6) | 1.090 (1.090–1.092) | 11072.0 (11069.3–11085.0) | 0.740 (0.739–0.740) | 7432.7 (7431.9–7441.9) | 1.102 (1.101–1.102) | 1834.2 (1833.3–1835.4) | 4.466 (4.463–4.469) |
| 32768 | 7452.9 (7452.3–7454.0) | 4.397 (4.396–4.397) | 10900.3 (10892.9–10908.5) | 3.006 (3.004–3.008) | 7411.3 (7404.7–7419.3) | 4.421 (4.417–4.425) | 1827.0 (1798.0–1829.4) | 17.936 (17.912–18.225) |
| 65536 | 7261.8 (7255.0–7270.7) | 9.025 (9.014–9.033) | 10535.6 (10528.5–10551.3) | 6.220 (6.211–6.225) | 7226.0 (7212.5–7237.3) | 9.069 (9.055–9.086) | 1779.0 (1777.7–1780.9) | 36.839 (36.800–36.866) |
| 128000 | 6965.5 (6956.1–6968.6) | 18.376 (18.368–18.401) | 9952.9 (9941.4–9962.2) | 12.861 (12.849–12.875) | 6933.4 (6931.2–6933.6) | 18.461 (18.461–18.467) | 1718.6 (1713.8–1722.3) | 74.479 (74.319–74.688) |
| 261632 | 6472.0 (6469.7–6480.1) | 40.425 (40.375–40.440) | 8967.4 (8959.7–8982.5) | 29.176 (29.127–29.201) | 6452.9 (6441.8–6457.1) | 40.545 (40.518–40.614) | 1620.6 (1619.4–1620.7) | 161.445 (161.429–161.563) |

Raw: [EXL3](exl3-final/prefill.json), [NVFP4](nvfp4-final/prefill.json), [EXL3 PLE8 mmap](exl3-ple8-mmap-final/prefill.json), [EXL3 mmap Spark (BF16 PLE)](spark-final/prefill.json).

## Context and decode scaling: C1

Synthetic filler followed by 256 forced output tokens. One warmup and three measurements at each depth; median (minimum–maximum). This measures serving capacity and speed, not long-context reasoning quality.

| Prompt tokens | EXL3 decode tokens/s | EXL3 TTFT, s | NVFP4 decode tokens/s | NVFP4 TTFT, s | EXL3 PLE8 mmap decode tokens/s | EXL3 PLE8 mmap TTFT, s | EXL3 mmap Spark (BF16 PLE) decode tokens/s | EXL3 mmap Spark (BF16 PLE) TTFT, s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2048 | 216.74 (153.01–224.41) | 0.304 (0.298–0.305) | 155.04 (142.64–189.43) | 0.206 (0.206–0.207) | 190.00 (176.44–212.07) | 0.305 (0.297–0.307) | 34.56 (33.12–35.25) | 1.257 (1.215–2.667) |
| 8192 | 219.86 (217.52–220.13) | 1.114 (1.110–1.117) | 147.89 (140.88–191.44) | 0.755 (0.752–0.758) | 219.37 (156.44–223.49) | 1.127 (1.118–1.128) | 39.39 (32.90–39.84) | 4.537 (4.490–8.041) |
| 32768 | 219.54 (211.66–223.77) | 4.460 (4.457–4.462) | 192.36 (192.16–193.06) | 3.055 (3.053–3.058) | 216.10 (210.91–219.33) | 4.493 (4.486–4.494) | 39.65 (34.94–39.65) | 18.057 (18.011–21.469) |
| 65536 | 220.39 (220.12–220.72) | 9.142 (9.137–9.143) | 193.20 (191.47–193.29) | 6.309 (6.307–6.319) | 215.01 (214.89–219.06) | 9.292 (9.231–9.546) | 39.13 (34.48–39.64) | 40.217 (40.152–40.305) |
| 131072 | 219.82 (218.19–221.66) | 18.998 (18.977–18.999) | 193.55 (193.44–194.84) | 13.349 (13.347–13.357) | 217.44 (217.28–219.78) | 19.031 (19.022–19.195) | 39.59 (39.11–39.63) | 82.992 (82.938–86.699) |
| 261632 | 224.17 (221.72–226.40) | 40.586 (40.571–40.632) | 196.69 (196.09–197.54) | 29.303 (29.295–29.306) | 220.81 (217.99–220.81) | 40.749 (40.737–40.763) | 39.66 (39.66–39.66) | 179.194 (179.059–179.221) |

Raw: [EXL3](exl3-final/context.jsonl), [NVFP4](nvfp4-final/context.jsonl), [EXL3 PLE8 mmap](exl3-ple8-mmap-final/context.jsonl), [EXL3 mmap Spark (BF16 PLE)](spark-final/context.jsonl).

## Reference coding task: C1 across KV depths

The async task-runner prompt is identical to the reference recipe. Qwen's native non-thinking template replaces GLM's template. Temperature is 0.2, with a fixed seed and 256 forced output tokens. One warmup precedes three measurements per depth. Prompts repeat to retain existing KV; these TTFTs are not uncached prefill measurements. Rates use the reference's N−1 token convention; raw receipts also retain the rate excluding the whole initial SSE burst. The fixed token cap is not a generated-code correctness test.

| Prompt depth | EXL3 decode tokens/s | NVFP4 decode tokens/s | EXL3 PLE8 mmap decode tokens/s | EXL3 mmap Spark (BF16 PLE) decode tokens/s |
| --- | --- | --- | --- | --- |
| Task only | 185.55 (185.06–185.95) | 166.92 (166.08–171.40) | 183.45 (183.41–183.58) | 36.21 (36.09–36.22) |
| 8192 | 185.51 (181.73–190.09) | 173.65 (170.58–174.45) | 185.42 (183.75–188.69) | 36.86 (35.03–36.91) |
| 32768 | 183.37 (167.16–188.15) | 166.82 (166.40–169.35) | 180.28 (171.85–186.36) | 36.33 (36.32–37.50) |
| 65536 | 182.49 (177.04–193.39) | 165.82 (165.53–176.76) | 176.87 (176.69–188.08) | 36.11 (35.63–36.84) |
| 128000 | 186.82 (186.38–190.87) | 169.31 (169.25–170.33) | 184.41 (181.97–194.83) | 37.95 (37.21–38.16) |
| 261632 | 190.37 (190.17–197.46) | 177.83 (164.82–178.54) | 183.27 (181.28–184.39) | 37.18 (36.10–37.71) |

Raw: [EXL3](exl3-final/code-agent.jsonl), [NVFP4](nvfp4-final/code-agent.jsonl), [EXL3 PLE8 mmap](exl3-ple8-mmap-final/code-agent.jsonl), [EXL3 mmap Spark (BF16 PLE)](spark-final/code-agent.jsonl).

EXL3 also returned all 256 requested tokens after a 261888-token prompt at the exact 262144-token boundary: [receipt](exl3-final/context-boundary.jsonl).

NVFP4 also returned all 256 requested tokens after a 261888-token prompt at the exact 262144-token boundary: [receipt](nvfp4-final/context-boundary.jsonl).

EXL3 PLE8 mmap also returned all 256 requested tokens after a 261888-token prompt at the exact 262144-token boundary: [receipt](exl3-ple8-mmap-final/context-boundary.jsonl).

EXL3 mmap Spark (BF16 PLE) also returned all 256 requested tokens after a 261888-token prompt at the exact 262144-token boundary: [receipt](spark-final/context-boundary.jsonl).

## Functional and tool checks

| Quant | API tool choices | Numbered images per request | 8K/240K retrieval |
| --- | --- | --- | --- |
| EXL3 | 16/16 | 1: pass, 4: pass, 16: pass | 6/6 |
| NVFP4 | 16/16 | 1: pass, 4: pass, 16: pass | 6/6 |
| EXL3 PLE8 mmap | 16/16 | 1: pass, 4: pass, 16: pass | 6/6 |
| EXL3 mmap Spark (BF16 PLE) | 16/16 | 1: pass, 4: pass, 16: pass | 6/6 |

| Quant | Full suite points | Hard Mode points | Raw |
| --- | --- | --- | --- |
| EXL3 | 152/176 | 32/38 | [full tool traces](exl3-final/tools.md) |
| NVFP4 | 149/176 | 29/38 | [full tool traces](nvfp4-final/tools.md) |
| EXL3 PLE8 mmap | 146/176 | 27/38 | [full tool traces](exl3-ple8-mmap-final/tools.md) |
| EXL3 mmap Spark (BF16 PLE) | 154/176 | 29/38 | [full tool traces](spark-final/tools.md) |

EXL3 mmap Spark (BF16 PLE) evaluator-flagged cases:

- TC-42 (Extra Parameter Injection): Injected extra parameters despite additionalProperties: false.

API checks cover required/named/auto/none choices, thinking on/off and streaming/non-streaming. Retrieval places a random key early, midway and late in 8192- and 240000-token filler archives. Image checks read ordered numbers from 1, 4 and 16 images; they are smoke tests, not broad vision evaluation.

Tool-eval-bench is pinned at `cf54b4bfe705f12f71e8866f10730572497c8105`. Results are earned/possible points from a C8 run (eight concurrent cases), not a normalized score for comparison with other execution setups. The full 88-case suite includes 19 Hard Mode scenarios, with thinking enabled, temperature zero, one trial, eight parallel cases and at most eight turns. The linked reports retain failures and partial scores.

The Spark tool server logged two XGrammar FSM-rejection diagnostics, with no grammar-triggered request termination logged and zero evaluator-reported request errors. [Diagnostic review](spark-review/SERVER-DIAGNOSTICS.md).

## mmap memory snapshot

Captured after the performance/retrieval suite, before the full tool evaluation. These are process mapping observations, not a working-set ceiling or a low-RAM test. Linux can retain and reclaim clean checkpoint pages as workloads change.

| Checkpoint mappings | Mapped GiB | Resident mapped GiB | Anonymous mapped GiB | Dirty mapped GiB |
| --- | --- | --- | --- | --- |
| 128 | 47.68 | 19.45 | 0.00 | 0.00 |

The backing filesystem is ext4 on a Samsung 9100 PRO 4TB NVMe. PREWARM, READAHEAD and PINNED are off; the run uses the existing file cache and the warmups specified above. [Full memory and storage receipt](exl3-ple8-mmap-final/memory.json).

## Spark BF16 PLE memory snapshot

Spark uses unified CPU/GPU memory with GPU memory utilization capped at 0.7. Mapped checkpoint pages are reclaimable file cache; their resident size is a snapshot, not a fixed working-set limit. The BF16 PLE table is approximately 95.37 GiB on disk.

| Checkpoint mappings | Mapped GiB | Resident mapped GiB | Anonymous mapped GiB | Dirty mapped GiB |
| --- | --- | --- | --- | --- |
| 128 | 95.37 | 2.61 | 0.00 | 0.00 |

[Full Spark memory and storage receipt](spark-final/memory.json).

