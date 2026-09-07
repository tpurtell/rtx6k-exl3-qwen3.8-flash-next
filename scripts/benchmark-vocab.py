#!/usr/bin/env python3
"""Compare native and B12x BF16 vocabulary projection at Qwen's real geometry."""
import json
import statistics

import torch
from b12x.gemm import bf16_vocab_projection as vocab

torch.manual_seed(787)
device = torch.device("cuda", 0)
weight = torch.randn((248320, 2560), dtype=torch.bfloat16, device=device)
x = torch.randn((1, 2560), dtype=torch.bfloat16, device=device) / 2560**0.5
planned = vocab.plan(vocab.Caps(device=device, max_tokens=1, in_features=2560, out_features=248320))
binding = vocab.bind(planned, source=x, weight=weight)
functions = {"torch": lambda: torch.nn.functional.linear(x, weight),
             "b12x": lambda: vocab.run(binding)}
graphs, outputs = {}, {}
stream = torch.cuda.Stream()
stream.wait_stream(torch.cuda.current_stream())
with torch.cuda.stream(stream):
    for name, fn in functions.items():
        fn()
        graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph, stream=stream):
            for _ in range(20):
                output = fn()
        graphs[name], outputs[name] = graph, output
    errors = []
    for _ in range(3):
        x.normal_().div_(2560**0.5)
        for graph in graphs.values():
            graph.replay()
        reference, actual = outputs["torch"].float(), outputs["b12x"].float()
        relative = ((reference - actual).norm() / reference.norm()).item()
        max_error = (reference - actual).abs().max().item()
        assert relative < 0.004 and max_error < 0.05
        errors.append({"relative_l2": relative, "max_absolute": max_error,
                       "top1_equal": reference.argmax().item() == actual.argmax().item()})
    measurements = {name: [] for name in graphs}
    for run in range(7):
        for name in (list(graphs) if run % 2 == 0 else list(reversed(graphs))):
            graph = graphs[name]
            begin, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
            begin.record()
            graph.replay()
            end.record()
            end.synchronize()
            measurements[name].append(begin.elapsed_time(end) * 1000 / 20)
torch.cuda.synchronize()
print(json.dumps({"geometry": {"m": 1, "n": 248320, "k": 2560},
                  "dtype": "bfloat16", "b12x_config": planned.config.to_dict(),
                  "method": "20 projections per graph replay; 7 interleaved measurements; CUDA events; random weights exceed L2",
                  "numerical_checks": errors, "microseconds": measurements,
                  "median_microseconds": {k: statistics.median(v) for k, v in measurements.items()}}, indent=2))
