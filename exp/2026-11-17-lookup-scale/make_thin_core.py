#!/usr/bin/env python3
"""README 7.2: keep at most PER phrasings per core intent (stated-attribute key) of train_26_clean.jsonl,
matching the added domains' density (gen_train_scale_llm.py writes 6 per intent). Sampling seed 13.
usage: python3 make_thin_core.py train_26_clean.jsonl train_26_thin6.jsonl [PER]"""
import collections
import json
import random
import sys

src, dst = sys.argv[1], sys.argv[2]
per = int(sys.argv[3]) if len(sys.argv) > 3 else 6
qs = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
by = collections.defaultdict(list)
for q in qs:
    by[json.dumps(q["stated"], ensure_ascii=False, sort_keys=True)].append(q)
rng = random.Random(13)
out = []
for k in sorted(by):
    g = by[k]
    out += rng.sample(g, min(per, len(g)))
with open(dst, "w", encoding="utf-8") as f:
    f.writelines(json.dumps(q, ensure_ascii=False) + "\n" for q in out)
print(json.dumps({"intents": len(by), "kept": len(out), "from": len(qs), "absent_kept": sum(not q["gold"] for q in out)}))
