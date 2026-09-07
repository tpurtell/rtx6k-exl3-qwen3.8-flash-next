# Final server diagnostics

All four servers remained running after their suites completed. The logs
contain Transformers messages about undocumented `min_frames` / `max_frames`
processor kwargs. The 1/4/16-image checks still pass.

Kiwi also logs two XGrammar FSM rejection messages for token 271. No
`Unexpected: grammar`, request-termination message, assertion traceback, CUDA
error or out-of-memory exception accompanies them. The evaluator reports zero
request errors and retains all 88 scenario results.

The pinned vLLM source calls `grammar.accept_tokens` during speculative
bitmask preparation and during actual scheduler advancement. The former
explicitly tolerates rejection of draft tokens immediately after reasoning
ends; the latter logs an additional termination error if rejected. The observed
logs are consistent with the tolerated draft path, but no call-stack tracing
was added to this qualification. These diagnostics are not evidence that the
TC-42 extra-parameter failure was caused by that path.

[Unfiltered matching diagnostic lines](server-diagnostics.json) are retained.
The TC-42 quality failure remains in the main tables and full tool traces.

These are the original qualification image's diagnostics. The reviewed
[structured-output backports](../spark-structured-review/README.md) address
the speculative reasoning and termination paths; the release uses corrected
images while preserving these original receipts.
