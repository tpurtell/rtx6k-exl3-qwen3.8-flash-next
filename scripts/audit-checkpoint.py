#!/usr/bin/env python3
"""Audit local shard headers and EXL3 per-projection geometry without loading weights."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import struct

parser = argparse.ArgumentParser()
parser.add_argument("model", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
config = json.loads((args.model / "config.json").read_text())
index = json.loads((args.model / "model.safetensors.index.json").read_text())
headers = {}
sizes = Counter()
for shard in sorted(set(index["weight_map"].values())):
    with (args.model / shard).open("rb") as stream:
        length = struct.unpack("<Q", stream.read(8))[0]
        header = json.loads(stream.read(length))
    for name, entry in header.items():
        if name == "__metadata__":
            continue
        assert name not in headers, name
        assert index["weight_map"][name] == shard, name
        headers[name] = entry
        category = "ngram" if any(s in name for s in ("ngram", "ple")) else "other"
        sizes[category] += entry["data_offsets"][1] - entry["data_offsets"][0]
assert set(headers) == set(index["weight_map"])
report = {"revision": args.model.name, "tensor_bytes": dict(sizes),
          "tensors": len(headers), "model_type": config["model_type"],
          "max_position_embeddings": config["text_config"]["max_position_embeddings"]}
quant_path = args.model / "quantize_config.json"
if quant_path.exists():
    quant = json.loads(quant_path.read_text())
    counts = Counter()
    families = {}
    for name, entry in quant["tensor_storage"].items():
        match = re.fullmatch(r"(model.language_model.layers|mtp.layers)\.(\d+)\.mlp.experts\.(\d+)\.(gate_proj|up_proj|down_proj)", name)
        assert match, name
        namespace, layer, expert, projection = match.groups()
        bits = entry["bits_per_weight"]
        assert bits in (4, 5), (name, bits)
        for tensor, spec in entry["stored_tensors"].items():
            assert headers[tensor]["shape"] == spec["shape"], tensor
        assert headers[name + ".trellis"]["shape"][-1] == 16 * bits, name
        counts[f"{namespace}/{projection}/K{bits}"] += 1
        families.setdefault((namespace, layer, expert), {})[projection] = bits
    expected = (config["text_config"]["num_hidden_layers"] + 1) * config["text_config"]["num_experts"]
    assert len(families) == expected
    assert all(len(v) == 3 for v in families.values())
    report["projection_tiers"] = dict(sorted(counts.items()))
    report["experts_with_different_projection_bits"] = sum(len(set(v.values())) > 1 for v in families.values())
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
