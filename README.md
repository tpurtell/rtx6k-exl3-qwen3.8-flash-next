# Qwen3.8 Flash Next on one RTX PRO 6000 96 GB

Recipe under development for:

- `wrldsuksgo2mars/Qwen3.8-Flash-Next-EXL3-K4.25-v1`, retaining mixed K4/K5
  allocation separately for each expert projection, including MTP.
- `nvidia/Qwen3.8-Flash-Next-NVFP4`.

Target: TP=1, host-resident embeddings and n-gram tables, FP8 KV, vision, tuned
MTP, 262144 context and concurrency 16 (minimum 8 subject to measured capacity).

C1 performance is the priority for selecting the default profile. The recipe
also records the C16 throughput and capacity tradeoffs from tuning.

Both quants serve with CUDA graphs, FP8 KV, host token embeddings and the
entire n-gram PLE table in host RAM. EXL3 preserves each expert's independent
gate/up/down K4/K5 allocation, including MTP. This mixed-projection support
is required for the checkpoint and is included in the pinned B12x fork.

Development measurements on one RTX PRO 6000 Blackwell 96 GB at 400 W:

| Measurement | EXL3, MTP3 | NVFP4, MTP2 |
|---|---:|---:|
| Seven-workload weighted decode, tokens/s | 152.97 | 152.40 |
| Code workload median, tokens/s | 205.58 | 182.82 |
| Accepted draft tokens | 56.05% | 65.50% |
| Independent 16-client aggregate decode, tokens/s | Pending final test | 881.49 |
| Retrieval at early/middle/late positions, 8K and 240K filler | 6/6 | 6/6 |

The blend uses one warmup and three measured responses per workload,
excluding prefill and the first SSE token burst. Rates include responses
that fail output contracts; they are not successful-task throughput.
The 16-client probe uses 128 forced output tokens and one measured run.
All 16 NVFP4 streams overlap. Full-context requests share the KV pool;
16 configured slots do not imply 16 simultaneous 262144-token requests.

Both quants have passed 1/4/16-image probes. The full 88-case tool evaluation
with Hard Mode enabled scores EXL3 145/176 and NVFP4 153/176 points, but
EXL3 was tested before a tool-constraint parser fix and needs a rerun.
Exact 100-word orchid repetition is unreliable; raw failures are retained.
MTP tuning, final benchmark matrices and release publication remain in progress.

Build and run from this checkout (Docker with NVIDIA GPU access required):

```bash
bash recipe/build.sh
QUANT=exl3 bash recipe/download.sh
QUANT=exl3 GPU=0 MTP_TOKENS=3 bash recipe/start.sh
# Stop the first model before loading the other to release its host tables.
bash recipe/stop.sh
QUANT=nvfp4 bash recipe/download.sh
QUANT=nvfp4 GPU=0 MTP_TOKENS=2 bash recipe/start.sh
```

The API listens on port 8001 with model aliases `qwen38-exl3` and
`qwen38-nvfp4`. This recipe is being qualified on a host with 183 GiB RAM.
EXL3's BF16 PLE table alone occupies approximately 95 GiB; NVIDIA's FP8
table uses approximately 48 GiB. Each target/draft token embedding uses
another 1.184 GiB of host memory. Checkpoint weights are downloaded separately.

See the
[qualification ledger](docs/qualification.md) and
[checkpoint audit receipts](recipe/benchmarks).
