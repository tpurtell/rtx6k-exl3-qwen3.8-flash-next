# Qualification ledger

Selection priority: the user clarified that C1 matters most. Final defaults
should favor measured C1 performance; retain C16 tuning and capacity results
as documented tradeoffs rather than optimizing the default primarily for C16.

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

## Host embeddings and single-GPU PLE worker

- Native CUDA UVA allows the ordinary embedding gather to access pinned host
  memory. `qwen_host_embedding.py` applies it only to token embeddings, not
  the output head. A GPU test confirms `cudaPointerGetAttributes` reports
  host memory, exact lookups, and exact graph replay after token-ID mutation.
  Receipt: `recipe/benchmarks/host-embedding-gpu.txt`.
- `dev6` target+MTP memory profiling completed for both quants. The processes
  then stalled in real warmup; a live py-spy stack found the driver waiting
  during QSA kernel loading. Source inspection shows PLE spawn/wait methods
  are called only in `multiproc_executor.py`, not the default TP1 uniproc
  executor. Both probes had a registered PLE connector but no PLE CPU process.
  The GPU semaphore wait consequently had no producer. They were explicitly
  stopped after this diagnosis, not merely because observation timed out.
- `start.sh` now selects `--distributed-executor-backend mp` with TP1.
  This uses vLLM's native PLE worker lifecycle and still exposes exactly one
  GPU per server. `dev7` includes the verified host-token-embedding helper;
  `qwen38-exl3-fp8-dev7` and `qwen38-nvfp4-fp8-dev7` are the new probes.
- Ported the reference's generic decode/prefill, seven semantic content and
  vision harnesses, with provenance. Full benchmark execution remains pending.

## NVIDIA FP8 PLE and first serving diagnostic

- `dev7` revealed that native PLE dispatch recognized `Fp8Config` but not
  ModelOpt mixed metadata. NVIDIA's FP8 ngram table was allocated as BF16;
  concurrent EXL3 startup exhausted host RAM. The new patch selects the
  existing scalar-scale FP8 PLE implementation for the actual NVIDIA layer
  metadata. A storage test verifies FP8 CPU allocation, scalar scale loading,
  and byte-exact CPU lookup (`recipe/benchmarks/nvidia-ple-storage.txt`).
  This isolated test mocks tensor-parallel rank/world size; it does not test
  the complete serving lifecycle.
- `dev8` NVIDIA successfully starts its PLE CPU worker, loads target and
  MTP, and serves with host token embeddings, host FP8 PLE, FP8 KV, MTP3,
  TP1 and eager execution. An arithmetic smoke returned 42 for 19+23.
  Reported KV capacity is 661722 tokens: 16 scheduler slots do **not** imply
  16 simultaneous 262144-token requests (capacity ratio is about 2.52).
- The first seven-workload diagnostic is preserved in
  `recipe/benchmarks/nvfp4-dev8-seven-diagnostic.jsonl`. It has no warmup,
  one repetition and eager execution; it is not a release performance result.
  Code, greeting, topic and JSON pass the inherited validators. Math runs
  out of its 128-token budget before the final answer; fable has 173 words
  against a 140–170 requirement. Chinese explains the mechanism and fork
  example, but fails the validator's literal phrase check. These failures
  remain recorded; full numerical and task-quality qualification is pending.
- Added a streaming workload harness retaining complete responses, token IDs,
  usage and SSE chunk times. Decode timing excludes every token in the first
  burst; the conventional N−1 rate is also retained. Compiler caches now
  persist under `~/.cache/qwen38-rtx/<quant>` between recipe containers.
- EXL3 mixed K4/K5 projection support remains mandatory, including MTP.
  Its loader and geometry tests pass, but successful full serving and all
  requested benchmark suites still need qualification. Initial full-model
  tests run one quant at a time to respect host RAM capacity.
