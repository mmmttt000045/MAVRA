#!/usr/bin/env python3
"""TeCoD (SIGMOD 2026) as a population-study arm (structural-variation study, 2026-11-09).

A minimal memory service for `metric-bench --population --modes paper-tecod` (the bench's published-memory bridge:
FIG6_MEMORY_URL, FIG6_CELL_KEY). Selection, prompt pieces and the pool SQL rule are the change study's TeCoD arm:
the selection server tools/relbench/tecod_server.py (released template selection, one pool per cell), the prompt
pieces tools/relbench/harness.py tecod_block (template, then three examples, then the question again), and
tecod_pair_sql copied from exp/2026-11-01-change-study/memory-service.py. Two differences follow the population
protocol, where no method receives answer feedback and every memory learns only from verified learning sessions:

1. no feedback block in the prompt (the change study gave every method its own last three binary outcomes);
2. a pair joins the pool only when the question stated the business definition (a learning question) and the answer
   was judged correct -- the premise under which MAVRA extracts definitions and example retrieval stores a session.

The masked question (nlq_masked) masks digits, as in the change study, and the dimension values written in 「」.

  python3 exp/2026-11-09-structural-reuse/tecod-service.py --port 19541 --tecod-url http://127.0.0.1:19532/tecod --out DIR
"""
import argparse
import importlib.util
import json
import re
import threading
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("relbench_harness", ROOT / "tools/relbench/harness.py")
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)
TECOD_URL = "http://127.0.0.1:19532/tecod"


def tecod(req):
    """One request to the TeCoD selection server; raises on its errors."""
    data = json.dumps(req, ensure_ascii=False).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(TECOD_URL, data=data, headers={"Content-Type": "application/json"}),
                                    timeout=1800) as r:
            value = json.loads(r.read())
    except urllib.error.HTTPError as err:
        value = json.loads(err.read() or b"{}")
    if value.get("error"):
        raise RuntimeError(f"TeCoD: {value['error']}")
    return value


def tecod_pair_sql(transcript):
    """Copied from exp/2026-11-01-change-study/memory-service.py: the SQL that produced a correct answer (the executed
    query named by the derivation, or the derivation over several queries as scalar subqueries)."""
    refs = {}
    for e in transcript:
        if e.get("kind", "tool") != "tool" or e.get("tool") != "run_sql":
            continue
        try:
            out = json.loads(e["output"])
        except (ValueError, TypeError):
            continue
        if isinstance(out, dict) and out.get("ref") and isinstance(out.get("result"), dict):
            cols = out["result"].get("columns") or []
            refs[out["ref"]] = ((e.get("input") or {}).get("sql") or "", cols[0] if cols else None)
    final = [e for e in transcript if e.get("tool") == "final_answer"]
    if not final:
        return None, "no final answer"
    inp = final[-1].get("input") or {}
    m = re.match(r"[\sr0-9+\-*/().]+", (inp.get("derivation") or "").strip())
    expr = m.group(0).strip() if m else ""
    names = re.findall(r"r\d+", expr)
    if not names and len(inp.get("used") or []) == 1:
        expr = inp["used"][0]
        names = re.findall(r"r\d+", expr)
    if not names:
        return None, "no derivation over executed queries"
    if any(n not in refs or not refs[n][0].strip() for n in names):
        return None, "the derivation names a query without an executed result"
    if re.fullmatch(r"r\d+", expr):
        return refs[expr][0].strip().rstrip(";"), "one query"
    if any(refs[n][1] is None for n in names):
        return None, "a referenced result has no columns"

    def scalar(mo):
        sql, col = refs[mo.group(0)]
        return '(SELECT "' + col.replace('"', '""') + '" FROM (' + sql.strip().rstrip(";") + ") AS " + mo.group(0) + " LIMIT 1)"
    return "SELECT " + re.sub(r"r\d+", scalar, expr), "derivation over queries"


