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

## QSA and mixed kernel qualification

- B12x `c76a40ee684cb3ef7d2c223d56a9b9cff25a3a1e` is pushed to the fork's
  master branch. It fixes the implicit mixed projection tile selection for
  Qwen H2560/I640: both FC stages use N128 when N256 cannot divide the
  projection. Matching FC1/FC2 CTA thread counts are preserved. Two planner
  tests passed, plus two SM120 K4/K5 numerical-versus-serial and CUDA graph
  replay tests, covering packed and direct routes. This is kernel evidence,
  not full-model correctness evidence. Logs: `.work/qwen-mixed-tests.log`.
- Before this fix, `qwen38-exl3-loader-dev1` loaded all 22 shards and prepared
  mixed target experts, then failed in its first forward with an invalid
  N256 projection tile. Log: `.work/exl3-loader-dev1.log`. The container exited.
- Four B12x QSA tests passed on GPU1: FP8 3008-token-page reference/graph
  replay, direct binary reuse, and BF16/FP8 high physical-page-offset cases.
  Command: `python3 -m pytest /opt/b12x/tests/attention/test_qsa_sparse_gqa.py
  -q -k 'fp8_3008_page or high_physical_page_offsets or reuses_direct_binary'`.
  Log: `.work/qsa-kernel-tests.log`.
- `qwen38-rtx:dev2` built successfully with an initial B12x sparse-GQA bridge.
  It retains the vLLM selector and cache writes, passes K/V descales, and
  shares scratch between sequential layers on each stream. This currently
  uses a pinned private B12x launch API; public planning and complete serving
  replay qualification remain outstanding.
- `qwen38-nvfp4-fp8-dev2` passed the FP8 QSA construction gate and loaded the
  target, then exited loading MTP: no `w2_weight_scale_inv` parameter for
  `mtp.layers.48.mlp.experts.0.down_proj.weight_scale_inv`.
  NVIDIA MTP's FP8_PB_WO needs both per-layer quant-config index remapping
  (checkpoint layer 0 to runtime layer 48) and block-FP8 expert support in
  ModelOpt mixed configuration. Log: `.work/nvfp4-fp8-dev2.log`.
- Next: rebuild with the pushed mixed geometry fix and qualify EXL3 forward;
  repair NVIDIA MTP block-FP8 loading; validate actual FP8 cache scales and
  serving outputs. Neither quant is yet serving successfully.

## MTP loader and bridge corrections

- `dev3` EXL3 loaded target plus mixed-projection MTP at layer 48, using
  73.17 GiB reported model memory. V2's MTP prefill reached 2048 rows while
  the old GLM draft arena allowed only concurrency-sized batches. The adapter
  now plans draft capacity from max_num_batched_tokens. This corrects an
  observed execution path; it is not an increase in configured concurrency.
- NVIDIA `dev4` loaded target and MTP, using 76.41 GiB reported model memory.
  The new ModelOpt patch remaps MTP quantized-layer metadata to layer 48 and
  dispatches FP8_PB_WO experts to native vLLM block-FP8 with dynamic activation
  quantization. Original E4M3 weights and BF16 2D scales are retained; no
  checkpoint rewrite. Numerical task-quality verification remains required.
- NVIDIA `dev4` then exposed a QSA bridge scratch validation error. The bridge
  now selects the unsplit direct path with no partial tensors above 64 rows.
  Eight bridge GPU checks passed: BF16/FP8 × rows 1,64,65,2048, dense attention
  oracle plus graph replay after query mutation. Receipt:
  `recipe/benchmarks/qsa-bridge-gpu.txt`; runner:
  `recipe/scripts/test-qsa-bridge.py`. Physical NHD layout and non-unit FP8
  descales are covered. These checks do not qualify complete model outputs.
- `dev5` probes were deliberately stopped after the bridge test identified
  the missing unsplit flag, before spending another startup on that known
  error. `dev6` incorporates the tested bridge fix and is building from
  `recipe/build.sh` (local log `.work/build-dev6.log`).
- Added executable build/download/start/stop scripts and immutable model
  profiles. They expose tuning controls and pin TP1/FP8/MTP/PLE offload.
  They are development commands, not a qualified release. Token embedding
  offload, complete host-residency checks, and all full-model release gates
  remain outstanding.
