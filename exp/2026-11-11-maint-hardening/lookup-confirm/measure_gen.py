#!/usr/bin/env python3
"""Measure tokens per training-data generation call (lookup amortization, review point 6): rerun the
generator's own prompt for 6 sampled intents at PER=15 with the pilot's model settings."""
import json, os, random, statistics, sys
os.chdir("/root/lookup-pilot-20261110"); sys.path.insert(0, ".")
os.environ["PER"] = "15"
import common
common.KEY = open("/root/.deepseek-change-study.key").read().strip()
src = open("gen_train.py").read()
src = src[:src.index("with cf.ThreadPoolExecutor")]
g = {"__name__": "measure"}
exec(src, g)
random.seed(7)
use = []
for t in random.sample(g["targets"], 6):
    out, u = common.chat(g["SYSTEM"], "口径：\n" + g["describe"](t) + "\n\n写 15 个问题。")
    use.append(u); print(u, flush=True)
print(json.dumps({"calls": len(use), "prompt_mean": statistics.mean(x["prompt"] for x in use),
                  "completion_mean": statistics.mean(x["completion"] for x in use),
                  "seconds_mean": statistics.mean(x["seconds"] for x in use), "model": common.MODEL,
                  "extra": common.EXTRA}))
