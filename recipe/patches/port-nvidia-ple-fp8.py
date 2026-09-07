#!/usr/bin/env python3
"""Select the existing global-scale FP8 PLE loader for ModelOpt mixed weights."""
from pathlib import Path
import sys

path = Path(sys.argv[1]) / "models/qwen3_8_flash_next/nvidia/ple_layer.py"
text = path.read_text()
old = '    if not isinstance(quant_config, Fp8Config):\n        return None\n'
assert text.count(old) == 1
text = text.replace(old, '''    from vllm.model_executor.layers.quantization.modelopt import ModelOptMixedPrecisionConfig
    if isinstance(quant_config, ModelOptMixedPrecisionConfig):
        if quant_config.is_layer_excluded(prefix):
            return None
        if quant_config._resolve_quant_algo(prefix) == "FP8":
            return Qwen3_8FlashNextPLEFp8EmbeddingMethod()
        return None
''' + old)
compile(text, str(path), "exec")
path.write_text(text)
print("ModelOpt mixed PLE preserves global-scale FP8 host storage")
