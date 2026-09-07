#!/usr/bin/env python3
"""Verify ordered image reading and, optionally, a configured API image limit."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
import struct
import urllib.error
import urllib.request
import zlib
from pathlib import Path


GLYPHS = {
    "0": ("11111", "10001", "10011", "10101", "11001", "10001", "11111"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("11110", "00001", "00001", "11110", "10000", "10000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("10010", "10010", "10010", "11111", "00010", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01111", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "11110"),
}


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
    )


def numbered_png(number: int, size: int = 448, scale: int = 35) -> bytes:
    pixels = bytearray([255]) * (size * size * 3)
    digits = str(number)
    glyph_width = 5 * scale
    gap = scale
    text_width = len(digits) * glyph_width + (len(digits) - 1) * gap
    x0 = (size - text_width) // 2
    y0 = (size - 7 * scale) // 2
    for digit_index, digit in enumerate(digits):
        glyph = GLYPHS[digit]
        digit_x = x0 + digit_index * (glyph_width + gap)
        for row, pattern in enumerate(glyph):
            for column, active in enumerate(pattern):
                if active != "1":
                    continue
                for y in range(y0 + row * scale, y0 + (row + 1) * scale):
                    start = (y * size + digit_x + column * scale) * 3
                    end = start + scale * 3
                    pixels[start:end] = b"\0" * (scale * 3)
    scanlines = b"".join(
        b"\0" + pixels[row * size * 3 : (row + 1) * size * 3]
        for row in range(size)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(scanlines, 9))
        + _chunk(b"IEND", b"")
    )


def image_url(number: int) -> str:
    payload = base64.b64encode(numbered_png(number)).decode("ascii")
    return "data:image/png;base64," + payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument(
        "--model", default="qwen38-exl3"
    )
    parser.add_argument("--image-counts", type=int, nargs="+", default=[1, 4, 16])
    parser.add_argument("--image-limit", type=int, help="Test rejection above an explicitly configured limit")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(n < 1 or n > 99 for n in args.image_counts):
        parser.error("image counts must be between 1 and 99")
    if args.image_limit is not None and not (1 <= args.image_limit < 99):
        parser.error("image limit must be between 1 and 98")

    def request(images: int) -> tuple[int, dict]:
        content: list[dict] = [
            {
                "type": "text",
                "text": (
                    f"These {images} images each contain one large decimal number. "
                    "Read every image in order and return only the comma-separated "
                    "numbers, with no prose."
                ),
            }
        ]
        content.extend(
            {"type": "image_url", "image_url": {"url": image_url(value)}}
            for value in range(1, images + 1)
        )
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": content}],
            "chat_template_kwargs": {"enable_thinking": False},
            "temperature": 0,
            "max_tokens": 128,
        }
        req = urllib.request.Request(
            args.base_url.rstrip("/") + "/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=args.timeout) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8", errors="replace"))

    supported = {}
    for image_count in args.image_counts:
        status, body = request(image_count)
        if status != 200:
            supported[str(image_count)] = {"passed": False, "status": status, "response": body}
            continue
        content = body["choices"][0]["message"].get("content") or ""
        observed = [int(value) for value in re.findall(r"\d+", content)]
        expected = list(range(1, image_count + 1))
        supported[str(image_count)] = {
            "passed": observed == expected,
            "status": status,
            "expected": expected,
            "observed": observed,
            "response": content,
            "usage": body.get("usage"),
        }

    overflow = None
    if args.image_limit is not None:
        overflow_status, overflow_body = request(args.image_limit + 1)
        overflow_text = json.dumps(overflow_body, ensure_ascii=False)
        overflow = {
            "passed": overflow_status == 400 and str(args.image_limit) in overflow_text,
            "status": overflow_status,
            "response": overflow_body,
        }
    report = {
        "schema": "qwen38-vllm-vision.v1",
        "model": args.model,
        "supported_image_counts": supported,
        "configured_image_limit": args.image_limit,
        "overflow_rejected": overflow,
        "passed": all(item["passed"] for item in supported.values())
        and (overflow is None or overflow["passed"]),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
