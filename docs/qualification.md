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
- Base image downloaded: `vllm/vllm-openai:qwen38-flash-next` at digest
  `sha256:fc120ece0a388cc0aa1caad4a9f1cd92113484ab7ec2fd0efadd62585be05bf8`.
  Torch `2.13.0+cu130`, vLLM `0.1.dev20073+g8e685d198`, CUTLASS `4.6.2`.
  Source copied to `.work/vllm` from idle inspection container `qwen38-source`.
  Model implementation: `vllm/models/qwen3_8_flash_next/nvidia/`; PLE already
  has a `VLLM_PLE_CPU_OFFLOAD` process path. No EXL3 module is present in base.
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

## Runtime integration progress

- `qwen38-rtx:dev1` builds from the pinned Qwen base plus the released GLM
  adapter artifact, preserving its mixed projection preparation. Build/import
  passed. `recipe/patches/port-exl3-qwen38.py` adds Qwen config types, MTP
  metadata aliases, and distinguishes individual EXL3 trellis tensors from
  fused expert-bank tensors in the modern vLLM loader. Serving remains unproven.
- NVIDIA baseline `qwen38-nvfp4-baseline` exited during construction with
  `NotImplementedError: Qwen3.8-Flash-Next QSA requires a BF16 main KV cache`.
  Requested TP1, FP8 KV, context 262144, 16 sequences, MTP3, batch tokens 2048,
  memory utilization 0.94, PLE CPU offload. Full local log:
  `.work/nvfp4-baseline.log`.
- FP8 QSA integration is required. B12x already contains BF16/FP8 E4M3 sparse
  GQA support with explicit K/V descales in `attention/qsa/_sparse_gqa.py`;
  its serving integration and correctness gates are outstanding.
- `qwen38-exl3-loader-dev1` is a diagnostic startup on GPU0, port 8001:
  MTP3, 16 sequences, eager mode, 8192 context, BF16 KV, PLE CPU offload.
  This isolates the EXL3 loader from the known FP8 construction failure and
  does not qualify the requested release configuration. Inspect current
  container state and logs before proceeding or restarting.
