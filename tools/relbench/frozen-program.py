#!/usr/bin/env python3
"""How much does a cutoff-1 feature program lose at later cutoffs when it is only refitted, never re-explored?

For every given run and task, the final SQL of the cutoff-1 session (the program a reuse session starts from) is
refitted and scored at cutoffs 2-5 exactly as the harness scores a session after a run (evaluate_after_run): views
that keep the rows up to that cutoff's test timestamp, that cutoff's seed tables, the 50k training sample and the fixed
LightGBM. No model calls. The output pairs each frozen score with the score of the program the run's own session
produced at that cutoff, so `fresh - frozen` is what re-exploring (No memory) or refining (MAVRA) adds over refitting.

  python3 tools/relbench/frozen-program.py --runs results/relbench-main/none-rel-trial-r1 ... \\
      --data results/relbench-data/rel-trial --prep results/relbench-data/rel-trial-prep --template relbench_trial_t1 \\
      --out results/frozen-rel-trial.json
"""
import argparse
import concurrent.futures as cf
import json
from pathlib import Path

import pandas as pd
import psycopg

import harness as H


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", nargs="+", type=Path, required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--prep", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    programs = {}  # (run, task) -> cutoff-1 final SQL; fresh scores per cutoff
    fresh = {}
    skipped = []
    for run in a.runs:
        for path in sorted((run / "sessions").glob("*.json")):
            if path.name.endswith(".partial.json"):
                continue
            s = json.loads(path.read_text())
            fresh[(str(run), s["task"], s["k"])] = (s.get("eval") or {}).get("test")
            if s["k"] == 1:
                if not s.get("final_sql") or (s.get("audit") or {}).get("result") != "clean":
                    skipped.append({"run": str(run), "task": s["task"], "why": "cutoff-1 session has no clean final SQL"})
                    continue
                programs[(str(run), s["task"])] = s["final_sql"]
    settings = json.loads((a.runs[0] / "run.json").read_text())["settings"]
    config = argparse.Namespace(arm="none", run=0, data=a.data, prep=a.prep, template=a.template,
                                out=str(a.out.parent / (a.out.stem + "-work")), tasks=None, cutoffs=None,
                                targets_from=None, reasoning_effort=settings["reasoning_effort"], eval_now=False,
                                llm=settings["llm"])
    Path(config.out).mkdir(parents=True, exist_ok=True)
    run = H.Run(config)
    cuts = [c["test_timestamp"] for c in next(iter(run.tasks.values()))["cutoffs"]]
    rows = []
    H.create_run_db(run.url_admin, a.template, run.db_name)
    try:
        run.append(pd.Timestamp(cuts[0]), pd.Timestamp(cuts[-1]))
        for k in range(2, len(cuts) + 1):
            schema = f"frozen_k{k}"
            seeds = run.seed_tables(k)
            with psycopg.connect(run.url, autocommit=True) as con:
                con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
                con.execute(f"CREATE SCHEMA {schema}")
                for name, spec in run.manifest["tables"].items():
                    tc = spec.get("time_col")
                    cond = f" WHERE {tc.lower()} <= '{pd.Timestamp(cuts[k - 1])}'" if tc else ""
                    con.execute(f"CREATE VIEW {schema}.{name.lower()} AS SELECT * FROM public.{name.lower()}{cond}")

            def score(item):
                (rname, task), sql = item
                try:
                    r = run.evaluate(task, k, H.in_schema(sql, schema), seeds[task], search_path=f"{schema}, public")
                    return {"run": rname, "task": task, "k": k, "frozen_test": r["test"], "frozen_val": r["val"],
                            "fresh_test": fresh.get((rname, task, k)), "n_features": r["n_features"]}
                except Exception as err:  # noqa: BLE001 - recorded, never dropped
                    return {"run": rname, "task": task, "k": k, "error": str(err)[:300],
                            "fresh_test": fresh.get((rname, task, k))}

            try:
                with cf.ThreadPoolExecutor(4) as ex:
                    for r in ex.map(score, sorted(programs.items())):
                        rows.append(r)
                        H.log(f"{r['task']} k{k} {Path(r['run']).name}: frozen={r.get('frozen_test')} fresh={r['fresh_test']}")
            finally:
                with psycopg.connect(run.url, autocommit=True) as con:
                    con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    finally:
        H.drop_db(run.url_admin, run.db_name)
    a.out.write_text(json.dumps({"runs": [str(r) for r in a.runs], "template": a.template, "rows": rows, "skipped": skipped}, indent=1))


if __name__ == "__main__":
    main()
