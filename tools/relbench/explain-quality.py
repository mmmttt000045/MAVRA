#!/usr/bin/env python3
"""Why MAVRA's RelBench quality is what it is, from the session records of the Table III runs (read-only).

Per database and task, for MAVRA and No memory (the arms reported as means over runs, MULTI_RUN in paper-stats.py):
  - each run's task mean (cutoffs 1-5) and the range over runs, so a gap can be set against run-to-run spread;
  - the per-cutoff mean over runs, so a gap can be placed at cutoff 1 (exploration) or at the reuse cutoffs;
and for MAVRA's reuse sessions (cutoffs 2-5): how often the stored program was refitted (first try or retry) or lost,
how often the agent's added columns ran clean, and how often they improved validation and replaced the program.
Failed sessions take the reference score of No memory's run 1, as in paper-stats.py.

  python3 tools/relbench/explain-quality.py --out exp/2026-11-12-relbench-quality/explain.json
"""
import argparse
import importlib.util
import json
import os
import statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("paper_stats", HERE / "paper-stats.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


def sessions(folder):
    out = {}
    for f in sorted(Path(folder, "sessions").glob("*.json")):
        if not f.name.endswith(".partial.json"):
            s = json.loads(f.read_text())
            out[(s["task"], s["k"])] = s
    return out


def anatomy(runs):
    c = dict.fromkeys(("reuse", "refit_first_try", "refit_retried", "refit_lost", "additions_tried",
                       "additions_clean", "additions_improved", "kept_program_only"), 0)
    for run in runs:
        for (_, k), s in run.items():
            if k < 2:
                continue
            c["reuse"] += 1
            why = (s.get("target_detail") or {}).get("why") or ""
            tries = (s.get("charged_current_refit") or {}).get("attempt_timeouts") or []
            if "statement timeout" in why or "previous model failed" in why:
                c["refit_lost"] += 1
            elif len(tries) > 1:
                c["refit_retried"] += 1
            else:
                c["refit_first_try"] += 1
            adds = [v for v in s["validations"] if v.get("source") == "agent_additions"]
            clean = [v for v in adds if not v.get("error") and not v.get("leak")]
            improved = [v for v in clean if v.get("improved")]
            c["additions_tried"] += bool(adds)
            c["additions_clean"] += bool(clean)
            c["additions_improved"] += bool(improved)
            c["kept_program_only"] += not improved
    return c


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    report = {}
    for db in ("rel-stack", "rel-trial"):
        ref_run = P.MULTI_RUN["none"][db][0]
        ref = {(t, c["k"]): v.get("test") for c in json.load(open(os.path.join(ref_run, "run.json")))["cutoffs"]
               for t, v in (c.get("reference") or {}).items()}
        arms = {arm: [sessions(f) for f in P.MULTI_RUN[arm][db]] for arm in ("mavra", "none")}
        test = lambda s: s["eval"]["test"] if (s.get("eval") or {}).get("test") is not None else ref[(s["task"], s["k"])]
        tasks = sorted({t for t, _ in arms["none"][0]})
        out = {"tasks": {}, "mavra_reuse": anatomy(arms["mavra"])}
        for t in tasks:
            row = {}
            for arm, runs in arms.items():
                per_run = [st.mean(test(r[(t, k)]) for k in range(1, 6)) for r in runs]
                per_cut = [st.mean(test(r[(t, k)]) for r in runs) for k in range(1, 6)]
                row[arm] = {"run_means": per_run, "mean": st.mean(per_run), "range": [min(per_run), max(per_run)],
                            "per_cutoff": per_cut}
            row["higher_is_better"] = arms["none"][0][(t, 1)]["higher_is_better"]
            out["tasks"][t] = row
        report[db] = out
        print(f"===== {db}   reuse anatomy (MAVRA): {out['mavra_reuse']}")
        for t, row in out["tasks"].items():
            m, n = row["mavra"], row["none"]
            f = (lambda v: f"{v:.4f}") if abs(m["mean"]) < 1 else (lambda v: f"{v:.2f}")
            print(f"{t:16} MAVRA {f(m['mean'])} [{f(m['range'][0])}-{f(m['range'][1])}]  "
                  f"NoMem {f(n['mean'])} [{f(n['range'][0])}-{f(n['range'][1])}]")
            print(f"{'':16} per cutoff MAVRA {' '.join(f(v) for v in m['per_cutoff'])} | NoMem {' '.join(f(v) for v in n['per_cutoff'])}")
    Path(a.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
