"""Independent regression cases from review of PR 54129 scale validation."""
import pytest
import torch
from test_ple_mmap_upstream import _write_ple_layer
from vllm.models.qwen3_8_flash_next.nvidia import ple_mmap

@pytest.mark.parametrize('disk_scale,streamed_scale', [
    (1e-8, 2e-8),  # atol=1e-6 used to accept a 100% relative error.
    (0.5, [0.5, 0.5]),  # broadcasting used to accept a nonscalar streamed scale.
])
def test_reject_nonidentical_streamed_scale(tmp_path, disk_scale, streamed_scale):
    _write_ple_layer(tmp_path, layer_idx=0, vocab=8, parts=2, cols=4, scale=disk_scale)
    shards = ple_mmap.discover_shards(str(tmp_path))[0]
    embedding = ple_mmap.MmapNgramEmbedding(8, 4)
    ple_mmap.set_weight_scale(embedding, torch.tensor(streamed_scale, dtype=torch.bfloat16), torch.device('cpu'))
    embedding.weights_streamed = True
    try:
        with pytest.raises(RuntimeError, match='weight_scale mismatch'):
            ple_mmap._attach_table(embedding, shards, 2, 0, str(tmp_path))
    finally:
        if embedding.table is not None:
            embedding.table.close()

@pytest.mark.parametrize('scale', [float('inf'), float('-inf'), float('nan')])
def test_reject_nonfinite_checkpoint_scale(tmp_path, scale):
    _write_ple_layer(tmp_path, layer_idx=0, vocab=8, parts=2, cols=4, scale=scale)
    shards = ple_mmap.discover_shards(str(tmp_path))[0]
    with pytest.raises(ValueError, match='finite'):
        ple_mmap._read_scale(shards.scale_entry)