- The eager NVIDIA orchid diagnostic (one warmup, three measured runs) also
  fails exact-100 repetition quality: measured counts 101, 750, 750; the last
  two terminate at the 1500-token limit. Raw responses and timings are in
  `recipe/benchmarks/nvfp4-dev8-orchid-diagnostic.jsonl`. The roughly 90–94
  measured decode tokens/s are diagnostic throughput, not successful-task
  performance. MTP and target-only comparisons remain necessary.

## EXL3 first serving and vision

- `dev8` EXL3 now serves successfully on GPU0 with target and MTP retaining
  separate K4/K5 gate/up/down assignments. MTP layer48 reports K4 expert
  counts 440/392/320 and K5 counts 72/120/192 for these projections.
  Target plus MTP loading reports 71.99 GiB; host token offload is logged
  twice at 1.184 GiB each. The PLE worker verifies its BF16 table and starts.
- EXL3 reports 837333 KV tokens (3.19×262144), with 16 scheduler slots.
  The development image, arguments, GPU selection, and relevant startup
  evidence for both quants are in `recipe/benchmarks/dev8-runtime.json`.
- The eager, unwarmed EXL3 seven-workload diagnostic passes code, greeting,
  topic and JSON. Math again truncates at 128 tokens after correct
  intermediate calculations; fable has 176 words; Chinese fails the
  inherited literal phrase check. Original evidence is preserved in
  `recipe/benchmarks/exl3-dev8-seven-diagnostic.jsonl`.
- For subsequent runs, the math output budget is 256 tokens. The Chinese
  proxy now accepts 寫入觸發複製 and 寫入時觸發複製 as well as 寫入時複製;
  four bullets, fork and page checks remain. Positive variants and
  missing-term counterexamples were checked. This is a wording check,
  not comprehensive semantic grading. The fable criterion is unchanged.
- EXL3 correctly reads the ordered numerals in 1, 4 and 16 images with native
  nonthinking chat: `recipe/benchmarks/exl3-dev8-vision-diagnostic.json`.
  No maximum-image rejection claim is made; no explicit limit was configured.
- Added exact-depth C1 synthetic context/decode harness with retained SSE
  token IDs and timings. Launch supports MTP_TOKENS=0 for target-only control
  runs. Native batch-size speculative scheduling is available; confidence
  adaptive verification is DSpec-only in this pinned source. Tuning remains
  pending, and B12x currently reports heuristic MoE choices for Qwen geometry.
- EXL3 eager context probes complete at 2048, 8192, 32768, 131072 and
  261632 prompt tokens. The last point generates 128 further tokens and
  measures 40.780 s TTFT / 57.109 decode tokens/s. These are single, unwarmed
  synthetic probes, not retrieval quality or final performance measurements.
  Raw receipts: `exl3-dev8-context-diagnostic.jsonl` and
  `exl3-dev8-long-context-diagnostic.jsonl` under `recipe/benchmarks`.
  Both GPUs report a 400 W power limit during these probes.
- Eager short-context parallel continuations complete at C8 and C16 after
  one warmup per point, emitting 64 tokens per sequence. Single measured
  aggregate rates are 203.71 / 407.27 tokens/s using the global first-to-last
  SSE window and sum(N−1) numerator. This is a shared-prompt continuation
  load, not 16 independent long-prefill requests; timing arrays are retained
  in `recipe/benchmarks/exl3-dev8-concurrency-diagnostic.json`.
- EXL3 orchid exact-count results are 100/750/100 across three measured
  runs (one prior warmup produced 101). The 750 case hits the 1500-token
  output limit. Raw diagnostic responses are retained in
  `recipe/benchmarks/exl3-dev8-orchid-diagnostic.jsonl`; two successes do not
  qualify the failing repetition workload. The next probe enables CUDA
  graphs with the same image, checkpoint and MTP3 settings.

## QSA workspace on the graph capture stream

- `qwen38-exl3-fp8-graph-dev8` fails its first graph startup because vLLM
  warms QSA on one CUDA stream and captures on another. The bridge keyed
  scratch by stream and rejected allocation during capture.
