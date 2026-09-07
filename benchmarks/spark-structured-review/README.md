# Structured-output backport review

Source: `../brandon-glm-5.3-flash/recipe` commit
`9c35641652670bd216a4ad29495c3edd41f0828c`.

The reasoning-end guard matches upstream vLLM commit
[c6e19b3be243](https://github.com/vllm-project/vllm/commit/c6e19b3be243).
The installed Qwen manager has exactly the expected source SHA-256
`355f6f1193c15d5d6901a0f567e2e16005e3681f04f70079c6ba11e020b4d33a`.
It validates unconstrained post-reasoning draft tokens before attempting to
advance the grammar, while preserving real errors on already constrained tokens.

The adjacent termination correction matches merged upstream
[PR 52805](https://github.com/vllm-project/vllm/pull/52805), commit
`12f64b39d29282437e35be9aa5db432fb2a1a6e6`. Qwen has the same four pre-fix
method bodies, but a different complete backend file. The port uses Qwen's
verified source SHA-256
`cdaebca794c8aa919097ee250f1bc0fa87f8fe52a026eee4877605e18134752e`.
Acceptance stops at termination, validation rolls back only accepted tokens,
and reset clears the cached termination state. Invalid active-grammar tokens
continue to fail.

Negative controls against the installed qualification image fail two reasoning
regressions and three termination regressions. Both native image builds pass all
fourteen CPU regressions against the actual installed method bodies. The corrected
Spark image also passes all 218 mmap tests, API16/16 and 29 complete live
JSON/reasoning/EOS canaries with speculation active. Its full C8 tool run earns
154/176 points and 34/38 Hard Mode points, with zero evaluator request errors.
TC-42 still adds prohibited extra arguments; its warning and trace are retained.
No FSM rejection, request termination, traceback, CUDA error or OOM appears in
the corrected server logs. [Completed qualification](../spark-structured-final/qualification.json).

Only the structured-output manager/backend are changed. Completed performance,
vision, retrieval and boundary measurements remain immutable; the corrected
image preserves every original numerical layer and reruns the affected API and
C8 tool checks plus the focused JSON/reasoning/EOS canary. The previous diagnostic
receipts and tool results remain available.

Release instruction: after the corrected image is qualified and uploaded,
merge `spark` into `main` and publish stable `v0.3.0`. This supersedes the
earlier plan to leave main unchanged for a prerelease trial.
