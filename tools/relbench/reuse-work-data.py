#!/usr/bin/env python3
"""Data of the paper's tool-call figure (reuse-work) from the five-cutoff RelBench study, the runs of Table III.

Per database and LLM agent method: the agent's tool calls per reuse session (cutoffs 2-5, every session, failures
included), split into schema inspection, SQL probes, validation, memory tools and submission (the categories the
harness records per call). FeatPilot has no agent and no tool calls, so it is not part of this figure.

  python3 tools/relbench/reuse-work-data.py --out exp/2026-10-20-relbench/reuse-work-data.json
"""
import argparse
import glob
import json
import os

RUNS = {"rel-stack": "results/relbench-pilot3/{arm}-rel-stack-r1", "rel-trial": "results/relbench-main/{arm}-rel-trial-r1"}
ARMS = ("none", "ace", "awm", "gmemory", "tecod", "mavra")
KINDS = ("schema", "probe", "validate", "memory", "submit")
RUN_FOLDER = {"mavra": "mavra-push"}  # as in paper-stats.py: MAVRA's 11-07 version


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    work = {}
    for db, pattern in RUNS.items():
        for arm in ARMS:
            folder = pattern.format(arm=RUN_FOLDER.get(arm, arm))
            run = json.load(open(os.path.join(folder, "run.json")))
            if not run.get("finished") or run.get("error"):
                raise SystemExit(f"{folder}: run not finished")
            sessions = [json.load(open(f)) for f in glob.glob(os.path.join(folder, "sessions", "*.json"))
                        if not f.endswith(".partial.json")]
            late = [s for s in sessions if s["k"] >= 2]
            if len(late) != 12:
                raise SystemExit(f"{folder}: {len(late)} reuse sessions, expected 12")
            row = {k: sum(s["totals"]["tool_calls_by_category"].get(k, 0) for s in late) / len(late) for k in KINDS}
            row["llm_calls"] = sum(s["totals"]["llm_calls"] for s in late) / len(late)
            row["sessions"] = len(late)
            work.setdefault(db, {})[arm] = row
    with open(a.out, "w") as f:
        json.dump({"scope": "five-cutoff RelBench study (Table III runs), reuse sessions at cutoffs 2-5, failures included",
                   "work": work}, f, indent=1)
    print(json.dumps(work, indent=1))


if __name__ == "__main__":
    main()
