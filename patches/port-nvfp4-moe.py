#!/usr/bin/env python3
"""Route the tested Qwen NVFP4 geometry through optional precise B12x."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
path = root / "model_executor/layers/quantization/modelopt.py"
text = path.read_text()
start = text.index("class ModelOptNvFp4FusedMoE(")
end = text.index("ModelOptNvFp4Config.LinearMethodCls", start)
section = text[start:end]
old = "        self.moe_kernel.fused_experts.process_weights_after_loading(layer)\n"
assert section.count(old) == 1
section = section.replace(old, old + '''        from vllm.model_executor.layers.qwen_nvfp4_moe import prepare
        prepare(self, layer)
''')
text = text[:start] + section + text[end:]
compile(text, str(path), "exec")
path.write_text(text)

path = root / "model_executor/layers/fused_moe/experts/flashinfer_cutlass_moe.py"
text = path.read_text()
old = "    def expects_unquantized_inputs(self) -> bool:\n"
assert text.count(old) == 1
text = text.replace(old, old + '''        if hasattr(self, "_qwen_b12x"):
            return True
''')
old = 'output_shape = (M, K * 2 if self.quant_dtype == "nvfp4" else K)'
assert text.count(old) == 1
text = text.replace(old, 'output_shape = (M, K * 2 if self.quant_dtype == "nvfp4" and not hasattr(self, "_qwen_b12x") else K)')
old = "        quant_scales = None\n"
assert text.count(old) == 1
text = text.replace(old, '''        if hasattr(self, "_qwen_b12x"):
            from vllm.model_executor.layers.qwen_nvfp4_moe import run
            if expert_map is not None or apply_router_weight_on_input:
                raise ValueError("Unsupported routing for Qwen B12x NVFP4")
            run(self, output, hidden_states, topk_weights, topk_ids)
            return
''' + old)
compile(text, str(path), "exec")
path.write_text(text)
print("Optional precise Qwen NVFP4 expert bridge applied")
