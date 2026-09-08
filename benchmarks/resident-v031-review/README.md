# v0.3.1 resident PLE loading repair

The released v0.3.0 RTX image fails with the original EXL3 K4.25 BF16 PLE
checkpoint, `PLE_MMAP=0`, GPU1 and the normal MTP3 settings. The GPU worker
raises `AttributeError` at `ple_layer.py:691` before completing model loading.
[Original startup log](v030-resident-startup.txt) records the reproduction.

The mmap backport moved `self.ngram_embedding` access before the existing
CPU-offload worker branch. A resident-mode GPU worker intentionally has no
embedding table: its CPU subprocess owns that table, while the GPU worker
retains only optional FP8 scale metadata. The fix handles that worker before
accessing the embedding. The mmap reload guard still runs before consuming
weights for an mmap module, retaining its rejection of repeat attachment.

The strict-hash patch changes only that ordering in `ple_layer.py`. The new
regressions cover BF16 and FP8 metadata loading without a local table. Both
fail on v0.3.0 and pass after the fix. All 220 tests pass on RTX. The two new
regressions and the existing fourteen structured-output build regressions also
pass in the native Spark image; no running Spark service was stopped.

Full-model verification uses the locally available original BF16 PLE model.
No PLE8/NVFP4 checkpoint was downloaded. Those formats' metadata handling is
covered by the focused regression; their full-model runs are not repeated.
Historical performance and quality measurements retain their original images.
