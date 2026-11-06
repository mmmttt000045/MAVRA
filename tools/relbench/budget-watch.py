#!/usr/bin/env python3
"""Spending guard for paid RelBench cells: polls the DeepSeek account balance (a free endpoint) and stops the cells
once the balance has dropped by more than --cap CNY since the guard started. It never touches the model requests, so
the guarded cells send exactly what the other arms sent.

At the cap it sends SIGTERM to every process whose command line contains --match (the guard itself excluded) and
exits. One line per poll goes to --log; the guard also exits when no matching process has been seen for --idle
seconds. Spending by anything else on the same key counts too, so run one paid study at a time.

  python3 tools/relbench/budget-watch.py --cap 15 --match "harness.py --arm tecod" --log results/relbench-tecod-budget.log
"""
import argparse
import os
import signal
import time

import requests


def api_key(path=".env"):
    for line in open(path, encoding="utf-8"):
        if line.startswith("DEEPSEEK_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("DEEPSEEK_API_KEY not in .env")


def balance(http, key):
    r = http.get("https://api.deepseek.com/user/balance", headers={"Authorization": f"Bearer {key}"}, timeout=20)
    r.raise_for_status()
    return sum(float(x["total_balance"]) for x in r.json()["balance_infos"] if x["currency"] == "CNY")


def matching(pattern):
    me, pids = os.getpid(), []
    for d in os.listdir("/proc"):
        if not d.isdigit() or int(d) == me:
            continue
        try:
            cmd = open(f"/proc/{d}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if pattern in cmd and "budget-watch.py" not in cmd:
            pids.append(int(d))
    return pids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=float, required=True, help="CNY")
    ap.add_argument("--match", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--every", type=int, default=60)
    ap.add_argument("--idle", type=int, default=1800)
    a = ap.parse_args()
    key = api_key()
    http = requests.Session()
    http.trust_env = False
    start = balance(http, key)
    last_seen = time.time()
    with open(a.log, "a") as log:
        def say(msg):
            log.write(f"[{time.strftime('%m-%d %H:%M:%S')}] {msg}\n")
            log.flush()
        say(f"start: balance {start:.2f} CNY, cap {a.cap:.2f} CNY, watching '{a.match}'")
        while True:
            time.sleep(a.every)
            pids = matching(a.match)
            if pids:
                last_seen = time.time()
            try:
                now = balance(http, key)
            except Exception as err:  # noqa: BLE001 - keep guarding with the last value
                say(f"balance read failed: {err}")
                continue
            spent = start - now
            say(f"balance {now:.2f}, spent {spent:.2f}, {len(pids)} matching processes")
            if spent > a.cap:
                for p in pids:
                    try:
                        os.kill(p, signal.SIGTERM)
                    except OSError:
                        pass
                say(f"CAP REACHED: sent SIGTERM to {pids}")
                return
            if not pids and time.time() - last_seen > a.idle:
                say("no matching process for a while; guard exits")
                return


if __name__ == "__main__":
    main()
