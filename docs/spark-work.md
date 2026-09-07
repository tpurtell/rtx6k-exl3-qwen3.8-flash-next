# Spark qualification and tuning record

This branch extends the recipe to RTX SM120 and DGX Spark SM121. Main remains
unchanged until the user tries the completed Spark release.

The Spark target is the pinned EXL3 K4.25 model with original BF16 PLE, mmap,
FP8 KV and a GPU memory utilization cap of 0.7. Native arm64 build/run detection
selects Spark settings automatically. The published image is
`ghcr.io/tpurtell/spark-exl3-qwen3.8-flash-next`.

All four hosts (ostrich, dodo, emu, kiwi) are available for concurrent work.
Initial builds use the existing pinned multiarch vLLM base and B12x commit;
the EXL3 source stage copies Python from its pinned amd64 image only.

Qualification checklist:

- [x] Native arm64 build and strict mmap patch/base checks.
- [x] Mixed-projection loading, BF16 checkpoint gathers and mutable CUDA graphs.
- [x] Component numerical checks and kernel comparisons on Spark.
- [x] End-to-end C1 MTP and mmap tuning, plus C16 tradeoffs.
- [x] Full final default-profile performance, API, vision, retrieval and C8 tool
  qualification using the existing contracts and complete raw receipts.
- [x] Fourth table entry: EXL3 mmap Spark (BF16 PLE), compact README tables and
  platform defaults comparison. Historical RTX evidence remains unchanged.
- [x] Published arm64 image, source branch and verifiable release evidence.

The 0.7 utilization cap is enforced for Spark configuration; no qualification
result is claimed until the actual run has completed.

## Final result

The full original-EXL3 BF16-PLE mmap qualification is complete. The recipe
selects native arm64 build, pull, download and run defaults automatically:
MTP2, B12x vocabulary, GPU memory utilization capped at 0.7, and targeted
readahead2048. RTX retains MTP3/native vocabulary; readahead2048 is global.
All 5951 unequal per-projection expert allocations remain preserved.

- C1 seven-workload blend: **31.11 tokens/s**, with 19/21 content contracts.
- Greedy merge-intervals median: **38.12 tokens/s**; sampled async coding:
  **36.21 tokens/s** at task-only depth.
- C8 / C16 aggregate medians: **97.46 / 101.00 tokens/s**. C16 reaches twelve
  overlapping streams in each measurement; the remaining requests queue.
- API constraints **16/16**; vision **1/4/16 images**; retrieval **6/6**.
- Exact context boundary: **261888 input + 256 output = 262144 tokens**.
- C8 tool evaluation: **154/176 points**, Hard Mode **29/38**, no backend errors.
  TC-42 adds extra parameters despite `additionalProperties: false`; the
  warning and full failed trace remain visible. Orchid repetition passes 3/5.
- All 218 mmap tests pass in the final image with NVIDIA device access.
  All four post-qualification PLE snapshots contain 128 clean mappings and
  no anonymous or dirty PLE pages. Their RSS is a workload-dependent snapshot.

[Complete results](../benchmarks/RESULTS.md),
[raw qualification and host manifest](../benchmarks/spark-final/qualification-manifest.json),
and [tuning comparisons](../benchmarks/spark-review/TUNING.md) retain the evidence.
Independent suites ran on ostrich (core/coding), dodo (prefill/retrieval),
emu (context/boundary) and kiwi (tools). Each measurement uses one TP=1 Spark;
image IDs, serving arguments and selected environment settings match across
all four hosts. Dynamically profiled KV pools differ, as recorded below.

The tested linux/arm64 image is published as `v0.3.0-spark.1` and `latest` in
`ghcr.io/tpurtell/spark-exl3-qwen3.8-flash-next`, both at
`sha256:0e17cebbff2a95de615f4c1f68ba4e16ad07710164e82c0bf90f044216e8cbd3`.
The package is currently private; visibility remains the owner's manual
post-publication step. Main and all historical RTX raw measurements are unchanged.

## Development record

The following entries preserve the tuning sequence and intermediate statuses;
the completed result above supersedes their pending-work notes.

