#!/usr/bin/env python3
"""Real checkpoint: shard-edge byte equality and mutated CUDA graph replay."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import re
import numpy as np
from safetensors import safe_open
import torch
from vllm.models.qwen3_8_flash_next.nvidia import ple_mmap

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('model',type=Path)
a=p.parse_args()
index=json.loads((a.model/'model.safetensors.index.json').read_text())['weight_map']
shards=ple_mmap.discover_shards(str(a.model))[1]
rows=sum(v[2] for v in shards.shards.values())
parts=len(shards.shards); size=(rows+parts-1)//parts
embedding=ple_mmap.MmapNgramEmbedding(rows,shards.cols)
ple_mmap._attach_table(embedding,shards,parts,1,str(a.model))
rng=np.random.default_rng(787)
ids=np.array([v for i,(_f,_off,n) in sorted(shards.shards.items()) for v in (i*size,i*size+n-1)]+rng.integers(0,rows,256).tolist(),dtype=np.int64)
lookup={int(re.search(r'shard_(\d+)',name)[1]):(name,file) for name,file in index.items() if '.layers.1.ple.ple_embedding.ngram_embedding.shard_' in name}
with ExitStack() as stack:
    opened={f:stack.enter_context(safe_open(str(a.model/f),framework='pt',device='cpu')) for f in set(f for _,f in lookup.values())}
    reference=[]
    for i in ids:
        name,file=lookup[int(i)//size];r=int(i)%size
        reference.append(opened[file].get_slice(name)[r:r+1].view(torch.uint8).numpy())
    expected=np.concatenate(reference)
    got=embedding.table.gather(ids)
    np.testing.assert_array_equal(got,expected)
    print(f'PASS: {len(ids)} real checkpoint rows, both boundaries of all {parts} shards, byte-exact against safetensors slices',flush=True)
    device=torch.device('cuda')
    staging=torch.empty((64,shards.cols),dtype=embedding.table.torch_dtype,device=device)
    scale=embedding.weight_scale.to(device).float()
    stream=torch.cuda.Stream()
    graph=torch.cuda.CUDAGraph()
    with torch.cuda.stream(stream):
        staging.zero_()
        with torch.cuda.graph(graph,stream=stream):
            output=(staging.float()*scale).to(torch.bfloat16)
        for run in range(8):
            selected=np.arange(run*64,(run+1)*64)%len(ids)
            device_ids=torch.tensor(ids[selected],device=device)
            embedding.gather_into(device_ids,staging)
            graph.replay()
            stream.synchronize()
            ref=torch.from_numpy(expected[selected].copy()).view(embedding.table.torch_dtype).float()*float(embedding.weight_scale.item())
            torch.testing.assert_close(output.cpu(),ref.to(torch.bfloat16),rtol=0,atol=0)
    print('PASS: 8 CUDA graph replays with changed real rows, exact scaled BF16 output',flush=True)
embedding.table.close()
