#!/usr/bin/env python3
"""Summary of frozen-program.py: per database, arm and task, the mean gain of the program each session actually used
over the run's cutoff-1 program refitted at that cutoff (positive = better than refitting; MAE sign flipped).
For No memory the gain is what re-exploring at every cutoff buys; for MAVRA it is what refinement adds to the refit.

  python3 tools/relbench/frozen-summary.py [exp/relbench-attribution/frozen-rel-*.json] [--out FILE_OR_DIR]
"""
import argparse
import glob
import json
import os
import statistics as st

HIGHER = {"post-votes": False, "user-badge": True, "user-engagement": True,
          "site-success": False, "study-adverse": False, "study-outcome": True}


def row_is_none(r):
    if "arm" in r:
        return r["arm"] == "none"
    run = str(r.get("run") or "")
    base = os.path.basename(run.replace("\\", "/"))
    return base.startswith("none-") or "/none-" in run


def print_archived(out):
    for db, arms in out.items():
        print(f"== {db} (archived summary)")
        for arm in ("none", "mavra"):
            for t, info in sorted((arms.get(arm) or {}).items()):
                by_k = info.get("by_cutoff") or {}
                print(f"  {arm:5} {t:16} gain {info['mean_gain']:+.4f}  "
                      + " ".join(f"k{k}:{v:+.4f}" for k, v in sorted(by_k.items(), key=lambda x: int(x[0])))
                      + f"  n={info['n']}")


def write_out(out, out_arg):
    if not out_arg:
        return
    target = out_arg if out_arg.endswith(".json") else os.path.join(out_arg, "frozen-summary.json")
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    json.dump(out, open(target, "w", encoding="utf-8"), indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", help="frozen-rel-*.json files (defaults to exp/relbench-attribution/)")
    ap.add_argument("--out", default=None, help="optional output JSON path or directory")
    args = ap.parse_args()
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    attr_dir = os.path.join(root, "exp", "relbench-attribution")
    paths = args.paths or sorted(glob.glob(os.path.join(attr_dir, "frozen-rel-*.json")))
    if not paths:
        summary_path = os.path.join(attr_dir, "frozen-summary.json")
        out = json.load(open(summary_path, encoding="utf-8"))
        print_archived(out)
        write_out(out, args.out)
        return
    out = {}
    for path in paths:
        d = json.load(open(path, encoding="utf-8"))
        if "rows" not in d:
            out.update(d)
            continue
        db = d["template"].split("_")[1]
        errors = [r for r in d["rows"] if "error" in r]
        print(f"== rel-{db}: {len(d['rows'])} rows, {len(errors)} errors, {len(d.get('skipped', []))} skipped programs")
        for arm in ("none", "mavra"):
            for t in sorted({r["task"] for r in d["rows"]}):
                per_k = {}
                for r in d["rows"]:
                    if r["task"] != t or "error" in r or r["fresh_test"] is None or (row_is_none(r) != (arm == "none")):
                        continue
                    g = r["fresh_test"] - r["frozen_test"] if HIGHER[t] else r["frozen_test"] - r["fresh_test"]
                    per_k.setdefault(r["k"], []).append(g)
                if not per_k:
                    continue
                gains = [g for v in per_k.values() for g in v]
                out.setdefault(f"rel-{db}", {}).setdefault(arm, {})[t] = {
                    "mean_gain": st.mean(gains), "by_cutoff": {k: st.mean(v) for k, v in sorted(per_k.items())}, "n": len(gains)}
                print(f"  {arm:5} {t:16} gain {st.mean(gains):+.4f}  "
                      + " ".join(f"k{k}:{st.mean(v):+.4f}" for k, v in sorted(per_k.items())) + f"  n={len(gains)}")
    if not out:
        summary_path = os.path.join(attr_dir, "frozen-summary.json")
        if os.path.exists(summary_path):
            out = json.load(open(summary_path, encoding="utf-8"))
            print_archived(out)
    write_out(out, args.out)


if __name__ == "__main__":
    main()
