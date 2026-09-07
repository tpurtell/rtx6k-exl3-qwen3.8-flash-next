#!/usr/bin/env python3
"""Snapshot resident/anonymous/file-backed memory without disturbing page cache."""
import argparse
import json
from pathlib import Path
import subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('container')
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
inside=r'''
import json,os,re,time
from pathlib import Path
fields=('Size','Rss','Pss','Shared_Clean','Private_Clean','Shared_Dirty','Private_Dirty','Anonymous','Swap')
result={'unix_seconds':time.time(),'processes':[],'meminfo':Path('/proc/meminfo').read_text()}
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit() or int(proc.name)==os.getpid():continue
 try:
  comm=(proc/'comm').read_text().strip()
  rollup=(proc/'smaps_rollup').read_text()
  smaps=(proc/'smaps').read_text()
 except (FileNotFoundError,PermissionError,ProcessLookupError):continue
 maps=[];current=None
 for line in smaps.splitlines():
  if re.match(r'^[0-9a-f]+-[0-9a-f]+ ',line):
   current=None
   if '/huggingface/hub/' in line:
    current={'mapping':line};maps.append(current)
  elif current is not None:
   key,_,value=line.partition(':')
   if key in fields:current[key+'_KiB']=int(value.strip().split()[0])
 result['processes'].append({'pid':int(proc.name),'comm':comm,'smaps_rollup':rollup,
   'checkpoint_mappings':maps,
   'checkpoint_totals_KiB':{k:sum(m.get(k+'_KiB',0) for m in maps) for k in fields}})
print(json.dumps(result))
'''
r=json.loads(subprocess.check_output(['docker','exec','-i',a.container,'python3','-'],input=inside,text=True))
r['container']=a.container
r['storage']=subprocess.check_output(['findmnt','-T',str(Path.home()/'.cache/huggingface'),'-o','SOURCE,FSTYPE,TARGET'],text=True)
r['devices']=subprocess.check_output(['lsblk','-d','-o','NAME,MODEL,SIZE,ROTA','-e','7'],text=True)
a.output.parent.mkdir(parents=True,exist_ok=True)
with a.output.open('x') as out:json.dump(r,out,indent=2);out.write('\n')
