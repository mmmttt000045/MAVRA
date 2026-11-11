#!/usr/bin/env python3
"""Check complete RelBench candidates against every reported quality and cost.

This is reporting after a run, never an optimization input. It keeps the paper's
fixed pricing, failed-session fallback and cutoff definitions unchanged.
"""
import argparse
import hashlib
import json
import statistics
from pathlib import Path

import importlib.util


SPEC = importlib.util.spec_from_file_location("compare_stats", Path(__file__).with_name("compare-stats.py"))
CS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CS)
ARMS = ("none", "ace", "gmemory", "awm", "tecod", "featpilot", "mavra-push")
DIRECTORIES = {"rel-stack": "relbench-pilot3", "rel-trial": "relbench-main"}
COSTS = ("tokens", "token_ratio", "llm_calls", "tool_calls", "agent_seconds", "usd")


def load(path, reference):
    data = CS.load(str(path), prices=CS.USD_PRICES)
    fixes = path.parent / "time-corrections.json"
    seconds = json.loads(fixes.read_text()).get("seconds", {}).get(path.name, {}) if fixes.exists() else {}
    for (task, cutoff), row in data.items():
        row["agent_s"] -= seconds.get(f"{task}-k{cutoff}", 0)
        row["valid"] = row["test"] is not None and row["audit"] == "clean"
        if row["test"] is None:
            row["test"] = reference.get((task, cutoff))
    return data


def aggregate(data, denominator, cutoffs=(2, 3, 4, 5)):
    late = [r for (_, k), r in data.items() if k in cutoffs]
    tokens = sum(r["tokens"] for r in late)
    return {"tokens": tokens, "token_ratio": tokens / denominator, "llm_calls": sum(r["llm"] for r in late),
            "tool_calls": sum(r["tools"] for r in late), "agent_seconds": sum(r["agent_s"] for r in late),
            "usd": sum(r["cost"]["offpeak"] for r in late)}


def session_hashes(path):
    files = [p for p in (path / "sessions").glob("*.json") if not p.name.endswith(".partial.json")]
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def check(source, candidates, arm, run):
    output = {"schema_version": 1, "candidate_arm": arm, "candidate_run": run,
              "used_for_selection": False, "panels": {},
              "reporting_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for db, directory in DIRECTORIES.items():
        base_dir = source / "results" / directory
        none = base_dir / f"none-{db}-r1"
        run_data = json.loads((none / "run.json").read_text())
        reference = {(t, c["k"]): v.get("test") for c in run_data["cutoffs"] for t, v in c.get("reference", {}).items()}
        old = {a: load(base_dir / f"{a}-{db}-r1", reference) for a in ARMS}
        path = candidates / f"{arm}-{db}-r{run}"
        current = load(path, reference)
        expected = set(old["none"])
        if len(expected) != 15 or any(set(data) != expected for data in old.values()):
            raise ValueError(f"{db}: reported source arms do not cover the same complete 15-session cohort")
        metadata_path = path / "run.json"
        metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
        report = {"candidate_path": str(path), "sessions": len(current), "expected_sessions": len(expected),
                  "finished": bool(metadata.get("finished")), "run_error": metadata.get("error"),
                  "complete": set(current) == expected and bool(metadata.get("finished")) and not metadata.get("error"),
                  "valid_sessions": sum(r["valid"] for r in current.values())}
        if not report["complete"]:
            report["missing"] = sorted(expected - set(current))
            output["panels"][db] = report
            continue
        denominator = sum(r["tokens"] for (_, k), r in old["none"].items() if k >= 2)
        baseline_cost = aggregate(old["mavra-push"], denominator)
        cost = aggregate(current, denominator)
        report["reuse_cost"] = cost
        report["original_mavra_cost"] = baseline_cost
        report["cost_pass"] = {name: cost[name] <= baseline_cost[name] for name in COSTS}
        report["end_to_end_tokens"] = sum(r["tokens"] for r in current.values())
        all_denominator = sum(r["tokens"] for r in old["none"].values())
        cold_denominator = sum(r["tokens"] for (_, k), r in old["none"].items() if k == 1)
        report["all_cutoff_cost"] = aggregate(current, all_denominator, (1, 2, 3, 4, 5))
        report["original_all_cutoff_cost"] = aggregate(old["mavra-push"], all_denominator, (1, 2, 3, 4, 5))
        report["cold_start_cost"] = aggregate(current, cold_denominator, (1,))
        report["original_cold_start_cost"] = aggregate(old["mavra-push"], cold_denominator, (1,))
        report["candidate_session_sha256"] = session_hashes(path)
        report["reported_session_sha256"] = {a: session_hashes(base_dir / f"{a}-{db}-r1") for a in ARMS}
        report["quality"] = {}
        for task in sorted({t for t, _ in expected}):
            keys = [key for key in expected if key[0] == task]
            higher = old["none"][keys[0]]["higher"]
            scores = {a: statistics.mean(old[a][key]["test"] for key in keys) for a in ARMS
                      if all(key in old[a] and old[a][key]["test"] is not None for key in keys)}
            best_arm = (max if higher else min)(scores, key=scores.get)
            val = statistics.mean(current[key]["test"] for key in keys) if all(current[key]["test"] is not None for key in keys) else None
            report["quality"][task] = {"higher": higher, "candidate": val, "best_reported_arm": best_arm,
                                        "best_reported_score": scores[best_arm], "all_reported_scores": scores,
                                        "first_or_tied": val is not None and (val >= scores[best_arm] if higher else val <= scores[best_arm]),
                                        "per_cutoff": [{"cutoff": key[1], "candidate_test": current[key]["test"],
                                                        "candidate_validation": current[key].get("val"),
                                                        "candidate_valid": current[key]["valid"],
                                                        "reported_winner_test": old[best_arm][key]["test"],
                                                        "reported_winner_valid": old[best_arm][key]["valid"],
                                                        "original_mavra_test": old["mavra-push"][key]["test"]}
                                                       for key in keys]}
        report["all_costs_preserved"] = all(report["cost_pass"].values())
        report["all_qualities_first"] = all(r["first_or_tied"] for r in report["quality"].values())
        report["accepted"] = (report["all_costs_preserved"] and report["all_qualities_first"]
                              and report["valid_sessions"] == len(expected))
        output["panels"][db] = report
    output["accepted"] = len(output["panels"]) == 2 and all(r.get("accepted", False) for r in output["panels"].values())
    return output


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--candidates", type=Path, required=True)
    ap.add_argument("--arm", default="mavra-budgeted")
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    result = check(a.source_root, a.candidates, a.arm, a.run)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"accepted": result["accepted"], "panels": {
        db: {k: r.get(k) for k in ("sessions", "valid_sessions", "all_costs_preserved", "all_qualities_first")}
        for db, r in result["panels"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
