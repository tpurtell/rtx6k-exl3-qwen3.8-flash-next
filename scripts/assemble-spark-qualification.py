#!/usr/bin/env python3
"""Assemble complete single-Spark measurements from identical four-host runtimes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--input', type=Path, required=True, help='Collected host/part directories')
p.add_argument('--output', type=Path, required=True, help='New flat report directory')
a = p.parse_args()
parts = {
    'core': ('ostrich', ['api-tools.jsonl', 'vision.json', 'seven.jsonl', 'orchid.jsonl', 'clients.json']),
    'coding': ('ostrich', ['code-agent.jsonl']),
    'prefill': ('dodo', ['prefill.json']),
    'retrieval': ('dodo', ['retrieval.jsonl']),
    'context': ('emu', ['context.jsonl', 'context-boundary.jsonl']),
    'tools': ('kiwi', ['tools.json', 'tools.md']),
}

def read(path):
    if path.suffix == '.jsonl':
        return [json.loads(line) for line in path.read_text().splitlines() if line]
    return json.loads(path.read_text())

def require(condition, message):
    if not condition:
        raise ValueError(message)

runtimes = {}
for host in ('ostrich', 'dodo', 'emu', 'kiwi'):
    path = a.input / f'runtime-{host}.json'
    r = read(path)
    argv = r['args']
    env = set(r['selected_environment'])
    require(r['host'].split('.')[0] == host, f'Wrong host in {path}')
    require(r['architecture'] in ('aarch64', 'arm64'), f'Non-arm64 runtime: {host}')
    require(float(argv[argv.index('--gpu-memory-utilization')+1]) == 0.7, f'Wrong GPU cap: {host}')
    require('qwen38-exl3' in argv, f'Wrong model alias: {host}')
    require(any('73a050c27b8c488c65acd6d1c74e45ff02be5fab' in value for value in argv),
            f'Wrong checkpoint revision: {host}')
    for option, expected in [('--max-model-len','262144'), ('--max-num-seqs','16'),
                             ('--max-num-batched-tokens','2048'), ('--kv-cache-dtype','fp8')]:
        require(argv[argv.index(option)+1] == expected, f'Wrong {option}: {host}')
    require(json.loads(argv[argv.index('--speculative-config')+1]) == {'method':'mtp','num_speculative_tokens':2}, f'Wrong speculation: {host}')
    require({'VLLM_PLE_MMAP=1','VLLM_PLE_CPU_OFFLOAD=0','VLLM_PLE_MMAP_SERIAL=128',
             'VLLM_PLE_MMAP_READAHEAD=2048','QWEN38_B12X_VOCAB=1','CUTE_DSL_ARCH=sm_121a'} <= env,
            f'Wrong serving defaults: {host}')
    require(any('PLE mmap:' in line and 'attached' in line for line in r['selected_startup_lines']), f'No mmap attachment: {host}')
    require(sum('EXL3 projection-mixed Trellis' in line for line in r['selected_startup_lines']) == 49,
            f'Incomplete target/draft mixed-projection startup evidence: {host}')
    require(any('Prepared B12x BF16 vocabulary projection' in line for line in r['selected_startup_lines']), f'No vocabulary preparation: {host}')
    runtimes[host] = r
reference = runtimes['ostrich']
for host, r in runtimes.items():
    require(r['image_id'] == reference['image_id'], f'Different image on {host}')
    require(r['args'] == reference['args'], f'Different serving arguments on {host}')
    require(set(r['selected_environment']) == set(reference['selected_environment']), f'Different environment on {host}')

sources = {}
for part, (host, names) in parts.items():
    for name in names:
        source = a.input / part / name
        require(source.is_file(), f'Missing {source}')
        sources[name] = (source, host, part)
for name, count in {'seven.jsonl':21,'orchid.jsonl':5,'context.jsonl':18,
                    'context-boundary.jsonl':1,'code-agent.jsonl':18}.items():
    rows = read(sources[name][0])
    require(len([r for r in rows if r.get('timed')]) == count, f'Incomplete {name}')
api = [r for r in read(sources['api-tools.jsonl'][0]) if r.get('record') != 'meta']
require(len(api) == 16 and all(r['passed'] for r in api), 'API constraints failed or incomplete')
retrieval = [r for r in read(sources['retrieval.jsonl'][0]) if r.get('record') != 'meta']
require(len(retrieval) == 6 and all(r['passed'] for r in retrieval), 'Retrieval failed or incomplete')
require(read(sources['vision.json'][0])['passed'], 'Vision checks failed')
tools = read(sources['tools.json'][0])
require(tools['status'] == 'completed' and tools['total_scenarios'] == 88, 'Tool suite incomplete')
require(tools['config']['concurrency'] == 8 and tools['config']['temperature'] == 0,
        'Tool evaluation must retain C8 and temperature zero')
require(tools['config']['extra_params']['chat_template_kwargs']['enable_thinking'] is True,
        'Tool evaluation must use thinking')
for name, count in [('clients.json',5), ('prefill.json',6)]:
    data = read(sources[name][0])
    require(len(data['points']) == count and data['runs_per_point'] == 3, f'Incomplete {name}')
    require(all(len(point['runs']) == 3 for point in data['points']), f'Missing measured runs in {name}')
memory = a.input / 'memory.json'
require(memory.is_file(), 'Missing final memory snapshot')
require(not a.output.exists(), f'Refusing to overwrite {a.output}')
a.output.mkdir(parents=True)
manifest = {'schema':'spark-distributed-qualification-v1',
            'method':'Each measurement uses one TP=1 Spark; independent suites run on four identically configured hosts.',
            'image_id':reference['image_id'], 'files':{}}
for name, (source, host, part) in sources.items():
    shutil.copyfile(source, a.output/name)
    manifest['files'][name] = {'host':host, 'part':part, 'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
for host in runtimes:
    shutil.copyfile(a.input/f'runtime-{host}.json', a.output/f'runtime-{host}.json')
shutil.copyfile(a.input/'runtime-ostrich.json', a.output/'runtime.json')
shutil.copyfile(memory, a.output/'memory.json')
(a.output/'qualification-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'complete':True,'image_id':reference['image_id'],'files':len(sources),'output':str(a.output)}))
