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
REFUSED_KIND = {"run_sql": "probe", "list_tables": "schema", "describe_table": "schema", "join_path": "schema",
                "check_join": "schema", "submit": "submit"}
# as in paper-stats.py (11-12): MAVRA is the mean over three runs of arm mavra-retry (v10), the others their run 1
MULTI_RUN = {"mavra": [f"results/quality-20261112-v10/mavra-retry-{{db}}-r{i}" for i in (1, 2, 3)],
             "none": [None] + [f"results/quality-20261112-v10-none/none-{{db}}-r{i}" for i in (2, 3)]}  # None: run 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    work = {}
    for db, pattern in RUNS.items():
        for arm in ARMS:
            folders = ([pattern.format(arm=arm) if f is None else f.format(db=db) for f in MULTI_RUN[arm]]
                       if arm in MULTI_RUN else [pattern.format(arm=arm)])
            rows = []
            for folder in folders:
                run = json.load(open(os.path.join(folder, "run.json")))
                if not run.get("finished") or run.get("error"):
                    raise SystemExit(f"{folder}: run not finished")
                sessions = [json.load(open(f)) for f in glob.glob(os.path.join(folder, "sessions", "*.json"))
                            if not f.endswith(".partial.json")]
                late = [s for s in sessions if s["k"] >= 2]
                if len(late) != 12:
                    raise SystemExit(f"{folder}: {len(late)} reuse sessions, expected 12")
                # a call the harness refused at that step (category "other": MAVRA's reuse offers only some tools per
                # step) or a call of a tool that does not exist (no category) still counts in the table's tool calls,
                # so it is drawn under the kind of the tool it asked for (unknown names as SQL probes)
                counts = {k: sum(s["totals"]["tool_calls_by_category"].get(k, 0) for s in late) for k in KINDS}
                for s in late:
                    for x in s["tools"]:
                        if x.get("category") in ("other", None):
                            counts[REFUSED_KIND.get(x["name"], "probe")] += 1
                if sum(counts.values()) != sum(s["totals"]["tool_calls"] for s in late):
                    raise SystemExit(f"{folder}: tool calls by kind do not add up to the table's tool calls")
                row = {k: v / len(late) for k, v in counts.items()}
                row["llm_calls"] = sum(s["totals"]["llm_calls"] for s in late) / len(late)
                rows.append(row)
            row = {k: sum(r[k] for r in rows) / len(rows) for k in rows[0]}  # mean over runs (one run for most arms)
            row["sessions"], row["runs"] = 12, len(rows)
            work.setdefault(db, {})[arm] = row
    with open(a.out, "w") as f:
        json.dump({"scope": "five-cutoff RelBench study (Table III runs), reuse sessions at cutoffs 2-5, failures included; MAVRA mean over three runs",
                   "work": work}, f, indent=1)
    print(json.dumps(work, indent=1))


if __name__ == "__main__":
    main()
