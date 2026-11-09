#!/usr/bin/env python3
"""Statistics for the structural-variation population study (README.md; written before the formal runs).

usage: analyse.py --runs results/structural-reuse-20261109 [--json-out FILE] [--md-out FILE]

Records are the population cells (cell-pop-*.json) of metric-bench --question-set v3, phase pop-v1 only. Cost of a
task as in tools/population-stats.py: tokens = session input + output tokens plus the extraction's tokens when the
memory learned from that session; seconds = the session's wall time. Provider failures (outcome "error") are not scored
and add no cost.

Groups of questions: control (P1: a new month only), structural (T1 category filter, T2 store-city difference,
T3 top category, T4 top weekday), split into questions whose dimension table is already in the definition and those
that need a new join (NEW_JOIN, fixed in the README). Per method: pooled over runs, with each run's value and the
range. MAVRA mechanism counts: structural sessions with a dimension ask of run_metric that was served, where the new
join came from (in the definition / reused / explored), and rejections. TeCoD: selection method per session.
"""
import argparse
import collections
import glob
import json
import os
import re

METHODS = ["middle-alone", "traj-global", "traj-push", "paper-tecod", "metric-global-snap", "metric-global-push"]
NAMES = {"middle-alone": "No memory", "traj-global": "Example retrieval", "traj-push": "Example retrieval (delivered)",
         "paper-tecod": "TeCoD", "metric-global-snap": "MAVRA (lookup)", "metric-global-push": "MAVRA (delivered)"}
FORMS = ["P1", "T1", "T2", "T3", "T4"]
NEW_JOIN = {"M1-T2", "M3-T1", "M3-T3", "M4-T1", "M4-T3", "M5-T1", "M5-T2", "M5-T3"}
DIM_KINDS = {"slice", "slice_diff", "rank_by"}


def load(root):
    cells = []
    for f in sorted(glob.glob(os.path.join(root, "**", "cell-pop-*.json"), recursive=True)):
        d = json.load(open(f, encoding="utf-8"))
        if d.get("population"):
            cells.append(d)
    return cells


def cost(r):
    tok = r["run"]["input_tokens"] + r["run"]["output_tokens"]
    l = r.get("learning") or {}
    ex = l.get("extraction") or {}
    return tok + ex.get("input_tokens", 0) + ex.get("output_tokens", 0), r["run"]["seconds"]


def form(r):
    return r["task"].split("-", 1)[1] if "-" in r["task"] else r["task"]


def dimension_calls(r):
    """run_metric calls with a dimension ask in the session: (served, join source or rejection reason)."""
    out = []
    for e in r["run"].get("transcript") or []:
        if e.get("kind", "tool") != "tool" or e.get("tool") != "run_metric":
            continue
        ask = (e.get("input") or {}).get("ask") or {}
        if ask.get("kind") not in DIM_KINDS:
            continue
        try:
            v = json.loads(e.get("output") or "{}")
        except (ValueError, TypeError):
            v = {}
        if not isinstance(v, dict):
            v = {}
        served = not v.get("rejected") and e.get("status") != "error" and "error" not in v
        src = (v.get("dimension") or {}).get("join") if served else (v.get("reason") or e.get("output", ""))[:120]
        out.append((served, src))
    return out


