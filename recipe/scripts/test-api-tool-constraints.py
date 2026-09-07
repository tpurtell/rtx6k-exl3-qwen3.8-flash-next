#!/usr/bin/env python3
"""Verify required/named/auto/none tool choices in both API response modes."""
import argparse
import json
from pathlib import Path
import urllib.request


def request(base, payload):
    req = urllib.request.Request(base.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as response:
        if not payload["stream"]:
            body = json.load(response)
            return body["choices"][0]["message"].get("tool_calls") or [], body
        events, calls = [], {}
        for line in response:
            if not line.startswith(b"data:"):
                continue
            raw = line[5:].strip()
            if raw == b"[DONE]":
                break
            event = json.loads(raw)
            events.append(event)
            for choice in event.get("choices", []):
                for call in choice.get("delta", {}).get("tool_calls") or []:
                    current = calls.setdefault(call["index"], {"function": {"name": "", "arguments": ""}})
                    for field in ("name", "arguments"):
                        current["function"][field] += (call.get("function") or {}).get(field) or ""
        return [calls[i] for i in sorted(calls)], events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tool = {"type": "function", "function": {
        "name": "calculator", "description": "Evaluate arithmetic.",
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}},
                       "required": ["expression"], "additionalProperties": False}}}
    cases = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        output.write(json.dumps({"record": "meta", "schema": "qwen38-api-tool-constraints-v1",
                                 "args": vars(args) | {"output": str(args.output)}}) + "\n")
        for thinking in (False, True):
            for streaming in (False, True):
                for mode in ("required", "named", "auto", "none"):
                    payload = {
                        "model": args.model,
                        "messages": [{"role": "system", "content": "Use the calculator if the user asks for it. Otherwise answer directly."},
                                     {"role": "user", "content": "What is 7 times 8?" + (" Use the calculator." if mode == "auto" else "")}],
                        "tools": [tool], "tool_choice": mode if mode != "named" else {"type": "function", "function": {"name": "calculator"}},
                        "temperature": 0, "max_tokens": 1024,
                        "chat_template_kwargs": {"enable_thinking": thinking},
                        "stream": streaming,
                    }
                    if streaming:
                        payload["stream_options"] = {"include_usage": True}
                    calls, raw = request(args.base_url, payload)
                    correct = not calls if mode == "none" else len(calls) == 1
                    for call in calls:
                        try:
                            params = json.loads(call["function"]["arguments"])
                            correct &= call["function"]["name"] == "calculator"
                            correct &= set(params) == {"expression"}
                            correct &= params["expression"].replace(" ", "") in ("7*8", "8*7")
                        except (ValueError, KeyError, TypeError, AttributeError):
                            correct = False
                    row = {"record": "measurement", "thinking": thinking, "streaming": streaming,
                           "mode": mode, "passed": correct, "request": payload,
                           "calls": calls, "raw_response": raw}
                    cases.append(row)
                    output.write(json.dumps(row) + "\n")
                    output.flush()
                    print(json.dumps({k: row[k] for k in ("thinking", "streaming", "mode", "passed")}), flush=True)
    if not all(row["passed"] for row in cases):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
