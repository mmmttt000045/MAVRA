#!/usr/bin/env python3
"""v1 / v2 / v3 side by side (README 5.3) for MAVRA (refreshed), main 390 and fresh 204, every catalog size.

First response and selective risk come from the policy replays; final exact, tokens and seconds from the
confirmation runs. In results_v3*/ the policy config named "v2" (R + W + C) is v3: same rule, v3 judges/retriever.
The LLM-judge control is Top-8 + LLM judge over the retriever of that version (raw bge-m3 for v1).
Usage: python3 report_v123.py [--json results_v3/report-v123.json]
"""
import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--json", default="results_v3/report-v123.json")
args = ap.parse_args()
H = Path(__file__).resolve().parent
SCALES = ["26", "100", "500", "1000"]


def load(p):
    p = H / p
    return json.load(open(p, encoding="utf-8")) if p.exists() else None


SRC = {
    "main": {
        "sub": ["all_390", "orig_96", "glm_174", "scale_120"],
        "v1": (("results_v2/policy-summary.json", "v1"), ("scale-summary.json", "mavra_refreshed"), "scale-summary.json"),
        "v2": (("results_v2/policy-summary.json", "v2"), ("results_v2/llm/llm-summary.json", "mavra_refreshed_v2"),
               "results_v2/llm/llm-summary.json"),
        "v3": (("results_v3/policy-summary.json", "v2"), ("results_v3/llm/llm-summary.json", "mavra_refreshed_v3"),
               "results_v3/llm/llm-summary.json"),
    },
    "fresh": {
        "sub": ["glm_scale"],
        "v1": (("results_v2_fresh/policy-summary.json", "v1"), ("results_v2_fresh/llm/llm-summary.json", "mavra_refreshed_v1"),
               None),
        "v2": (("results_v2_fresh/policy-summary.json", "v2"), ("results_v2_fresh/llm/llm-summary.json", "mavra_refreshed_v2"),
               "results_v2_fresh/llm/llm-summary.json"),
        "v3": (("results_v3_fresh/policy-summary.json", "v2"), ("results_v3_fresh/llm/llm-summary.json", "mavra_refreshed_v3"),
               "results_v3_fresh/llm/llm-summary.json"),
    },
}

out = {}
for setname, spec in SRC.items():
    out[setname] = {}
    for ver in ("v1", "v2", "v3"):
        (pf, cfg), (cfile, fam), tfile = spec[ver]
        P, Cf, T = load(pf), load(cfile), load(tfile) if tfile else None
        out[setname][ver] = {}
        for m in SCALES:
            out[setname][ver][m] = {}
            for sub in spec["sub"]:
                row = {}
                if P:
                    a = P["mavra_refreshed"][cfg][m][sub]
                    row.update(first=a["first_exact_rate"], cov=a["direct_coverage"], risk=a["selective_risk"])
                if Cf and fam in Cf["mavra_confirmed"]:
                    b = Cf["mavra_confirmed"][fam][m][sub]
                    row.update(final=b["final_exact_rate"], tok=b["tokens_mean"], sec=b["seconds_mean"])
                if T and m in T["top8_llm_judge"]:
                    c = T["top8_llm_judge"][m][sub]
                    row.update(llm=c["exact_rate"], llm_tok=c["tokens_mean"], llm_sec=c["seconds_mean"])
                out[setname][ver][m][sub] = row


def f(x, pct=True):
    return "—" if x is None else (f"{100 * x:.1f}" if pct else f"{x:.0f}")


for setname, spec in SRC.items():
    for sub in spec["sub"]:
        print(f"\n### {setname} / {sub}\n")
        print("| M | ver | first exact | direct cov | sel. risk | final | tok | s | LLM ctrl |")
        print("|---:|---|---:|---:|---:|---:|---:|---:|---:|")
        for m in SCALES:
            for ver in ("v1", "v2", "v3"):
                r = out[setname][ver][m][sub]
                sec = "—" if r.get("sec") is None else f"{r['sec']:.2f}"
                print(f"| {m} | {ver} | {f(r.get('first'))} | {f(r.get('cov'))} | {f(r.get('risk'))} | {f(r.get('final'))} "
                      f"| {f(r.get('tok'), False)} | {sec} | {f(r.get('llm'))} |")

Path(H / args.json).parent.mkdir(parents=True, exist_ok=True)
json.dump(out, open(H / args.json, "w", encoding="utf-8"), indent=1)
print(f"\nwrote {args.json}")
