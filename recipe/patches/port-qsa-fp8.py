#!/usr/bin/env python3
"""Route QSA main-cache attention through the pinned B12x FP8/BF16 kernel."""
from pathlib import Path
import sys

path = Path(sys.argv[1]) / "models/qwen3_8_flash_next/nvidia/qsa.py"
text = path.read_text()


def replace(old, new, count=1):
    global text
    if text.count(old) != count:
        raise RuntimeError(f"expected {count} matches, found {text.count(old)}: {old!r}")
    text = text.replace(old, new)


replace('["auto", "bfloat16"]', '["auto", "bfloat16", "fp8", "fp8_e4m3"]')
replace('return "QWEN38_FLASH_NEXT_QSA_TRITON"', 'return "QWEN38_FLASH_NEXT_QSA_B12X"')
# FA2 is retained only for metadata and cache writes; its attention kernel is
# not used. Initialize its BF16 capability checks, then retain actual storage.
replace('        super().__init__(*args, **kwargs)\n',
        '        args = list(args)\n'
        '        cache_dtype = args[6] if len(args) > 6 else kwargs["kv_cache_dtype"]\n'
        '        if len(args) > 6:\n'
        '            args[6] = "auto"\n'
        '        else:\n'
        '            kwargs["kv_cache_dtype"] = "auto"\n'
        '        super().__init__(*args, **kwargs)\n'
        '        self.kv_cache_dtype = cache_dtype\n')
replace('not in ("auto", "bfloat16")', 'not in ("auto", "bfloat16", "fp8", "fp8_e4m3")', count=2)
replace('"Qwen3.8-Flash-Next QSA requires a BF16 main KV cache"',
        '"B12x QSA requires BF16 or FP8 E4M3 main KV cache"', count=2)
replace('        token_to_req: torch.Tensor,\n',
        '        token_to_req: torch.Tensor,\n        logical_positions: torch.Tensor,\n')
start = text.index('        if key_cache.dtype != torch.bfloat16 or query.dtype != torch.bfloat16:')
end = text.index('        return output\n', start)
text = text[:start] + '''        if self.kv_cache_dtype in ("fp8", "fp8_e4m3"):
            key_cache = key_cache.view(torch.float8_e4m3fn)
            value_cache = value_cache.view(torch.float8_e4m3fn)
        from .b12x_qsa_attention import run
        run(layer, query[:num_tokens], key_cache, value_cache, logical_indices,
            attn_metadata.block_table, token_to_req,
            logical_positions[:num_tokens], output[:num_tokens])
''' + text[end:]
replace('        if self.kv_cache_torch_dtype != torch.bfloat16:\n',
        '        if self.kv_cache_torch_dtype not in (torch.bfloat16, torch.uint8, torch.float8_e4m3fn):\n')
replace('"Qwen3.8-Flash-Next QSA requires BF16 cache storage"',
        '"B12x QSA requires BF16 or FP8 cache storage"')
replace('            token_to_req=side_metadata.token_to_req,\n',
        '            token_to_req=side_metadata.token_to_req,\n'
        '            logical_positions=side_metadata.logical_positions,\n')
compile(text, str(path), "exec")
path.write_text(text)
print("B12x BF16/FP8 QSA serving bridge applied")
