#!/usr/bin/env python3
"""README 7.3 (attribution, not registered): the 7.1 judges without peer differences under the full v3 rule.

7.1 registered the plain judges under the Section 3 rule only, on the belief that the absence check (W) and peer-group
coherence (C) need attributes. They need the catalog's attributes, not the judge's input, so the plain judges can run
the complete v3 policy; this isolates the input rendering. The script feeds policy_v2.py a cache in which the
"mavra_refreshed" family holds the plain judges' scores (mavra_zero is copied unchanged from results_v3 and is not
read downstream), and writes results_v3_plain/policy-summary.json and risk-coverage-v2.json.
Usage: python3 replay_plain_rule.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

H = Path(__file__).resolve().parent
P = json.load(open(H / "results_v3_plain/cache.json", encoding="utf-8"))
C = json.load(open(H / "results_v3/cache.json", encoding="utf-8"))
assert P["recall"] == C["recall"], "plain and v3 caches must share the retriever output"
assert [r["uid"] for r in P["meta"]["requests"]] == [r["uid"] for r in C["meta"]["requests"]]
P["scores"] = {"mavra_zero": C["scores"]["mavra_zero"], "mavra_refreshed": P["scores"]["single_ce_refreshed"]}
with tempfile.TemporaryDirectory() as tmp:
    shim = Path(tmp) / "cache.json"
    shim.write_text(json.dumps(P), encoding="utf-8")
    subprocess.run([sys.executable, str(H / "policy_v2.py"), "--cache", str(shim), "--out", str(H / "results_v3_plain")],
                   cwd=H, check=True, stdout=subprocess.DEVNULL)
S = json.load(open(H / "results_v3_plain/policy-summary.json", encoding="utf-8"))["mavra_refreshed"]
for cfg in ("r", "v2"):
    print(cfg, {m: (S[cfg][m]["all_390"]["first_exact_rate"], S[cfg][m]["all_390"]["direct_coverage"],
                    S[cfg][m]["all_390"]["selective_risk"]) for m in ("26", "100", "500", "1000")})
