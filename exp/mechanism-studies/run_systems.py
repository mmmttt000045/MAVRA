#!/usr/bin/env python3
"""Run the fixed LLM-free mechanism benchmarks (Parts B and C)."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "results/mechanism-systems")
    args = ap.parse_args()

    os.chdir(ROOT)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    state_file = out / "status.json"
    state = {"status": "starting", "runs": []}

    def save():
        state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def execute(stage, cmd, env=None):
        state["status"] = stage
        save()
        log_path = out / f"{stage}.log"
        with log_path.open("w", encoding="utf-8") as log:
            r = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=3900)
        state["runs"].append({"stage": stage, "exit_code": r.returncode})
        save()
        if r.returncode:
            raise RuntimeError(f"{stage} failed; inspect {log_path}")

    try:
        save()
        execute("build", ["cargo", "test", "--locked", "--release", "--no-run", "-j", "4"])
        for part in ["C", "B"]:
            env = os.environ.copy()
            env["MECHANISM_PART"] = part
            execute(
                f"run-{part}",
                [
                    "cargo", "test", "--locked", "--release", "q5_bench_tests::postgres_mechanism_supplement",
                    "--", "--ignored", "--nocapture", "--test-threads=1",
                ],
                env,
            )
        state["status"] = "complete"
    except Exception as e:
        state.update(status="stopped", error=str(e))
    finally:
        save()
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
