#!/usr/bin/env python3
"""Published ACE/AWM adapters and the unchanged G-Memory core for SQL tasks (change study, 2026-11-01); TeCoD
(SIGMOD 2026) added on 2026-11-06 through tools/relbench/tecod_server.py.

Only the agent's question, own transcript, and binary correctness cross this
boundary. Gold SQL/answers and change labels never appear in memory prompts.
Every independent scenario restores the post-heldout checkpoint.
"""
import argparse
import copy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
import traceback
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((Path(__file__).resolve().parent / "protocol.json").read_text())
spec = importlib.util.spec_from_file_location("relbench_harness", ROOT / "tools/relbench/harness.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
# Domain wording only. All published online sampling/induction settings remain.
h.AWM_OVERRIDES[0] = ("Given a list of web navigation tasks", "Given a list of analytical SQL tasks")
STATE_FIELDS = ("playbooks", "ace_steps", "awm_pool", "awm_workflows", "refs", "tasks", "task_desc")
TECOD_URL = "http://127.0.0.1:19532/tecod"


def tecod(req):
    """One request to the TeCoD selection server (one pool per cell); raises on its errors."""
    import urllib.error
    import urllib.request

    data = json.dumps(req, ensure_ascii=False).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(TECOD_URL, data=data, headers={"Content-Type": "application/json"}),
                                    timeout=900) as r:
            value = json.loads(r.read())
    except urllib.error.HTTPError as err:
        value = json.loads(err.read() or b"{}")
    if value.get("error"):
        raise RuntimeError(f"TeCoD: {value['error']}")
    return value


def tecod_pair_sql(transcript):
    """The SQL that produced a correct answer, for TeCoD's pool, and how it was found. The final answer names the
    queries it used (derivation "r2", or "r2 - r3": first cell of each result, metric.rs eval_derivation); one query
    gives its executed SQL, several give one SQL with each query as a scalar subquery in the derivation. The
    self-reported final_answer.sql is not used: for a derived answer it holds only one of the queries."""
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
    if not expr and len(inp.get("used") or []) == 1:
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
    """TeCoD's masked question (nlq_masked): the question with its literal values masked; in these questions the only
    literals are the period's numbers (year, month, quarter)."""
    return re.sub(r"\d+", "_", question)


def messages(req):
    result = [{"role": "system", "content": "Analytical SQL agent"},
              {"role": "user", "content": req["question"]}]
    for index,event in enumerate(req["transcript"]):
        if event.get("kind") == "assistant":
            result.append({**event["message"], "role": "assistant"})
        elif event.get("kind") == "tool":
            content = event["output"]
            if event.get("status") == "error":
                content = json.dumps({"error": content}, ensure_ascii=False)
            result.append({"role": "tool", "tool_call_id": event["call_id"], "content": content})
        elif 'kind' not in event and event.get('tool'):
            call_id=f'flat-trace-{index}'
            result.append({'role':'assistant','content':None,'tool_calls':[{'id':call_id,'type':'function',
                'function':{'name':event['tool'],'arguments':json.dumps(event.get('input') or {},ensure_ascii=False)}}]})
            result.append({'role':'tool','tool_call_id':call_id,'content':event['output']})
    return result


