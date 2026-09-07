"""Keep the token embedding table in pinned host RAM with a CUDA UVA view."""
import torch
from vllm.logger import init_logger
from vllm.utils.torch_utils import get_accelerator_view_from_cpu_tensor

logger = init_logger(__name__)


def offload_token_embedding(layer):
    weight = layer.weight
    if weight.device.type != "cuda" or getattr(weight, "_vllm_is_uva_offloaded", False):
        return
    host = torch.empty(weight.shape, dtype=weight.dtype, device="cpu", pin_memory=True)
    host.copy_(weight.detach())
    weight.data = get_accelerator_view_from_cpu_tensor(host)
    weight._vllm_is_uva_offloaded = True
    # Keep host ownership explicit for the complete layer lifetime.
    layer._qwen_host_embedding_storage = host
    logger.info("Token embedding offloaded to pinned host RAM: %s, %.3f GiB",
                tuple(weight.shape), host.numel() * host.element_size() / 2**30)
