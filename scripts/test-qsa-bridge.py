#!/usr/bin/env python3
"""Check the serving bridge's scales, decode/prefill boundary, and graph replay."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import torch

source = Path(__file__).resolve().parents[1] / "patches/b12x_qsa_attention.py"
spec = importlib.util.spec_from_file_location("bridge", source)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
torch.manual_seed(787)
device = "cuda"
stream = torch.cuda.Stream()
with torch.cuda.stream(stream):
    for dtype in (torch.bfloat16, torch.float8_e4m3fn):
        # vLLM logical [page, head, token, 2*dim], physical NHD layout.
        storage = torch.randn((3, 16, 2, 512), device=device, dtype=torch.bfloat16).to(dtype)
        logical_cache = storage.transpose(1, 2)
        keys, values = logical_cache.transpose(1, 2).split(256, dim=-1)
        table = torch.tensor([[2, 0]], device=device, dtype=torch.int32)
        layer = SimpleNamespace(
            _k_scale=torch.tensor(0.25 if dtype == torch.float8_e4m3fn else 1., device=device),
            _v_scale=torch.tensor(0.5 if dtype == torch.float8_e4m3fn else 1., device=device),
            scaling=1 / 16,
        )
        k = keys[2, :8].float().repeat_interleave(12, dim=1) * layer._k_scale
        v = values[2, :8].float().repeat_interleave(12, dim=1) * layer._v_scale
        for rows in (1, 64, 65, 2048):
            q = torch.randn((rows, 24, 256), device=device, dtype=torch.bfloat16)
            indices = torch.full((rows, 2051), -1, device=device, dtype=torch.int32)
            indices[:, :8] = torch.arange(8, device=device)
            positions = torch.full((rows,), 7, device=device, dtype=torch.int64)
            requests = torch.zeros(rows, device=device, dtype=torch.int32)
            output = torch.empty_like(q)

            def launch():
                return bridge.run(layer, q, keys, values, indices, table,
                                  requests, positions, output)

            def reference():
                scores = torch.einsum("rhd,thd->rht", q.float(), k) * layer.scaling
                return torch.einsum("rht,thd->rhd", scores.softmax(-1), v).to(q.dtype)

            launch()
            torch.testing.assert_close(output, reference(), atol=0.015, rtol=0.015)
            graph = torch.cuda.CUDAGraph()
            capture_stream = torch.cuda.Stream()
            capture_stream.wait_stream(stream)
            # Match vLLM: kernels warmed above, but scratch has never been
            # allocated on this separate graph-capture stream.
            with torch.cuda.graph(graph, stream=capture_stream):
                launch()
            stream.wait_stream(capture_stream)
            q.mul_(-1)
            graph.replay()
            torch.testing.assert_close(output, reference(), atol=0.015, rtol=0.015)
            assert torch.isfinite(output).all() and output.abs().sum() > 0
            print(f"PASS dtype={dtype} rows={rows} oracle and mutated graph replay", flush=True)
torch.cuda.synchronize()