def summarize(rows):
    rows = [r for r in rows if r["outcome"] != "error"]
    n = len(rows)
    if not n:
        return {"n": 0}
    c = [cost(r) for r in rows]
    return {"n": n, "correct": sum(r["outcome"] == "correct" for r in rows), "wrong": sum(r["outcome"] == "wrong" for r in rows),
            "clarify": sum(r["outcome"] == "clarify" for r in rows),
            "acc": sum(r["outcome"] == "correct" for r in rows) / n,
            "tok": sum(x[0] for x in c) / n, "s": sum(x[1] for x in c) / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--json-out")
    ap.add_argument("--md-out")
    a = ap.parse_args()
    cells = load(a.runs)
    by = collections.defaultdict(dict)
    for d in cells:
        by[d["mode"]][d["repeat"]] = d
    out = {"runs_dir": a.runs, "methods": {}}
    for m in METHODS:
        if m not in by:
            continue
        runs = sorted(by[m])
        recs = {k: [r for r in by[m][k]["records"] if r["phase"] == "pop-v1"] for k in runs}
        allr = [r for k in runs for r in recs[k]]
        errors = sum(r["outcome"] == "error" for r in allr)
        groups = {
            "control": lambda r: form(r) == "P1",
            "structural": lambda r: form(r).startswith("T"),
            "structural_in_definition": lambda r: form(r).startswith("T") and r["task"] not in NEW_JOIN,
            "structural_new_join": lambda r: r["task"] in NEW_JOIN,
            "learning": lambda r: form(r).startswith("L"),
            **{f: (lambda f: lambda r: form(r) == f)(f) for f in FORMS},
        }
        res = {"runs": runs, "errors_not_scored": errors, "groups": {}}
        for g, keep in groups.items():
            res["groups"][g] = {"pooled": summarize([r for r in allr if keep(r)]),
                                "per_run": {k: summarize([r for r in recs[k] if keep(r)]) for k in runs}}
        res["cumulative"] = {}
        for k in runs:
            c = [cost(r) for r in recs[k] if r["outcome"] != "error"]
            res["cumulative"][k] = {"sessions": len(c), "tok": sum(x[0] for x in c), "s": sum(x[1] for x in c),
                                    "correct": sum(r["outcome"] == "correct" for r in recs[k])}
        if m in ("metric-global-snap", "metric-global-push"):
            st = [r for r in allr if form(r).startswith("T") and r["outcome"] != "error"]
            calls = [(r, dimension_calls(r)) for r in st]
            src = collections.Counter(s for _, cs in calls for ok, s in cs if ok)
            res["mechanism"] = {
                "structural_sessions": len(st),
                "with_served_dimension_ask": sum(any(ok for ok, _ in cs) for _, cs in calls),
                "served_dimension_asks": sum(ok for _, cs in calls for ok, _ in cs),
                "rejected_dimension_asks": sum(not ok for _, cs in calls for ok, _ in cs),
                "join_source": dict(src),
                "rejections": [s for _, cs in calls for ok, s in cs if not ok][:20],
                "definitions_published": {k: sum(1 for e in (by[m][k].get("metric_report") or {}).get("entries", [])
                                                 if e.get("status") == "valid" or e.get("status") == "Valid") for k in runs},
            }
        if m == "paper-tecod":
            res["selection"] = dict(collections.Counter(
                ((r.get("memory_lookup") or {}).get("tecod") or {}).get("method", "none") for r in allr if r["outcome"] != "error"))
        out["methods"][m] = res
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if a.json_out:
        open(a.json_out, "w").write(text)
    lines = ["| Method | Runs | Control acc | Control tok | Structural acc | Structural tok | Structural s | New-join acc | Cum. tok (M) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for m, res in out["methods"].items():
        g = res["groups"]
        cum = [v["tok"] / 1e6 for v in res["cumulative"].values()]
        f = lambda x, k, p=1: (f"{x[k] * 100:.1f}%" if k == "acc" else f"{x[k] / 1e3:.1f}k" if k == "tok" else f"{x[k]:.1f}") if x.get("n") else "-"
        lines.append(f"| {NAMES[m]} | {len(res['runs'])} | {f(g['control']['pooled'], 'acc')} | {f(g['control']['pooled'], 'tok')} | "
                     f"{f(g['structural']['pooled'], 'acc')} | {f(g['structural']['pooled'], 'tok')} | {f(g['structural']['pooled'], 's')} | "
                     f"{f(g['structural_new_join']['pooled'], 'acc')} | {sum(cum) / len(cum):.2f} ({min(cum):.2f}–{max(cum):.2f}) |")
    md = "\n".join(lines) + "\n"
    if a.md_out:
        open(a.md_out, "w").write(md)
    print(md)


if __name__ == "__main__":
    main()
