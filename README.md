# Qwen3.8 Flash Next on one RTX PRO 6000 96 GB

Recipe under development for:

- `wrldsuksgo2mars/Qwen3.8-Flash-Next-EXL3-K4.25-v1`, retaining mixed K4/K5
  allocation separately for each expert projection, including MTP.
- `nvidia/Qwen3.8-Flash-Next-NVFP4`.

Target: TP=1, host-resident embeddings and n-gram tables, FP8 KV, vision, tuned
MTP, 262144 context and concurrency 16 (minimum 8 subject to measured capacity).

Both quants now serve in eager mode with FP8 KV, MTP3 and host embeddings.
EXL3 also passes ordered image reading at 1, 4 and 16 images. These are
development diagnostics; quality, graph execution and performance tuning
remain unfinished. The configured 16 slots share a KV pool of about 837K
tokens (EXL3) or 662K (NVFP4), so they cannot all hold full-length contexts.

See the
[qualification ledger](docs/qualification.md) and
[checkpoint audit receipts](recipe/benchmarks).
