#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]) / "model_executor/layers"
for name in ("linear.py", "vocab_parallel_embedding.py"):
    path = root / name
    text = path.read_text()
    needle = "    def process_weights_after_loading(self, layer: torch.nn.Module) -> None:\n"
    assert text.count(needle) == 1
    text = text.replace(needle, needle + "        from .qwen_vocab_projection import prepare\n        prepare(layer)\n")
    compile(text, str(path), "exec")
    path.write_text(text)
path = root / "logits_processor.py"
text = path.read_text()
needle = "        if self.head_dtype is None or self.head_dtype == hidden_states.dtype:\n"
assert text.count(needle) == 1
text = text.replace(needle, needle + """            from .qwen_vocab_projection import maybe_project
            projected = maybe_project(lm_head, hidden_states, embedding_bias)
            if projected is not None:
                return projected
""")
compile(text, str(path), "exec")
path.write_text(text)
print("Added opt-in planned B12x vocabulary projection with native dtype fallback")
