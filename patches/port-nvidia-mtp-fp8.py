#!/usr/bin/env python3
"""Preserve NVIDIA Qwen MTP's serialized 128x128 block-FP8 experts."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
mtp = root / "models/qwen3_8_flash_next/nvidia/mtp.py"
text = mtp.read_text()
old = '        configure_quant_config(draft_quant_config, Qwen3_8FlashNextMTP)\n'
assert text.count(old) == 1
text = text.replace(old, old + '''        quantized_layers = getattr(draft_quant_config, "quantized_layers", None)
        if quantized_layers:
            draft_quant_config.quantized_layers = {
                _remap_ignored_layers([name], mtp_start_layer_idx)[0]: spec
                for name, spec in quantized_layers.items()
            }
''')
compile(text, str(mtp), "exec")
mtp.write_text(text)
path = root / "model_executor/layers/quantization/modelopt.py"
text = path.read_text()
start = text.index('class ModelOptMixedPrecisionConfig(')
old = '        quant_algo = self._resolve_quant_algo(prefix)\n'
assert text[start:].count(old) == 1
replacement = old + '''        if quant_algo == "FP8_PB_WO" and isinstance(layer, RoutedExperts):
            # Qwen NVIDIA MTP exports E4M3 weights and 2D weight_scale_inv
            # tensors for 128x128 blocks, the native vLLM block-FP8 ABI.
            candidates = self._quantized_layer_prefix_candidates(prefix)
            specs = [self.quantized_layers[name] for name in candidates
                     if name in self.quantized_layers]
            if len(specs) != 1 or specs[0].get("group_size") != 128:
                raise ValueError("FP8_PB_WO MoE requires explicit 128x128 block metadata")
            from .fp8 import Fp8Config
            return Fp8Config(is_checkpoint_fp8_serialized=True,
                             activation_scheme="dynamic",
                             weight_block_size=[128, 128]).get_quant_method(layer, prefix)
'''
text = text[:start] + text[start:].replace(old, replacement)
compile(text, str(path), "exec")
path.write_text(text)
print("NVIDIA MTP block-FP8 quantization mapping applied")
