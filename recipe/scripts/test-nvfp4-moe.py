#!/usr/bin/env python3
"""Exercise the patched expert ABI with actual checkpoint scales and weights."""
import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, "/opt/b12x")
import torch
from benchmarks.benchmark_moe import (
    MODEL_PROFILES, build_model_spec, load_expert_weights,
    get_quant_mode_params, make_profile_routed_inputs, make_oracle_reference,
    compare_to_reference, check_oracle_metrics)
from vllm.model_executor.layers.fused_moe.config import (
    FusedMoEConfig, FusedMoEParallelConfig, FusedMoEQuantConfig, RoutingMethodType)
from vllm.model_executor.layers.fused_moe.activation import MoEActivation
from vllm.model_executor.layers.fused_moe.experts.flashinfer_cutlass_moe import FlashInferExperts
from vllm.model_executor.layers import qwen_nvfp4_moe as bridge

parser = argparse.ArgumentParser()
parser.add_argument("model_path", type=Path)
args = parser.parse_args()
os.environ["QWEN38_B12X_NVFP4"] = "1"
device = torch.device("cuda:0")
torch.cuda.set_device(device)
profile = MODEL_PROFILES["qwen38-flash-next"]
spec = build_model_spec(args.model_path, profile, tp_size_override=1)
weights = load_expert_weights(args.model_path, spec, layer_idx=0,
                              activation="silu", checkpoint_family="qwen")
assert weights.w13_layout == "w13"
params = get_quant_mode_params(weights, "shared", "nvfp4")
parallel = FusedMoEParallelConfig(tp_size=1, pcp_size=1, dp_size=1, ep_size=1,
    tp_rank=0, pcp_rank=0, dp_rank=0, ep_rank=0, sp_size=1,
    use_ep=False, all2all_backend="naive", enable_eplb=False)
config = FusedMoEConfig(num_experts=512, experts_per_token=10, hidden_dim=2560,
    intermediate_size=640, num_local_experts=512, num_logical_experts=512,
    activation=MoEActivation.SILU, device=device, routing_method=RoutingMethodType(0),
    moe_parallel_config=parallel, in_dtype=torch.bfloat16, max_num_tokens=2048)
quant = FusedMoEQuantConfig.make(quant_dtype="nvfp4", weight_dtype="nvfp4",
    w1_scale=weights.w13_blockscale_swizzled, w2_scale=weights.w2_blockscale_swizzled,
    g1_alphas=params.g1_alphas, g2_alphas=params.g2_alphas,
    a1_gscale=params.a1_gscale, a2_gscale=params.a2_gscale)
runtime = FlashInferExperts(config, quant)
assert not runtime.expects_unquantized_inputs
layer = SimpleNamespace(w13_weight=weights.w13_weight, w2_weight=weights.w2_weight,
                        expert_map=None, apply_router_weight_on_input=False)
method = SimpleNamespace(nvfp4_backend=SimpleNamespace(value="FLASHINFER_CUTLASS"),
                         moe_kernel=SimpleNamespace(fused_experts=runtime), moe=config)
bridge.prepare(method, layer)
assert runtime.expects_unquantized_inputs
stream = torch.cuda.Stream()
for rows in (1, 3, 4, 16, 48, 64, 2048):
    x, ids, routing = make_profile_routed_inputs(profile, weights, spec, rows, 42+rows, device)
    out = torch.empty_like(x)
    assert runtime.workspace_shapes(rows, 1280, 2560, 10, 512, 512, None,
                                    MoEActivation.SILU)[2] == tuple(out.shape)
    def launch():
        runtime.apply(out, x, weights.w13_weight, weights.w2_weight, routing, ids,
                      MoEActivation.SILU, 512, None, None, None, None, None, None, False)
    launch()
    stream.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(stream):
        launch()
        graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph):
            launch()
    torch.cuda.current_stream().wait_stream(stream)
    for mutation in range(3):
        x.mul_(0.99)
        ids.add_(1).remainder_(512)
        out.fill_(float("nan"))
        graph.replay()
        oracle = make_oracle_reference("nvfp4", "nvfp4", x, weights, params,
                                       ids, routing, activation="silu")
        metrics = compare_to_reference(out, oracle)
        failures = check_oracle_metrics("bridge", metrics, rows, oracle_mode="nvfp4")
        if failures:
            raise AssertionError("\n".join(failures))
        print(json.dumps({"rows": rows, "mutation": mutation, "cosine": metrics.cos,
                          "max_abs": metrics.max_abs, "passed": True}), flush=True)
print("Patched NVFP4 expert ABI: weight sharing, BF16 input/output, and 21 mutated graph oracle checks passed.")