def tecod_masked(question):
    """Literal values masked: numbers (periods) and the dimension values written in 「」."""
    return re.sub(r"\d+", "_", re.sub(r"「[^」]*」", "「_」", question))


class Actor:
    def __init__(self, key, out):
        self.key, self.lock, self.active, self.index = key, threading.Lock(), None, 0
        self.journal = Path(out) / f"{key}.jsonl"

    def begin(self, req):
        if self.active is not None:
            raise ValueError("Previous task has not ended")
        self.active = (req["task"], req["agent"], req["phase"])
        sel = tecod({"op": "select", "pool": self.key, "query": req["question"]})
        block = h.tecod_block(sel)
        return {"system_prompt": "", "user_prompt": f"\n\n{block}\n\nQuestion: {req['question']}" if block else "",
                "tecod": {"method": "sgc" if sel["matched"] else ("icl" if sel["icl"] else "zs"), "prompt_chars": len(block),
                          **{k: sel.get(k) for k in ("matched", "t_id", "nli_label", "entailment", "cosine", "icl_ids",
                                                     "pool_examples", "pool_templates", "seconds")}},
                "input_tokens": 0, "output_tokens": 0}

    def end(self, req):
        if self.active != (req["task"], req["agent"], req["phase"]):
            raise ValueError("Task-end mismatch")
        t0 = time.monotonic()
        result = {"added": False}
        if req.get("defined") and req["correct"] and not req.get("error"):
            sql, how = tecod_pair_sql(req["transcript"])
            result["pair_sql"] = how
            if sql:
                try:
                    v = tecod({"op": "add", "pool": self.key, "text": req["question"], "nlq_masked": tecod_masked(req["question"]),
                               "sql": sql})
                    result.update(added=True, **{k: v.get(k) for k in ("t_id", "new_template", "masking", "pool_examples",
                                                                      "pool_templates")})
                except Exception as e:  # noqa: BLE001 - a failed addition is recorded, the cell goes on
                    result["add_error"] = f"{type(e).__name__}: {e}"[:500]
                    traceback.print_exc()
        self.active = None
        return {**result, "input_tokens": 0, "output_tokens": 0, "seconds": time.monotonic() - t0}

    def dispatch(self, req):
        with self.lock:
            self.index += 1
            with self.journal.open("a") as f:
                f.write(json.dumps({"event": "request", "index": self.index, "utc": datetime.now(timezone.utc).isoformat(),
                                    "request": {k: v for k, v in req.items() if k != "transcript"}}, ensure_ascii=False) + "\n")
            try:
                if req["op"] == "begin":
                    result = self.begin(req)
                elif req["op"] == "end":
                    result = self.end(req)
                else:
                    raise ValueError("Unknown operation")
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                result = {"error": f"{type(e).__name__}: {e}"}
            with self.journal.open("a") as f:
                f.write(json.dumps({"event": "response", "index": self.index, "utc": datetime.now(timezone.utc).isoformat(),
                                    "response": result}, ensure_ascii=False) + "\n")
            return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, code, value):
        raw = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.reply(200 if self.path == "/health" else 404, {"ok": self.path == "/health"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            if not 0 < n <= 8_000_000:
                raise ValueError("Request size outside limit")
            req = json.loads(self.rfile.read(n))
            key = req["key"]
            if not key.replace("-", "").isalnum() or req["arm"] != "tecod":
                raise ValueError("Invalid actor")
            with self.server.registry_lock:
                actor = self.server.actors.setdefault(key, Actor(key, self.server.out))
            result = actor.dispatch(req)
            self.reply(500 if result.get("error") else 200, result)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.reply(500, {"error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=19541)
    p.add_argument("--tecod-url", default=TECOD_URL)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    TECOD_URL = a.tecod_url
    Path(a.out).mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    server.actors, server.registry_lock, server.out = {}, threading.Lock(), a.out
    server.serve_forever()
