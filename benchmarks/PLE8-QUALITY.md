## EXL3 with FP8 PLE: quality-only qualification

`exl3-ple8` uses the same MTP3 setting as EXL3, FP8 KV, and host token embeddings and PLE storage. Its pinned checkpoint is `888306bd3996d6317758c07df50622829259ad17`. No performance matrix was run for this profile; incidental request timings in raw quality receipts are not evidence of performance equivalence.

| Check | Result | Evidence |
|---|---|---|
| Required/named/auto/none tool API | 16/16 | [api-tools.jsonl](exl3-ple8-final/api-tools.jsonl) |
| Seven content contracts | 18/21 | [seven.jsonl](exl3-ple8-final/seven.jsonl) |
| Exact 100-word orchid | 2/5 | [orchid.jsonl](exl3-ple8-final/orchid.jsonl) |
| Numbered-image requests | 1: pass, 4: pass, 16: pass | [vision.json](exl3-ple8-final/vision.json) |
| 8K/240K early/middle/late retrieval | 6/6 | [retrieval.jsonl](exl3-ple8-final/retrieval.jsonl) |
| Full 88-case tool suite | 149/176 points; 85/100 | [tools.md](exl3-ple8-final/tools.md) |
| Hard Mode subset (19 cases) | 32/38 points | [tools.json](exl3-ple8-final/tools.json) |

Orchid word counts: 100, 101, 100, 750, 750.

Content checks use three responses per workload at temperature zero without thinking; orchid uses five responses. Tool-eval-bench uses the same pinned 88-case suite, thinking enabled, one trial and eight parallel cases as the other profiles. These are not controlled perplexity/KL comparisons or a proof of unchanged model quality. The content contracts include literal wording proxies; all failed and partial results remain available for inspection.

Runtime and memory observations: [runtime.json](exl3-ple8-final/runtime.json).

Evaluator-flagged cases:

- TC-33 (Hallucination Resistance): Did not appropriately handle the request for internal data.
- TC-42 (Extra Parameter Injection): Injected extra parameters despite additionalProperties: false.
