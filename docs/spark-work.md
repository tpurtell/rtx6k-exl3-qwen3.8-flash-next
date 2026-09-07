# Spark branch qualification work

This branch extends the recipe to RTX SM120 and DGX Spark SM121. Main remains
unchanged until the user tries the completed Spark release.

The Spark target is the pinned EXL3 K4.25 model with original BF16 PLE, mmap,
FP8 KV and a GPU memory utilization cap of 0.7. Native arm64 build/run detection
selects Spark settings automatically. The output image will be
`ghcr.io/tpurtell/spark-exl3-qwen3.8-flash-next`.

All four hosts (ostrich, dodo, emu, kiwi) are available for concurrent work.
Initial builds use the existing pinned multiarch vLLM base and B12x commit;
the EXL3 source stage copies Python from its pinned amd64 image only.

Pending qualification:

- Native arm64 build and strict mmap patch/base checks.
- Mixed-projection loading, BF16 checkpoint gathers and mutable CUDA graphs.
- Component numerical checks and kernel comparisons on Spark.
- End-to-end C1 MTP and mmap tuning, plus C16 tradeoffs.
- Full final default-profile performance, API, vision, retrieval and C8 tool
  qualification using the existing contracts and complete raw receipts.
- Fourth table entry: EXL3 mmap Spark (BF16 PLE), compact README tables and
  platform defaults comparison. Historical RTX evidence remains unchanged.
- Published arm64 image, source branch and verifiable release evidence.

The 0.7 utilization cap is enforced for Spark configuration; no qualification
result is claimed until the actual run has completed.
