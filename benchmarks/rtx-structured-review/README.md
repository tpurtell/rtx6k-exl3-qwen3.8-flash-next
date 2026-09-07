# RTX v0.3.0 structured-output update

The native linux/amd64 image uses the same reviewed patches and fourteen
build-time regressions as [Spark](../spark-structured-review/README.md).
The build and all 218 mmap tests pass on RTX with NVIDIA device access.

[Installed file comparison](runtime-file-comparison.json) hashes all 5738
vLLM/B12x files against the v0.2.0 RTX image. Only the structured-output manager
and xgrammar backend differ. Model code, mixed expert handling and numerical
kernels are identical. Image metadata additionally selects native sm_120a,
native vocabulary projection, readahead2048, and the renamed source repository.

Live qualification uses the shipping original EXL3 BF16 PLE mmap profile,
MTP3, native vocabulary and readahead2048. Existing RTX performance and quality
columns retain their original profile, image, and readahead settings; this new
structured-output check does not replace those historical measurements.

[Completed qualification](../rtx-structured-final/qualification.json): API16/16,
JSON/reasoning/EOS29/29 with speculation active, and all 88 C8 tool scenarios
completed with **148/176 points**, including **29/38 Hard Mode points**.
The evaluator reports zero request errors. No FSM rejection, grammar-triggered
termination, traceback, CUDA error or OOM appears in the corrected server logs.
Full failed/partial traces and all matching diagnostic lines are retained.
