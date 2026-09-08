# v0.3.1 resident PLE loading repair

The released v0.3.0 RTX image fails with the original EXL3 K4.25 BF16 PLE
checkpoint, `PLE_MMAP=0`, GPU1 and the normal MTP3 settings. The GPU worker
raises `AttributeError` at `ple_layer.py:691` before completing model loading.
[Original startup log](v030-resident-startup.txt) records the reproduction.

The v0.2.0 and v0.3.0 images have identical `ple_layer.py` hashes, so the
defect dates to the mmap backport in v0.2.0. The full-model reproduction here
uses v0.3.0.

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

The launcher checks in earlier releases covered mode arguments but did not
exercise resident model loading after the mmap backport. The new regressions
cover that missing worker state directly, and the full-model runs verify both
modes on one image. To reproduce the mode selection with the published recipe:

```bash
bash pull.sh
GPU=1 QUANT=exl3 PLE_MMAP=0 CONTAINER_NAME=qwen38-resident-check bash start.sh
# Stop that container before switching modes on the same GPU/port.
docker stop qwen38-resident-check
GPU=1 QUANT=exl3 PLE_MMAP=1 CONTAINER_NAME=qwen38-mmap-check bash start.sh
```

## Same-image full-model checks

| Check | Resident | mmap |
|---|---:|---:|
| API tool constraints | 16/16 | 16/16 |
| Concurrent JSON/reasoning/EOS canaries, MTP3 active | 29/29 | 29/29 |
| Retrieval, 8K/240K early/middle/late | 6/6 | 6/6 |
| Vision, numbered images per request | 1/4/16 pass | 1/4/16 pass |
| Content smoke contracts | 6/7 | 6/7 |

Both content runs miss only the fable length contract: 193 words against the
requested 140–170. Responses finish normally. The raw outputs retain this
failure; qualification PASS refers to the runtime/API/retrieval/vision checks,
not a claim that every content contract passes.

[Resident qualification](../resident-v031-resident/qualification.json) and
[mmap qualification](../resident-v031-mmap/qualification.json) record the same
immutable image ID, each mode's settings, full server logs and evidence hashes.
No AttributeError, traceback, FSM rejection, grammar-triggered termination,
CUDA error or OOM appears in either corrected run. These are functional mode
checks, not replacements for the historical performance measurements.
