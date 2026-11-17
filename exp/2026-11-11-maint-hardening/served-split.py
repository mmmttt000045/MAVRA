#!/usr/bin/env python3
"""Serving-vs-withholding & controlled template-invalidation decomposition (P1-2 + P1-3b).

Splits every scored change-study answer by whether the agent answered from a served definition (`y_j = 1`, i.e., at least
one declared metric reference executed without middleware rejection) or via fallback (`y_j = 0`, definition withheld,
unavailable, or unlearned so the agent explored SQL on its own or requested clarification).

Supports multiple cell directories so `mavra`/`recheck` (2026-11-11) and `template_schema`/`template_revoke` (2026-11-17)
are analyzed identically on the frozen 276-question banks (3 runs = 828 scored answers per arm).

Usage:
  python3 served-split.py CELLS_DIR [EXTRA_CELLS_DIR ...]
"""
import collections
import glob
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P = json.loads((ROOT / "exp/2026-11-01-change-study/protocol.json").read_text(encoding="utf-8"))
INV = {c: g for g, cs in P["groups"].items() for c in cs}
ARMS = ["mavra", "recheck", "template_schema", "template_revoke"]
DIRS = sys.argv[1:]
if not DIRS:
    raise SystemExit("Usage: served-split.py CELLS_DIR [EXTRA_CELLS_DIR ...]")


def is_served(r):
    mu = r.get("metric_use") or {}
    declared = mu.get("declared") or []
    rej_refs = sum(len(x.get("metrics") or []) for x in (r.get("rejections") or []))
    return (len(declared) - rej_refs) > 0


def tok_of(r):
    run = r.get("run") or {}
    pm = r.get("published_memory") or {}
    return (run.get("input_tokens") or 0) + (run.get("output_tokens") or 0) + (pm.get("input_tokens") or 0) + (pm.get("output_tokens") or 0)


def check_ms_of(r):
    bk = ((r.get("db") or {}).get("by_kind")) or {}
    ms = 0.0
    for k in ("check", "metric", "Check", "Metric"):
        v = bk.get(k)
        if isinstance(v, dict):
            ms += float(v.get("ms") or v.get("db_ms") or 0.0)
        elif isinstance(v, (int, float)):
            ms += float(v)
    return ms


raw_counts = {}
arm_summary = {}

for arm in ARMS:
    files = []
    for d in DIRS:
        files.extend(sorted(glob.glob(f"{d}/*-r*-{arm}/metric-*/task-journal.jsonl")))
    if not files:
        continue
    c = collections.Counter()
    rows = []
    runs_seen = set()
    for f in files:
        m_run = re.search(r"-r(\d+)-", f)
        if m_run:
            runs_seen.add(int(m_run.group(1)))
        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            if r["phase"] == "learn":
                continue
            used = is_served(r)
            grp = INV.get(r["phase"], "holdout")
            c[f'{grp}|{"def" if used else "own"}|{r["outcome"]}'] += 1
            rows.append((grp, used, r))
    raw_counts[arm] = dict(c)
    n_runs = max(1, len(runs_seen))

    def summarize_scope(sel_rows):
        n = len(sel_rows)
        served_r = [x for x in sel_rows if x[1]]
        own_r = [x for x in sel_rows if not x[1]]
        s_n = len(served_r)
        o_n = len(own_r)
        s_ok = sum(x[2]["outcome"] == "correct" for x in served_r)
        s_wr = sum(x[2]["outcome"] == "wrong" for x in served_r)
        o_ok = sum(x[2]["outcome"] == "correct" for x in own_r)
        o_cl = sum(x[2]["outcome"] == "clarify" for x in own_r)
        o_wr = sum(x[2]["outcome"] == "wrong" for x in own_r)
        tot_ok = sum(x[2]["outcome"] == "correct" for x in sel_rows)
        tot_wr = sum(x[2]["outcome"] == "wrong" for x in sel_rows)
        tot_cl = sum(x[2]["outcome"] == "clarify" for x in sel_rows)
        return {
            "pooled_n": n,
            "per_run_n": round(n / n_runs),
            "served_pooled": s_n,
            "served_per_run": round(s_n / n_runs),
            "served_coverage_pct": round(100.0 * s_n / max(1, n), 1),
            "served_correct_pooled": s_ok,
            "served_wrong_pooled": s_wr,
            "served_wrong_per_run": round(s_wr / n_runs),
            "served_accuracy_pct": round(100.0 * s_ok / s_n, 1) if s_n else None,
            "fallback_pooled": o_n,
            "fallback_per_run": round(o_n / n_runs),
            "fallback_pct": round(100.0 * o_n / max(1, n), 1),
            "fallback_correct_pooled": o_ok,
            "fallback_clarify_pooled": o_cl,
            "fallback_wrong_pooled": o_wr,
            "e2e_accuracy_pct": round(100.0 * tot_ok / max(1, n), 1),
            "e2e_wrong_pct": round(100.0 * tot_wr / max(1, n), 1),
            "e2e_clarify_pct": round(100.0 * tot_cl / max(1, n), 1),
            "tokens_mean": round(statistics.mean(tok_of(x[2]) for x in sel_rows), 1) if n else 0.0,
            "seconds_mean": round(statistics.mean(((x[2].get("run") or {}).get("seconds") or 0.0) for x in sel_rows), 1) if n else 0.0,
            "db_ms_mean": round(statistics.mean(((x[2].get("db") or {}).get("ms") or 0.0) for x in sel_rows), 1) if n else 0.0,
            "check_ms_mean": round(statistics.mean(check_ms_of(x[2]) for x in sel_rows), 1) if n else 0.0,
        }

    arm_summary[arm] = {
        "runs": sorted(runs_seen),
        "all": summarize_scope(rows),
        "groups": {g: summarize_scope([x for x in rows if x[0] == g]) for g in ("holdout", "non_breaking", "covered_breaks", "outside_conditions")},
    }