- The bridge now uses PyTorch's graph-aware allocator for a new stream and
  retains the tensors for graph replay. Per-stream isolation remains.
  Eight BF16/FP8 × 1/64/65/2048-row GPU checks pass against the dense oracle
  with a separate capture stream and mutated-query replay. Receipt:
  `recipe/benchmarks/qsa-cross-stream-gpu.txt`. `dev9` contains this correction;
  full-model graph qualification still needs a successful rerun.
- Tool evaluation is prepared in an isolated checkout at the reference
  recipe's commit `cf54b4bfe705f12f71e8866f10730572497c8105`, version
  2.6.1.dev45, containing 88 public cases including Hard Mode. The older,
  locally modified checkout in `~/Developer/tool-eval-bench` is untouched.

## EXL3 graph-mode serving

- `qwen38-exl3-fp8-graph-dev9` starts successfully with piecewise and full
  CUDA graphs. Capture takes 7 seconds and 0.96 GiB; KV capacity reports
  850059 tokens (3.24×262144). Runtime evidence is in
  `recipe/benchmarks/exl3-dev9-graph-runtime.json`. The torch profiler is
  configured but was not activated during the content measurements.
- The seven-workload run uses one warmup and three measured repetitions,
  native nonthinking chat, temperature0, MTP3 and 400 W. Weighted decode is
  152.97 tokens/s; medians: code205.58, math214.97, fable117.65,
  greeting175.90, topic148.78, JSON167.21, Chinese127.58 tokens/s.
  19/21 content checks pass; two fables exceed the requested word count.
  This is a measured development configuration, not a final tuned release.
- Timed-suite MTP counters record 2137 accepted / 3813 draft tokens, across
  1271 drafts: 56.05% acceptance and mean acceptance length2.681.
  The harness waits 11 seconds (outside request timing) before and after
  timed runs for vLLM's 10-second statistics interval. Raw snapshots and
  all responses are in `recipe/benchmarks/exl3-dev9-graph-seven.jsonl`.
  Counters are suite-level and require exclusive access to the endpoint.
- A full 88-case tool run, with thinking enabled and evaluation parallelism8,
  is underway against this configuration. Its results, graph vision/context
  reruns, target-only controls, MTP tuning and NVIDIA graph qualification
  remain pending.

## Tool evaluation, retrieval and constraint enforcement

- EXL3 dev9's 88-case run scores 145/176 points (82/100 rounded): 64 pass,
  17 partial, 7 fail. Hard Mode alone scores 29/38: 13 pass, 3 partial,
  3 fail. Full traces and summary are preserved as
  `recipe/benchmarks/exl3-dev9-graph-tools.md` and `.json`; the benchmark
  also persisted its SQLite run in the isolated tool-eval checkout.
- All six graph retrieval checks pass: exact keys at 5%, 50%, 95% character
  positions in 8192-token and 240000-token filler archives. Actual long
  prompts are 240070–240072 tokens, including chat framing/instructions.
  Receipt: `recipe/benchmarks/exl3-dev9-graph-retrieval.jsonl`. This is a
  single-key synthetic test, not comprehensive long-context task quality.
- TC-45 exposed an API constraint bug, independently reproduced for required
  and named tool choice with thinking both on and off. The combined Qwen
  parser engine skips grammar adjustment when reasoning/tool adapters are
  collapsed. The new patch keeps DelegatingParser for structural-tag tool
  adapters. A real-tokenizer CPU regression verifies required/named grammar,
  unconstrained auto/none behavior, and reasoning plus automatic call parsing.
  Receipt: `recipe/benchmarks/tool-constraints-cpu.txt`. `dev10` builds with
  this correction; live enforcement still needs qualification and the old
  tool score remains a pre-fix result.
- A short profiled EXL3 code completion identifies mixed MoE and BF16 matrix
  kernels as the main GPU time consumers. Raw trace and kernel-only totals:
  `recipe/benchmarks/exl3-dev9-code-profile.trace.json.gz` and
  `exl3-dev9-profile-summary.json`. Profiled timings are not throughput results.
