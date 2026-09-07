#!/usr/bin/env python3
"""Compare native and B12x fused HC combine+norm at real Qwen geometry."""
import json
import statistics

import torch
from b12x.norm import hyperconnection as hc
from vllm.models.qwen3_8_flash_next.nvidia.ops.hc import hc_combine_norm

torch.manual_seed(787)
device = torch.device("cuda", 0)
planned = hc.plan(hc.Caps(device=device, max_tokens=2048, hidden_size=2560, streams=4, lowrank=320))
records = []
stream = torch.cuda.Stream()
with torch.cuda.stream(stream):
    for rows in (1, 4, 16, 64, 2048):
        state = torch.randn((rows, 10240), dtype=torch.bfloat16, device=device)
        block = torch.randn((rows, 2560), dtype=torch.bfloat16, device=device)
        packed = torch.randn((rows, 336), dtype=torch.bfloat16, device=device)
        injection = packed[:, 320:324]
        weight = torch.randn((10240,), dtype=torch.bfloat16, device=device) * 0.02
        functions = {"native": lambda: hc_combine_norm(state, block, injection, weight, 1e-6, 4),
                     "b12x": lambda: hc.run_combine_norm(state, block, injection.contiguous(), weight, eps=1e-6, plan=planned)}
        graphs, outputs = {}, {}
        for name, fn in functions.items():
            fn()
            graph = torch.cuda.CUDAGraph()
            with torch.cuda.graph(graph, stream=stream):
                for _ in range(10):
                    output = fn()
            graphs[name], outputs[name] = graph, output
        state.mul_(-1)
        for graph in graphs.values():
            graph.replay()
        errors = []
        for reference, actual in zip(outputs["native"], outputs["b12x"]):
            torch.testing.assert_close(actual, reference, rtol=0.015, atol=0.04)
            errors.append(((actual.float() - reference.float()).norm() / reference.float().norm()).item())
        measurements = {name: [] for name in graphs}
        for run in range(7):
            for name in (list(graphs) if run % 2 == 0 else list(reversed(graphs))):
                begin, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
                begin.record()
                graphs[name].replay()
                end.record()
                end.synchronize()
                measurements[name].append(begin.elapsed_time(end) * 1000 / 10)
        record = {"tokens": rows, "b12x_includes_injection_pack": True, "relative_l2": errors, "microseconds": measurements,
                  "median_microseconds": {k: statistics.median(v) for k, v in measurements.items()}}
        records.append(record)
        print(json.dumps(record), flush=True)
torch.cuda.synchronize()
