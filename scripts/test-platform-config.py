#!/usr/bin/env python3
"""Check architecture dispatch and the Spark cap without launching a model."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
    tmp = Path(folder)
    fake = tmp / 'bin'
    fake.mkdir()
    for name, body in {'docker': 'printf "%s\\n" "$@"',
                       'uname': 'printf "%s\\n" "$TEST_ARCH"'}.items():
        path = fake / name
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)
    model = tmp / 'hf/hub/models--wrldsuksgo2mars--Qwen3.8-Flash-Next-EXL3-K4.25-v1/snapshots/73a050c27b8c488c65acd6d1c74e45ff02be5fab'
    model.mkdir(parents=True)
    (model / 'config.json').write_text('{}')
    env = os.environ | {'PATH': str(fake)+':'+os.environ['PATH'],
                       'HF_CACHE': str(tmp/'hf'), 'RUNTIME_CACHE': str(tmp/'runtime')}
    for key in ('IMAGE','QUANT','GPU_MEMORY_UTILIZATION','PLE_MMAP','VLLM_PLE_MMAP','PLE_MMAP_READAHEAD'):
        env.pop(key, None)
    for arch, image, fraction, cute in (
        ('x86_64','qwen38-rtx:local','0.94','sm_120a'),
        ('aarch64','spark-exl3-qwen3.8-flash-next:local','0.7','sm_121a')):
        env['TEST_ARCH'] = arch
        build = subprocess.check_output(['bash', str(root/'build.sh')], env=env, text=True).splitlines()
        assert image in build and 'CUTE_DSL_ARCH='+cute in build
        args = subprocess.check_output(['bash', str(root/'start.sh')], env=env, text=True).splitlines()
        assert image in args
        assert args[args.index('--gpu-memory-utilization')+1] == fraction
        assert 'VLLM_PLE_MMAP=1' in args
        assert 'VLLM_PLE_MMAP_READAHEAD=2048' in args
        print(json.dumps({'architecture':arch,'image':image,'memory_fraction':fraction,'passed':True}))
    for bad in ('0.71','0.94','1','0','-1','bogus','0.5oops'):
        result = subprocess.run(['bash', str(root/'start.sh')], env=env|{'GPU_MEMORY_UTILIZATION':bad}, capture_output=True)
        assert result.returncode == 2, bad
    for args in (['--gpu-memory-utilization','0.9'], ['--gpu-memory-utilization=0.9']):
        result = subprocess.run(['bash', str(root/'start.sh'), *args], env=env, capture_output=True)
        assert result.returncode == 2
    good = subprocess.check_output(['bash', str(root/'start.sh')], env=env|{'GPU_MEMORY_UTILIZATION':'0.65'}, text=True).splitlines()
    assert good[good.index('--gpu-memory-utilization')+1] == '0.65'
    print(json.dumps({'spark_cap_rejects_invalid_and_cli_bypass':True,'lower_fraction_supported':True,'passed':True}))
