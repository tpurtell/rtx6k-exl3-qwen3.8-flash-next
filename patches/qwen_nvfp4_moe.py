"""Optional precise B12x NVFP4 experts, within vLLM's modular MoE pipeline."""
import os
import torch
from b12x.moe import fused_moe
from vllm.logger import init_logger

logger = init_logger(__name__)
_PLANS = {}
_SCRATCH = {}


def prepare(method, layer):
    if os.environ.get("QWEN38_B12X_NVFP4", "0") != "1":
        return
    if method.nvfp4_backend.value != "FLASHINFER_CUTLASS":
        return
    if tuple(layer.w13_weight.shape) != (512, 1280, 1280):
        return
    if tuple(layer.w2_weight.shape) != (512, 2560, 320):
        return
    if layer.expert_map is not None or layer.apply_router_weight_on_input:
        raise ValueError("Qwen B12x NVFP4 requires TP1 with output routing weights")
    runtime = method.moe_kernel.fused_experts
    if type(runtime).__name__ != "FlashInferExperts":
        raise TypeError("Expected the FlashInfer modular expert ABI")
    plan = fused_moe.plan_weights(
        quant_modes="nvfp4", source_format="modelopt_nvfp4", activation="silu",
        params_dtype=torch.bfloat16, num_experts=512, hidden_size=2560,
        # vLLM's FlashInfer conversion stores [up, gate]; B12x calls that w13.
        intermediate_size=640, w13_layout="w13")
    experts = fused_moe.prepare_weights(
        plan=plan, params_dtype=torch.bfloat16,
        w1_fp4=layer.w13_weight, w2_fp4=layer.w2_weight,
        w1_blockscale=runtime.w1_scale, w2_blockscale=runtime.w2_scale,
        w1_global_scale=runtime.g1_alphas * runtime.a1_gscale,
        w2_global_scale=runtime.g2_alphas * runtime.a2_gscale,
        a1_gscale=runtime.a1_gscale, a2_gscale=runtime.a2_gscale)
    # Packed weights are shared with the native representation; never retain
    # another full model's worth of expert allocations for this option.
    assert experts.w1_fp4.data_ptr() == layer.w13_weight.data_ptr()
    assert experts.w2_fp4.data_ptr() == layer.w2_weight.data_ptr()
    device = layer.w13_weight.device
    capacity = int(method.moe.max_num_tokens)
    key = (device, capacity)
    if key not in _PLANS:
        _PLANS[key] = fused_moe.plan(fused_moe.Caps(
            max_tokens=capacity, num_topk=10, device=device,
            weight_plan=plan, quant_mode="nvfp4", frozen=False))
    runtime._qwen_b12x = (experts, _PLANS[key])
    logger.info_once("Qwen NVFP4 experts use precise B12x; packed weights shared")


def run(runtime, output, hidden_states, topk_weights, topk_ids):
    experts, plan = runtime._qwen_b12x
    device = hidden_states.device
    key = (device, torch.cuda.current_stream(device).cuda_stream, plan.caps.max_tokens)
    if key not in _SCRATCH:
        # Capture-owned allocations are retained for the lifetime of the
        # stream, just as for the QSA bridge. Layers execute serially per stream.
        (spec,) = plan.scratch_specs()
        _SCRATCH[key] = torch.empty(spec.shape, dtype=spec.dtype, device=device)
    binding = fused_moe.bind(plan, scratch=_SCRATCH[key], a=hidden_states,
                            experts=experts, topk_weights=topk_weights,
                            topk_ids=topk_ids, output=output, fast_math=False)
    return fused_moe.run(binding=binding)
