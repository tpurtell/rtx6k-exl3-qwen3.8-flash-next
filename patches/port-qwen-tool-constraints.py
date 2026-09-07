#!/usr/bin/env python3
"""Retain grammar adjustment when Qwen reasoning and tool parsers share an engine."""
from pathlib import Path
import sys

path = Path(sys.argv[1]) / "parser/parser_manager.py"
text = path.read_text()
old = "        if reasoning_engine_cls is not None and reasoning_engine_cls is tool_engine_cls:\n            return reasoning_engine_cls\n"
new = """        if (
            reasoning_engine_cls is not None
            and reasoning_engine_cls is tool_engine_cls
            and getattr(tool_parser_cls, "structural_tag_model", None) is None
        ):
            # Structural-tag adapters need DelegatingParser.adjust_request.
            # Collapsing them into the engine drops required/named tool grammar.
            return reasoning_engine_cls
"""
assert text.count(old) == 1
text = text.replace(old, new)
compile(text, str(path), "exec")
path.write_text(text)
print("Preserved structural tool constraints through the delegating parser")