out_payload = {"counts": raw_counts, "summary": arm_summary}
(HERE / "served-split.json").write_text(json.dumps(out_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def tot(arm, src=None, outcome=None, group=None):
    return sum(
        v
        for k, v in raw_counts.get(arm, {}).items()
        if (src is None or k.split("|")[1] == src)
        and (outcome is None or k.split("|")[2] == outcome)
        and (group is None or k.split("|")[0] == group)
    )


# 92 scored questions/run (46 synthetic + 46 tpch) x 3 runs = 276 total pooled answers
mac = {
    "SsMavraServed": tot("mavra", "def"),
    "SsMavraServedWrong": tot("mavra", "def", "wrong"),
    "SsMavraOwnWrong": tot("mavra", "own", "wrong"),
    "SsMavraBreakServed": tot("mavra", "def", group="covered_breaks"),
    "SsBreakN": tot("mavra", group="covered_breaks"),
    "SsRecheckBreakServed": tot("recheck", "def", group="covered_breaks"),
    "SsRecheckBreakOwn": tot("recheck", "own", group="covered_breaks"),
    "SsRecheckBreakOwnClarify": tot("recheck", "own", "clarify", "covered_breaks"),
    "SsRecheckBreakOwnWrong": tot("recheck", "own", "wrong", "covered_breaks"),
}

ATAG = {"mavra": "Mavra", "recheck": "Recheck", "template_schema": "Tschema", "template_revoke": "Trevoke"}
for arm, t in ATAG.items():
    if arm not in arm_summary:
        continue
    s_all = arm_summary[arm]["all"]
    s_brk = arm_summary[arm]["groups"]["covered_breaks"]
    s_ben = arm_summary[arm]["groups"]["non_breaking"]
    mac[f"Ss{t}Cov"] = f"{s_all['served_coverage_pct']:.1f}"
    mac[f"Ss{t}ServedAcc"] = "--" if s_all["served_accuracy_pct"] is None else f"{s_all['served_accuracy_pct']:.1f}"
    mac[f"Ss{t}ServedWrong"] = str(s_all["served_wrong_pooled"])
    mac[f"Ss{t}Fallback"] = f"{s_all['fallback_pct']:.1f}"
    mac[f"Ss{t}EteAcc"] = f"{s_all['e2e_accuracy_pct']:.1f}"
    mac[f"Ss{t}EteWrong"] = f"{s_all['e2e_wrong_pct']:.1f}"
    mac[f"Ss{t}TokK"] = f"{s_all['tokens_mean'] / 1000.0:.1f}"
    mac[f"Ss{t}Sec"] = f"{s_all['seconds_mean']:.0f}"
    mac[f"Ss{t}BrkCov"] = f"{s_brk['served_coverage_pct']:.1f}"
    mac[f"Ss{t}BrkServedAcc"] = "--" if s_brk["served_accuracy_pct"] is None else f"{s_brk['served_accuracy_pct']:.1f}"
    mac[f"Ss{t}BrkEteAcc"] = f"{s_brk['e2e_accuracy_pct']:.1f}"
    mac[f"Ss{t}BrkEteWrong"] = f"{s_brk['e2e_wrong_pct']:.1f}"
    mac[f"Ss{t}BrkTokK"] = f"{s_brk['tokens_mean'] / 1000.0:.1f}"
    mac[f"Ss{t}BrkSec"] = f"{s_brk['seconds_mean']:.0f}"
    mac[f"Ss{t}BenCov"] = f"{s_ben['served_coverage_pct']:.1f}"
    mac[f"Ss{t}BenEteAcc"] = f"{s_ben['e2e_accuracy_pct']:.1f}"
    mac[f"Ss{t}BenTokK"] = f"{s_ben['tokens_mean'] / 1000.0:.1f}"

cs_path = ROOT / "overleaf/gen/change-study.tex"
if cs_path.exists():
    cs = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{([^}]*)\}", cs_path.read_text(encoding="utf-8")))
    if "CsBreakMavra" in cs and "CsBreakRecheck" in cs:
        mac["CsBreakMavraGainRecheck"] = f"{float(cs['CsBreakMavra']) - float(cs['CsBreakRecheck']):.1f}"
        mac["CsBreakRecheckTokRatio"] = f"{float(cs['CsBreakRecheckTokK']) / float(cs['CsBreakMavraTokK']):.1f}"

tex = ["% Generated by exp/2026-11-11-maint-hardening/served-split.py; do not edit."]
tex += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(mac.items())]
(ROOT / "overleaf/gen/served-split.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
print("\n".join(tex))