- Prefill harness invocations now use a unique nonce so repeating a run on
  the same server cannot accidentally reuse the prior run's prompt cache.

## NVIDIA graph-mode serving and live tool constraints

- `qwen38-nvfp4-fp8-graph-dev10` successfully starts with FlashInfer MoE
  autotuning and CUDA graphs. Capture uses 1.00 GiB and takes 9 seconds;
  reported KV capacity is 621001 tokens (2.37×262144). Both token tables
  and the FP8 PLE remain host-resident. Runtime receipt:
  `recipe/benchmarks/nvfp4-dev10-graph-runtime.json`.
- All 16 live API tool-constraint checks pass: required/named/auto/none ×
  thinking on/off × streaming/nonstreaming. Raw requests and responses are
  in `recipe/benchmarks/nvfp4-dev10-tool-constraints.jsonl`; runner:
  `recipe/scripts/test-api-tool-constraints.py`.
- The seven-workload blend (one warmup, three measured runs, MTP3, 400 W)
  records 149.46 weighted decode tokens/s. Medians: code202.67, math214.94,
  fable115.08, greeting181.44, topic149.99, JSON174.13, Chinese119.90.
  18/21 content checks pass; all three failures are overlong fables.
  MTP counters: 2010 accepted / 3879 draft tokens over 1293 drafts,
  51.82% acceptance and mean acceptance length2.555. Raw evidence:
  `recipe/benchmarks/nvfp4-dev10-graph-seven.jsonl`.
- NVIDIA graph vision passes at 1/4/16 images. Its single-probe synthetic
  context sweep completes at 8192, 131072 and 261632 prompt tokens plus128
  output tokens. The last point measures 27.865 s TTFT and238.73 decode
  tokens/s. These are synthetic diagnostics, not final context-quality
  results. Receipts: `nvfp4-dev10-graph-vision.json` and
  `nvfp4-dev10-graph-context-diagnostic.jsonl` under `recipe/benchmarks`.
- Independent-client C8/C16 probes complete with unique prompts and128
  forced output tokens each. Measured global-window rates are549.68/544.11
  tokens/s. C8 has8 overlapping first-to-last SSE intervals; C16 peaks at13,
  with three TTFTs delayed about2.1–2.3 seconds. Thus this MTP3/.94 memory
  configuration has not demonstrated16 simultaneous active sequences.
  C8's logged KV usage is59.3%, consistent with cache pressure at16.
  The client runner preserves each request's timing arrays. MTP2 and memory
  budget tuning will test whether16 active sequences fit.
- NVIDIA graph MTP3 orchid counts are102/102/750 in measured runs; all
  fail exact100, and the last hits the1500-token budget. Warmup also hits
  the budget. Raw responses and timed-suite MTP counters are preserved in
  `recipe/benchmarks/nvfp4-dev10-graph-orchid.jsonl`. These repetition rates
  must not be represented as successful-task throughput.

## NVIDIA MTP2 comparison and vocabulary-kernel candidate

- NVIDIA MTP2 at the same .94 memory fraction and dev10 image reports644874
  KV tokens, with0.91 GiB graph capture. The seven-workload blend measures
  152.40 weighted tokens/s versus149.46 for MTP3. Code slows182.82 versus
  202.67 tokens/s, while fable and Chinese improve. Suite acceptance is
  65.50%, mean acceptance length2.310. One fable is overlong; two Chinese
  answers explain COW correctly but fail the literal-phrase proxy. Original
  validator results remain preserved in `nvfp4-dev10-mtp2-seven.jsonl`.
- Crucially, the independent C16 test reaches16 overlapping stream intervals
  and881.49 aggregate tokens/s. C8 reaches552.95. This demonstrates the
  requested16-client capacity at short context with MTP2, unlike the MTP3
  probe's13 overlapping streams. The full88-case tool run is now underway
  with MTP2. Runtime and client receipts are named `nvfp4-dev10-mtp2-*`
  under `recipe/benchmarks`.
