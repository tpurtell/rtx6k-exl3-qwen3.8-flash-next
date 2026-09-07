"""Qwen tile candidates against pinned serial-tier oracle and changed-row graphs."""
import inspect
import runpy
import torch
ns = runpy.run_path('/opt/b12x/tests/moe/test_w4a16_mixed_trellis.py')
fn = ns['test_mixed_two_tier_matches_serial_and_captures']
s = inspect.getsource(fn)
assert s.count('    m, topk = 2, 2') == 1
s = s.replace('    m, topk = 2, 2', '    m, topk = TEST_M, 2')
anchor = '    map0 = torch.tensor([1, -1, 0, -1], dtype=torch.int32, device=device)'
assert s.count(anchor) == 1
s = s.replace(anchor, '''    topk_ids = topk_ids.repeat(((m+1)//2, 1))[:m].contiguous()
    topk_weights = topk_weights.repeat(((m+1)//2, 1))[:m].contiguous()
''' + anchor)
anchor = '    assert torch.equal(captured, eager)'
assert s.count(anchor) == 1
s = s.replace(anchor, anchor + '''
    x.mul_(-1)
    changed_reference = _serial_tier(x, tier0, topk_weights, topk_ids, map0)
    changed_reference += _serial_tier(x, tier1, topk_weights, topk_ids, map1)
    graph.replay()
    torch.cuda.synchronize(device)
    relative_changed = (captured - changed_reference).norm() / changed_reference.norm().clamp_min(1e-12)
    assert float(relative_changed) < 4e-3
    x.mul_(-1)
    graph.replay()
    torch.cuda.synchronize(device)
''')
exec(compile(s, 'qwen-tile-numerical-probe', 'exec'), ns)
for tile_k in (64,128):
    for m in (1,2,3,4,5,8):
        ns['TEST_M'] = m
        ns[fn.__name__](torch.int32,'mcg',(4,5),False,'bf16',
                       geometry=(2560,640),tile_config=(tile_k,128,tile_k,128))
        print(f'PASS: Qwen H2560/I640 K4/K5, M={m}, K tile={tile_k}, serial oracle and changed-input CUDA graph',flush=True)
