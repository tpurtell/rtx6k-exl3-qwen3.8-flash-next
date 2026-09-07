#!/usr/bin/env python3
"""CPU regression test: real tokenizer, parser selection and tool grammar setup."""
import sys

from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest
from vllm.parser.abstract_parser import DelegatingParser
from vllm.parser.parser_manager import ParserManager
from vllm.tokenizers import get_tokenizer

tokenizer = get_tokenizer(sys.argv[1])
cls = ParserManager.get_parser("qwen3_coder", "qwen3", True)
assert issubclass(cls, DelegatingParser)
tool = {"type": "function", "function": {
    "name": "calculator", "description": "Evaluate arithmetic.",
    "parameters": {"type": "object", "properties": {"expression": {"type": "string"}},
                   "required": ["expression"], "additionalProperties": False}}}
for choice in ("required", {"type": "function", "function": {"name": "calculator"}}, "auto", "none"):
    request = ChatCompletionRequest(model="qwen38", messages=[{"role": "user", "content": "7 times 8?"}],
                                    tools=[tool], tool_choice=choice)
    parser = cls(tokenizer, request.tools)
    result = parser.adjust_request(request)
    tag = result.structured_outputs.structural_tag if result.structured_outputs else None
    if choice in ("auto", "none"):
        assert tag is None
    else:
        assert tag and "calculator" in tag
    assert result.skip_special_tokens is False
    print(f"PASS tool choice {choice}: structural tag present={bool(tag)}", flush=True)

request = ChatCompletionRequest(model="qwen38", messages=[{"role": "user", "content": "7 times 8?"}],
                                tools=[tool], tool_choice="auto")
parser = cls(tokenizer, request.tools)
raw = '<think>Use arithmetic.</think>\n<tool_call>\n<function=calculator>\n<parameter=expression>7*8</parameter>\n</function>\n</tool_call>'
reasoning, content, calls = parser.parse(raw, request, enable_auto_tools=True,
                                       model_output_token_ids=tokenizer.encode(raw, add_special_tokens=False))
assert reasoning and "arithmetic" in reasoning
assert len(calls) == 1 and calls[0].name == "calculator"
assert '7*8' in calls[0].arguments
print("PASS reasoning and automatic tool parsing remain intact", flush=True)
