"""Qwen serving bridge to pinned B12x selected-position sparse GQA.

The vLLM indexer still owns selection. B12x reads the selected main KV pages.
Workspace is shared by sequential attention layers on a single CUDA stream.
"""
import torch
from b12x.attention.qsa._sparse_gqa import launch_sparse_paged_gqa
from b12x.attention.qsa._sparse_gqa_cute_config import (
    BLOCK_N, MAX_SPLIT_ROWS, NUM_SPLITS,
)

_scratch = {}


def run(layer, query, key_cache, value_cache, indices, block_table,
        request_ids, positions, output):
    key = (query.device, torch.cuda.current_stream().cuda_stream, query.shape[1], query.shape[2])
    if key not in _scratch:
        if torch.cuda.is_current_stream_capturing():
            raise RuntimeError("B12x QSA workspace must be warmed before graph capture")
        _scratch[key] = (
            torch.empty((MAX_SPLIT_ROWS, NUM_SPLITS, query.shape[1], query.shape[2]),
                        dtype=torch.float32, device=query.device),
            torch.empty((MAX_SPLIT_ROWS, NUM_SPLITS, query.shape[1]),
                        dtype=torch.float32, device=query.device),
        )
    partial_output, partial_lse = _scratch[key]
    splits = NUM_SPLITS
    if query.shape[0] > MAX_SPLIT_ROWS:
        # The direct prefill kernel does not consume split scratch. Supplying
        # a decode-sized view would violate the launch validation contract.
        partial_output = partial_lse = None
        splits = 1
    return launch_sparse_paged_gqa(
        query=query, key_cache=key_cache, value_cache=value_cache,
        k_descale=layer._k_scale, v_descale=layer._v_scale,
        block_table=block_table, request_ids=request_ids,
        selected_positions=indices, query_positions=positions,
        output=output, partial_output=partial_output, partial_lse=partial_lse,
        softmax_scale=layer.scaling, block_n=BLOCK_N, splits=splits,
    )
