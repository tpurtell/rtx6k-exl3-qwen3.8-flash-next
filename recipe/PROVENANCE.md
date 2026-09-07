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

Kernel/bridge test receipts are not full-model benchmark results. Model loading
memory figures in the qualification ledger are startup observations, not
steady-state capacity guarantees. Recipe and borrowed vLLM/B12x code are
covered by their applicable source licenses; checkpoint weights retain their
own licenses and are downloaded separately.
