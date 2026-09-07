#!/usr/bin/env python3
from pathlib import Path
import sys

path = Path(sys.argv[1]) / "model_executor/layers/vocab_parallel_embedding.py"
text = path.read_text()
old = '    def process_weights_after_loading(self, layer: torch.nn.Module) -> None:\n'
assert text.count(old) == 1
text = text.replace(old, old + '''        import os
        if (os.getenv("QWEN38_HOST_EMBEDDINGS", "1") == "1"
                and type(layer) is VocabParallelEmbedding):
            from .qwen_host_embedding import offload_token_embedding
            offload_token_embedding(layer)
''')
compile(text, str(path), "exec")
path.write_text(text)
