#!/usr/bin/env python3
"""TeCoD's template selection (released models, tools/relbench/tecod_server.py) on the 96-request lookup benchmark.

Pool: per catalog definition, one canonical question ("<name>是多少？") and 5 single-target phrasings sampled (seed 7)
from the same catalog-generated data MAVRA's judges train on (pool.json, 156 examples); every definition gets its own
SQL template (a unique column), so a matched template names exactly one definition. Questions are masked as in the
change study (digits -> _). A request resolves to the matched template's definition, or to none when TeCoD reports no
entailment match. Scored against gold.json (set-exact, as for every method in Table V).
Usage: run_tecod.py SERVER_URL OUT_DIR
"""
import json, re, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.load(r)


def mask(q):
    return re.sub(r"\d+", "_", q)


def main():
    url, out = sys.argv[1], Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    pool = json.loads((HERE / "pool.json").read_text())
    reqs = json.loads((HERE / "requests.json").read_text())["requests"]
    gold = json.loads((HERE / "gold.json").read_text())
    tdef = {}
    t0 = time.time()
    for ex in pool:
        sql = f"select sum(m_{ex['def'].lower()}) from metric_catalog"
        r = post(url, {"op": "add", "pool": "lookup", "text": ex["text"], "nlq_masked": mask(ex["text"]), "sql": sql,
                       "tables": ["metric_catalog"], "columns": [f"m_{ex['def'].lower()}"]})
        tdef[r["t_id"]] = ex["def"]
    add_s = time.time() - t0
    rows = []
    for q in reqs:
        t = time.time()
        r = post(url, {"op": "select", "pool": "lookup", "query": q["text"]})
        got = [tdef[r["t_id"]]] if r["matched"] else []
        g = sorted(gold[q["id"]]) if isinstance(gold[q["id"]], list) else sorted(gold[q["id"]]["gold"])
        rows.append({"req": q["id"], "kind": q["kind"], "got": got, "gold": g, "ok": got == g, "seconds": time.time() - t,
                     "nli_label": r["nli_label"], "entailment": r["entailment"], "top_def": tdef.get(r["t_id"])})
        print(rows[-1]["req"], got, g, rows[-1]["ok"], flush=True)
    (out / "tecod-results.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))
    n = len(rows)
    summ = {"requests": n, "exact": sum(r["ok"] for r in rows), "two_def_exact": sum(r["ok"] for r in rows if len(r["gold"]) == 2),
            "two_def": sum(len(r["gold"]) == 2 for r in rows), "absent_rejected": sum(r["got"] == [] for r in rows if not r["gold"]),
            "absent": sum(not r["gold"] for r in rows), "single_exact": sum(r["ok"] for r in rows if len(r["gold"]) == 1),
            "single": sum(len(r["gold"]) == 1 for r in rows), "seconds_mean": sum(r["seconds"] for r in rows) / n,
            "pool_examples": len(pool), "pool_add_seconds": add_s}
    (out / "tecod-summary.json").write_text(json.dumps(summ, indent=2) + "\n")
    print(json.dumps(summ, indent=2))


if __name__ == "__main__":
    main()
