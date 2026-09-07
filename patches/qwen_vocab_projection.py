"""Opt-in B12x BF16 single-row vocabulary projection for the Qwen checkpoint."""
import os

import torch
from vllm.logger import init_logger

logger = init_logger(__name__)


def prepare(layer):
    if os.getenv("QWEN38_B12X_VOCAB", "0") != "1":
        return
    weight = getattr(layer, "weight", None)
    if (weight is None or not weight.is_cuda or weight.dtype != torch.bfloat16
            or tuple(weight.shape) != (248320, 2560) or not weight.is_contiguous()):
        return
    from b12x.gemm import bf16_vocab_projection as vocab
    planned = vocab.plan(vocab.Caps(device=weight.device, max_tokens=1,
                                   in_features=2560, out_features=248320))
    if planned.config.backend != "triton":
        return
    # Resolve policy and compile before any serving graph can call the head.
    source = torch.zeros((1, 2560), dtype=weight.dtype, device=weight.device)
    vocab.run(vocab.bind(planned, source=source, weight=weight))
    layer._qwen38_vocab_plan = planned
    logger.info("Prepared B12x BF16 vocabulary projection: %s", planned.config)


def maybe_project(layer, source, bias):
    planned = getattr(layer, "_qwen38_vocab_plan", None)
    if (planned is None or bias is not None or source.ndim != 2
            or source.shape[0] != 1 or source.dtype != torch.bfloat16
            or not source.is_contiguous()):
        return None
    from b12x.gemm import bf16_vocab_projection as vocab
    return vocab.run(vocab.bind(planned, source=source, weight=layer.weight))
