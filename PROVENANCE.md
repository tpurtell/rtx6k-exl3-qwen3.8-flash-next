# Development provenance

The Dockerfile pins the Qwen vLLM base, released GLM EXL3 adapter source image,
and tpurtell/sparkinfer-glmrt commit. The EXL3 adapter preserves the source
implementation's per-projection K4/K5 weight preparation. Patches in this
recipe adapt namespaces, loading, MTP capacity and QSA execution.

`benchmark-decode.py`, `benchmark-prefill.py`, `test-content-vllm.py` and
`test-vision-vllm.py` originate from the local
`brandon-glm-5.3-flash/recipe/scripts` reference. The content runner retains
the seven semantic contracts and uses Qwen's `enable_thinking=False` template
instead of manually adding GLM's closing thinking marker. Benchmark schema
identifiers and the default model alias were adapted for Qwen. No GLM
performance results are copied into this recipe.

`code-agent-prompt.txt` preserves the async task-runner prompt from the
reference's `benchmark-dflash2-vllm.py`. `benchmark-code-agent-depth.py`
adapts its depth experiment to native Qwen non-thinking rendering and retains
all output tokens and client timings. It reports both the post-initial-burst
decode rate and the reference's N−1 rate; forced output length does not
establish generated-code correctness.

Kernel/bridge test receipts are not full-model benchmark results. Model loading
memory figures in the qualification ledger are startup observations, not
steady-state capacity guarantees. Recipe and borrowed vLLM/B12x code are
covered by their applicable source licenses; checkpoint weights retain their
own licenses and are downloaded separately.

The optional mmap PLE backport derives from vLLM PR #54129 at
`50a061f792f36364f5f95a93eee21f1e9d77f65e`. The vendored patch and upstream
regression tests retain Apache-2.0 attribution. The port preserves this
recipe's base model namespaces, resident PLE path and kernels, and corrects
scale validation defects demonstrated by independent failing regressions.
See `docs/mmap-review.md` for the exact scope, compatibility adaptations and
real-checkpoint/CUDA replay evidence. The full follow-on benchmark applies
only to `exl3-ple8` with mmap enabled; v0.1.0 results remain historical.

## Native Spark build and qualification

The recipe uses the same pinned multiarch vLLM base for native
linux/arm64 builds, selecting `sm_121a` for CuTe. The amd64 EXL3 source
stage supplies only its Python adapter. The per-projection expert allocation
and checkpoint revisions are unchanged. Spark defaults select MTP2 and
B12x vocabulary after component and serving comparisons; native HC, native
GDN and the existing mixed-expert tile policy are retained. The numerical
failure from the optional GDN comparison remains in the raw receipts.

Targeted mmap readahead defaults to a 2048-range limit on both platforms.
This is a new launcher/build default, not a change to historical RTX
measurements or to the environment baked into the old v0.2.0 image.
`benchmarks/spark-review/TUNING.md` links every completed C1 tuning run.

Full qualification is distributed by independent suite across four Sparks.
Each measured request or concurrent batch uses one TP=1 GB10. The assembly
script requires identical immutable image IDs, serving arguments and selected
environment settings across hosts, and records each result's originating host
and SHA-256. The completed qualification is in `benchmarks/spark-final`, including that
manifest, all four runtime captures and post-qualification memory snapshots.

## Structured-output corrections in v0.3.0

Both native images include the reasoning-end guard from vLLM commit
[c6e19b3be243](https://github.com/vllm-project/vllm/commit/c6e19b3be243)
and termination correction from [PR 52805](https://github.com/vllm-project/vllm/pull/52805).
They were reviewed against upstream and the adjacent GLM recipe at commit
`9c35641652670bd216a4ad29495c3edd41f0828c`, with strict Qwen source hashes.
[Review and negative controls](benchmarks/spark-structured-review/README.md)
record the port and regressions. Both builds run all fourteen regression tests.

Spark preserves every original numerical image layer. The RTX comparison hashes
all 5738 installed vLLM/B12x files: only the two structured-output Python files
differ from v0.2.0. Image defaults additionally enable readahead2048 and native
architecture settings. Existing performance receipts retain their original
image IDs and environments; these are not new RTX performance measurements.
