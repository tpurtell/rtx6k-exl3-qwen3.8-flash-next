#!/usr/bin/env python3
"""Restore CPU-resident PLE loading before inspecting mmap/GPU embeddings."""
import hashlib
from pathlib import Path
import sys
p = Path(sys.argv[1]) / 'models/qwen3_8_flash_next/nvidia/ple_layer.py'
s = p.read_text()
expected = '2069d62b8ff4e19fb984a749dfc89b04009dc07877fbf1277e3fd8b97231f6ee'
if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
    raise RuntimeError('Resident PLE port base mismatch')
start = s.index('        embedding = self.ngram_embedding\n', s.index('    def load_weights('))
resident = s.index('        # GPU workers retain only the global FP8 scale.', start)
end = s.index('        persistent_buffers = {', resident)
# The resident GPU worker deliberately has no ngram_embedding. Handle its
# metadata-only load first; leave the mmap reload guard before weight iteration.
s = s[:start] + s[resident:end] + s[start:resident] + s[end:]
p.write_text(s)
print('Restored resident PLE worker metadata loading before mmap embedding access')
