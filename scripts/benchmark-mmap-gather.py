#!/usr/bin/env python3
"""Compare PLE gather knobs with fresh random rows under an idle loaded server.

Uses existing file cache, without eviction or memory-pressure changes. This is
an I/O component comparison, not serving throughput or a cold-cache guarantee.
"""
import argparse
import json
from pathlib import Path
import statistics
import time
import numpy as np
from vllm.models.qwen3_8_flash_next.nvidia import ple_mmap

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('model', type=Path)
p.add_argument('--runs', type=int, default=24)
p.add_argument('--rows', type=int, nargs='+', default=[32, 64, 80])
p.add_argument('--variants', nargs='+', default=['128:0:32','0:0:32','128:128:32','0:128:32','0:0:8','0:0:16'],
               help='serial:readahead:workers triples')
a = p.parse_args()
shards = ple_mmap.discover_shards(str(a.model))[1]
rows = sum(v[2] for v in shards.shards.values())
variants = [tuple(map(int, item.split(':'))) for item in a.variants]
if (len(set(variants)) != len(variants) or any(len(v) != 3 for v in variants)
        or any(s < 0 or r < 0 or w < 1 for s,r,w in variants)):
    p.error('variants must be distinct serial:readahead:workers triples with nonnegative limits and positive workers')
tables = {}
for serial, readahead, workers in variants:
    import os
    os.environ.update(VLLM_PLE_MMAP_SERIAL=str(serial),
                      VLLM_PLE_MMAP_READAHEAD=str(readahead),
                      VLLM_PLE_MMAP_WORKERS=str(workers))
    embedding = ple_mmap.MmapNgramEmbedding(rows, shards.cols)
    ple_mmap._attach_table(embedding, shards, len(shards.shards), 1, str(a.model))
    tables[(serial,readahead,workers)] = embedding.table
rng = np.random.default_rng(787)
try:
    for count in a.rows:
        timings = {v: [] for v in variants}
        for iteration in range(a.runs):
            for index in rng.permutation(len(variants)):
                v = variants[int(index)]
                ids = rng.integers(0,rows,count,dtype=np.int64)
                start = time.perf_counter()
                result = tables[v].gather(ids)
                elapsed = (time.perf_counter()-start)*1000
                assert result.shape[0] == count
                timings[v].append(elapsed)
        for (serial,readahead,workers), samples in timings.items():
            print(json.dumps({'rows':count,'runs':a.runs,'serial':serial,
                'readahead':readahead,'workers':workers,'median_ms':statistics.median(samples),
                'p90_ms':float(np.percentile(samples,90)),'samples_ms':samples,
                'method':'fresh uniform random rows; interleaved variants; existing file cache; idle loaded server retains GPU allocation'}),flush=True)
finally:
    for table in tables.values():
        table.close()
