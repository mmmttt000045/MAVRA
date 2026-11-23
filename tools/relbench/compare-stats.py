#!/usr/bin/env python3
"""Paired reuse-cost and quality comparison for exp/relbench-predictive/README.md: a memory run against the
no-memory run with the same draw (or archived gate summaries in exp/relbench-attribution/ when omitted).

Per session: tokens including learning (charged to the triggering session), LLM calls, tool calls by category, agent
seconds, test score. Gate: from cutoff 2 on, tokens per session <= 1/3 of no memory (total over those sessions), and
the test score not worse (classification AUC within 0.01, regression MAE within 2%), per task averaged over cutoffs.

  python3 tools/relbench/compare-stats.py [results/relbench/none-r1 results/relbench/mavra-r1] [--out OUT]
(a comma joins the folders of one run, e.g. a run resumed at a later cutoff)
"""
import argparse
import collections
import glob
import json
import os
import statistics


# Published DeepSeek USD rate card (cache hit, cache miss, output / 1M tokens).
# https://api-docs.deepseek.com/quick_start/pricing/
USD_PRICES = {"offpeak": (0.003, 0.15, 0.60), "peak": (0.006, 0.30, 1.20)}
PRICES = USD_PRICES


def cost(calls, extra_in, extra_out, prices):
    """Agent calls priced with their cache hits; memory operations (no cache figures) priced as cache misses."""
    hit, miss, out = prices
    c = sum((x.get("cached_tokens") or 0) * hit + (x["input_tokens"] - (x.get("cached_tokens") or 0)) * miss + x["output_tokens"] * out
            for x in calls)
    return (c + extra_in * miss + extra_out * out) / 1e6


def load(runs, prices=PRICES):
    out = {}
    files = [f for run in runs.split(",") for f in glob.glob(os.path.join(run, "sessions", "*.json")) if not f.endswith(".partial.json")]
    for f in files:
        s = json.load(open(f))
        tot = s["totals"]
        lr = s.get("learning") or {}
        calls = (s.get("llm") or []) + (s.get("llm_sub") or [])
        out[(s["task"], s["k"])] = {
            "cost": {name: cost(calls, lr.get("input_tokens", 0), lr.get("output_tokens", 0), pr) for name, pr in prices.items()},
            "goal": s.get("target"), "goal_why": (s.get("target_detail") or {}).get("why"), "goal_reached": bool(s.get("goal_reached")),
            "eval_error": (s.get("eval") or {}).get("error"), "learn_error": lr.get("error"),
            "retry_s": tot.get("llm_retry_seconds", 0),
            # validations cut by the 600 s statement timeout (load from parallel cells shows up here)
            "sql_timeouts": sum(1 for v in s["validations"] if "statement timeout" in (v.get("error") or "")),
            "tokens": tot.get("tokens_with_learning", tot["tokens"]), "agent_tokens": tot["tokens"],
            "learn_tokens": tot.get("learn_tokens", 0), "llm": tot["llm_calls"], "tools": tot["tool_calls"],
            # agent time without the leak audit (evaluation machinery; older runs counted it in agent_seconds)
            "by_cat": tot["tool_calls_by_category"],
            "agent_s": s["agent_seconds"] - (0 if "audit_seconds" in s else sum(v.get("audit_seconds", 0) for v in s["validations"])),
            "llm_s": tot["llm_seconds"],
            "test": (s.get("eval") or {}).get("test"), "val": s.get("best_val"), "higher": s["higher_is_better"],
            "audit": (s.get("audit") or {}).get("result"), "stop": s["stop"],
            "published": sum(1 for e in ((s.get("learning") or {}).get("events") or []) if e.get("event") in ("promoted", "corroborated")),
        }
    return out


