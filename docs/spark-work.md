# Spark branch qualification work

This branch extends the recipe to RTX SM120 and DGX Spark SM121. Main remains
unchanged until the user tries the completed Spark release.

The Spark target is the pinned EXL3 K4.25 model with original BF16 PLE, mmap,
FP8 KV and a GPU memory utilization cap of 0.7. Native arm64 build/run detection
selects Spark settings automatically. The output image will be
`ghcr.io/tpurtell/spark-exl3-qwen3.8-flash-next`.

All four hosts (ostrich, dodo, emu, kiwi) are available for concurrent work.
Initial builds use the existing pinned multiarch vLLM base and B12x commit;
the EXL3 source stage copies Python from its pinned amd64 image only.

Qualification checklist:

- [x] Native arm64 build and strict mmap patch/base checks.
- [x] Mixed-projection loading, BF16 checkpoint gathers and mutable CUDA graphs.
- [x] Component numerical checks and kernel comparisons on Spark.
- [ ] End-to-end C1 MTP and mmap tuning, plus C16 tradeoffs.
- [ ] Full final default-profile performance, API, vision, retrieval and C8 tool
  qualification using the existing contracts and complete raw receipts.
- [ ] Fourth table entry: EXL3 mmap Spark (BF16 PLE), compact README tables and
  platform defaults comparison. Historical RTX evidence remains unchanged.
- [ ] Published arm64 image, source branch and verifiable release evidence.

The 0.7 utilization cap is enforced for Spark configuration; no qualification
result is claimed until the actual run has completed.

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
