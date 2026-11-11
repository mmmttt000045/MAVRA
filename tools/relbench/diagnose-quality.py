#!/usr/bin/env python3
"""Audit feature-search, reuse and quality from frozen RelBench session records.

This reads existing records only. Test scores are diagnostic output and never
become candidate-selection inputs. Every contributing file is hashed.
"""
import argparse
import collections
import hashlib
import json
import statistics
from pathlib import Path


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def session(path):
    raw = path.read_bytes()
    s = json.loads(raw)
    vals = s.get("validations", [])
    clean = [v for v in vals if v.get("val") is not None and not v.get("leak")]
    final = next((v for v in reversed(clean) if v.get("sql") == s.get("final_sql")), {})
    higher = s.get("higher_is_better", False)
    learning = s.get("learning") or {}
    selection = s.get("memory_select") or {}
    totals = s.get("totals") or {}
    failures = collections.Counter()
    for f in learning.get("events") or learning.get("features") or []:
        if f.get("event") not in ("promoted", "corroborated"):
            failures[str(f.get("failed_gate") or f.get("event"))] += 1
    target = s.get("target")
    first = clean[0].get("val") if clean else None
    reached_first = target is not None and first is not None and (first >= target if higher else first <= target)
    sql = s.get("final_sql") or ""
    return {
        "source": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
        "arm": s.get("arm"), "run": s.get("run"), "task": s["task"], "k": s["k"],
        "higher": higher, "metric": s.get("metric"), "stop": s.get("stop"),
        "audit": (s.get("audit") or {}).get("result"),
        "test": (s.get("eval") or {}).get("test"), "best_val": s.get("best_val"),
        "first_clean_val": first, "target": target, "reached_at_first_clean_validation": reached_first,
        "validation_count": len(vals), "clean_validations": len(clean),
        "final_feature_count": final.get("n_features"), "final_important_features": final.get("importance"),
        "final_sql_sha256": hashlib.sha256(sql.encode()).hexdigest(), "final_sql_chars": len(sql),
        "tokens": totals.get("tokens_with_learning", totals.get("tokens", 0)),
        "llm_calls": totals.get("llm_calls", 0), "tool_calls": totals.get("tool_calls", 0),
        "agent_seconds": s.get("agent_seconds"),
        "schema_calls": (totals.get("tool_calls_by_category") or {}).get("schema", 0),
        "probe_calls": (totals.get("tool_calls_by_category") or {}).get("probe", 0),
        "learn_failures": dict(failures), "learning_error": learning.get("error"),
        "memory_push": s.get("memory_push"),
        "selection": {k: selection.get(k) for k in ("seconds", "sql_seconds", "train_seconds", "audit_seconds",
                                                      "definitions_offered", "extension_error", "extension_skipped")},
        "selection_candidates": selection.get("candidates"),
        "validations": [{k: v.get(k) for k in ("val", "error", "leak", "n_features", "importance", "improved")}
                        for v in vals],
    }


def audit(root):
    records = []
    groups = {}
    for db, directory in (("rel-stack", "relbench-pilot3"), ("rel-trial", "relbench-main")):
        for run_dir in sorted((root / "results" / directory).glob(f"*-{db}-r*")):
            if not run_dir.is_dir():
                continue
            ss = []
            for f in sorted((run_dir / "sessions").glob("*.json")):
                if f.name.endswith(".partial.json"):
                    continue
                row = session(f)
                row["database"] = db
                ss.append(row)
            if not ss:
                continue
            records.extend(ss)
            late = [r for r in ss if r["k"] >= 2]
            tasks = {}
            for task in sorted({r["task"] for r in ss}):
                rows = sorted((r for r in ss if r["task"] == task), key=lambda r: r["k"])
                tasks[task] = {"mean_test": mean(r["test"] for r in rows),
                               "first_test": rows[0]["test"], "first_val": rows[0]["best_val"],
                               "per_cutoff": [{k: r[k] for k in ("k", "best_val", "test", "stop", "validation_count",
                                                                  "reached_at_first_clean_validation", "final_feature_count")}
                                              for r in rows]}
            groups[run_dir.name] = {
                "database": db, "arm": ss[0]["arm"], "run": ss[0]["run"], "sessions": len(ss), "tasks": tasks,
                "valid_sessions": sum(r["audit"] == "clean" and r["test"] is not None for r in ss),
                "reuse": {"sessions": len(late), "tokens": sum(r["tokens"] for r in late),
                          "llm_calls": sum(r["llm_calls"] for r in late), "tool_calls": sum(r["tool_calls"] for r in late),
                          "agent_seconds": sum(r["agent_seconds"] or 0 for r in late),
                          "validation_count": sum(r["validation_count"] for r in late),
                          "first_validation_reaches_goal": sum(r["reached_at_first_clean_validation"] for r in late),
                          "stops": dict(collections.Counter(r["stop"] for r in late))},
                "total_tokens_with_learning": sum(r["tokens"] for r in ss),
            }
    return {"schema_version": 1, "selection_uses_test_scores": False, "groups": groups, "sessions": records}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sessions-jsonl", type=Path, help="keep detailed session records in a separate JSONL file")
    a = ap.parse_args()
    result = audit(a.root)
    count = len(result["sessions"])
    if a.sessions_jsonl:
        a.sessions_jsonl.parent.mkdir(parents=True, exist_ok=True)
        records = "".join(json.dumps(s, ensure_ascii=False, separators=(",", ":")) + "\n" for s in result.pop("sessions"))
        a.sessions_jsonl.write_text(records, encoding="utf-8")
        result["sessions_jsonl"] = {"file": a.sessions_jsonl.name, "records": count,
                                    "sha256": hashlib.sha256(records.encode()).hexdigest()}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"groups": len(result["groups"]), "sessions": count, "out": str(a.out)}))


if __name__ == "__main__":
    main()