## First native build and component results

All four native arm64 builds pass the strict mmap base-file hashes and patch
application. Emu verifies byte-exact gathers at both row edges of all 128 BF16
PLE shards plus random rows (512 total), followed by eight changed-row CUDA
graph replays. The mapped table is 95.37 GiB. The QSA FP8/BF16 bridge, host
embedding and optional vocabulary bridge checks pass.

The first unit run passed 206 tests and failed 12 because its default-off
fixture cleared mmap variables while retaining the image's resident-offload
flag. The fixture now also clears that flag; all 218 tests pass on arm64.
Both receipts are retained, and no runtime behavior or numerical tolerance
was changed for this test isolation fix.

Component comparisons on emu: vocabulary projection median is 7310 us native
and 5172 us B12x. HC is faster native at decode sizes and essentially tied at
2048 rows, including the B12x injection-pack cost. GDN fails its numerical
check, so it cannot become the serving default. These component findings do
not establish end-to-end gains; vocabulary still needs a serving comparison.

Four concurrent initial serving candidates use MTP1 (kiwi), MTP2 (ostrich),
MTP3 (dodo), and MTP4 (emu), with identical BF16 PLE/mmap and 0.7 memory cap.

## Initial serving and mmap tuning

Completed initial three-run C1 blends: MTP1 26.29, MTP2 27.32 and MTP3 25.72
tokens/s. Corresponding short C16 probes are 100.52, 94.53 and 82.94 aggregate
tokens/s. These are preliminary serial-gather runs, not final qualification.

Live logs show BF16 PLE gathers paying substantial page-fault time. An
interleaved component comparison on kiwi retains the idle loaded model's GPU
allocation and uses fresh uniform random rows with the existing page cache.
For 80 rows, medians are 17.50 ms serial/no-readahead, 4.84 ms threaded with 32
workers, and 1.88 ms serial plus a 128-run targeted readahead limit. The test
does not drop caches or claim cold-disk/serving throughput. Full samples are
in `benchmarks/spark-review/mmap-gather-kiwi.txt`; the reproducer is
`scripts/benchmark-mmap-gather.py`. Threaded and targeted-readahead candidates
now receive end-to-end comparisons before selection.

The RTX mmap PLE8 qualification used readahead off on a host with 183 GiB
system RAM plus separate GPU memory. Its approximately 48 GiB PLE table could
fit in the OS cache, although complete cache residency was not established.
Spark shares approximately 121 GiB between CPU and GPU and uses a 95 GiB BF16
PLE table, so the whole table cannot remain cached alongside the loaded model.
This is why the RTX serial-gather choice is being re-evaluated with targeted
readahead on Spark. It is not evidence that readahead cannot help an RTX host
with less RAM or the larger BF16 table.

The complete initial MTP4 run records 24.14 tokens/s C1 blend and 58.93 C16
probe throughput, with 19/21 content contracts. MTP2 leads the initial mixed
C1 blend, but MTP selection will be checked again with improved gather settings.

The selected Spark readahead value will become the global recipe/image default
for both architectures, as requested. It remains configurable. Existing RTX
measurements retain their original readahead-off configuration and will be
labeled historical; this defaults change does not trigger RTX remeasurement.
The value is pending the serving comparisons, rather than selected solely
from the random-row component test.

Threaded gathering measures 27.53 tokens/s at MTP2 and 27.58 at MTP3; the
MTP2 targeted-readahead-128 run measures 29.21 tokens/s. These completed C1
results support testing targeted readahead in the final configuration.

A larger-gather comparison on idle-loaded ostrich measures 1280 random rows
at 52.66 ms without readahead, 52.72 ms with a 128-range limit (skipped), and
14.20 ms with a 2048-range limit. A serving comparison of the higher limit
is pending. The same existing-cache/interleaved method is used.

The expert-tile numerical probe could not allocate its separate CUDA process
while the full model remained loaded. Its receipt is retained as a test setup
resource failure; the serving run completed normally. The numerical probe is
being rerun alone after stopping that completed benchmark's server.

