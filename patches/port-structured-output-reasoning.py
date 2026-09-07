#!/usr/bin/env python3
"""Backport vLLM c6e19b3be243 (#53046); ported from the GLM recipe issue #2 fix.

Unconstrained draft tokens after the thinking-end marker must be validated
before advancing the grammar. Do not suppress real grammar errors elsewhere.
Upstream: https://github.com/vllm-project/vllm/commit/c6e19b3be243
"""
import hashlib
from pathlib import Path
import sys

STOCK_SHA256 = "355f6f1193c15d5d6901a0f567e2e16005e3681f04f70079c6ba11e020b4d33a"
MARKER = "# Qwen recipe: vLLM c6e19b3be243 speculative reasoning guard."
OLD = '''                    if advance_grammar and not grammar.is_terminated():
                        accepted = grammar.accept_tokens(req_id, [token])
                        if accepted:
'''
NEW = '''                    if advance_grammar and not grammar.is_terminated():
                        if post_reasoning_end_in_window:
                            accepted = bool(grammar.validate_tokens([token]))
                            if accepted:
                                accepted = grammar.accept_tokens(req_id, [token])
                        else:
                            accepted = grammar.accept_tokens(req_id, [token])
                        if accepted:
'''


def transform(source):
    if MARKER in source:
        if source.count(NEW) != 1 or OLD in source:
            raise RuntimeError("incomplete speculative reasoning guard")
        return source
    if hashlib.sha256(source.encode()).hexdigest() != STOCK_SHA256:
        raise RuntimeError("unsupported Qwen structured-output source identity")
    if source.count(OLD) != 1:
        raise RuntimeError("structured-output anchor is missing or ambiguous")
    return MARKER + "\n" + source.replace(OLD, NEW)


def main():
    target = Path(sys.argv[1]) / "v1/structured_output/__init__.py"
    source = target.read_text()
    changed = transform(source)
    compile(changed, str(target), "exec")
    if changed != source:
        target.write_text(changed)
    print("[ok] Qwen speculative reasoning-end grammar validation backport")


if __name__ == "__main__":
    main()
