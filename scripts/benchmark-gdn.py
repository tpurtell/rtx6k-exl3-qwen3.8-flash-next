#!/usr/bin/env python3
"""Compare post-convolution Qwen GDN transactions at TP1 geometry.

Uses contiguous inputs (favorable to the candidate). Each graph invocation
starts from the same state; restoration runs before the timed CUDA event.
"""
import json
import statistics
import sys
sys.path.insert(0, "/opt/b12x")
import torch
from benchmarks.benchmark_gdn_decode import BenchmarkCase, build_case, _reference
from b12x.sequence import gdn_decode as gdn
from vllm import _custom_ops as ops

torch.cuda.set_device(0)
for batch, columns in ((1, 1), (1, 3), (1, 4), (8, 3), (16, 3)):
    case = BenchmarkCase(f"b{batch}-q{columns}", (columns,) * batch, 16, 48)
    buffers = build_case(case, device=torch.device("cuda:0"), seed=787,
                         capacity_seqs=batch, capacity_columns=columns)
    b = buffers.binding
    # vLLM reserves slot zero for null/padding. Use real slots in both paths.
    b.state_indices.add_(1)
    native_out = torch.empty_like(b.output)
    def native():
        return ops.fused_gdn_decode_post_conv_mtp(
            mixed_qkv=b.mixed_qkv, a=b.a, b=b.b, A_log=b.A_log,
            dt_bias=b.dt_bias, state_indices=b.state_indices,
            cu_seqlens=b.query_start_loc, num_accepted_tokens=b.num_accepted_tokens,
            state=b.recurrent_state, output_gate=b.z, norm_weight=b.norm_weight,
            out=native_out, norm_eps=1e-6, output_gate_activation="sigmoid")
    functions = {"native": native, "b12x": lambda: gdn.run(b)}
    graphs = {}
    stream = torch.cuda.Stream()
    stream.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(stream):
        for name, fn in functions.items():
            for _ in range(3):
                b.recurrent_state.copy_(buffers.initial_state)
                fn()
            graph = torch.cuda.CUDAGraph()
            with torch.cuda.graph(graph):
                fn()
            graphs[name] = graph
    torch.cuda.current_stream().wait_stream(stream)
    errors = []
    for _ in range(3):
        b.mixed_qkv.add_(0.001)
        b.recurrent_state.copy_(buffers.initial_state)
        graphs["native"].replay()
        expected_out, expected_state = native_out.clone(), b.recurrent_state.clone()
        b.recurrent_state.copy_(buffers.initial_state)
        graphs["b12x"].replay()
        try:
            torch.testing.assert_close(b.output, expected_out, atol=0.03, rtol=0.03)
        except AssertionError:
            oracle_out, oracle_state = _reference(buffers)
            print(json.dumps({"batch": batch, "columns": columns,
                "numerical_check_failed": True,
                "native_oracle_output_max_abs": (expected_out.float()-oracle_out.float()).abs().max().item(),
                "b12x_oracle_output_max_abs": (b.output.float()-oracle_out.float()).abs().max().item(),
                "native_oracle_state_max_abs": (expected_state-oracle_state).abs().max().item(),
                "b12x_oracle_state_max_abs": (b.recurrent_state-oracle_state).abs().max().item()}), flush=True)
            raise
        torch.testing.assert_close(b.recurrent_state, expected_state, atol=0.003, rtol=0.03)
        errors.append({"output_max_abs": (b.output.float()-expected_out.float()).abs().max().item(),
                       "state_max_abs": (b.recurrent_state-expected_state).abs().max().item()})
    timings = {name: [] for name in graphs}
    for _ in range(100):
        for name, graph in graphs.items():
            b.recurrent_state.copy_(buffers.initial_state)
            start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
            start.record()
            graph.replay()
            end.record()
            end.synchronize()
            timings[name].append(start.elapsed_time(end)*1000)
    print(json.dumps({"batch": batch, "columns": columns, "key_heads": 16,
                      "value_heads": 48, "state_dtype": "float32", "checks": errors,
                      "samples_us": timings,
                      "median_us": {name: statistics.median(values) for name, values in timings.items()}}), flush=True)