The standalone tile check passes all twelve H2560/I640 K4/K5 combinations
(M=1,2,3,4,5,8; K tile 64 and 128), including changed-input graph replay against
the serial-tier reference. The reproducer is `scripts/test-spark-trellis-tiles.py`;
it requires an otherwise free GPU. The experimental serving patch retains
N=128, applies only to small Qwen batches, and leaves checkpoint packing and
projection-tier descriptors unchanged. It remains an experiment pending
end-to-end results.

The MTP3 readahead-128 blend is 27.74 tokens/s, below the MTP2 result of 29.21.
The next round evaluates MTP2/readahead2048 on ostrich, MTP0/readahead2048 on
dodo, MTP2/readahead128/B12x vocabulary on kiwi, and MTP3/readahead128/K128
tiles on emu. Vocabulary and tile comparisons retain their same-host baselines.

The completed readahead-2048 run measures a 29.04 tokens/s C1 blend and
98.67 / 97.14 tokens/s in the short C8 / C16 probes. Readahead128 measured
29.21 and 94.53 / 89.09 respectively. These concurrency probes are single
measurements, not the final qualification medians. The recipe now defaults
to 2048 ranges globally, including newly built images; RTX is not remeasured.

The same-host vocabulary comparison improves the C1 blend from 29.21 to
30.75 tokens/s. MTP0 is 16.75 tokens/s, and the MTP3 K128 experiment
shows little overall improvement over K64. The combined qualification
candidate therefore uses MTP2, readahead2048, B12x vocabulary, and the
existing expert tile policy. RTX retains MTP3 and native vocabulary defaults.
Full qualification of that combined profile remains pending.

## Combined qualification image

The native arm64 qualification image is published under `qual-e3ae4a7` with
manifest digest `sha256:0e17cebbff2a95de615f4c1f68ba4e16ad07710164e82c0bf90f044216e8cbd3`
and image ID `sha256:8faa93589f6156c24d328dfcbf80f4e0a29ee0fcec07c74b39738687c0feebf9`.
All four running qualification containers have that same image ID. This is
a qualification tag; release promotion awaits the complete results. Anonymous
registry access currently returns 401, so package visibility is still private.

The final image passes all 218 mmap tests with NVIDIA device access. An initial
CPU-only container invocation failed vLLM device inference (203 passed, eight
failed, seven skipped); both receipts are retained. No implementation or test
changes were needed for the passing run. The CPU-only invocation was a setup
error for this GPU serving image.

Suites are assigned to ostrich (core and coding), dodo (prefill and retrieval),
emu (context and exact boundary), and kiwi (C8 tool evaluation). Each host
starts the same default configuration; no measurement combines GPU capacity
across hosts. Startup and all suites are still in progress.

The registry manifest confirms `linux/arm64`. Dodo has begun prefill, ostrich
has begun API constraints, and kiwi has begun the full 88-case C8 tool suite.
Captured startup receipts include B12x vocabulary preparation. Final results
are not yet complete.

All four startup captures contain 49 mixed-projection expert entries (target
and draft), and each reports 71.99 GiB for model loading. Identical launcher
settings do not force identical dynamically profiled KV pool sizes: ostrich
reports 456130 tokens, dodo 440401, emu 393216 and kiwi 450887. All exceed the
configured 262144-token context. These are separate host observations, and
the runtime receipts retain them; the qualification does not claim identical
page-cache histories or a fixed KV allocation across hosts.

The completed final seven-workload C1 run measures 31.11 tokens/s weighted
decode with 19/21 content contracts passing. API tool constraints pass 16/16
and vision passes at 1, 4 and 16 images. Remaining suites are still running.

The readahead2048 tuning probe's C16 batch reached 12 overlapping client
stream intervals, compared with eight at C8. Queuing is part of the observed
C16 throughput under the 0.7 cap. Final tables retain overlap counts rather
than treating 16 submitted clients as proof of 16 simultaneous decoders.
The compact README uses minimum observed overlap across the three final
measurements; the detailed report retains its range.
