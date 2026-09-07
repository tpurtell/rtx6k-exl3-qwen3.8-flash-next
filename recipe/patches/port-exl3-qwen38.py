#!/usr/bin/env python3
"""Port the pinned GLM mixed-projection EXL3 adapter to Qwen 3.8 vLLM."""
from pathlib import Path
import sys

root = Path(sys.argv[1])


def replace(path, old, new, count=1):
    text = path.read_text()
    if text.count(old) != count:
        raise RuntimeError(f"{path}: expected {count} matches for {old!r}, found {text.count(old)}")
    path.write_text(text.replace(old, new))


registry = root / "model_executor/layers/quantization/__init__.py"
replace(registry, '    "deepseek_v4_fp8",\n', '    "deepseek_v4_fp8",\n    "exl3",\n')
replace(registry, '    from .experts_int8 import ExpertsInt8Config\n',
        '    from .experts_int8 import ExpertsInt8Config\n    from .exl3 import Exl3Config\n')
replace(registry, '        "deepseek_v4_fp8": DeepseekV4FP8Config,\n',
        '        "deepseek_v4_fp8": DeepseekV4FP8Config,\n        "exl3": Exl3Config,\n')
exl3 = root / "model_executor/layers/quantization/exl3.py"
replace(exl3, '''            # A standard MTP forward has one row per live request, not one
            # row per target-prefill token. Planning its EXL3 prefill arena
            # for max_num_batched_tokens duplicated the target's ~GiB-scale
            # arena even though that capacity was unreachable. Keep its
            # independently captured runtime, but size it to concurrency.
            layer.exl3_max_num_batched_tokens = int(
                scheduler_config.max_num_seqs
                if is_draft
                else scheduler_config.max_num_batched_tokens
            )
''', '''            # V2 MTP executes a prefill across target rows in profiling
            # and proposal setup. Its arena must cover the scheduler token
            # capacity, not only the number of concurrent requests.
            layer.exl3_max_num_batched_tokens = int(
                scheduler_config.max_num_batched_tokens
            )
''')
replace(exl3, '            "glm5_next_text",\n',
        '            "glm5_next_text",\n            "qwen4_exp",\n            "qwen4_exp_text",\n'
        '            "qwen3_8_flash_next",\n            "qwen3_8_flash_next_text",\n'
        '            "qwen3_8_flash_next_mtp",\n')
replace(exl3, r'|mtp\.\d+)', r'|mtp\.(?:layers\.)?\d+)', count=2)
replace(exl3, r'|mtp\.(?P<mtp>\d+))', r'|mtp\.(?:layers\.)?(?P<mtp>\d+))')
replace(exl3, '        num_hidden_layers = int(getattr(hf_config, "num_hidden_layers", 0))\n',
        '        text_config = getattr(hf_config, "text_config", hf_config)\n'
        '        num_hidden_layers = int(getattr(text_config, "num_hidden_layers", 0))\n')
replace(exl3, '        if model_type != "deepseek_v4":\n',
        '        if model_type.startswith("qwen"):\n'
        '            # vLLM numbers draft layers after the target layers.\n'
        '            for name, entry in list(self.tensor_storage.items()):\n'
        '                match = re.match(r"^mtp\\.layers\\.(\\d+)\\.(.*)$", name)\n'
        '                if match:\n'
        '                    index = num_hidden_layers + int(match.group(1))\n'
        '                    self.tensor_storage[f"mtp.layers.{index}.{match.group(2)}"] = entry\n'
        '        if model_type != "deepseek_v4":\n')
routed = root / "model_executor/layers/fused_moe/routed_experts.py"
replace(routed, '            is_fused = loaded_weight.dim() == 3\n',
        '            # EXL3 per-expert trellis tiles also have rank three.\n'
        '            is_fused = (loaded_weight.dim() == 3\n'
        '                        and self.quant_method.__class__.__name__ != "Exl3MoEMethod")\n')
for path in (registry, exl3, routed):
    compile(path.read_text(), str(path), "exec")
print("Qwen EXL3 namespace and per-projection loader port applied")