def write_out(payload, out_path):
    if not out_path:
        return
    target = out_path if out_path.endswith(".json") else os.path.join(out_path, "compare-stats.json")
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*", help="base_run and memory_run directories (defaults to archived gate-r1..3.json)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if not args.runs:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        gate_dir = os.path.join(root, "exp", "relbench-attribution")
        gates = []
        for path in sorted(glob.glob(os.path.join(gate_dir, "gate-r*.json"))):
            d = json.load(open(path, encoding="utf-8"))
            gates.append({
                "file": os.path.basename(path),
                "run": d.get("candidate_run"),
                "accepted": d.get("accepted"),
                "panels": {
                    db: {
                        "reuse_cost": p.get("reuse_cost"),
                        "cost_pass": p.get("cost_pass"),
                        "quality_pass": p.get("quality_pass"),
                    }
                    for db, p in (d.get("panels") or {}).items()
                },
            })
        summary = {"runs": gates, "all_accepted": bool(gates) and all(g["accepted"] for g in gates)}
        print(json.dumps(summary, indent=1, ensure_ascii=False))
        write_out(summary, args.out)
        return
    if len(args.runs) != 2:
        ap.error("expected either zero positional arguments (archived mode) or two run folders: BASE_RUN MEMORY_RUN")
    base, other = load(args.runs[0]), load(args.runs[1])
    keys = sorted(set(base) & set(other), key=lambda x: (x[1], x[0]))
    print(f"{'task':16} {'k':>2} | {'tok none':>9} {'tok mem':>9} {'x':>5} | {'llm':>7} | {'tools':>7} | {'sec':>11} | {'test none':>9} {'test mem':>9} | pub")
    for k in keys:
        a, b = base[k], other[k]
        x = a["tokens"] / b["tokens"] if b["tokens"] else float("inf")
        f = lambda v: f"{v:.4f}" if isinstance(v, float) else str(v)
        print(f"{k[0]:16} {k[1]:>2} | {a['tokens']:>9} {b['tokens']:>9} {x:>5.1f} | {a['llm']:>3}/{b['llm']:<3} | {a['tools']:>3}/{b['tools']:<3} | "
              f"{a['agent_s']:>5.0f}/{b['agent_s']:<5.0f} | {f(a['test']):>9} {f(b['test']):>9} | {b['published']}")
    late = [k for k in keys if k[1] >= 2]
    ta, tb = sum(base[k]["tokens"] for k in late), sum(other[k]["tokens"] for k in late)
    quality = {}
    for task in sorted({k[0] for k in keys}):
        ks = [k for k in keys if k[0] == task and base[k]["test"] is not None and other[k]["test"] is not None]
        if not ks:
            continue
        ma, mb = statistics.mean(base[k]["test"] for k in ks), statistics.mean(other[k]["test"] for k in ks)
        higher = base[ks[0]]["higher"]
        ok = mb >= ma - 0.01 if higher else mb <= ma * 1.02
        quality[task] = {"none": round(ma, 4), "memory": round(mb, 4), "not_worse": ok}
    gate = {
        "late_sessions": len(late), "late_tokens_none": ta, "late_tokens_memory": tb,
        "late_token_ratio": round(tb / ta, 3) if ta else None, "tokens_pass": bool(ta) and tb <= ta / 3,
        "llm_calls_late": [sum(base[k]["llm"] for k in late), sum(other[k]["llm"] for k in late)],
        "tool_calls_late": [sum(base[k]["tools"] for k in late), sum(other[k]["tools"] for k in late)],
        "agent_seconds_late": [round(sum(base[k]["agent_s"] for k in late)), round(sum(other[k]["agent_s"] for k in late))],
        "quality": quality, "quality_pass": all(q["not_worse"] for q in quality.values()) if quality else False,
        "leaks_memory": sum(1 for k in keys if other[k]["audit"] == "leak"),
    }
    gate["cost_usd_late"] = {name: [round(sum(base[k]["cost"][name] for k in late), 4), round(sum(other[k]["cost"][name] for k in late), 4)]
                             for name in USD_PRICES}
    # what to check before trusting the numbers: sessions cut short, goals missing, scores missing, memory errors
    health = {}
    for label, d in (("none", base), ("memory", other)):
        health[label] = {
            "stops": dict(collections.Counter(d[k]["stop"] for k in keys)),
            "goal_reached": sum(1 for k in late if d[k]["goal_reached"]),
            "no_goal": {f"{k[0]} k{k[1]}": d[k]["goal_why"] for k in late if d[k]["goal"] is None},
            "missing_test": [f"{k[0]} k{k[1]}" for k in keys if d[k]["test"] is None],
            "eval_errors": {f"{k[0]} k{k[1]}": d[k]["eval_error"][:120] for k in keys if d[k]["eval_error"]},
            "learn_errors": {f"{k[0]} k{k[1]}": str(d[k]["learn_error"])[:120] for k in keys if d[k]["learn_error"]},
            "gateway_retry_seconds": round(sum(d[k]["retry_s"] for k in keys)),
            "validation_sql_timeouts": sum(d[k]["sql_timeouts"] for k in keys),
        }
    gate["health"] = health
    print(json.dumps(gate, indent=1, ensure_ascii=False))
    write_out(gate, args.out)


if __name__ == "__main__":
    main()
