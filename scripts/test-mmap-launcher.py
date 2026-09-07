#!/usr/bin/env python3
"""Exercise all profile/mmap launcher combinations with an inert Docker command."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
profiles={}
for name,body in re.findall(r'^  ([a-z0-9-]+)\)\n(.*?)    ;;',(root/'model-profiles.sh').read_text(),re.M|re.S):
    profiles[name]=tuple(re.search(r'^    '+k+r'=(.+)$',body,re.M)[1] for k in ('MODEL_REPO','MODEL_REVISION'))
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp)
    fake=tmp/'bin';fake.mkdir()
    docker=fake/'docker';docker.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n');docker.chmod(0o755)
    for name,(repo,revision) in profiles.items():
        model=tmp/'hf/hub'/('models--'+repo.replace('/','--'))/'snapshots'/revision
        model.mkdir(parents=True);(model/'config.json').write_text('{}')
        for mode in (0,1):
            env=os.environ|{'PATH':str(fake)+':'+os.environ['PATH'],'HF_CACHE':str(tmp/'hf'),
                'RUNTIME_CACHE':str(tmp/'runtime'),'QUANT':name,'PLE_MMAP':str(mode)}
            args=subprocess.check_output(['bash',str(root/'start.sh')],env=env,text=True).splitlines()
            assert f'VLLM_PLE_MMAP={mode}' in args
            assert f'VLLM_PLE_CPU_OFFLOAD={1-mode}' in args
            assert 'qwen38-'+name in args
            assert '--tensor-parallel-size' in args and '--kv-cache-dtype' in args
            print(json.dumps({'profile':name,'mmap':bool(mode),'passed':True}))
