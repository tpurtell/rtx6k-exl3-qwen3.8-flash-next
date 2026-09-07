#!/usr/bin/env python3
"""Carry vLLM #52805 / MIA #136 termination handling onto the pinned Qwen base.

Upstream: https://github.com/vllm-project/vllm/pull/52805
The Qwen base still contains the pre-fix accept/validate/reset methods.
"""
import hashlib
from pathlib import Path
import sys

STOCK_SHA256 = 'cdaebca794c8aa919097ee250f1bc0fa87f8fe52a026eee4877605e18134752e'
MARKER = '# Qwen / MIA #136: stop XGrammar batches at termination.'
EDITS = (
    ('''        if self._is_terminated:
            return False
        for token in tokens:
''', '''        if self._is_terminated:
            return True
        for token in tokens:
'''),
    ('''            self.num_processed_tokens += 1
        self._is_terminated = self.matcher.is_terminated()
        return True
''', '''            self.num_processed_tokens += 1
            self._is_terminated = self.matcher.is_terminated()
            if self._is_terminated:
                break
        return True
'''),
    ('''        accepted_tokens = []
        for token in tokens:
            if self.matcher.accept_token(token):
                accepted_tokens.append(token)
''', '''        if self._is_terminated:
            return []
        accepted_tokens = []
        for token in tokens:
            if self.matcher.accept_token(token):
                accepted_tokens.append(token)
                if self.matcher.is_terminated():
                    break
'''),
    ('''    def reset(self):
        self.num_processed_tokens = 0
        self.matcher.reset()
''', '''    def reset(self):
        self.matcher.reset()
        self.num_processed_tokens = 0
        self._is_terminated = False
'''),
)


def transform(source):
    if MARKER in source:
        if any(new not in source for _, new in EDITS):
            raise RuntimeError('incomplete XGrammar termination patch')
        return source
    for old, new in EDITS:
        if source.count(old) != 1:
            raise RuntimeError('XGrammar termination anchor is missing or ambiguous')
        source = source.replace(old, new)
    return MARKER + '\n' + source


def main():
    target = Path(sys.argv[1]) / 'v1/structured_output/backend_xgrammar.py'
    source = target.read_text()
    if MARKER not in source and hashlib.sha256(source.encode()).hexdigest() != STOCK_SHA256:
        raise SystemExit('unsupported Qwen XGrammar source identity')
    changed = transform(source)
    compile(changed, str(target), 'exec')
    if changed != source:
        target.write_text(changed)
    print('[ok] Qwen XGrammar accept/validate/reset termination backport')


if __name__ == '__main__':
    main()
