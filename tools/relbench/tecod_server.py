#!/usr/bin/env python3
"""TeCoD template selection for several pools in one process, over HTTP (change study, 2026-11-06).

Every pool behaves exactly like tecod_service.Pool (released TeCoD selection, see that file's docstring); the pools
share one copy of the two models, so all cells of a study fit in memory together. One request at a time (the models
run on the CPU).

  results/ext/venv-tecod/bin/python tools/relbench/tecod_server.py --models results/ext/tecod-models --port 19532

POST /tecod with a JSON body {"op", "pool", ...}:
  select   {"query"}                                   -> as tecod_service "select"
  add      {"text", "nlq_masked", "sql"[, "tables", "columns"]} -> as tecod_service "add"; without table and column
           names they are read from the SQL itself (every table and column it references), which for valid SQL keeps
           exactly the schema names that tecod_utils.convert_sql_string_to_template keeps
  snapshot {"name"} / restore {"name"}                 -> save or restore the pool's examples and templates
  dump                                                 -> {"examples", "templates"}
"""
import argparse
import copy
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tecod_service as ts  # noqa: E402


def sql_names(sql):
    """Tables and columns referenced by a SQL statement (PostgreSQL); empty lists if sqlglot cannot parse it."""
    from sqlglot import exp, parse_one

    try:
        tree = parse_one(sql.strip().rstrip(";"), read="postgres")
    except Exception:  # noqa: BLE001 - the template then falls back to token masking anyway
        return [], []
    columns = {c.name for c in tree.find_all(exp.Column) if c.name}
    for join in tree.find_all(exp.Join):  # JOIN ... USING (col): identifiers, not Column nodes
        columns.update(i.name for i in join.args.get("using") or [] if getattr(i, "name", None))
    return sorted({t.name for t in tree.find_all(exp.Table) if t.name}), sorted(columns)


class Pools:
    def __init__(self, models):
        self.base = ts.Pool(models)
        self.pools, self.saved = {}, {}
        self.lock = threading.Lock()

    def pool(self, name):
        if name not in self.pools:
            p = copy.copy(self.base)  # shares the models and tokenizer
            p.examples, p.vectors, p.templates = [], [], []
            self.pools[name] = p
        return self.pools[name]

    def handle(self, req):
        with self.lock:
            p, op = self.pool(req["pool"]), req["op"]
            if op == "select":
                return p.select(req["query"])
            if op == "add":
                tables, columns = req.get("tables"), req.get("columns")
                if tables is None or columns is None:
                    tables, columns = sql_names(req["sql"])
                return p.add(req["text"], req["nlq_masked"], req["sql"], tables, columns)
            if op == "snapshot":  # examples, vectors and templates are never changed after they are added
                self.saved[(req["pool"], req["name"])] = (list(p.examples), list(p.vectors), list(p.templates))
                return {"ok": True, "pool_examples": len(p.examples), "pool_templates": len(p.templates)}
            if op == "restore":
                examples, vectors, templates = self.saved[(req["pool"], req["name"])]
                p.examples, p.vectors, p.templates = list(examples), list(vectors), list(templates)
                return {"ok": True, "pool_examples": len(p.examples), "pool_templates": len(p.templates)}
            if op == "dump":
                return {"examples": p.examples, "templates": p.templates}
            raise ValueError(f"unknown op {op}")


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
        t0 = time.time()
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            value = self.server.pools.handle(req)
            value["seconds"] = time.time() - t0
            self.reply(200, value)
        except Exception as err:  # noqa: BLE001 - every failure goes back to the caller
            import traceback

            traceback.print_exc()
            self.reply(500, {"error": f"{type(err).__name__}: {err}", "seconds": time.time() - t0})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--port", type=int, default=19532)
    a = ap.parse_args()
    os.dup2(2, 1)  # library output goes to the log
    sys.stdout = sys.stderr
    server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    server.pools = Pools(a.models)
    print(f"tecod server ready on {a.port}; labels {server.pools.base.nli_model.config.id2label}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
