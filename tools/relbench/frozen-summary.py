#!/usr/bin/env python3
"""Summary of frozen-program.py: per database, arm and task, the mean gain of the program each session actually used
over the run's cutoff-1 program refitted at that cutoff (positive = better than refitting; MAE sign flipped).
For No memory the gain is what re-exploring at every cutoff buys; for MAVRA it is what refinement adds to the refit.

  python3 tools/relbench/frozen-summary.py exp/2026-11-12-relbench-quality/frozen-rel-*.json
"""
import json
import statistics as st
import sys

HIGHER = {"post-votes": False, "user-badge": True, "user-engagement": True,
          "site-success": False, "study-adverse": False, "study-outcome": True}

out = {}
for path in sys.argv[1:]:
    d = json.load(open(path))
    db = d["template"].split("_")[1]
    errors = [r for r in d["rows"] if "error" in r]
    print(f"== rel-{db}: {len(d['rows'])} rows, {len(errors)} errors, {len(d['skipped'])} skipped programs")
    for arm in ("none", "mavra"):
        for t in sorted({r["task"] for r in d["rows"]}):
            per_k = {}
            for r in d["rows"]:
                if r["task"] != t or "error" in r or r["fresh_test"] is None or (("/none-" in r["run"]) != (arm == "none")):
                    continue
                g = r["fresh_test"] - r["frozen_test"] if HIGHER[t] else r["frozen_test"] - r["fresh_test"]
                per_k.setdefault(r["k"], []).append(g)
            gains = [g for v in per_k.values() for g in v]
            out.setdefault(f"rel-{db}", {}).setdefault(arm, {})[t] = {
                "mean_gain": st.mean(gains), "by_cutoff": {k: st.mean(v) for k, v in sorted(per_k.items())}, "n": len(gains)}
            print(f"  {arm:5} {t:16} gain {st.mean(gains):+.4f}  " + " ".join(f"k{k}:{st.mean(v):+.4f}" for k, v in sorted(per_k.items())) + f"  n={len(gains)}")
json.dump(out, open("exp/2026-11-12-relbench-quality/frozen-summary.json", "w"), indent=1)
