#!/usr/bin/env python3
"""Verify NVIDIA PLE metadata selects FP8 storage and preserves lookup bytes."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch
import torch
from vllm.model_executor.layers.quantization.modelopt import ModelOptMixedPrecisionConfig
from vllm.models.qwen3_8_flash_next.nvidia.ple_layer import (
    _get_ple_embedding_quant_method, Qwen3_8FlashNextPLEFp8EmbeddingMethod,
)

parser = argparse.ArgumentParser()
parser.add_argument("model", type=Path)
args = parser.parse_args()
config = json.loads((args.model / "config.json").read_text())["quantization_config"]
quant = ModelOptMixedPrecisionConfig.from_config(config)
prefix = "language_model.model.layers.1.ple.ple_embedding.ngram_embedding"
method = _get_ple_embedding_quant_method(quant, prefix)
assert isinstance(method, Qwen3_8FlashNextPLEFp8EmbeddingMethod)
layer = torch.nn.Module()
# This storage-only test supplies TP1 parameter metadata without a process group.
with (patch("vllm.model_executor.parameter.get_tensor_model_parallel_rank", return_value=0),
      patch("vllm.model_executor.parameter.get_tensor_model_parallel_world_size", return_value=1)):
    method.create_weights(layer, 160, [64], 160, 64, torch.bfloat16,
                          weight_loader=lambda *args, **kwargs: None)
assert layer.weight.device.type == "cpu"
assert layer.weight.dtype == torch.float8_e4m3fn
assert layer.weight_scale.numel() == 1
torch.manual_seed(787)
source = torch.randn(64, 160).to(torch.float8_e4m3fn)
with torch.no_grad():
    layer.weight.copy_(source)
    layer.weight_scale.fill_(0.25)
ids = torch.tensor([0, 63, 1, 1], dtype=torch.long)
output = torch.empty(4, 160, dtype=layer.weight.dtype)
torch.index_select(layer.weight, 0, ids, out=output)
assert torch.equal(output.view(torch.uint8), source.view(torch.uint8)[ids])
assert layer.weight.numel() * layer.weight.element_size() == 64 * 160
print("PASS: real NVIDIA PLE metadata, FP8 CPU allocation, scalar scale and byte-exact lookup")
