#!/usr/bin/env python3
"""Exercise the logits-processor bridge, graph replay and native fallbacks."""
import os
from types import SimpleNamespace

import torch
from vllm.model_executor.layers.logits_processor import LogitsProcessor
from vllm.model_executor.layers.qwen_vocab_projection import prepare
from vllm.model_executor.layers.vocab_parallel_embedding import UnquantizedEmbeddingMethod

torch.manual_seed(787)
weight = torch.randn((248320, 2560), dtype=torch.bfloat16, device="cuda")
layer = SimpleNamespace(weight=weight, quant_method=UnquantizedEmbeddingMethod())
os.environ["QWEN38_B12X_VOCAB"] = "1"
prepare(layer)
assert layer._qwen38_vocab_plan.config.backend == "triton"
stream = torch.cuda.Stream()
stream.wait_stream(torch.cuda.current_stream())
with torch.cuda.stream(stream):
    for rows, head_dtype, with_bias in ((1, None, False), (2, None, False),
                                        (1, torch.float32, False), (1, None, True)):
        source = torch.randn((rows, 2560), dtype=torch.bfloat16, device="cuda") / 2560**0.5
        bias = torch.randn((248320,), dtype=torch.bfloat16, device="cuda") if with_bias else None
        processor = SimpleNamespace(head_dtype=head_dtype)

        def launch():
            return LogitsProcessor._apply_head(processor, layer, source, bias)

        launch()
        graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph, stream=stream):
            output = launch()
        source.mul_(-1)
        graph.replay()
        reference = (torch.mm(source, weight.t(), out_dtype=torch.float32)
                     if head_dtype == torch.float32 else torch.nn.functional.linear(source, weight, bias))
        assert output.dtype == reference.dtype
        torch.testing.assert_close(output, reference, rtol=0.015, atol=0.02)
        print(f"PASS rows={rows} head_dtype={head_dtype} bias={with_bias}: mutated graph and dtype", flush=True)
    del layer._qwen38_vocab_plan
    os.environ["QWEN38_B12X_VOCAB"] = "0"
    prepare(layer)
    assert not hasattr(layer, "_qwen38_vocab_plan")
    actual = LogitsProcessor._apply_head(SimpleNamespace(head_dtype=None), layer, source, None)
    torch.testing.assert_close(actual, torch.nn.functional.linear(source, weight), rtol=0, atol=0)
    print("PASS disabled path uses native projection", flush=True)
torch.cuda.synchronize()