- A GPU0 microbenchmark tests B12x's existing planned BF16 vocabulary
  projection at Qwen's actual M1/K2560/N248320 geometry against native
  F.linear. Median CUDA time is772.04 versus823.78 microseconds (about6.3%
  lower), over7 interleaved graph measurements of20 calls each. Three
  mutated-input numerical checks pass; the full weights exceed L2. This
  kernel is not yet integrated into serving, and no end-to-end gain is
  claimed. Runner: `recipe/scripts/benchmark-vocab.py`; receipt:
  `recipe/benchmarks/bf16-vocab-k2560-n248320.txt`.
- NVIDIA MTP2's full tool run scores153/176 points (87/100):69 pass,
  15 partial,4 fail. Hard Mode scores32/38:15 pass,2 partial,2 fail.
  TC-45 now passes with an enforced calculator call. Full traces and summary
  are retained as `recipe/benchmarks/nvfp4-dev10-mtp2-tools.md` and `.json`.
- All six NVIDIA MTP2 retrieval checks pass at early/middle/late positions
  in8192- and240000-token filler archives. Actual long prompts contain
  240071–240073 tokens. Receipt: `nvfp4-dev10-mtp2-retrieval.jsonl`.
- `dev11` adds an opt-in vocabulary bridge (`B12X_VOCAB=1` in start.sh,
  disabled by default). It preplans/precompiles after loading and only
  replaces single-row BF16, unbiased projections at the exact checkpoint
  geometry. Native multi-row, biased and explicit FP32-head paths remain.
  The actual logits-processor bridge passes mutated graph replay, dtype and
  native-fallback checks (`recipe/benchmarks/vocab-bridge-gpu.txt`).
  A same-MTP2 serving comparison remains required before enabling it by default.

## Candidate defaults after serving comparisons

- Enabling the planned B12x vocabulary projection with NVIDIA MTP2 measures
  150.14 weighted tokens/s versus152.40 without it. Code improves186.14
  versus182.82, but Chinese and the overall blend regress; accepted draft
  fraction also changes63.55% versus65.50%. Three repetitions do not
  establish an overall win, so the option stays disabled by default. Raw
  evidence: `recipe/benchmarks/nvfp4-dev11-mtp2-vocab-seven.jsonl`.
- The B12x HC combine+norm API rejects vLLM's strided injection view at M>1.
  A second comparison includes the necessary contiguous packing. Native is
  faster at M1/4/16/64; at M2048 B12x is only slightly faster (79.38 versus
  81.27 microseconds). Mutated graph outputs agree with native within the
  stated tolerance. Native remains the serving choice; no HC bridge is
  installed. Runner: `recipe/scripts/benchmark-hc.py`; complete timings:
  `recipe/benchmarks/hc-native-vs-b12x.txt`.

## MTP1 and GDN comparisons

- NVIDIA dev11 MTP1 at .94 measures 130.35 weighted tokens/s on the same
  seven-workload suite, versus 152.40 for MTP2. Acceptance is 76.58%, but
  mean acceptance length is only 1.766. Independent C8/C16 probes improve
  to 597.43/915.16 tokens/s. These are one measured run after one warmup;
  a batch-size-dependent draft schedule remains a candidate, not a default.
  Receipts: `recipe/benchmarks/nvfp4-dev11-mtp1-*`.
- The public B12x GDN transaction was compared with native post-convolution
  GDN at QK16/V48, FP32 recurrent state, BF16 activations and sigmoid gating.
  Native was faster for B1 with 1/3/4 tokens and B8 with 3 tokens; for B8,
  native measured 30.43 microseconds versus B12x 42.99. These comparisons
  use contiguous inputs and restore state outside the timed CUDA events.
