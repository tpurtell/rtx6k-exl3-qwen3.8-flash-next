#!/usr/bin/env python3
"""Report the extra FP8-PLE checkpoint's quality-only qualification."""
import argparse
import json
import os
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--results', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
def read(name):
    path = a.results / name
    if path.suffix == '.jsonl':
        return [json.loads(l) for l in path.read_text().splitlines() if l]
    return json.loads(path.read_text())
def rows(name):
    return [r for r in read(name) if r.get('record') == 'measurement' and r.get('timed', True)]
def link(name):
    return f'[{name}]({os.path.relpath(a.results / name, a.output.parent)})'
api = rows('api-tools.jsonl')
seven = rows('seven.jsonl')
orchid = rows('orchid.jsonl')
retrieval = rows('retrieval.jsonl')
vision = read('vision.json')['supported_image_counts']
tool = read('tools.json')
assert len(api) == 16 and len(seven) == 21 and len(orchid) == 5 and len(retrieval) == 6
assert tool['status'] == 'completed' and tool['total_scenarios'] == 88
score = tool['scores']
hard = next(c for c in score['category_scores'] if c['label'] == 'Hard Mode')
lines = ['## EXL3 with FP8 PLE: quality-only qualification', '',
    '`exl3-ple8` uses the same MTP3 setting as EXL3, FP8 KV, and host token embeddings '
    'and PLE storage. Its pinned checkpoint is `888306bd3996d6317758c07df50622829259ad17`. '
    'No performance matrix was run for this profile; incidental request timings in '
    'raw quality receipts are not evidence of performance equivalence.', '',
    '| Check | Result | Evidence |', '|---|---|---|',
    f"| Required/named/auto/none tool API | {sum(r['passed'] for r in api)}/16 | {link('api-tools.jsonl')} |",
    f"| Seven content contracts | {sum(r['contract']['quality_contract_passed'] for r in seven)}/21 | {link('seven.jsonl')} |",
    f"| Exact 100-word orchid | {sum(r['contract']['pass'] for r in orchid)}/5 | {link('orchid.jsonl')} |",
    f"| Numbered-image requests | {', '.join(str(n)+': '+('pass' if vision[str(n)]['passed'] else 'fail') for n in (1,4,16))} | {link('vision.json')} |",
    f"| 8K/240K early/middle/late retrieval | {sum(r['passed'] for r in retrieval)}/6 | {link('retrieval.jsonl')} |",
    f"| Full 88-case tool suite | {score['total_points']}/{score['max_points']} points; {score['final_score']}/100 | {link('tools.md')} |",
    f"| Hard Mode subset (19 cases) | {hard['earned']}/{hard['max']} points | {link('tools.json')} |", '',
    'Orchid word counts: '+', '.join(str(r['contract']['occurrences']) for r in orchid)+'.', '',
    'Content checks use three responses per workload at temperature zero without thinking; '
    'orchid uses five responses. Tool-eval-bench uses the same pinned 88-case suite, '
    'thinking enabled, one trial and eight parallel cases as the other profiles. '
    'These are not controlled perplexity/KL comparisons or a proof of unchanged model quality. '
    'The content contracts include literal wording proxies; all failed and partial results '
    'remain available for inspection.', '', 'Runtime and memory observations: '+link('runtime.json')+'.', '']
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text('\n'.join(lines))
