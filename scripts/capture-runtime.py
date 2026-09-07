#!/usr/bin/env python3
"""Save the container configuration and selected model-startup evidence."""
import argparse
import json
import platform
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("container")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
info = json.loads(subprocess.check_output(["docker", "inspect", args.container]))[0]
logs = subprocess.run(["docker", "logs", args.container], capture_output=True,
                      text=True, check=True)
markers = ("PLE offload matched", "Token embedding offloaded", "Model loading took",
           "Worker ready -", "GPU KV cache size:", "Graph capturing finished",
           "B12x vocabulary", "Qwen NVFP4 experts use precise B12x",
           "PLE mmap:", "PLE mmap input prep")
environment_names = {"VLLM_PLE_CPU_OFFLOAD", "VLLM_EXL3_TRELLIS_MIN_M",
                     "VLLM_EXL3_PREFILL_TRELLIS", "VLLM_EXL3_PREFILL_CAPACITY",
                     "QWEN38_B12X_VOCAB", "QWEN38_B12X_NVFP4", "OMP_NUM_THREADS", "CUTE_DSL_ARCH"}
receipt = {
    "container": args.container,
    "host": platform.node(),
    "architecture": platform.machine(),
    "image_id": info["Image"],
    "args": info["Args"],
    "started_at": info["State"]["StartedAt"],
    "device_requests": info["HostConfig"]["DeviceRequests"],
    "selected_environment": [item for item in info["Config"]["Env"]
                             if item.split("=", 1)[0] in environment_names
                             or item.startswith("VLLM_PLE_MMAP") ],
    "selected_startup_lines": [line for line in (logs.stdout + logs.stderr).splitlines()
                               if any(marker in line for marker in markers)],
    "gpu_inventory_csv": subprocess.check_output([
        "nvidia-smi", "--query-gpu=index,name,uuid,driver_version,memory.total,power.limit",
        "--format=csv"], text=True).splitlines(),
}
with args.output.open("x") as destination:
    json.dump(receipt, destination, indent=2)
    destination.write("\n")
