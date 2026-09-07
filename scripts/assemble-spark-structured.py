#!/usr/bin/env python3
"""Validate corrected structured-output evidence without replacing performance receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--input',type=Path,required=True)
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--equivalence',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()

def read(path):
    if path.suffix=='.jsonl':return [json.loads(l) for l in path.read_text().splitlines() if l]
    return json.loads(path.read_text())

def require(ok,message):
    if not ok:raise ValueError(message)

baseline=read(a.baseline/'runtime.json')
equivalence=read(a.equivalence)
old=equivalence['original_rootfs_layers'];new=equivalence['corrected_rootfs_layers']
require(new[:len(old)]==old and len(new)>len(old),'Numerical base layers changed')
require(equivalence['old_image_id']==baseline['image_id'],'Wrong performance baseline')
runtimes={role:read(a.input/role/'runtime.json') for role in ('canary','tools')}
for role,r in runtimes.items():
    require(r['image_id']==equivalence['new_image_id'],f'Wrong corrected image: {role}')
    require(r['args']==baseline['args'],f'Serving arguments changed: {role}')
    require(set(r['selected_environment'])==set(baseline['selected_environment']),f'Environment changed: {role}')
api=[r for r in read(a.input/'canary/api-tools.jsonl') if r.get('record')=='measurement']
require(len(api)==16 and all(r['passed'] for r in api),'API checks failed or incomplete')
canary=read(a.input/'canary/json-reasoning.json')
require(canary['status']=='PASS' and canary['completed_cases']==29 and canary['failed_cases']==0,
        'JSON/reasoning/EOS canary failed or incomplete')
require(canary['speculation_active'],'Speculation was not exercised')
tools=read(a.input/'tools/tools.json')
require(tools['status']=='completed' and tools['total_scenarios']==88,'Tool suite incomplete')
require(len(tools['scores']['scenario_results'])==88,'Missing tool results')
require(tools['config']['concurrency']==8 and tools['config']['temperature']==0,'Tool protocol changed')
require(tools['config']['error_rate']==0,'Tool request errors')
require(tools['config']['extra_params']['chat_template_kwargs']['enable_thinking'] is True,'Tool thinking disabled')
diagnostics=read(a.input/'server-diagnostics.json')
require(set(diagnostics)=={'ostrich','kiwi'},'Missing server log audit')
for host,lines in diagnostics.items():
    require(not any(any(needle in line for needle in ('Failed to advance FSM','Unexpected: grammar',
            'Terminating request','AssertionError','Traceback','CUDA error','OutOfMemory')) for line in lines),
            f'Runtime errors remain on {host}')
require(not a.output.exists(),'Refusing to overwrite corrected qualification')
a.output.mkdir(parents=True)
files={
    'api-tools.jsonl':a.input/'canary/api-tools.jsonl',
    'json-reasoning.json':a.input/'canary/json-reasoning.json',
    'tools.json':a.input/'tools/tools.json',
    'tools.md':a.input/'tools/tools.md',
    'runtime.json':a.input/'canary/runtime.json',
    'runtime-canary.json':a.input/'canary/runtime.json',
    'runtime-tools.json':a.input/'tools/runtime.json',
    'server-diagnostics.json':a.input/'server-diagnostics.json',
}
manifest={'schema':'spark-structured-qualification-v1','status':'PASS',
          'corrected_image_id':equivalence['new_image_id'],'performance_image_id':baseline['image_id'],
          'scope':'Corrected API/tool/JSON/reasoning/EOS qualification; numerical performance and other functional receipts remain unchanged.',
          'hosts':{role:r['host'] for role,r in runtimes.items()},'files':{},
          'equivalence':str(a.equivalence),'equivalence_sha256':hashlib.sha256(a.equivalence.read_bytes()).hexdigest()}
for name,source in files.items():
    shutil.copyfile(source,a.output/name)
    manifest['files'][name]={'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
(a.output/'qualification.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'status':'PASS','image_id':manifest['corrected_image_id'],'files':len(files)}))
