#!/usr/bin/env python3
"""Apply the reviewed PR #54129 backport to the pinned, patched vLLM base."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
root = Path(sys.argv[1]).parent
assets = Path(__file__).parent
for name, expected in json.loads((assets / 'ple-mmap-base-hashes.json').read_text()).items():
    p = root / name
    actual = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    if actual != expected:
        raise RuntimeError(f'Mmap backport base mismatch: {name}: {actual} != {expected}')
subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-d', str(root),
                '-i', str((assets / 'ple-mmap-pr54129.patch').resolve())], check=True)
print('Applied reviewed mmap PLE backport from PR 54129 @ 50a061f792f36364f5f95a93eee21f1e9d77f65e')
