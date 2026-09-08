"""Resident GPU workers must load metadata without owning the CPU PLE table."""
import pytest
import torch
from vllm import envs
from vllm.models.qwen3_8_flash_next.nvidia import ple_layer

@pytest.mark.parametrize('quantized', [False, True])
def test_resident_worker_without_embedding_loads_only_optional_scale(monkeypatch, quantized):
    monkeypatch.setenv('VLLM_PLE_CPU_OFFLOAD', '1')
    monkeypatch.setenv('VLLM_PLE_MMAP', '0')
    monkeypatch.setattr(ple_layer, 'is_offload_process', lambda: False)
    monkeypatch.setattr(torch.accelerator, 'current_accelerator', lambda: torch.device('cpu'))
    module = ple_layer.Qwen3_8FlashNextNGramEmbedding.__new__(ple_layer.Qwen3_8FlashNextNGramEmbedding)
    torch.nn.Module.__init__(module)
    assert not hasattr(module, 'ngram_embedding')
    scale = torch.tensor([0.25], dtype=torch.bfloat16)
    weights = [('ngram_embedding.shard_0.weight', torch.zeros(4, 2)),
               ('layer_multipliers', torch.ones(3, dtype=torch.long))]
    if quantized:
        weights.append(('ngram_embedding.weight_scale', scale))
    loaded = module.load_weights(iter(weights))
    assert not hasattr(module, 'ngram_embedding')
    assert loaded == ({'ngram_embedding.weight_scale'} if quantized else set())
    if quantized:
        assert torch.equal(module._offload_weight_scale, scale)
        assert module.get_offload_output_dtype(torch.bfloat16) == torch.float8_e4m3fn
    else:
        assert not hasattr(module, '_offload_weight_scale')
        assert module.get_offload_output_dtype(torch.bfloat16) == torch.bfloat16
