#!/usr/bin/env python3
"""Filter a benchmark definition library to definitions whose learning query returns a non-null, non-zero value.

Usage: python3 tools/bench-support.py SPEC LIB DB_URL OUT
  Definitions whose initial learning period evaluates to NULL or 0 cannot be learned from that period and would make all
  maintenance policies trivially agree on zero; excluded definitions and their initial values are recorded in `excluded`.
"""
import json
import subprocess
import sys


def main():
    spec, lib, db, out = sys.argv[1:5]
    _ = json.load(open(spec, encoding="utf-8"))
    L = json.load(open(lib, encoding="utf-8"))

    def q(sql):
        r = subprocess.run(["psql", "-X", "-tA", db, "-c", sql], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else "ERROR " + (r.stderr.strip().splitlines() or ["?"])[0]

    def compile_(m, y, mo):
        frm = m["fact"]
        for j in m["joins"]:
            frm += f" join {j['right']} on " + " and ".join(f"{j['left']}.{a} = {j['right']}.{b}" for a, b in j["on"])
        w = [f"({x})" for x in m["filters"].values()]
        for j in m["joins"]:
            w += [f"({x})" for x in j.get("filters", {}).values()]
        t = m["time"]
        if t.get("strategy") == "column":
            y2, m2 = (y + 1, 1) if mo == 12 else (y, mo + 1)
            w.append(f"{t['fact_col']} >= date '{y}-{mo:02d}-01' and {t['fact_col']} < date '{y2}-{m2:02d}-01'")
        else:
            frm += f" join {t['dim']} on {m['fact']}.{t['fact_col']} = {t['dim']}.{t['dim_col']}"
            w.append(f"{t['dim']}.{t.get('year_col', 'd_year')} = {y} and {t['dim']}.{t.get('month_col', 'd_moy')} = {mo}")
        return f"select {m['measure']} from {frm} where " + " and ".join(w)

    kept, excluded = [], []
    for e in L["metric_report"]["entries"]:
        ask = e["evidence"]["ask"]["period"]
        v = q(compile_(e["metric"], ask["year"], ask["m1"]))
        try:
            ok = float(v) != 0.0
        except ValueError:
            ok = False
        (kept if ok else excluded).append(e if ok else {"key": e["key"], "learning_value": v or "NULL"})
    L["metric_report"]["entries"] = kept
    L["excluded"] = excluded
    L["support_rule"] = "non-null, non-zero answer on the initial learning period"
    json.dump(L, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"kept": len(kept), "excluded": excluded}, ensure_ascii=False))


if __name__ == "__main__":
    main()
