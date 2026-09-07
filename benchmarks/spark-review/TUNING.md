# Spark C1 tuning comparisons

Each run uses one GB10, BF16 PLE mmap, a 0.7 GPU memory fraction, and the same seven-workload protocol (one warmup and three measured responses). The blend divides total measured decode tokens by total decode time. These are tuning comparisons; the combined release configuration still requires full qualification.

| Configuration | Host | C1 weighted blend (tokens/s) | Raw |
|---|---|---:|---|
| mtp0-readahead2048 | dodo | 16.75 | [receipts](../spark-mtp0-readahead2048/) |
| mtp1-dev1 | kiwi | 26.29 | [receipts](../spark-mtp1-dev1/) |
| mtp2-dev1 | ostrich | 27.32 | [receipts](../spark-mtp2-dev1/) |
| mtp2-readahead128 | kiwi | 29.21 | [receipts](../spark-mtp2-readahead128/) |
| mtp2-readahead128-vocab | kiwi | 30.75 | [receipts](../spark-mtp2-readahead128-vocab/) |
| mtp2-readahead2048 | ostrich | 29.04 | [receipts](../spark-mtp2-readahead2048/) |
| mtp2-serial0 | ostrich | 27.53 | [receipts](../spark-mtp2-serial0/) |
| mtp3-dev1 | dodo | 25.72 | [receipts](../spark-mtp3-dev1/) |
| mtp3-readahead128 | emu | 27.74 | [receipts](../spark-mtp3-readahead128/) |
| mtp3-readahead128-tile128 | emu | 27.93 | [receipts](../spark-mtp3-readahead128-tile128/) |
| mtp3-serial0 | dodo | 27.58 | [receipts](../spark-mtp3-serial0/) |
| mtp4-dev1 | emu | 24.14 | [receipts](../spark-mtp4-dev1/) |

Initial `dev1` runs use serial threshold128, readahead0, native vocabulary and the existing K64 small-batch expert tile policy. Named variants change the indicated setting. The vocabulary and tile candidates retain same-host baselines. Different hosts, page-cache histories and generated responses limit interpretation of small changes. The short concurrency probes use one measured run and are not substitutes for the full C16 qualification.

The selected combined candidate uses MTP2, serial128, readahead2048 and B12x vocabulary, retaining the existing expert tile policy. Readahead2048 also becomes the RTX recipe default without new RTX measurements.
