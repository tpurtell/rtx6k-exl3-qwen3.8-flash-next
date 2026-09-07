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
