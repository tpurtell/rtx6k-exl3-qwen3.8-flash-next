# mmap PLE review and backport

This follow-on release ports [vLLM PR #54129](https://github.com/vllm-project/vllm/pull/54129)
at `50a061f792f36364f5f95a93eee21f1e9d77f65e`. The PR is open at the time of
review. Its description is not treated as qualification evidence for this
recipe; the tests and live model run below exercise our actual port.

The original release's resident PLE worker stays the default. `PLE_MMAP=1`
works with every profile and takes precedence over the resident-worker flag,
including when the image is started directly with `VLLM_PLE_MMAP=1`. mmap
requires Model Runner V2 and keeps PP=1. The input-preparation path hashes
actual request rows, gathers bytes from read-only mappings, and fills stable
GPU staging buffers before graph execution. Padding and dummy batches zero
those buffers rather than reusing stale data. The existing MTP context and
rollback logic remain in the model state.

## Changes found during review

The upstream scale comparison used `allclose(atol=1e-6)`. Our independent
regressions demonstrate that it accepted both a 100% relative mismatch for
small scales and a repeated, nonscalar streamed scale through broadcasting.
The direct scale reader also accepted positive/negative infinity and NaN.
All five regressions fail before the fix. The port now requires finite scales
and exact equality between flattened streamed and disk values, which also
rejects differing element counts. Matching scalar shapes `[]` and `[1]` remain
compatible; negative finite values are not arbitrarily prohibited.

- [Original failures](../benchmarks/mmap-review/scale-validation-before.txt)
- [Passing component and hook tests](../benchmarks/mmap-review/component-tests.txt)
- [Independent regressions](../tests/test_ple_mmap_review.py)

The pinned base differs substantially from the PR's Qwen module layout. The
backport preserves its `PleOffloadLayer` API, existing hash computation, shard
copy semantics, model weight mappings and native kernels. It adds the PR's
mmap loader, staging, dummy-run dispatch and reload transaction guards. It
does not import unrelated PR-base changes such as HPC kernels or a different
resident PLE implementation. Base-file hashes are verified before the patch
is applied, and patch fuzz is disabled.

The 218 passing tests comprise 204 adapted upstream mmap cases, five new
review regressions, two runner dummy-input tests and seven PR weight-update
transaction tests. Compatibility shims change constructor/forward calling
conventions and test fixtures to match the pinned base; the mapped gather,
staging and scale algorithms themselves are not mocked out of the graph
replay tests. An independent real-checkpoint test checks both row boundaries
of all 128 shards plus sampled rows (512 total), followed by eight changed-row
CUDA graph replays with exact scaled BF16 comparisons against safetensors.

- [Real-checkpoint receipt](../benchmarks/mmap-review/real-checkpoint.txt)
- [All six launcher combinations](../benchmarks/mmap-review/launcher-profiles.jsonl)

## Memory and performance interpretation

The initial live process snapshot contains 128 checkpoint mappings spanning
47.68 GiB, with about 2.3 GiB of mapped pages resident after the initial C1
probe, all clean/file-backed and no anonymous PLE mapping pages. This is a
snapshot, not a maximum: Linux may cache more of the table and reclaim clean
pages under pressure. mmap avoids the complete anonymous resident table;
it does not promise a fixed tiny working set or disk-speed-independent
latency. Token embeddings still use host memory.

The checkpoint resides on an ext4 filesystem on a Samsung 9100 PRO 4TB NVMe.
No global cache drop or artificial memory-pressure operation is used. The
benchmark is performed with the existing OS file cache and explicit warmups,
not as a cold-disk or low-RAM capacity test. PREWARM, READAHEAD and PINNED are
off for initial qualification. A C1 comparison of the threaded gather and
SERIAL=128 setting precedes the final matrix.

[Process mapping snapshot](../benchmarks/mmap-review/memory-after-load.json)
records per-process anonymous/file/shared memory and checkpoint mapping
sizes, resident bytes and dirty bytes. The runtime receipt records all mmap
settings. The full matrix is limited to mmap-enabled `exl3-ple8`, as requested;
other model performance numbers remain the historical v0.1.0 measurements.

The three-run C1 comparison measured **138.30 tokens/s** with SERIAL=0 and
**147.94 tokens/s** with SERIAL=128. The recipe and published image therefore
default to SERIAL=128 when mmap is enabled; callers can override it. This
setting only bypasses the gather thread pool for at most 128 distinct rows.
Large prefills continue to use the worker pool. Both use MTP3 and the same
checkpoint, with PREWARM/READAHEAD/PINNED off. Full raw responses and metrics
are in `benchmarks/exl3-ple8-mmap-serial{0,128}-seven.jsonl`.
