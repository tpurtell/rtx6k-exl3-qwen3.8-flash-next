#!/usr/bin/env python3
"""Honor the explicit qflashrt.fp8-ple.v1 annotation in EXL3 hybrids."""
from pathlib import Path
import sys
root = Path(sys.argv[1])
path = root / 'model_executor/layers/quantization/exl3.py'
s = path.read_text()
old = '        base_quantization_config: dict[str, Any] | None = None,\n'
assert s.count(old) == 1
s = s.replace(old, old + '        qflashrt_ple: dict[str, Any] | None = None,\n')
old = '        self.bits = bits\n'
assert s.count(old) == 1
s = s.replace(old, old + '        self.qflashrt_ple = qflashrt_ple\n')
old = '            base_quantization_config=config.get("base_quantization_config"),\n'
assert s.count(old) == 1
s = s.replace(old, old + '            qflashrt_ple=config.get("meta", {}).get("qflashrt_ple"),\n')
compile(s, str(path), 'exec')
path.write_text(s)
path = root / 'models/qwen3_8_flash_next/nvidia/ple_layer.py'
s = path.read_text()
old = '    if not isinstance(quant_config, Fp8Config):\n        return None\n'
assert s.count(old) == 1
s = s.replace(old, '''    annotation = getattr(quant_config, "qflashrt_ple", None)
    if annotation is not None:
        module = annotation.get("module", "")
        expected = {
            "schema": "qflashrt.fp8-ple.v1",
            "quant_algo": "FP8",
            "storage_dtype": "F8_E4M3",
            "scale_dtype": "BF16",
            "arithmetic_transform": False,
            "weight_scale": module + ".weight_scale",
        }
        if not module.startswith("model.language_model.layers.") or any(
            annotation.get(key) != value for key, value in expected.items()
        ):
            raise ValueError("Unsupported EXL3 FP8 PLE annotation")
        runtime_module = module.replace("model.language_model.", "language_model.model.", 1)
        if prefix == runtime_module:
            return Qwen3_8FlashNextPLEFp8EmbeddingMethod()
        return None
''' + old)
compile(s, str(path), 'exec')
path.write_text(s)
print('EXL3 annotated PLE preserves global-scale FP8 host storage')