class Actor:
    def __init__(self, key, arm, directory, proxy, model, total_tasks):
        self.key, self.arm = key, arm
        self.root = Path(directory) / key
        self.root.mkdir(parents=True, exist_ok=False)
        self.lock = threading.Lock()
        self.journal = self.root / "memory-events.jsonl"
        self.index, self.k, self.snapshot, self.gmem = 0, 0, None, None
        self.branch_index = 0
        self.branch = self.root / "branch-000"
        self.branch.mkdir()
        self.env = {"DEEPSEEK_API_KEY": PROTOCOL["local_token"], "DEEPSEEK_MODEL": model,
                    "DEEPSEEK_BASE_URL": f"{proxy}/arm/{key}", "DEEPSEEK_THINKING": "enabled",
                    "DEEPSEEK_REASONING_EFFORT": "low", "DEEPSEEK_REQUIRE_MODEL": model}
        self.llm = h.Llm(self.env)
        # The official API is behind a loopback accounting relay. Older harness
        # versions infer the provider from the URL and otherwise omit G-Memory's
        # non-thinking override. This cohort is exclusively official DeepSeek.
        self.llm.keep_reasoning = True
        self.actor = h.Run.__new__(h.Run)
        self.actor.llm = self.llm
        self.actor.a = SimpleNamespace(out=str(self.branch), run=int(key.split("-r")[1].split("-")[0]))
        # ACE's schedule length: the number of tasks one cell answers (learning plus scored, all branches)
        self.actor.timeline = {"K": total_tasks[key.split("-r")[0]]}
        for name in STATE_FIELDS:
            setattr(self.actor, name, {})
        self.active = None
        self.feedback = []

    def gstart(self):
        if self.gmem is None:
            self.gmem = h.GMemoryService(self.env, str(self.branch), self.llm)
        return self.gmem

    def gsend(self, req):
        value = self.gstart().send(req)
        if value.get("error"):
            raise RuntimeError(value["error"])
        return value

    def close(self):
        if self.gmem is not None:
            self.gmem.close()
            self.gmem.err.close()
            self.gmem = None

    def begin(self, req):
        if self.active is not None:
            raise ValueError("Previous task has not ended")
        self.active = (req["task"], req["agent"], req["phase"])
        common = "\n\nEnvironment feedback from your own earlier tasks (binary correctness; no reference answers):\n" + json.dumps(self.feedback[-3:], ensure_ascii=False)
        if self.arm == "mavra":
            return {"system_prompt": common, "user_prompt": "", "common_feedback": self.feedback[-3:]}
        if self.arm == "ace":
            book = self.actor.playbooks.get(req["agent"], h.ACE_EMPTY_PLAYBOOK)
            block = (Path(h.ACE_DIR) / "appworld_playbook_block.txt").read_text().replace("{{ playbook }}", book)
            return {"system_prompt": common + "\n\n" + block + "\nReport any used playbook bullet IDs in final_answer.bullet_ids.",
                    "user_prompt": "", "playbook_bullets": h.ace_pb.get_playbook_stats(book)["total_bullets"]}
        if self.arm == "tecod":
            sel = tecod({"op": "select", "pool": self.key, "query": req["question"]})
            block = h.tecod_block(sel)
            # released prompt order: template, examples, question; the bench appends user_prompt to the question, so
            # the question is repeated after the TeCoD pieces
            return {"system_prompt": common, "user_prompt": f"\n\n{block}\n\nQuestion: {req['question']}" if block else "",
                    "tecod": {"method": "sgc" if sel["matched"] else ("icl" if sel["icl"] else "zs"), "prompt_chars": len(block),
                              **{k: sel.get(k) for k in ("matched", "t_id", "nli_label", "entailment", "cosine", "icl_ids",
                                                         "pool_examples", "pool_templates", "seconds")}},
                    "input_tokens": 0, "output_tokens": 0}
        if self.arm == "awm":
            workflows = self.actor.awm_workflows.get(req["agent"], "")
            return {"system_prompt": common + ("\n\n" + workflows if workflows else ""), "user_prompt": "",
                    "workflow_chars": len(workflows)}
        value = self.gsend({"op": "begin", "task_main": req["question"], "task_description": req["question"]})
        return {**value, "system_prompt": common, "user_prompt": "\n\n" + value["prompt"],
                "input_tokens": value.get("prompt_tokens", 0), "output_tokens": value.get("completion_tokens", 0)}

    def end(self, req):
        if self.active != (req["task"], req["agent"], req["phase"]):
            raise ValueError("Task-end mismatch")
        t0 = time.monotonic()
        self.k += 1
        executions = [e for e in req["transcript"] if e.get("kind","tool")=="tool" and e.get("tool") in ("run_sql","run_metric")]
        observations=[]
        own_sql=req.get("sql") or ""
        for e in executions:
            output=e["output"]
            try:
                value=json.loads(output)
                if isinstance(value,dict):
                    if e['tool']=='run_metric' and 'result' in value:
                        output=json.dumps({k:v for k,v in value.items() if k not in ('sql','metric')},ensure_ascii=False,separators=(',',':'))
            except (ValueError,TypeError): pass
            observations.append({"tool":e["tool"],"output":output[:350]})
        self.feedback.append({"question":req["question"], "own_answer":req.get("answer"),
            "correct":bool(req["correct"]), "own_sql":own_sql[:1800], "own_observations":observations[-3:]})
        self.feedback = self.feedback[-3:]
        if self.arm == "mavra":
            self.active = None
            return {"common_feedback_recorded":True,"feedback_records":len(self.feedback),"input_tokens":0,"output_tokens":0}
        if self.arm == "tecod":
            # a verified pair joins the cell's pool: the answer was correct (the binary feedback every method sees); a
            # failed addition is recorded and the cell goes on (as in the RelBench arm)
            result = {"added": False}
            if req["correct"] and not req.get("error"):
                sql, how = tecod_pair_sql(req["transcript"])
                result["pair_sql"] = how
                if sql:
                    try:
                        value = tecod({"op": "add", "pool": self.key, "text": req["question"],
                                       "nlq_masked": tecod_masked(req["question"]), "sql": sql})
                        result.update(added=True, **{k: value.get(k) for k in ("t_id", "new_template", "masking", "pool_examples",
                                                                              "pool_templates")})
                    except Exception as e:  # noqa: BLE001 - "error" would end the cell on the bench side
                        result["add_error"] = f"{type(e).__name__}: {e}"[:500]
                        traceback.print_exc()
            self.active = None
            return {**result, "input_tokens": 0, "output_tokens": 0, "seconds": time.monotonic() - t0}
        t, agent, k = req["metric"], req["agent"], self.k
        ask = req["ask"]
        # The predictive harness uses one timestamp as task-file metadata. SQL
        # questions can instead compare periods or summarize an entire year.
        period = ask.get("period") or ask.get("a") or {"year": ask["year"], "m1": 1}
        cutoff = f"{period['year']:04}-{period['m1']:02}-01"
        e = self.actor.tasks.setdefault(t, {"cutoffs": []})
        while len(e["cutoffs"]) < k:
            e["cutoffs"].append({"test_timestamp": cutoff})
        e["cutoffs"][k - 1] = {"test_timestamp": cutoff}
        self.actor.task_desc[t] = {"description": req["question"]}
        correctness = float(bool(req["correct"]))
        rec = {"metric": "answer_correctness", "best_val": correctness, "higher_is_better": True,
               "validations": [{"val": correctness}], "stop": "model_error" if req.get("error") else "task_end",
               "final_sql": req.get("sql"), "bullet_ids": []}
        for event in req["transcript"]:
            if event.get("tool") == "final_answer":
                rec["bullet_ids"] = event["input"].get("bullet_ids") or []
        self.actor.refs[(t, k)] = {"val": .5}
        msgs = messages(req)
        if self.arm == "ace":
            result = self.actor.ace_update(t, k, rec, msgs, agent)
        elif self.arm == "awm":
            result = self.actor.awm_update(t, k, rec, msgs, agent)
        else:
            for event in req["transcript"]:
                if event.get("kind","tool") != "tool":
                    continue
                self.gsend({"op": "step", "agent": agent,
                            "action": event["tool"] + ": " + json.dumps(event["input"], ensure_ascii=False),
                            "observation": event["output"][:h.GMEMORY_OBS_CHARS],
                            "reward": -1 if event.get("status") == "error" else 0})
            value = self.gsend({"op": "end", "label": bool(req["correct"]),
                               "feedback": "The final answer was correct." if req["correct"] else "The final answer was incorrect."})
            result = {**value, "input_tokens": value.get("prompt_tokens", 0),
                      "output_tokens": value.get("completion_tokens", 0)}
        self.active = None
        result["seconds"] = time.monotonic() - t0
        return result

    def checkpoint(self):
        if self.active is not None or self.snapshot is not None:
            raise ValueError("Invalid checkpoint boundary")
        self.snapshot = {"k": self.k, "feedback":copy.deepcopy(self.feedback), "state": {name: copy.deepcopy(getattr(self.actor, name)) for name in STATE_FIELDS}}
        if self.arm == "gmemory":
            self.close()
            shutil.copytree(self.branch / "gmemory", self.root / "post-heldout-gmemory")
        if self.arm == "tecod":
            tecod({"op": "snapshot", "pool": self.key, "name": "post-heldout"})
        return {"ok": True, "k": self.k, "boundary": "post-heldout"}

    def restore(self):
        if self.active is not None or self.snapshot is None:
            raise ValueError("No checkpoint available")
        self.close()
        self.k = self.snapshot["k"]
        self.feedback = copy.deepcopy(self.snapshot["feedback"])
        for name, value in self.snapshot["state"].items():
            setattr(self.actor, name, copy.deepcopy(value))
        self.branch_index += 1
        self.branch = self.root / f"branch-{self.branch_index:03}"
        self.branch.mkdir()
        self.actor.a.out = str(self.branch)
        if self.arm == "gmemory":
            shutil.copytree(self.root / "post-heldout-gmemory", self.branch / "gmemory")
        if self.arm == "tecod":
            tecod({"op": "restore", "pool": self.key, "name": "post-heldout"})
        return {"ok": True, "k": self.k, "branch": self.branch_index}

    def dispatch(self, req):
        with self.lock:
            self.index += 1
            started = datetime.now(timezone.utc).isoformat()
            # Archive before execution, so partial updates cannot disappear.
            with self.journal.open("a") as f:
                f.write(json.dumps({"event": "request", "index": self.index, "utc": started, "request": req}, ensure_ascii=False) + "\n")
            try:
                op = req["op"]
                if op == "begin":
                    result = self.begin(req)
                    result["common_feedback"] = copy.deepcopy(self.feedback[-3:])
                elif op == "end":
                    result = self.end(req)
                elif op == "checkpoint":
                    result = self.checkpoint()
                elif op == "restore":
                    result = self.restore()
                elif op == "close":
                    self.close()
                    result = {"ok": True}
                else:
                    raise ValueError("Unknown operation")
            except Exception as e:
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
            key, arm = req["key"], req["arm"]
            if not key.replace("-", "").isalnum() or arm not in ("ace", "awm", "gmemory", "mavra", "tecod"):
                raise ValueError("Invalid actor")
            with self.server.registry_lock:
                if key not in self.server.actors:
                    if req["op"] != "begin":
                        raise ValueError("First operation must be begin")
                    self.server.actors[key] = Actor(key, arm, self.server.args.out, self.server.args.proxy, self.server.args.model,
                                                    self.server.total_tasks)
                actor = self.server.actors[key]
            if actor.arm != arm:
                raise ValueError("Actor arm mismatch")
            result = actor.dispatch(req)
            self.reply(500 if result.get("error") else 200, result)
        except Exception as e:
            traceback.print_exc()
            self.reply(500, {"error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=19531)
    p.add_argument("--proxy", default="http://127.0.0.1:19530")
    p.add_argument("--model", default=PROTOCOL["model"])
    p.add_argument("--out", required=True)
    p.add_argument("--total-tasks", required=True, help="dataset=count,...")
    p.add_argument("--tecod-url", default=TECOD_URL)
    a = p.parse_args()
    TECOD_URL = a.tecod_url
    server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    server.actors, server.registry_lock, server.args = {}, threading.Lock(), a
    server.total_tasks = {k: int(v) for k, v in (x.split("=") for x in a.total_tasks.split(","))}
    server.serve_forever()