- The B16/3-token candidate failed numerical verification after mutated
  graph replay. The independent reference agrees with native (maximum
  output error 0.015625), while B12x has a maximum error of 1.684 and a
  state error of 0.06675. The runner stops without reporting B16 timing.
  No B12x GDN bridge is installed. Native remains the serving path based
  on both performance and correctness. The reproducible runner is
  `recipe/scripts/benchmark-gdn.py`; full measurements and failure evidence
  are in `recipe/benchmarks/gdn-native-vs-b12x.txt`.
- NVIDIA's no-MTP control measures 96.38 weighted tokens/s, with C8/C16
  independent clients at 500.96/855.50 tokens/s. Static MTP2 improves the
  blend by approximately 58%; MTP1 improves the C16 probe by approximately
  7%. Raw responses, client timings and runtime configuration are retained
  in `recipe/benchmarks/nvfp4-dev11-mtp0-*`.

## Adaptive draft schedule and precise NVFP4 MoE candidate

- NVIDIA's native dynamic schedule `[[1,4,2],[5,16,1]]` at maximum MTP2
  measures 146.04 weighted tokens/s, below static MTP2's 152.40. Its
  independent C8/C16 probes measure 585.89/858.97 tokens/s. It does not
  establish an overall advantage, so static MTP2 remains the leading profile.
  Runtime, raw responses and all client timings are retained as
  `recipe/benchmarks/nvfp4-dev11-adaptive21-*`.
- EXL3 MTP2 measures 149.16 weighted tokens/s, versus MTP3's 152.97.
  Code measures 179.04 versus 205.58. Independent C8/C16 probes measure
  532.52/718.39 tokens/s. Receipts: `recipe/benchmarks/exl3-dev11-mtp2-*`.
- The pinned fork's checkpoint-backed NVFP4 MoE benchmark compares layer 0,
  TP1, H2560/I640/E512/top10, shared activation scales, synthetic routes,
  three timing repetitions and 256 MiB L2 eviction per launch. Fast math
  fails the unchanged 0.9999 cosine threshold at six of seven shapes;
  FlashInfer also misses that oracle threshold and is reported separately
  as a reference warning. No tolerance was relaxed.
- Disabling fast math passes all seven candidate oracle checks, with
  cosine similarity 0.999958–0.999966. Precise B12x CUDA graph medians at
  M1/3/4/16/48/64/2048 are 47.1/73.7/98.3/264.2/591.9/692.2/1283.1
  microseconds, versus FlashInfer 61.4/100.4/118.8/311.3/632.4/738.6/1371.6.
  Full command configuration, error metrics and timing ranges are in
  `recipe/benchmarks/nvfp4-moe-fast-math.txt` and `nvfp4-moe-precise.txt`.
  These are component measurements; serving integration is still under test.
- The opt-in `B12X_NVFP4=1` bridge in dev13 passes all 21 mutated graph
  checks against the unchanged oracle, using the checkpoint's real weights
  and scales. The test exercises the patched FlashInfer expert class,
  BF16 input deferral, output dimensions and pointer-identical weight
  storage at M1/3/4/16/48/64/2048. Runtime scratch is shared serially across
  layers within each CUDA stream. Native routing and shared-expert handling
  remain in vLLM's modular pipeline. Full-model qualification is pending.
  Receipt: `recipe/benchmarks/nvfp4-moe-bridge-gpu.txt`; runner:
  `recipe/scripts/test-nvfp4-moe.py`.
- EXL3's no-MTP control measures 92.76 weighted tokens/s; MTP3 is about
  65% faster on the blend. C8/C16 target-only probes measure 465.99/762.88
  tokens/s. The C16 result exceeds static MTP2's 718.39, motivating a
  shorter-draft batch comparison. Receipts: `recipe/benchmarks/exl3-dev12-mtp0-*`.
- EXL3 MTP1 measures 131.54 weighted tokens/s and 141.99 median code
  tokens/s. Its C8/C16 probes improve to 561.14/861.92 tokens/s; all 16
  client streams overlap. This supports testing a shorter draft at larger
  batch sizes, while retaining longer drafts for low concurrency.
  Receipts: `recipe/benchmarks/exl3-dev13-mtp1-*`.
