#!/usr/bin/env python3
"""Serving-vs-withholding & controlled template-invalidation decomposition (Table 4).

Splits every scored schema-evolution answer by whether the agent answered from a served definition
(`y_j = 1`, at least one declared metric reference executed without middleware rejection) or via
fallback (`y_j = 0`, definition withheld, unavailable, or unlearned so the agent explored SQL on
its own or requested clarification).

When run with explicit cell directories (`CELLS_DIR ...` or `--cells-dir`), recomputes `served-split.json`
and `results/gen/served-split.tex` (refusing to overwrite `served-split.json` if zero journals match).
When run without cell directories, loads archived `served-split.json` directly and emits all `Ss*`
LaTeX macros without overwriting `served-split.json`.
"""
import argparse
import collections
import glob
import json
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GROUPS = {
    "holdout": ["holdout"],
    "non_breaking": ["append", "backfill", "correct", "addcol"],
    "covered_breaks": ["status", "revision", "dupload", "dimhist", "latekey"],
    "outside_conditions": ["unit", "mirror"],
}
INV = {c: g for g, cs in GROUPS.items() for c in cs}
ARMS = ["mavra", "recheck", "template_schema", "template_revoke"]


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


def summarize_arm_journals(journal_iters):
    c = collections.Counter()
    rows = []
    runs_seen = set()
    for name, lines in journal_iters:
        m_run = re.search(r"-r(\d+)-", name)
        if m_run:
            runs_seen.add(int(m_run.group(1)))
        for line in lines:
            if not line.strip():
                continue
            r = json.loads(line)
            if r["phase"] == "learn":
                continue
            used = is_served(r)
            grp = INV.get(r["phase"], "holdout")
            c[f'{grp}|{"def" if used else "own"}|{r["outcome"]}'] += 1
            rows.append((grp, used, r))
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

    return dict(c), {
        "runs": sorted(runs_seen),
        "all": summarize_scope(rows),
        "groups": {g: summarize_scope([x for x in rows if x[0] == g]) for g in ("holdout", "non_breaking", "covered_breaks", "outside_conditions")},
    }


def build_macros(raw_counts: dict, arm_summary: dict, cs_path: Path) -> dict[str, str]:
    def tot(arm, src=None, outcome=None, group=None):
        return sum(
            v
            for k, v in raw_counts.get(arm, {}).items()
            if (src is None or k.split("|")[1] == src)
            and (outcome is None or k.split("|")[2] == outcome)
            and (group is None or k.split("|")[0] == group)
        )

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

    atag = {"mavra": "Mavra", "recheck": "Recheck", "template_schema": "Tschema", "template_revoke": "Trevoke"}
    for arm, t in atag.items():
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

    if cs_path.exists():
        cs = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{([^}]*)\}", cs_path.read_text(encoding="utf-8")))
        if "CsBreakMavra" in cs and "CsBreakRecheck" in cs:
            mac["CsBreakMavraGainRecheck"] = f"{float(cs['CsBreakMavra']) - float(cs['CsBreakRecheck']):.1f}"
            mac["CsBreakRecheckTokRatio"] = f"{float(cs['CsBreakRecheckTokK']) / float(cs['CsBreakMavraTokK']):.1f}"
    return mac


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dirs", nargs="*", metavar="CELLS_DIR", help="Cell directories containing *-r*-<arm>/metric-*/task-journal.jsonl")
    ap.add_argument("--cells-dir", action="append", default=[], help="Additional cell directory")
    ap.add_argument("--out", type=Path, default=HERE / "served-split.json", help="Output JSON path when aggregating live cell directories")
    ap.add_argument("--tex", type=Path, default=ROOT / "results/gen/served-split.tex", help="Output LaTeX macro path")
    args = ap.parse_args()

    all_dirs = [*args.dirs, *args.cells_dir]
    cs_path = args.tex.parent / "change-study.tex"

    if not all_dirs:
        archived_path = HERE / "served-split.json"
        if not archived_path.is_file():
            raise SystemExit(f"No CELLS_DIR supplied and archived {archived_path} is missing")
        archived = json.loads(archived_path.read_text(encoding="utf-8"))
        mac = build_macros(archived["counts"], archived["summary"], cs_path)
        tex = ["% Generated by exp/maintenance-guards/served-split.py; do not edit."]
        tex += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(mac.items())]
        args.tex.parent.mkdir(parents=True, exist_ok=True)
        args.tex.write_text("\n".join(tex) + "\n", encoding="utf-8")
        print(f"wrote {len(mac)} macros to {args.tex}")
        return

    raw_counts = {}
    arm_summary = {}
    for arm in ARMS:
        files = []
        for d in all_dirs:
            files.extend(sorted(glob.glob(f"{d}/*-r*-{arm}/metric-*/task-journal.jsonl")))
        if not files:
            continue
        iters = [(f, Path(f).read_text(encoding="utf-8").splitlines()) for f in files]
        raw_counts[arm], arm_summary[arm] = summarize_arm_journals(iters)

    if not arm_summary:
        raise SystemExit(f"No matching task-journal.jsonl files found in {all_dirs}; refusing to overwrite {args.out}")

    out_payload = {"counts": raw_counts, "summary": arm_summary}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    mac = build_macros(raw_counts, arm_summary, cs_path)
    tex = ["% Generated by exp/maintenance-guards/served-split.py; do not edit."]
    tex += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(mac.items())]
    args.tex.parent.mkdir(parents=True, exist_ok=True)
    args.tex.write_text("\n".join(tex) + "\n", encoding="utf-8")
    print("\n".join(tex))


if __name__ == "__main__":
    main()
