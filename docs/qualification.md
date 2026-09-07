# Qualification ledger

Status: development; no serving or performance claims yet.

## Required release gates

Both checkpoints must independently pass these gates on a single RTX PRO 6000
Blackwell 96 GB (TP=1):

- Original quantization preserved, including EXL3 K4/K5 per-projection allocation
  in target and MTP experts. Verify numerical behavior against original weights.
- N-gram tables fully resident in host RAM; token embedding table in host RAM.
- FP8 KV, vision enabled, MTP enabled, 262144 maximum context if capacity permits.
  Qualify concurrency 16, or at least 8, and document measured capacity limits.
- Tune fixed MTP depths and evaluate adaptive MTP on throughput and correctness.
- Seven content blends, orchid repeat, prefill matrix, context decode scaling,
  hard-mode tool evaluation, vision, long-context and graph/replay verification.
- Profile actual serving paths; select and qualify B12x kernels by numerical
  evidence and speed. Push any B12x work to tpurtell/sparkinfer-glmrt.
- Reproducible pinned Docker build, launch/download/stop scripts, complete README
  with raw benchmark evidence, clean-image verification, image publication and
  GitHub release. User will manually change package visibility after publication.

## Initial evidence (2026-09-07)

- Reference: `/home/tj/Developer/brandon-glm-5.3-flash/recipe`.
- B12x fork HEAD: `53f9d89c16f70e6580d0015de2934a882c61ed29`, merging Qwen
  support while retaining GLM and mixed EXL3 kernels. Local checkout: `.work/b12x`.
- Base image pull: `vllm/vllm-openai:qwen38-flash-next`; must record digest and
  inspect its APIs before implementing ports. Initial exec session: 81523.
- Two idle RTX PRO 6000 GPUs, each 97887 MiB; 183 GiB total system RAM.
- Checkpoint header audit receipts in `recipe/benchmarks/*-checkpoint-audit.json`.
  These verify indexed tensors, projection metadata and packed shapes, not
  numerical inference correctness or weight digests.
- EXL3 revision `73a050c27b8c488c65acd6d1c74e45ff02be5fab`:
  76900493024 bytes outside names containing `ple`/`ngram`, 102466171160 bytes
  in those names; 5951 experts have unequal projection bitrates.
- NVFP4 revision `2061e0b0c5d92bdf7c8fbd4241bbc2af239d7e2d`:
  81373920992 bytes outside names containing `ple`/`ngram`, 51265925402 bytes
  in those names. These name-based groups include PLE auxiliary tensors and
  must not be treated as exact runtime residency measurements.
- EXL3 MTP uses mixed K4/K5; NVIDIA MTP metadata specifies FP8_PB_WO.
- Model config declares max_position_embeddings=262144, 512 experts, hidden
  width 2560, expert width 640, 48 target layers and one MTP layer.

## Next work

Inspect the downloaded vLLM model, PLE offload, MTP, NVFP4, and quant loader APIs.
Port the GLM recipe's mature EXL3 adapter and mixed-projection preparation to
Qwen namespaces and geometry. Establish independent single-GPU baseline servers,
then address correctness/capacity and profile before tuning. GLM-specific MLA,
mHC and DCP patches require architecture review, not mechanical reuse.
