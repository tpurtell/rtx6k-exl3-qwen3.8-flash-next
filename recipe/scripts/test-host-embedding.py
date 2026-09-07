#!/usr/bin/env python3
"""Verify physical host residency, exact GPU lookup and CUDA graph replay."""
import importlib.util
from pathlib import Path
import torch
from cuda.bindings import runtime as cudart

source = Path(__file__).resolve().parents[1] / "patches/qwen_host_embedding.py"
spec = importlib.util.spec_from_file_location("host_embedding", source)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
torch.manual_seed(787)
layer = torch.nn.Embedding(1024, 2560, device="cuda", dtype=torch.bfloat16)
original = layer.weight.detach().cpu()
helper.offload_token_embedding(layer)
assert layer._qwen_host_embedding_storage.is_pinned()
assert layer._qwen_host_embedding_storage.device.type == "cpu"
error, attrs = cudart.cudaPointerGetAttributes(layer.weight.data_ptr())
assert int(error) == 0
assert attrs.type == cudart.cudaMemoryType.cudaMemoryTypeHost, attrs
ids = torch.tensor([0, 7, 1023, 7], device="cuda")
torch.testing.assert_close(layer(ids).cpu(), original[ids.cpu()], rtol=0, atol=0)
stream = torch.cuda.Stream()
with torch.cuda.stream(stream):
    layer(ids)
    graph = torch.cuda.CUDAGraph()
    with torch.cuda.graph(graph, stream=stream):
        output = layer(ids)
    ids.copy_(torch.tensor([1023, 31, 0, 700], device="cuda"))
    graph.replay()
stream.synchronize()
torch.testing.assert_close(output.cpu(), original[ids.cpu()], rtol=0, atol=0)
print("PASS: CUDA pointer is host memory; exact embedding lookup and mutated-ID graph replay")
