# Qwen3.8 Flash Next on one RTX PRO 6000 96 GB

Recipe under development for:

- `wrldsuksgo2mars/Qwen3.8-Flash-Next-EXL3-K4.25-v1`, retaining mixed K4/K5
  allocation separately for each expert projection, including MTP.
- `nvidia/Qwen3.8-Flash-Next-NVFP4`.

Target: TP=1, host-resident embeddings and n-gram tables, FP8 KV, vision, tuned
MTP, 262144 context and concurrency 16 (minimum 8 subject to measured capacity).

Serving and benchmark qualification is pending. See the
[qualification ledger](docs/qualification.md) and
[checkpoint audit receipts](recipe/benchmarks).
