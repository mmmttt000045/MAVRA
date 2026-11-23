#!/usr/bin/env python3
"""Controlled rendering attribution: evaluate judges trained without peer differences under the full routing rule.

Feeds policy.py a score cache in which the `mavra_refreshed` family holds the plain cross-encoder
scores (while keeping retriever candidates identical), isolating the effect of peer-difference input
rendering from absence widening (W) and peer-group coherence (C).
Usage: python3 replay_plain_rule.py [--main-dir results/lookup] [--plain-dir results/lookup_plain]
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

H = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--main-dir", type=Path, default=H / "results/lookup")
    ap.add_argument("--plain-dir", type=Path, default=H / "results/lookup_plain")
    args = ap.parse_args()

    P = json.loads((args.plain_dir / "cache.json").read_text(encoding="utf-8"))
    C = json.loads((args.main_dir / "cache.json").read_text(encoding="utf-8"))
    assert P["recall"] == C["recall"], "plain and main caches must share retriever output"
    assert [r["uid"] for r in P["meta"]["requests"]] == [r["uid"] for r in C["meta"]["requests"]]
    P["scores"] = {"mavra_zero": C["scores"]["mavra_zero"], "mavra_refreshed": P["scores"]["single_ce_refreshed"]}
    with tempfile.TemporaryDirectory() as tmp:
        shim = Path(tmp) / "cache.json"
        shim.write_text(json.dumps(P), encoding="utf-8")
        subprocess.run(
            [sys.executable, str(H / "policy.py"), "--cache", str(shim), "--out", str(args.plain_dir)],
            cwd=H,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    S = json.loads((args.plain_dir / "policy-summary.json").read_text(encoding="utf-8"))["mavra_refreshed"]
    for cfg in ("r", "full"):
        print(
            cfg,
            {
                m: (
                    S[cfg][m]["all_390"]["first_exact_rate"],
                    S[cfg][m]["all_390"]["direct_coverage"],
                    S[cfg][m]["all_390"]["selective_risk"],
                )
                for m in ("26", "100", "500", "1000")
            },
        )


if __name__ == "__main__":
    main()
