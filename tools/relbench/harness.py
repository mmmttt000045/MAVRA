#!/usr/bin/env python3
"""Agent sessions on the RelBench retraining timeline (exp/2026-10-20-relbench/README.md).

One run = one method on one database: a fresh copy of the template database built by prepare.py, one agent per task,
one session per (task, cutoff). Before cutoff k > 1 the rows with time in (test_{k-1}, test_k] are appended. Every
session gets the same tools: the middle layer's list_tables / describe_table / join_path / check_join / run_sql over
HTTP (`agentdb-mid serve --mode <m> --no-etl`), plus validate_features and submit implemented here with a fixed
LightGBM. The framework enforces the stopping rule; test labels never enter the database or the agent's context.

Run on noctis (repo root), without the dead local proxy:
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy PYTHONPATH=.pydeps-relbench \
  python3 tools/relbench/harness.py --arm none --run 1 --data results/relbench-data/rel-stack \
      --prep results/relbench-data/rel-stack-prep --template relbench_stack_t1 --out results/relbench-pilot/none-r1
"""
import argparse
import concurrent.futures as cf
import glob
import json
import os
import random
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
import hashlib

import numpy as np
import pandas as pd
import psycopg
import requests

# ACE's official prompts and playbook helpers (Apache-2.0), see third_party/ace/README.md
ACE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "third_party", "ace")
AWM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "third_party", "awm")
# AWM's induction instruction (webarena/prompt/instruction.txt) with its web wording replaced, the rest verbatim
AWM_OVERRIDES = [
    ("Given a list of web navigation tasks", "Given a list of database feature engineering tasks"),
    ("(input text, button strings)", "(task-specific values such as time windows, thresholds and filter values)"),
    ('e.g., id of "Search" or "Customers"', "e.g., names of tables and columns"),
]
AWM_TEMPERATURE = 1.0  # webarena/induce_prompt.py
AWM_MAX_TOKENS = 2048
# AWM induces with a non-reasoning model (GPT-4) within 2048 tokens; with thinking on, the reasoning used up those tokens
# (finish_reason "length", empty workflows), so induction runs without thinking, as G-Memory's memory operations do
AWM_THINKING = "disabled"
AWM_PER_TEMPLATE = 1  # num_samples: at most this many trajectories of one task template
sys.path.insert(0, ACE_DIR)
import curator_prompts as ace_curator  # noqa: E402
import playbook_utils as ace_pb  # noqa: E402
import reflector_prompts as ace_reflector  # noqa: E402

sys.path.pop(0)
# ACE._initialize_empty_playbook (ace/ace.py)
ACE_EMPTY_PLAYBOOK = """## STRATEGIES & INSIGHTS

## FORMULAS & CALCULATIONS

## CODE SNIPPETS & TEMPLATES

## COMMON MISTAKES TO AVOID

## PROBLEM-SOLVING HEURISTICS

## CONTEXT CLUES & INDICATORS

## OTHERS"""
ACE_TOKEN_BUDGET = 80_000  # the official Curator prompt's default token_budget

# ───────────────────────── fixed settings (README §1.2) ─────────────────────────

MAX_LLM_CALLS = 40
MAX_VALIDATIONS = 8
PATIENCE = 2
SAMPLE_SIZE = 50_000          # RelBench's lightgbm_entity.py default
SAMPLE_SEED = 42
MAX_FEATURES = 100
TOOL_OUTPUT_CHARS = 20_000
FEATURE_SQL_TIMEOUT_S = 600
AUDIT_SEEDS = 2000  # seeds for the reproduction check of MAVRA's learning
AUDIT_LEAK_SEEDS = 5000  # seeds of the leak audit (latest training seed time); 500 in the pilot missed leaks
IDLE_RECONNECT_S = 30  # a new connection to the gateway after this long without a request
LLM_RETRIES = 12  # failed requests per call before the run stops (backoff up to 60 s: about 8 minutes)
POST_GOAL_LLM_CALLS = 5  # after the goal: one more validation within this many model calls (README §1.2, rule B)
SELECT_MAX_DEFS = 40  # mavra-select: verified definitions of the entity tried as an extension of the task's program
SELECT_MIN_ROOM = 10  # mavra-select: program columns the joint fit never splits on make room for this many definitions
SELECT_CHECK_SEEDS = 2000  # mavra-select: validation seeds on which the extended SQL must reproduce the scored columns
# mavra-select2 (11-09): the start selection works within a time budget instead of the 600 s statement timeout
SELECT_P_TIMEOUT_S = 300  # each statement of the program; a program over it falls back to its definitions
SELECT_EXTEND_MAX_P_S = 120  # the extension is tried only when the program's SQL took at most this long (its check reruns it)
SELECT_PROBE_TIMEOUT_S = 30  # a definitions SQL is first timed on the check seeds; compiled definitions cost per seed row
SELECT_CHECK_TIMEOUT_S = 120
FIRST_ATTEMPTS = 2  # mavra-select2: a task's first session (no program yet) explores this many times; the better validation is kept
FIRST_LIST_DEFS = 40  # mavra-select2: definitions listed (keys and meanings, no SQL) at a task's first session
LGB_PARAMS = dict(n_estimators=300, learning_rate=0.05, num_leaves=63, min_child_samples=20, colsample_bytree=0.8,
                  subsample=0.8, subsample_freq=1, random_state=42, deterministic=True, force_row_wise=True,
                  n_jobs=8, verbose=-1)
ARMS = {
    "none": {"middle_mode": "middle-alone", "parallel_ok": True},
    # README §1.6: feature definitions shared by all agents; sessions of one cutoff run one after another
    "mavra": {"middle_mode": "relbench-mavra", "parallel_ok": False, "feature_memory": True, "extractor": True},
    # 11-07: MAVRA hands each session its task's verified program and the entity's verified definitions at the start
    # (as the other memories put theirs into the prompt) instead of the agent looking them up with two tool calls
    "mavra-push": {"middle_mode": "relbench-mavra", "parallel_ok": False, "feature_memory": True, "extractor": True,
                   "push_memory": True},
    # 11-08: from the second cutoff the memory validates, without model calls, the task's program and the program
    # extended with verified definitions other agents published for the same entity, and the better one starts the
    # session as its best features (Run.select_start); the program keeps the columns its sessions tried without
    # keeping them, and a session below the single-table reference still records its audited SQL as the task's program
    "mavra-select": {"middle_mode": "relbench-mavra", "parallel_ok": False, "feature_memory": True, "extractor": True,
                     "push_memory": True, "select_start": True},
    # 11-09 (README 4.z): the selection within a time budget (a program over it falls back to its definitions; the
    # extension may cost at most what the program cost); a task's first session gets the entity's definitions as keys
    # and meanings without their SQL, and explores twice, the better validation becoming the session
    "mavra-select2": {"middle_mode": "relbench-mavra", "parallel_ok": False, "feature_memory": True, "extractor": True,
                      "push_memory": True, "select_start": True, "select_budget": True, "first_keys_only": True,
                      "first_attempts": FIRST_ATTEMPTS},
    # 11-12: validation-only feature pruning reuses computed matrices; an audited
    # entity-table model is a cold-start fallback. Reuse gets a small, explicit
    # model/tool budget instead of repeatedly reading a large memory payload.
    "mavra-budgeted": {"middle_mode": "relbench-mavra", "parallel_ok": False, "feature_memory": True, "extractor": True,
                       "push_memory": True, "select_start": True, "select_budget": True, "first_keys_only": True,
                       "first_attempts": FIRST_ATTEMPTS, "subset_selection": True,
                       "reuse_llm_limit": 3, "reuse_tool_limit": 6, "program_timeout": 45},
    "mavra-portfolio": {"middle_mode": "relbench-mavra", "parallel_ok": False, "feature_memory": True, "extractor": True,
                       "push_memory": True, "select_start": True, "select_budget": True, "first_keys_only": True,
                       "first_attempts": FIRST_ATTEMPTS, "subset_selection": True, "cold_union": True, "sanitize_candidates": True,
                       "reuse_llm_limit": 3, "reuse_tool_limit": 6, "program_timeout": 45},
    "mavra-directed": {"middle_mode": "relbench-mavra", "parallel_ok": False, "feature_memory": True, "extractor": True,
                       "push_memory": True, "select_start": True, "select_budget": True, "first_keys_only": True,
                       "first_attempts": FIRST_ATTEMPTS, "subset_selection": True, "cold_union": True, "sanitize_candidates": True,
                       "reuse_llm_limit": 3, "reuse_tool_limit": 6, "program_timeout": 45,
                       "budget_guidance": True, "reuse_validation_timeout": 45, "audit_diagnostics": True},
    "mavra-cached": {"middle_mode": "relbench-mavra", "parallel_ok": False, "feature_memory": True, "extractor": True,
                     "push_memory": True, "select_start": True, "select_budget": True, "first_keys_only": True,
                     "first_attempts": FIRST_ATTEMPTS, "subset_selection": True, "cold_union": True, "sanitize_candidates": True,
                     "reuse_llm_limit": 3, "reuse_tool_limit": 6, "program_timeout": 45,
                     "budget_guidance": True, "reuse_validation_timeout": 45, "audit_diagnostics": True, "reuse_goal_frames": True},
    "mavra-signal": {"middle_mode": "relbench-mavra", "parallel_ok": False, "feature_memory": True, "extractor": True,
                     "push_memory": True, "select_start": True, "select_budget": True, "first_keys_only": True,
                     "first_attempts": FIRST_ATTEMPTS, "subset_selection": True, "cold_union": True, "sanitize_candidates": True,
                     "reuse_llm_limit": 3, "reuse_tool_limit": 6, "program_timeout": 45,
                     "budget_guidance": True, "reuse_validation_timeout": 45, "audit_diagnostics": True,
                     "reuse_goal_frames": True, "require_start_signal": True},
    # Same base metadata/query caches as MAVRA; only task-local, audited SQL is retained.
    # No feature tools, extraction, definition publication or composition are used.
    "sql-only": {"middle_mode": "relbench-mavra", "parallel_ok": False, "sql_memory": True},
    # ACE (ICLR 2026) as published: one playbook per agent, online, no ground-truth labels (README §1.3)
    "ace": {"middle_mode": "middle-alone", "parallel_ok": True, "ace": True},
    # G-Memory (NeurIPS 2025) as published: one store shared by all agents, tasks one at a time (README §1.3)
    "gmemory": {"middle_mode": "middle-alone", "parallel_ok": False, "gmemory": True},
    # AWM (ICML 2025) as published (online WebArena pipeline): one workflow memory per agent, re-induced after every task
    "awm": {"middle_mode": "middle-alone", "parallel_ok": True, "awm": True},
    # TeCoD (SIGMOD 2026) as released, API mode: one template pool per database from verified (question, SQL) pairs;
    # a matched template and three examples, or the examples alone, go into the prompt (tools/relbench/tecod_service.py)
    "tecod": {"middle_mode": "middle-alone", "parallel_ok": False, "tecod": True},
}
# Spend one additional response on refinement within the original reuse-call ceilings.
ARMS["mavra-refine"] = {**ARMS["mavra-signal"], "reuse_llm_limit": 4}
ARMS["mavra-early"] = {**ARMS["mavra-refine"], "cold_first_validation_by": 8}
ARMS["mavra-delta"] = {**ARMS["mavra-refine"], "typed_reference": True, "delta_refinement": True,
                       "cold_validation_timeout":45,"current_refit_timeout":45,
                       "current_refit_attempts":1,"skip_failed_refit":True}
ARMS["mavra-delta-headers"] = {**ARMS["mavra-delta"], "reuse_header_metadata": True}
# v10 (11-12): v9 dropped the stored program when its refit at a new cutoff hit the 45 s limit (5 of 36 rel-trial and
# 2 of 36 rel-stack reuse sessions in three runs); one retry under the standard 600 s statement limit keeps it
ARMS["mavra-retry"] = {**ARMS["mavra-delta-headers"], "current_refit_attempts": 2,
                       "current_refit_retry_timeout": FEATURE_SQL_TIMEOUT_S}
GMEMORY_REPO = "results/ext/GMemory"
GMEMORY_PYTHON = "results/ext/venv-gmem/bin/python"
GMEMORY_OBS_CHARS = 2000
TECOD_PYTHON = "results/ext/venv-tecod/bin/python"
TECOD_MODELS = "results/ext/tecod-models"
# prompts/default.py Default: the pieces of TeCoD's prompt around the question
TECOD_TEMPLATE_INST = "Here is the SQL template for the question. Follow this template to generate the SQL query.\n"
TECOD_ICL_INST = "Here are some examples of user questions and their corresponding SQL queries:\n"
TECOD_ICL_FORMAT = "Question: {question}\nAnswer: {sql}\n"
FEATURE_TOOLS = ("find_features", "compose_features", "find_program")

LOCK = threading.Lock()


PUBLIC_RE = re.compile(r'(?<![\w"])"?public"?\s*\.', re.I)


def in_schema(sql, schema):
    """Point tables named as public.x (or "public".x) at another schema, e.g. views that hide later rows."""
    return PUBLIC_RE.sub(f"{schema}.", sql)


def log(msg):
    with LOCK:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_env(path=".env"):
    env = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith(("DEEPSEEK_", "RIVER_", "HAPPY_", "AGENTDB_"))})
    return env


# ───────────────────────── LLM (OpenAI-compatible; same request shape as src/llm.rs) ─────────────────────────

# provider name -> (.env prefix, default base URL), as OPENAI_PROFILES in src/llm.rs; since 10-21 every run uses DeepSeek's own API
PROVIDERS = {"deepseek": ("DEEPSEEK", "https://api.deepseek.com"), "river": ("RIVER", "https://api.river.ai/v1"),
             "happy": ("HAPPY", "https://happycoding.xyz/v1")}

class LlmUnavailable(RuntimeError):
    """The model service failed after all retries (or refused a request): the run stops instead of recording a cut session."""


class Llm:
    def __init__(self, env, provider="deepseek"):
        prefix, base = PROVIDERS[provider]
        self.provider, self.prefix = provider, prefix
        self.base = env.get(f"{prefix}_BASE_URL", base).rstrip("/")
        self.key = env[f"{prefix}_API_KEY"]
        self.model = env[f"{prefix}_MODEL"]
        self.effort = env.get(f"{prefix}_REASONING_EFFORT")
        self.thinking = env.get(f"{prefix}_THINKING")
        self.require = env.get(f"{prefix}_REQUIRE_MODEL")
        # DeepSeek's thinking mode wants reasoning_content passed back within a tool-calling loop (as src/llm.rs does)
        self.keep_reasoning = provider == "deepseek" or "api.deepseek.com" in self.base
        self.local = threading.local()

    def history(self, m):
        """The assistant message as it goes back into the conversation."""
        keep = ("role", "content", "tool_calls", "reasoning_content") if self.keep_reasoning else ("role", "content", "tool_calls")
        return {k: v for k, v in m.items() if k in keep and v is not None} | {"role": "assistant"}

    @property
    def http(self):
        # a kept-alive connection idle for minutes (sessions run one after another, with learning and goals in between)
        # can be dropped on the way without notice; the next request then waits for the full timeout (pilot: 5 times 300 s)
        if not hasattr(self.local, "s") or time.time() - self.local.used > IDLE_RECONNECT_S:
            if hasattr(self.local, "s"):
                self.local.s.close()
            self.local.s = requests.Session()
            self.local.s.trust_env = False
        self.local.used = time.time()
        return self.local.s

    def _post(self, body):
        """One reply; also the number of failed attempts and the seconds they took (gateway stalls, reported apart)."""
        failures = limited = 0
        lost = 0.0
        while True:
            t0 = time.time()
            try:
                r = self.http.post(f"{self.base}/chat/completions", json=body, timeout=300,
                                   headers={"Authorization": f"Bearer {self.key}"})
            except requests.RequestException as e:
                failures += 1
                if failures > LLM_RETRIES:
                    raise LlmUnavailable(f"request failed: {e}")
                time.sleep(min(60, 2 ** failures))
                lost += time.time() - t0
                continue
            if r.status_code == 200:
                try:
                    return r.json(), failures + limited, lost
                except ValueError:
                    failures += 1
                    if failures > LLM_RETRIES:
                        raise LlmUnavailable(f"non-JSON 200: {r.text[:300]}")
                    time.sleep(min(60, 2 ** failures))
                    lost += time.time() - t0
                    continue
            if r.status_code == 429:
                limited += 1
                if limited > 8:
                    raise LlmUnavailable(f"HTTP 429 after 8 retries: {r.text[:300]}")
                time.sleep(min(120, int(r.headers.get("retry-after", 5 * 2 ** (limited - 1)))) + random.random() * 2)
                lost += time.time() - t0
                continue
            if r.status_code >= 500:
                failures += 1
                if failures > LLM_RETRIES:
                    raise LlmUnavailable(f"HTTP {r.status_code}: {r.text[:300]}")
                time.sleep(min(60, 2 ** failures))
                lost += time.time() - t0
                continue
            raise LlmUnavailable(f"HTTP {r.status_code}: {r.text[:500]}")

    def chat(self, messages, tools=None, temperature=None, max_tokens=None, thinking=None):
        body = {"model": self.model, "messages": messages}
        thinking = thinking or self.thinking
        if max_tokens:
            body["max_tokens"] = max_tokens
        if self.effort and thinking != "disabled":
            body["reasoning_effort"] = self.effort
        if thinking:
            body["thinking"] = {"type": thinking}
        if tools:
            body["tools"] = tools
        if temperature is not None:
            body["temperature"] = temperature
        discarded, wasted, retries, lost = 0, 0, 0, 0.0
        invalid = []
        t0 = time.time()
        for _ in range(15):
            t1 = time.time()
            v, n, secs = self._post(body)
            retries, lost = retries + n, lost + secs
            if self.require and v.get("model") != self.require:
                discarded += 1
                wasted += (v.get("usage") or {}).get("total_tokens", 0)
                lost += time.time() - t1 - secs
                continue
            u = v.get("usage") or {}
            choice = (v.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            # Some gateways return HTTP 200 with finish_reason=error and reasoning-only text.
            # Such a reply cannot be appended as a role-only assistant message: the next
            # upstream request rejects it. Retry the identical conversation and retain usage.
            if choice.get("finish_reason") == "error" or not (msg.get("content") or msg.get("tool_calls")):
                invalid.append({"finish_reason": choice.get("finish_reason"), "model": v.get("model"),
                                "input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0),
                                "cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0,
                                "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0})
                retries += 1
                if len(invalid) >= 4:
                    raise LlmUnavailable(f"four unusable model responses; attempts={json.dumps(invalid)}")
                time.sleep(min(20, 2 ** len(invalid)))
                lost += time.time() - t1 - secs
                continue
            return {
                "message": msg,
                "finish_reason": choice.get("finish_reason"),
                "model": v.get("model"),
                "input_tokens": u.get("prompt_tokens", 0) + sum(x["input_tokens"] for x in invalid),
                "output_tokens": u.get("completion_tokens", 0) + sum(x["output_tokens"] for x in invalid),
                "cached_tokens": ((u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0) + sum(x["cached_tokens"] for x in invalid),
                "reasoning_tokens": ((u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0) + sum(x["reasoning_tokens"] for x in invalid),
                "invalid_responses": invalid,
                "seconds": time.time() - t0,
                "discarded": discarded,
                "discarded_tokens": wasted,
                # failed attempts and replies from another model: time the gateway lost, included in "seconds"
                "retries": retries,
                "retry_seconds": lost,
            }
        raise LlmUnavailable(f"no reply from {self.require} in 15 rounds ({discarded} discarded)")


# ───────────────────────── middle layer ─────────────────────────

def tecod_block(sel):
    """TeCoD's prompt pieces for one selection, as the released method "sgc" builds them (prompts/default.py): the
    matched template (placeholders shown as {{string}} and {{number}}) and the ICL examples, or the examples alone."""
    parts = []
    if sel["matched"]:
        parts.append(TECOD_TEMPLATE_INST + sel["template"].replace("string_rule", "{{string}}").replace("number_rule", "{{number}}"))
    if sel["icl"]:
        parts.append(TECOD_ICL_INST + "".join(TECOD_ICL_FORMAT.format(question=q, sql=y) + "\n" for q, y in sel["icl"]).rstrip("\n"))
    return "\n\n".join(parts)


class TecodService:
    """tools/relbench/tecod_service.py in TeCoD's own Python 3.12 environment, one JSON line per request (no LLM calls)."""

    def __init__(self, out):
        self.err = open(os.path.join(out, "tecod.log"), "w")
        e = {k: v for k, v in os.environ.items() if "proxy" not in k.lower() and k != "PYTHONPATH"}
        e.update(TOKENIZERS_PARALLELISM="false", HF_HUB_OFFLINE="1")
        here = os.path.dirname(os.path.abspath(__file__))
        self.proc = subprocess.Popen([TECOD_PYTHON, os.path.join(here, "tecod_service.py"), "--models", TECOD_MODELS],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err, env=e, text=True, bufsize=1)
        first = json.loads(self.proc.stdout.readline() or "{}")
        if not first.get("ready") or "entailment" not in first.get("nli_labels", []):
            raise RuntimeError(f"TeCoD service did not start ({first}); see tecod.log")

    def send(self, req):
        self.proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("TeCoD service exited; see tecod.log")
        return json.loads(line)

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(60)
        except subprocess.TimeoutExpired:
            self.proc.kill()


class GMemoryService:
    """tools/relbench/gmemory_service.py in G-Memory's own Python 3.12 environment, one JSON line per request."""

    def __init__(self, env, out, llm):
        self.err = open(os.path.join(out, "gmemory.log"), "w")
        # its own environment: no proxies, and none of the harness's packages (PYTHONPATH)
        e = {k: v for k, v in os.environ.items() if "proxy" not in k.lower() and k != "PYTHONPATH"}
        if llm.keep_reasoning:  # DeepSeek's API: G-Memory's own calls in non-thinking mode (reproduction notes)
            e["GMEMORY_THINKING"] = "disabled"
        e.update(OPENAI_API_BASE=llm.base, OPENAI_API_KEY=llm.key,
                 HF_ENDPOINT="https://hf-mirror.com", TOKENIZERS_PARALLELISM="false")
        here = os.path.dirname(os.path.abspath(__file__))
        self.proc = subprocess.Popen([GMEMORY_PYTHON, os.path.join(here, "gmemory_service.py"), "--repo", GMEMORY_REPO,
                                      "--working-dir", os.path.join(out, "gmemory"), "--model", llm.model],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err, env=e, text=True, bufsize=1)
        first = json.loads(self.proc.stdout.readline() or "{}")
        if not first.get("ready"):
            raise RuntimeError("G-Memory service did not start; see gmemory.log")

    def send(self, req):
        self.proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("G-Memory service exited; see gmemory.log")
        return json.loads(line)

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(30)
        except subprocess.TimeoutExpired:
            self.proc.kill()


class Middle:
    def __init__(self, url, mode, out, port, extractor=None, effort=None, prefix=None):
        self.base = f"http://127.0.0.1:{port}"
        self.log = open(os.path.join(out, "middle.log"), "w")
        env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
        if effort and prefix:
            env[f"{prefix}_REASONING_EFFORT"] = effort  # the extractor uses the agents' setting
        self.proc = subprocess.Popen(
            ["./target/release/agentdb-mid", "--db", url, "--pool", "8", "--out", os.path.join(out, "middle"),
             "serve", "--addr", f"127.0.0.1:{port}", "--mode", mode, "--no-etl", *(["--extractor", extractor] if extractor else [])],
            stdout=self.log, stderr=subprocess.STDOUT, env=env)
        self.local = threading.local()
        for _ in range(120):
            if self.proc.poll() is not None:
                raise RuntimeError(f"middle layer exited ({self.proc.returncode}); see middle.log")
            try:
                if self.http.get(f"{self.base}/v1/tools", timeout=5).ok:
                    time.sleep(1)  # a middle layer that could not bind the port exits at once: the answer was not ours
                    if self.proc.poll() is None:
                        return
                    raise RuntimeError(f"middle layer exited ({self.proc.returncode}); port {port} belongs to another process")
            except requests.RequestException:
                pass
            time.sleep(1)
        raise RuntimeError("middle layer did not start")

    @property
    def http(self):
        if not hasattr(self.local, "s"):
            self.local.s = requests.Session()
            self.local.s.trust_env = False
        return self.local.s

    def call(self, name, agent, session, task, args):
        r = self.http.post(f"{self.base}/v1/tools/{name}", json={"agent": agent, "session": session, "task": task, "args": args},
                           timeout=FEATURE_SQL_TIMEOUT_S)
        return r.json()

    def post(self, path, body, timeout=1800):
        return self.http.post(f"{self.base}{path}", json=body, timeout=timeout).json()

    def get(self, path):
        return self.http.get(f"{self.base}{path}", timeout=120).json()

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(30)
        except subprocess.TimeoutExpired:
            self.proc.kill()


# ───────────────────────── database helpers ─────────────────────────

def base_url(url):
    return url.rsplit("/", 1)[0]


def free_port():
    """A port no other process listens on: cells running side by side must never reach each other's middle layer."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def create_run_db(url, template, name):
    with psycopg.connect(f"{base_url(url)}/postgres", autocommit=True) as con:
        con.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
        con.execute(f"CREATE DATABASE {name} TEMPLATE {template}")


def drop_db(url, name):
    with psycopg.connect(f"{base_url(url)}/postgres", autocommit=True) as con:
        con.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")


def copy_rows(con, table, df):
    import io

    cols = ", ".join(c.lower() for c in df.columns)
    with con.cursor() as cur, cur.copy(f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '\\N')") as cp:
        for start in range(0, len(df), 200_000):
            part = df.iloc[start:start + 200_000].copy()
            for c in part.columns:
                if part[c].dtype == object:
                    part[c] = part[c].map(lambda v: v.replace("\x00", "") if isinstance(v, str) else v)
            buf = io.StringIO()
            # rows end with CR LF so that the csv writer quotes every text with a bare CR as well as LF (rel-amazon reviews have
            # both; an unquoted CR ends the COPY with "unquoted carriage return found in data")
            part.to_csv(buf, index=False, header=False, na_rep="\\N", date_format="%Y-%m-%d %H:%M:%S.%f", lineterminator="\r\n")
            cp.write(buf.getvalue())


def read_sql(url, sql, timeout_s=FEATURE_SQL_TIMEOUT_S, search_path=None):
    t0 = time.time()
    with psycopg.connect(url, autocommit=False) as con:
        with con.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL lc_messages = 'C'")
            cur.execute(f"SET LOCAL statement_timeout = {timeout_s * 1000}")
            if search_path:
                cur.execute(f"SET LOCAL search_path = {search_path}")
            cur.execute(sql)
            cols = [d.name for d in cur.description]
            rows = cur.fetchall()
        con.rollback()
    return pd.DataFrame(rows, columns=cols), time.time() - t0


# ───────────────────────── tasks and learner ─────────────────────────

def tname(task):
    return task.replace("-", "_")


def metric_of(task_type):
    return ("roc_auc", True) if task_type == "binary_classification" else ("mae", False)


def score(task_type, y, p):
    from sklearn.metrics import mean_absolute_error, roc_auc_score

    return float(roc_auc_score(y, p)) if task_type == "binary_classification" else float(mean_absolute_error(y, p))


def train_predict(task_type, xtr, ytr, xev):
    import lightgbm as lgb

    t0 = time.time()
    if task_type == "binary_classification":
        m = lgb.LGBMClassifier(objective="binary", **LGB_PARAMS)
        m.fit(xtr, ytr)
        p = m.predict_proba(xev)[:, 1]
    else:
        m = lgb.LGBMRegressor(objective="l1", **LGB_PARAMS)
        m.fit(xtr, ytr)
        p = m.predict(xev)
    imp = sorted(zip(xtr.columns, m.booster_.feature_importance("gain")), key=lambda x: -x[1])
    return p, [(c, round(float(g), 1)) for c, g in imp], time.time() - t0


class FeatureError(Exception):
    pass


def features(url, sql, seeds_table, seeds, ec, search_path=None, timeout_s=FEATURE_SQL_TIMEOUT_S):
    """Run feature SQL against one seed table and check the contract; returns (aligned features, seconds)."""
    if "{seeds}" not in sql:
        raise FeatureError("the SQL must use {seeds} as the seed table")
    q = sql.strip().rstrip(";").replace("{seeds}", seeds_table)
    # one row per seed is the contract: more rows are an error, so the database stops after len(seeds) + 1 rows
    q = f"SELECT * FROM ({q}) AS feature_rows LIMIT {len(seeds) + 1}"
    try:
        df, secs = read_sql(url, q, timeout_s=max(1, int(timeout_s)), search_path=search_path)
    except psycopg.Error as e:
        raise FeatureError(f"SQL error: {str(e).strip()[:1500]}")
    if len(df) > len(seeds):
        raise FeatureError(f"more than {len(seeds)} rows for {len(seeds)} seeds; return one row per seed (check joins that multiply rows)")
    if df.shape[1] < 3:
        raise FeatureError("need the entity key, seed_time and at least one feature column")
    if df.shape[1] - 2 > MAX_FEATURES:
        raise FeatureError(f"{df.shape[1] - 2} feature columns; at most {MAX_FEATURES}")
    source_keys = list(df.columns[:2])
    df = df.rename(columns={df.columns[0]: ec, df.columns[1]: "seed_time"})
    if df.duplicated([ec, "seed_time"]).any():
        raise FeatureError(f"{int(df.duplicated([ec, 'seed_time']).sum())} duplicate (key, seed_time) rows; return one row per seed")
    df["seed_time"] = pd.to_datetime(df["seed_time"])
    merged = seeds[[ec, "seed_time"]].merge(df, on=[ec, "seed_time"], how="left", indicator=True)
    missing = int((merged["_merge"] == "left_only").sum())
    if missing or len(df) != len(seeds):
        raise FeatureError(f"returned {len(df)} rows for {len(seeds)} seeds ({missing} seeds missing); return one row per seed")
    x = merged.drop(columns=[ec, "seed_time", "_merge"])
    if x.columns.duplicated().any():
        raise FeatureError(f"duplicate feature column names: {sorted(set(x.columns[x.columns.duplicated()]))[:10]}")
    bad = []
    for c in x.columns:
        if not pd.api.types.is_numeric_dtype(x[c]):
            conv = pd.to_numeric(x[c], errors="coerce")
            if conv.isna().sum() > x[c].isna().sum():
                bad.append(c)
            else:
                x[c] = conv
    if bad:
        raise FeatureError(f"non-numeric feature columns: {bad[:10]}; encode them as numbers in SQL")
    try:
        result = x.astype(float)
        from delta_features import remember_headers
        remember_headers(sql, result, source_keys)
        return result, secs
    except (TypeError, ValueError) as err:
        raise FeatureError(f"feature columns are not numeric: {str(err)[:200]}")


def quote_ident(c):
    return '"' + str(c).replace('"', '""') + '"'


def select_columns_sql(sql, keys, cols):
    """A feature SQL restricted to some of its columns (keys: its own names for the entity and seed_time columns)."""
    body = sql.strip().rstrip(";")
    return (f"SELECT q.{quote_ident(keys[0])}, q.{quote_ident(keys[1])}, " + ", ".join(f"q.{quote_ident(c)}" for c in cols)
            + f" FROM (\n{body}\n) AS q")


def union_sql(psql, pkeys, pcols, dsql, dkeys, dcols):
    """One feature SQL with the program's columns pcols and the definitions' columns dcols, matched per seed row."""
    p, d = psql.strip().rstrip(";"), dsql.strip().rstrip(";")
    sel = [f"p.{quote_ident(pkeys[0])}", f"p.{quote_ident(pkeys[1])}"] + [f"p.{quote_ident(c)}" for c in pcols] \
        + [f"d.{quote_ident(c)}" for c in dcols]
    return (f"WITH mem_program AS (\n{p}\n),\nmem_definitions AS (\n{d}\n)\nSELECT " + ", ".join(sel)
            + f"\nFROM mem_program p LEFT JOIN mem_definitions d ON d.{quote_ident(dkeys[0])} = p.{quote_ident(pkeys[0])} "
            f"AND d.{quote_ident(dkeys[1])} = p.{quote_ident(pkeys[1])}")


# ───────────────────────── one run ─────────────────────────

class Run:
    def __init__(self, a):
        self.a = a
        self.env = load_env()
        self.url_admin = self.env["AGENTDB_URL"]
        self.timeline = json.load(open(os.path.join(a.prep, "timeline.json")))
        self.tasks = {t: e for t, e in self.timeline["tasks"].items() if not a.tasks or t in a.tasks}
        self.manifest = __import__("yaml").safe_load(open(os.path.join(a.data, "manifest.yaml")))
        self.task_desc = {t: __import__("yaml").safe_load(open(os.path.join(a.data, "tasks", t, "manifest.yaml"))) for t in self.tasks}
        self.db_name = f"relbench_{a.arm.replace('-', '_')}_r{a.run}_{os.getpid()}"
        self.url = f"{base_url(self.url_admin)}/{self.db_name}"
        self.llm = Llm(self.env, a.llm)
        self.llm.effort = a.reasoning_effort or self.llm.effort
        self.arm = ARMS[a.arm]
        self.refs = {}
        # retraining goal (README §1.2, 10-21): the previous cutoff's model, refit on this cutoff's data.
        # task -> (cutoff, final feature SQL whose audit was clean) of this run's latest session
        self.prev_sql = {}
        self.incumbent_frames = {}  # task/cutoff-local, private train/validation values; never test rows
        self.incumbent_work = {}  # charged once if the new arm uses incumbent preflight as its preparation
        self.sql_programs = {}  # SQL-only: latest successful, clean program per task; never other tasks' SQL
        self.targets = {}
        if a.targets_from:
            first = min(int(x) for x in a.cutoffs) if a.cutoffs else 1
            for f in glob.glob(os.path.join(a.targets_from, "sessions", "*.json")):
                if f.endswith(".partial.json"):
                    continue
                r0 = json.load(open(f))
                if r0["k"] == first - 1 and r0.get("final_sql") and (r0.get("audit") or {}).get("result") == "clean":
                    self.prev_sql[r0["task"]] = (r0["k"], r0["final_sql"])
        self.playbooks = {}  # ACE: agent -> playbook text
        self.awm_pool = {}  # AWM: agent -> successful trajectories
        self.awm_workflows = {}  # AWM: agent -> induced workflows (appended to the system prompt)
        self.ace_steps = {}
        # a run resumed at a later cutoff (--cutoffs from k, --targets-from the earlier run, whose sessions before k were
        # copied into --out): the earlier cutoffs' records, and each ACE agent's latest playbook before k
        self.kept_cutoffs = []
        if a.targets_from:
            run0 = os.path.join(a.targets_from, "run.json")
            if os.path.exists(run0):
                self.kept_cutoffs = [c for c in json.load(open(run0))["cutoffs"] if c["k"] < first]
                self.refs.update({(t, c["k"]): v for c in self.kept_cutoffs for t, v in (c.get("reference") or {}).items()})
            latest = {}
            for f in glob.glob(os.path.join(a.targets_from, "playbooks", "*-k*.txt")):
                agent, kk = os.path.basename(f)[:-4].rsplit("-k", 1)
                if int(kk) < first and int(kk) > latest.get(agent, (0, None))[0]:
                    latest[agent] = (int(kk), f)
            for agent, (kk, f) in latest.items():
                self.playbooks[agent] = open(f).read()
                self.ace_steps[agent] = kk
            if self.arm.get("awm"):
                self.restore_awm(a.targets_from, first)
        self.gmem = None
        self.tecod = None
        self.tecod_names = None  # tables and columns of the database, for TeCoD's literal masking
        os.makedirs(os.path.join(a.out, "sessions"), exist_ok=True)

    # data changes and seed tables
    def table(self, name, rows=None):
        """One database table from the dataset files; with `rows`, only rows whose time column is in (rows[0], rows[1]]."""
        import pyarrow.parquet as pq

        path = os.path.join(self.a.data, "db", f"{name}.parquet")
        tc = self.manifest["tables"][name].get("time_col")
        if rows is None or not tc:
            return pd.read_parquet(path)
        lo, hi = rows
        return pq.read_table(path, filters=[(tc, ">", lo), (tc, "<=", hi)]).to_pandas()

    def append(self, prev, cur):
        t0, n = time.time(), {}
        with psycopg.connect(self.url, autocommit=False) as con:
            for name, spec in self.manifest["tables"].items():
                tc = spec.get("time_col")
                if not tc:
                    continue
                part = self.table(name, (prev, cur))
                if len(part):
                    copy_rows(con, name.lower(), part)
                    # one ETL batch per appended table, as metric-bench logs its data changes
                    con.execute("INSERT INTO etl_batch_log (table_name, batch_id, note) SELECT %s, coalesce(max(batch_id), 0) + 1, %s "
                                "FROM etl_batch_log WHERE table_name = %s", (name.lower(), f"append ({prev}, {cur}]", name.lower()))
                n[name.lower()] = len(part)
            con.commit()
        with psycopg.connect(self.url, autocommit=True) as con:
            for name in self.manifest["tables"]:
                con.execute(f"ANALYZE {name.lower()}")
        return {"rows": n, "seconds": time.time() - t0}

    def seed_tables(self, k):
        """Create schema task with <t>_train / _train_sample / _val (labelled) and _test (unlabelled) for cutoff k."""
        seeds = {}
        with psycopg.connect(self.url, autocommit=True) as con:
            con.execute("DROP SCHEMA IF EXISTS task CASCADE")
            con.execute("CREATE SCHEMA task")
            for t, e in self.tasks.items():
                ec, tc, yc = e["entity_col"].lower(), e["time_col"], e["target_col"].lower()
                d = os.path.join(self.a.prep, "tasks", t, f"k{k}")
                s = {}
                for split in ("train", "val", "test"):
                    df = pd.read_parquet(os.path.join(d, f"{split}.parquet"))
                    df.columns = [c.lower() for c in df.columns]
                    df = df.rename(columns={tc.lower(): "seed_time"})
                    df["seed_time"] = pd.to_datetime(df["seed_time"])
                    s[split] = df
                rng = np.random.RandomState(SAMPLE_SEED)
                tr = s["train"]
                s["train_sample"] = tr.iloc[rng.permutation(len(tr))[:SAMPLE_SIZE]].reset_index(drop=True) if len(tr) > SAMPLE_SIZE else tr
                for split, cols in (("train", [ec, "seed_time", yc]), ("train_sample", [ec, "seed_time", yc]),
                                    ("val", [ec, "seed_time", yc]), ("test", [ec, "seed_time"])):
                    df = s[split][cols]
                    types = {ec: "bigint" if pd.api.types.is_integer_dtype(df[ec]) else "text", "seed_time": "timestamp",
                             yc: "double precision"}
                    con.execute(f"CREATE TABLE task.{tname(t)}_{split} ({', '.join(f'{c} {types[c]}' for c in cols)})")
                    copy_rows(con, f"task.{tname(t)}_{split}", df)
                    con.execute(f"ANALYZE task.{tname(t)}_{split}")
                seeds[t] = s
        return seeds

    def reference_sql(self, t):
        """Entity-table columns only (the input of RelBench's LightGBM baseline): numeric columns and days since each time column."""
        e = self.tasks[t]
        et = e["entity_table"]
        spec = self.manifest["tables"][et]
        pk = spec["pkey"].lower()
        df = self.table(et)
        fk = {c.lower() for c in (spec.get("fkeys") or {})}
        cols = []
        for c in df.columns:
            lc = c.lower()
            if lc == pk or lc in fk:
                continue
            if pd.api.types.is_bool_dtype(df[c]) or pd.api.types.is_numeric_dtype(df[c]):
                cols.append(f"e.{lc}::double precision AS {lc}")
            elif pd.api.types.is_datetime64_any_dtype(df[c]):
                cols.append(f"extract(epoch from (s.seed_time - e.{lc})) / 86400.0 AS days_since_{lc}")
        if not cols:
            cols = ["0.0 AS constant"]
        ec = e["entity_col"].lower()
        return f"SELECT s.{ec}, s.seed_time, {', '.join(cols)} FROM {{seeds}} s LEFT JOIN {et.lower()} e ON e.{pk} = s.{ec}"

    def evaluate(self, t, k, sql, seeds, search_path=None):
        """Validation and test scores of a feature SQL (train on the 50k sample)."""
        e = self.tasks[t]
        ec, yc = e["entity_col"].lower(), e["target_col"].lower()
        test_labels = pd.read_parquet(os.path.join(self.a.prep, "tasks", t, f"k{k}", "test.parquet"))
        test_labels.columns = [c.lower() for c in test_labels.columns]
        test_labels = test_labels.rename(columns={e["time_col"].lower(): "seed_time"})
        test_labels["seed_time"] = pd.to_datetime(test_labels["seed_time"])
        xtr, s1 = features(self.url, sql, f"task.{tname(t)}_train_sample", seeds["train_sample"], ec, search_path=search_path)
        xva, s2 = features(self.url, sql, f"task.{tname(t)}_val", seeds["val"], ec, search_path=search_path)
        xte, s3 = features(self.url, sql, f"task.{tname(t)}_test", seeds["test"], ec, search_path=search_path)
        ytest = seeds["test"][[ec, "seed_time"]].merge(test_labels[[ec, "seed_time", yc]], on=[ec, "seed_time"], how="left")[yc]
        pv, _, _ = train_predict(e["task_type"], xtr, seeds["train_sample"][yc], xva)
        pt, _, tt = train_predict(e["task_type"], xtr, seeds["train_sample"][yc], xte)
        return {"val": score(e["task_type"], seeds["val"][yc], pv), "test": score(e["task_type"], ytest, pt),
                "sql_seconds": s1 + s2 + s3, "train_seconds": tt, "n_features": xtr.shape[1]}

    def audit(self, t, k, sql, seeds):
        """Leakage audit: recompute features for the latest training seeds on views that hide rows after that seed time."""
        e = self.tasks[t]
        ec = e["entity_col"].lower()
        tr = seeds["train_sample"]
        tstar = tr["seed_time"].max()
        sub = tr[tr["seed_time"] == tstar].sort_values(ec).head(AUDIT_LEAK_SEEDS).reset_index(drop=True)
        schema = f"audit_{tname(t)}_k{k}"
        # tables named as public.x read the audit views too
        hidden_sql = in_schema(sql, schema)
        with psycopg.connect(self.url, autocommit=True) as con:
            con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            con.execute(f"CREATE SCHEMA {schema}")
            for name, spec in self.manifest["tables"].items():
                tc = spec.get("time_col")
                cond = f" WHERE {tc.lower()} <= '{tstar}'" if tc else ""
                con.execute(f"CREATE VIEW {schema}.{name.lower()} AS SELECT * FROM public.{name.lower()}{cond}")
            con.execute(f"CREATE TABLE {schema}.seeds AS SELECT * FROM task.{tname(t)}_train_sample WHERE false")
            copy_rows(con, f"{schema}.seeds", sub[[c for c in sub.columns]])
            con.execute(f"ANALYZE {schema}.seeds")
        try:
            normal, _ = features(self.url, sql, f"{schema}.seeds", sub, ec)
            hidden, _ = features(self.url, hidden_sql, f"{schema}.seeds", sub, ec, search_path=f"{schema}, public")
        except FeatureError as err:
            return {"result": "error", "why": str(err)[:300]}
        finally:
            with psycopg.connect(self.url, autocommit=True) as con:
                con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        a, b = normal.to_numpy(), hidden.to_numpy()
        diff = ~np.isclose(a, b, rtol=1e-6, atol=1e-9, equal_nan=True)
        cols = [c for c, d in zip(normal.columns, diff.any(axis=0)) if d]
        return {"result": "leak" if diff.any() else "clean", "seed_time": str(tstar), "seeds": len(sub),
                "cells_differing": int(diff.sum()), "columns_differing": cols[:20], "all_columns_differing": cols}

    # ───────── one session ─────────
    def system_prompt(self, t, k, seeds):
        e, d = self.tasks[t], self.task_desc[t]
        cut = e["cutoffs"][k - 1]
        metric, higher = metric_of(e["task_type"])
        ec = e["entity_col"].lower()
        spec = self.manifest["tables"][e["entity_table"]]
        n_times = seeds["train"]["seed_time"].nunique()
        guided = self.arm.get("budget_guidance") and k > 1
        model_calls = self.arm.get("reuse_llm_limit", MAX_LLM_CALLS) if guided else MAX_LLM_CALLS
        budget_detail = (f" At most {self.arm['reuse_tool_limit']} executed agent tools in total. "
                         f"Feature SQL statements stop after {self.validation_timeout(k)} seconds. "
                         "When memory provides a checked incumbent, it is already validated; do not repeat that validation. "
                         "Use at most one response for essential exploration, then validate one deliberate improvement. "
                         "On the last response only validate_features and submit are available. "
                         "A failed refinement retains the checked incumbent."
                         if guided else "")
        if self.arm.get('delta_refinement'):
            budget_detail = (f" Feature SQL statements stop after {self.validation_timeout(k)} seconds. "
                             "Validate a compact working query early and keep each query within that limit.")
            if guided:
                budget_detail += (f" At most {self.arm['reuse_tool_limit']} executed agent tools in total. "
                                  "With a checked base, validate_additions tests a small complementary query and keeps the best checked result. "
                                  "A clean trial has priority over submit; repair errors within the same budget. "
                                  "On the last response only the current validation action and, after a clean trial, submit are available.")
        return f"""You are a data scientist agent working on a PostgreSQL database: {self.manifest.get('description', '')}
Your job is to engineer features with SQL for one prediction task. A fixed LightGBM model is trained on your features; you cannot change the model.

Task: {d['description']}
Entity: {e['entity_table'].lower()}.{spec['pkey'].lower()} (column `{ec}` in the seed tables). Target: `{e['target_col'].lower()}` ({e['task_type'].replace('_', ' ')}); metric: {metric}, {'higher' if higher else 'lower'} is better.
Each seed row ({ec}, seed_time) asks for a prediction made at seed_time; the target describes the {e['timedelta']} after seed_time.
Seed tables: task.{tname(t)}_train (labelled training seeds, {len(seeds['train'])} rows over {n_times} seed times), task.{tname(t)}_val (labelled validation seeds at {cut['val_timestamp'][:10]}), task.{tname(t)}_test (unlabelled seeds at {cut['test_timestamp'][:10]}). The other tables are in schema public and hold data up to {cut['test_timestamp'][:10]}.

Feature SQL contract: one SELECT statement that uses {{seeds}} as the seed table (columns {ec}, seed_time) and returns exactly one row per seed row, with {ec} and seed_time as the first two columns followed by numeric feature columns (at most {MAX_FEATURES}). A feature may only use rows whose time is at or before the seed row's seed_time; using later rows is leakage and makes the features invalid.

Tools: list_tables, describe_table, join_path, check_join and run_sql explore the database; the first four cover the tables in schema public, and the seed tables are read with run_sql (read-only, at most 50 rows returned). validate_features(sql) computes your features on a {SAMPLE_SIZE}-row training sample and on the validation seeds, trains the model and returns the validation {metric}. submit(sql) ends the session with your final features.
Budget: at most {MAX_VALIDATIONS} validations and {model_calls} model calls; the session also ends after {PATIENCE} validations in a row without improvement. If you do not submit, your best validated features are used.{budget_detail}""" + (
            f"\n\nRetraining goal: this task's model from the previous cutoff ({e['cutoffs'][k - 2]['test_timestamp'][:10]}), refit on this cutoff's data, "
            f"reaches validation {metric} {self.target(t, k):.5f}. Once your features reach that score you may make one more attempt to improve them: "
            f"one more validation within the next {self.post_goal_window(k)} model calls, after which the session ends with your best validated features." if self.target(t, k) is not None else "") + ("""

Shared memory: agents on this database publish verified feature definitions and feature programs. Start with find_program (this task's verified program from an earlier cutoff: its complete feature SQL when it still runs, and a feature SQL of its definitions) and find_features (definitions for the entity table, with a feature SQL of them for these seed tables). If they return a feature SQL, validate it first (the complete program SQL first); explore the tables and extend the SQL only to improve on it. compose_features compiles chosen definitions (by key) into a feature SQL.""" if self.arm.get("feature_memory") and not self.arm.get("push_memory") else "") + ("""

Shared memory: agents on this database publish verified feature definitions and feature programs. This task's verified program from an earlier cutoff (its complete feature SQL when it still runs, and a feature SQL of its definitions) and the verified definitions for the entity table (with a feature SQL of them for these seed tables) are looked up for you and follow the task line. If they include a feature SQL, validate it first (the complete program SQL first); explore the tables and extend the SQL only to improve on it. compose_features compiles chosen definitions (by key) into a feature SQL.""" if self.arm.get("push_memory") and not self.arm.get("select_start") else "") + ("""

Shared memory: agents on this database publish verified feature definitions and feature programs. When this task has a verified program from an earlier cutoff, the memory validates it on this cutoff's data, together with the program extended by verified definitions that other agents published for the entity; the better one becomes your current best features and follows the task line with its SQL and validation score. Explore the tables and extend that SQL only to improve on it. """ + (
            "Otherwise (this task has no program yet) the verified definitions that other agents published for the entity follow "
            "the task line as keys and meanings, without SQL; they were made for other tasks, so explore this task's tables and "
            "use them only where they fit." if self.arm.get("first_keys_only") else
            "Otherwise the memory's lookups follow the task line: if they include a feature SQL, validate it first.")
            + " compose_features compiles verified definitions (by key) into a feature SQL." if self.arm.get("select_start") else "") + (
            "\n\nSQL memory: successful sessions save their complete audited feature SQL for this task. Start with find_program "
            "(this task's verified program from an earlier cutoff: its complete feature SQL when it still runs). If it returns "
            "a feature SQL, validate it first; explore the tables and extend the SQL only to improve on it."
            if self.arm.get("sql_memory") else "") + (
            "\n\n" + open(os.path.join(ACE_DIR, "appworld_playbook_block.txt")).read().replace(
                "{{ playbook }}", self.playbooks.get(f"{tname(t)}-agent", ACE_EMPTY_PLAYBOOK)).rstrip()
            + "\nWhen you call validate_features or submit, list in bullet_ids the playbook bullets you used." if self.arm.get("ace") else "") + (
            "\n\n" + self.awm_workflows[f"{tname(t)}-agent"] if self.arm.get("awm") and self.awm_workflows.get(f"{tname(t)}-agent") else "")

    def target(self, t, k):
        """Validation score of this run's previous-cutoff model of task t, refit on cutoff k (none at the first cutoff)."""
        return (self.targets.get((t, k)) or {}).get("val")

    def post_goal_window(self, k, calls_used=0):
        if self.arm.get("budget_guidance") and k > 1:
            return max(0, min(POST_GOAL_LLM_CALLS, self.arm["reuse_llm_limit"] - calls_used))
        return POST_GOAL_LLM_CALLS

    def validation_timeout(self, k):
        return (self.arm.get("reuse_validation_timeout", FEATURE_SQL_TIMEOUT_S) if k > 1
                else self.arm.get('cold_validation_timeout',FEATURE_SQL_TIMEOUT_S))

    def remaining_budget_message(self, k, calls_used, tools_used):
        if not self.arm.get("budget_guidance") or k <= 1:
            return None
        remaining_calls = max(0, self.arm["reuse_llm_limit"] - calls_used)
        remaining_tools = max(0, self.arm["reuse_tool_limit"] - tools_used)
        if self.arm.get("delta_refinement"):
            return (f"Remaining session budget: {remaining_calls} model response(s), {remaining_tools} tool call(s). "
                    "Use validate_additions for a small complementary feature query on the checked base. "
                    "If no checked base is available, validate_features creates one. Repair a failed query within this budget; "
                    "after a clean trial, submit without sql to keep the best checked result.")
        return (f"Remaining session budget: {remaining_calls} model response(s), {remaining_tools} executed tool call(s). "
                "Validate a concrete feature refinement now, or submit without sql to retain the checked incumbent. "
                "Exploration alone does not improve it. The SQL must still obey seed_time and the statement limit.")

    def early_validation_hint(self, k, calls_used=0, validations_used=0):
        deadline = self.arm.get("cold_first_validation_by")
        if k != 1 or not deadline or validations_used:
            return None
        return (f"Make your first validate_features attempt no later than model response {deadline}; "
                f"{max(0, deadline - calls_used)} response(s) remain before that deadline. "
                "Build a simple working SQL from the known schema, preserving every seed row. "
                "Use validation feedback to refine it afterwards; do not spend the whole search on probes.")

    def step_tools(self, k, calls_used, tools_used, validations_used=0):
        specs = self.tool_specs()
        deadline = self.arm.get("cold_first_validation_by")
        if k == 1 and deadline and calls_used >= deadline - 1 and validations_used == 0:
            return [s for s in specs if s["function"]["name"] == "validate_features"]
        if (self.arm.get("budget_guidance") and k > 1
                and (calls_used >= self.arm["reuse_llm_limit"] - 1 or tools_used >= self.arm["reuse_tool_limit"] - 1)):
            return [s for s in specs if s["function"]["name"] in ("validate_features", "submit")]
        return specs

    def delta_step_tools(self, k, calls_used, tools_used, validations_used, has_base, clean_trial):
        specs = self.step_tools(k,calls_used,tools_used,validations_used)
        if not self.arm.get('delta_refinement'):
            return specs
        if k<=1 or not has_base:
            return [s for s in specs if s['function']['name']!='validate_additions']
        specs = [s for s in self.tool_specs() if s['function']['name']!='validate_features']
        if not clean_trial:
            specs = [s for s in specs if s['function']['name']!='submit']
        if (calls_used>=self.arm['reuse_llm_limit']-1 or tools_used>=self.arm['reuse_tool_limit']-1):
            specs = [s for s in specs if s['function']['name'] in ('validate_additions','submit')]
        return specs

    def audit_rejection_feedback(self, audit):
        if self.arm.get("audit_diagnostics") and audit.get("result") not in ("clean", "leak"):
            return {"audit_error": {"counted": False, "reason": audit.get("why") or "audit did not finish cleanly",
                                    "note": "Correct this SQL or seed-row error and validate again. Preserve every seed row "
                                            "even when related rows are hidden. An audit error is not evidence of safety."}}
        return {"leak": {"counted": False, "columns_reading_data_after_seed_time": audit.get("columns_differing"),
                         "note": "these columns change when rows after seed_time are hidden; this validation does not count"}}

    def incumbent(self, t, k, seeds):
        """Refit the previous cutoff's final feature SQL on cutoff k and score it on the validation seeds (no LLM)."""
        if self.arm.get("reuse_goal_frames"):
            detail = self.prepare_incumbent(t, k, seeds)
            work = self.incumbent_work.get((t, k))
            return {**detail, "seconds": work["seconds"], "charged_to_session": True} if work else detail
        prev = self.prev_sql.get(t)
        if not prev or prev[0] != k - 1:
            return {"val": None, "why": "no previous model"}
        e = self.tasks[t]
        ec, yc = e["entity_col"].lower(), e["target_col"].lower()
        t0 = time.time()
        for attempt in (1, 2):
            try:
                xtr, _ = features(self.url, prev[1], f"task.{tname(t)}_train_sample", seeds["train_sample"], ec)
                xva, _ = features(self.url, prev[1], f"task.{tname(t)}_val", seeds["val"], ec)
                p, _, _ = train_predict(e["task_type"], xtr, seeds["train_sample"][yc], xva)
                val = score(e["task_type"], seeds["val"][yc], p)
                break
            except Exception as err:  # noqa: BLE001 - a previous model that no longer runs gives no goal
                # a statement timeout can come from load (cells run side by side): one more try before giving up the goal
                if attempt == 1 and "statement timeout" in str(err):
                    continue
                return {"val": None, "why": f"previous model failed: {str(err)[:200]}", "attempts": attempt, "seconds": time.time() - t0}
        leak = self.audit(t, k, prev[1], seeds)
        if leak.get("result") == "leak":
            # rule (10-21, all arms): columns of the model in use that read later rows on this cutoff are dropped and the
            # rest refit, as a team would do with an incumbent whose leak shows up on new data (an audit is a sample)
            bad = set(leak.get("all_columns_differing") or [])
            keep = [c for c in xtr.columns if c not in bad]
            if not keep:
                return {"val": None, "why": "every column of the previous model reads rows after seed_time on this cutoff",
                        "seconds": time.time() - t0}
            p, _, _ = train_predict(e["task_type"], xtr[keep], seeds["train_sample"][yc], xva[keep])
            return {"val": score(e["task_type"], seeds["val"][yc], p), "from_cutoff": prev[0], "dropped_leaking": sorted(bad),
                    "seconds": time.time() - t0}
        return {"val": val, "from_cutoff": prev[0], "seconds": time.time() - t0}

    def prepare_incumbent(self, t, k, seeds):
        """Keep a clean current refit; all attempts are later charged to this arm.

        The common benchmark target used to discard these values. Reusing them
        does not make them free: their complete non-audit duration and fits are
        allocated to this task's measured session, including failed preflights.
        """
        prev = self.prev_sql.get(t)
        if not prev or prev[0] != k - 1:
            return {"val": None, "why": "no previous model"}
        e = self.tasks[t]
        ec, yc = e["entity_col"].lower(), e["target_col"].lower()
        started = time.time()
        work = {"audit_seconds": 0.0, "sql_seconds": 0.0, "feature_fits": [], "cached": False}
        self.incumbent_frames.pop((t, k), None)
        if self.arm.get('skip_failed_refit'):
            if not hasattr(self,'refit_inputs'):
                self.refit_inputs = {}
            aligned = [ec,'seed_time',yc]
            self.refit_inputs[(t,k)] = (prev,seeds['train_sample'][aligned].copy(),seeds['val'][aligned].copy())

        def fit(xt, xv):
            ts, failed = time.time(), None
            try:
                return train_predict(e["task_type"], xt, seeds["train_sample"][yc], xv)
            except Exception as err:
                failed = type(err).__name__
                raise
            finally:
                work["feature_fits"].append({"purpose": "current_incumbent_preflight", "train_rows": len(xt),
                                              "features": xt.shape[1], "seconds": time.time() - ts, "error": failed})

        try:
            attempts = self.arm.get('current_refit_attempts',2)
            work["attempt_timeouts"] = []
            for attempt in range(1,attempts+1):
                # mavra-retry (v10): a refit cut by the short limit is retried once under the standard statement limit
                timeout = (self.arm.get('current_refit_retry_timeout') if attempt > 1 else None) or self.arm.get('current_refit_timeout')
                options = {'timeout_s':timeout} if timeout else {}
                work["attempt_timeouts"].append(timeout)
                try:
                    xtr, s1 = features(self.url, prev[1], f"task.{tname(t)}_train_sample", seeds["train_sample"], ec, **options)
                    work["sql_seconds"] += s1
                    xva, s2 = features(self.url, prev[1], f"task.{tname(t)}_val", seeds["val"], ec, **options)
                    work["sql_seconds"] += s2
                    prediction, importance, _ = fit(xtr, xva)
                    val = score(e["task_type"], seeds["val"][yc], prediction)
                    break
                except Exception as err:
                    if attempt < attempts and "statement timeout" in str(err):
                        continue
                    return {"val": None, "why": f"previous model failed: {str(err)[:200]}", "attempts": attempt}
            ta = time.time()
            try:
                audited = self.audit(t, k, prev[1], seeds)
            finally:
                work["audit_seconds"] += time.time() - ta
            work["audit"] = audited.get("result")
            kept_sql, kept_xtr, kept_xva, dropped = prev[1], xtr, xva, []
            if audited.get("result") == "leak":
                bad = set(audited.get("all_columns_differing") or [])
                keep = [c for c in xtr if c not in bad]
                if not bad or not keep:
                    return {"val": None, "why": "incumbent has no identified clean output subset"}
                headers, seconds = read_sql(self.url, f"SELECT * FROM ({prev[1].strip().rstrip(';').replace('{seeds}', f'task.{tname(t)}_val')}) q LIMIT 0")
                work["sql_seconds"] += seconds
                kept_sql = select_columns_sql(prev[1], list(headers.columns[:2]), keep)
                check = {"sql_seconds": 0.0}
                self.check_columns(t, k, kept_sql, seeds, xva[keep], check, timeout_s=SELECT_CHECK_TIMEOUT_S)
                work["sql_seconds"] += check["sql_seconds"]
                ta = time.time()
                try:
                    projected_audit = self.audit(t, k, kept_sql, seeds)
                finally:
                    work["audit_seconds"] += time.time() - ta
                work["projection_audit"] = projected_audit.get("result")
                if projected_audit.get("result") != "clean":
                    return {"val": None, "why": "projected incumbent did not pass a fresh audit",
                            "audit_error": projected_audit.get("why")}
                kept_xtr, kept_xva, dropped = xtr[keep], xva[keep], sorted(bad)
                prediction, importance, _ = fit(kept_xtr, kept_xva)
                val = score(e["task_type"], seeds["val"][yc], prediction)
            elif audited.get("result") != "clean":
                return {"val": None, "why": "incumbent audit did not pass", "audit_error": audited.get("why")}
            aligned = [ec, "seed_time", yc]
            self.incumbent_frames[(t, k)] = {"previous": prev, "sql": kept_sql, "val": val, "importance": importance,
                                             "train": kept_xtr, "valid": kept_xva, "dropped_leaking": dropped,
                                             "train_seeds": seeds["train_sample"][aligned].copy(),
                                             "valid_seeds": seeds["val"][aligned].copy(), "audit": "clean"}
            work["cached"] = True
            if not self.start_is_informative(xtr):
                return {"val": None, "fallback_val": val, "fallback_only": True, "from_cutoff": prev[0],
                        "current_refit_retained": True, "why": "previous program has no varying training features"}
            return {"val": val, "from_cutoff": prev[0], "current_refit_retained": True, "dropped_leaking": dropped}
        except Exception as err:
            return {"val": None, "why": f"incumbent preparation failed: {str(err)[:200]}"}
        finally:
            work["seconds"] = time.time() - started
            work["agent_seconds"] = max(0.0, work["seconds"] - work["audit_seconds"])
            self.incumbent_work[(t, k)] = work

    def current_incumbent(self, t, k, seeds):
        cached = self.incumbent_frames.get((t, k)) if self.arm.get("reuse_goal_frames") else None
        if not cached or cached["audit"] != "clean" or self.prev_sql.get(t) != cached["previous"]:
            return None
        e = self.tasks[t]
        cols = [e["entity_col"].lower(), "seed_time", e["target_col"].lower()]
        if not (cached["train_seeds"].equals(seeds["train_sample"][cols])
                and cached["valid_seeds"].equals(seeds["val"][cols])):
            return None
        return cached

    def start_is_informative(self, train):
        """Constant defaults remain fallbacks, using training values alone."""
        if not self.arm.get("require_start_signal"):
            return True
        return train is not None and bool((train.nunique(dropna=False) > 1).any())

    @staticmethod
    def constant_start_message():
        return ("The checked default has no varying training features. It is kept only as an emergency fallback, "
                "not as a feature-search starting point. Build task-relevant relational features and validate a working "
                "SQL early; its best clean validation will be retained.")

    def charge_incumbent_work(self, t, k, rec):
        if not self.arm.get("reuse_goal_frames") or k <= 1:
            return
        charged = self.incumbent_work.pop((t, k), None)
        if charged:
            rec["charged_current_refit"] = charged
            rec["agent_seconds"] += charged["agent_seconds"]
            rec.setdefault("feature_fits", []).extend(charged["feature_fits"])
        self.incumbent_frames.pop((t, k), None)

    def cached_start(self, t, k, seeds, cached):
        """Start from the exact freshly audited values, without re-running SQL."""
        from feature_selection import select_subset

        started = time.time()
        e = self.tasks[t]
        xtr, xva, sql = cached["train"], cached["valid"], cached["sql"]
        original = {"name": "program", "sql": sql, "val": cached["val"], "columns": list(xtr),
                    "importance": cached["importance"], "from_cutoff": e["cutoffs"][k - 2]["test_timestamp"],
                    "source": "current audited refit", "dropped_leaking": cached.get("dropped_leaking", [])}
        choice, candidates = original, [original]
        rec = {"audit_seconds": 0.0, "sql_seconds": 0.0, "train_seconds": 0.0, "cached_current_refit": True,
               "definitions_offered": 0, "extension_skipped": "reuse the complete audited incumbent; agent may compose a refinement",
               "pruning_closed": True}
        # A speculative projection of an expensive program would need another
        # expensive SQL reproduction/audit. Keep that program intact instead.
        work = self.incumbent_work.get((t, k), {})
        if work.get("sql_seconds", float("inf")) <= 20 and work.get("agent_seconds", float("inf")) <= 60:
            try:
                selected = select_subset(xtr, seeds["train_sample"][e["target_col"].lower()], xva,
                                         seeds["val"][e["target_col"].lower()], cached["importance"], cached["val"],
                                         metric_of(e["task_type"])[1],
                                         lambda a, b, c: self.fit_feature_model(e["task_type"], a, b, c, "cached_start_subset"),
                                         lambda y, p: score(e["task_type"], y, p))
                rec["subset_selection"] = [{key: value for key, value in selected.items() if key != "chosen"}]
                rec["train_seconds"] += selected["train_seconds"]
                best = selected["chosen"]
                if best["columns"] != list(xtr):
                    headers, _ = read_sql(self.url, f"SELECT * FROM ({sql.strip().rstrip(';').replace('{seeds}', f'task.{tname(t)}_val')}) q LIMIT 0")
                    projected = select_columns_sql(sql, list(headers.columns[:2]), best["columns"])
                    self.check_columns(t, k, projected, seeds, xva[best["columns"]], rec, timeout_s=SELECT_CHECK_TIMEOUT_S)
                    ta = time.time()
                    try:
                        audit = self.audit(t, k, projected, seeds)
                    finally:
                        rec["audit_seconds"] += time.time() - ta
                    if audit.get("result") == "clean":
                        choice = {**original, "name": "program_pruned", "sql": projected, "val": best["val"],
                                  "columns": best["columns"], "importance": best["importance"]}
                        candidates.append(choice)
                    else:
                        rec["projection_rejected"] = audit.get("result")
            except Exception as err:
                rec["pruning_error"] = str(err)[:300]
        else:
            rec["pruning_skipped"] = "the cached SQL was expensive; preserve its complete checked output"
        rec["candidates"] = [{key: value for key, value in c.items() if key not in ("sql", "importance", "columns")}
                             | {"n_features": len(c["columns"])} for c in candidates]
        rec["chosen"] = {**choice, "importance": [c for c, _ in choice["importance"][:30]],
                         "top": choice["importance"][:10], "never_split": sum(1 for _, g in choice["importance"] if g == 0)}
        rec["_frames"] = (choice["sql"], xtr[choice["columns"]], xva[choice["columns"]], choice["importance"])
        rec["seconds"] = time.time() - started
        return rec

    def select_start(self, t, k, seeds, prog, feats, middle, agent, sid):
        """MAVRA's start selection (arm mavra-select, 11-08). On this cutoff's data, without model calls, validate (P) the
        task's program -- its complete SQL when it still runs, else its definitions; columns that read rows after
        seed_time here are dropped, as for the goal -- and (U) P extended with the verified definitions other agents
        published for the same entity (the definitions' columns ranked by gain in one fit together with P's, P's
        never-split columns making room under the column cap). The better validation score starts the session.
        Returns None when there is no program; otherwise a record with the candidates and the chosen SQL.
        Arm mavra-select2 (select_budget) bounds its time: each statement of the program gets SELECT_P_TIMEOUT_S, and a
        program over it falls back to its definitions when their estimated time fits; the extension is tried only after
        a program that took at most SELECT_EXTEND_MAX_P_S, and only when its definitions' estimated time (timed on the
        check seeds first) is no more than the program's."""
        cached = self.current_incumbent(t, k, seeds)
        if cached and (prog.get("program_sql") or prog.get("sql")) == cached["sql"]:
            return self.cached_start(t, k, seeds, cached)
        if self.arm.get('skip_failed_refit') and not cached:
            bound = getattr(self,'refit_inputs',{}).get((t,k))
            work = getattr(self,'incumbent_work',{}).get((t,k))
            if bound and work and not work['cached']:
                e = self.tasks[t]
                cols = [e['entity_col'].lower(),'seed_time',e['target_col'].lower()]
                if (bound[0]==self.prev_sql.get(t) and (prog.get('program_sql') or prog.get('sql'))==bound[0][1]
                        and bound[1].equals(seeds['train_sample'][cols]) and bound[2].equals(seeds['val'][cols])):
                    return {'chosen':None,'candidates':[],'audit_seconds':0.0,'sql_seconds':0.0,'train_seconds':0.0,
                            'seconds':0.0,'skipped_failed_current_refit':True}
        made = []  # the probe schema, dropped at the end
        try:
            return self._select_start(t, k, seeds, prog, feats, middle, agent, sid, made)
        finally:
            if made:
                with psycopg.connect(self.url, autocommit=True) as con:
                    con.execute(f"DROP SCHEMA IF EXISTS {made[0]} CASCADE")

    def fit_feature_model(self, task_type, xtrain, ytrain, xvalid, purpose):
        """Keep the unchanged learner, recording every internal fit as well as agent validations."""
        started, failed = time.time(), None
        try:
            return train_predict(task_type, xtrain, ytrain, xvalid)
        except Exception as err:
            failed = type(err).__name__
            raise
        finally:
            ledger = getattr(self, "_fit_ledger", None)
            if ledger is not None:
                ledger.append({"purpose": purpose, "train_rows": len(xtrain), "features": xtrain.shape[1],
                               "seconds": time.time() - started, "error": failed})

    def typed_reference_start(self, t, k, seeds):
        """Method-owned entity views; the framework common reference stays unchanged."""
        import pyarrow.parquet as pq
        from typed_attributes import compile_view, schema_columns

        started = time.time()
        e = self.tasks[t]
        spec = self.manifest['tables'][e['entity_table']]
        columns = schema_columns(pq.read_schema(os.path.join(self.a.data,'db',e['entity_table']+'.parquet')))
        ec,yc = e['entity_col'].lower(),e['target_col'].lower()
        metric,higher = metric_of(e['task_type'])
        record = {'candidates':[], 'audit_seconds':0.0,'sql_seconds':0.0,'train_seconds':0.0,
                  'selection_split':'validation','framework_reference_changed':False}
        best,seen = None,set()
        for expanded,kind in ((False,'numeric_date'),(True,'typed')):
            sql,_ = compile_view(e['entity_table'],spec['pkey'],ec,spec.get('time_col'),
                                  list(spec.get('fkeys') or {}),columns,expanded,max_features=MAX_FEATURES)
            item = {'kind':kind,'audit_seconds':0.0,'sql_seconds':0.0,'train_seconds':0.0}
            record['candidates'].append(item)
            if sql in seen:
                item['duplicate_sql'] = True
                continue
            seen.add(sql)
            began = time.time()
            try:
                xtr,s1 = features(self.url,sql,f'task.{tname(t)}_train_sample',seeds['train_sample'],ec,
                                   timeout_s=self.validation_timeout(k))
                item['sql_seconds'] += s1
                xva,s2 = features(self.url,sql,f'task.{tname(t)}_val',seeds['val'],ec,
                                   timeout_s=self.validation_timeout(k))
                item['sql_seconds'] += s2
                pred,imp,tt = self.fit_feature_model(e['task_type'],xtr,seeds['train_sample'][yc],xva,
                                                    'reference_start_'+kind)
                val = score(e['task_type'],seeds['val'][yc],pred)
                item['train_seconds'] += tt
                ta = time.time()
                audit = self.audit(t,k,sql,seeds)
                item['audit_seconds'] += time.time()-ta
                sanitized,repaired = self.sanitize_candidate(t,k,seeds,sql,xtr,xva,audit)
                if sanitized:
                    item['sanitization'] = sanitized
                    item['audit_seconds'] += sanitized['audit_seconds']
                    item['train_seconds'] += sanitized['train_seconds']
                    item['sql_seconds'] += sanitized['sql_seconds']
                    if repaired:
                        sql,xtr,xva,imp,val = repaired
                        audit = {'result':'clean','source':'checked_projection'}
                item.update(val=val,audit=audit.get('result'),columns=list(xtr),
                            sql_sha256=hashlib.sha256(sql.encode()).hexdigest())
                if audit.get('result')=='clean' and (best is None or (val>best[0] if higher else val<best[0])):
                    best = (val,(sql,xtr,xva,imp),kind)
            except Exception as err:
                item['error'] = f'{type(err).__name__}: {str(err)[:300]}'
            finally:
                item['seconds'] = time.time()-began
                for key in ('audit_seconds','sql_seconds','train_seconds'):
                    record[key] += item[key]
        record['seconds'] = time.time()-started
        if best is None:
            record.update(audit='error',error='no entity view passed a fresh audit')
            return None,None,record
        val,frames,kind = best
        record.update(audit='clean',val=val,chosen={'kind':kind,'columns':list(frames[1]),
                      'sql_sha256':hashlib.sha256(frames[0].encode()).hexdigest()})
        return frames,val,record

    def prepare_delta(self, t, k, seeds, base, sql, event):
        """Read additions only, then reproduce their join with the checked base."""
        from delta_features import cached_headers, delta_pool, remember_headers

        if base is None:
            raise FeatureError('no checked base is available; validate a complete feature SQL first')
        started = time.time()
        ec = self.tasks[t]['entity_col'].lower()
        event.update(sql_seconds=0.0,queries=[],base_sql_sha256=hashlib.sha256(base[0].encode()).hexdigest())

        def query(split):
            row = {'split':split}
            event['queries'].append(row)
            began = time.time()
            try:
                frame,seconds = features(self.url,sql,f'task.{tname(t)}_{split}',seeds[split],ec,
                                          timeout_s=self.validation_timeout(k))
                event['sql_seconds'] += seconds
                row.update(sql_seconds=seconds,columns=len(frame.columns))
                return frame
            except Exception as err:
                row['error'] = str(err)[:300]
                raise
            finally:
                row['seconds'] = time.time()-began

        try:
            added_train,added_valid = query('train_sample'),query('val')
            psql,pxtr,pxva,importance = base
            xt,xv,chosen = delta_pool(pxtr,pxva,importance,added_train,added_valid,
                                      max_new=12,max_features=MAX_FEATURES)
            event.update(chosen)
            val_table = f'task.{tname(t)}_val'

            def headers(body, train, valid, role):
                if self.arm.get('reuse_header_metadata'):
                    found = cached_headers(body, train, valid)
                    if found is not None:
                        event.setdefault('headers', []).append({'role':role, 'source':'successful feature query'})
                        return found
                timeout = self.validation_timeout(k) if self.arm.get('reuse_header_metadata') else min(5,self.validation_timeout(k))
                event.setdefault('headers', []).append({'role':role, 'source':'SQL probe', 'timeout_seconds':timeout})
                result,seconds = read_sql(self.url,
                    f"SELECT * FROM ({body.strip().rstrip(';').replace('{seeds}',val_table)}) q LIMIT 0",
                    timeout_s=timeout)
                event['sql_seconds'] += seconds
                return list(result.columns[:2])

            pkeys,dkeys = headers(psql,pxtr,pxva,'base'),headers(sql,added_train,added_valid,'addition')
            mapping = chosen['added_columns']
            projection = ', '.join(f'q.{quote_ident(old)} AS {quote_ident(new)}' for old,new in mapping.items())
            secondary = (f'SELECT q.{quote_ident(dkeys[0])},q.{quote_ident(dkeys[1])},{projection} '
                         f"FROM ({sql.strip().rstrip(';')}) q")
            combined = (union_sql(psql,pkeys,chosen['primary_columns'],secondary,dkeys,list(mapping.values()))
                        if chosen['primary_columns'] else secondary)
            check = {'sql_seconds':0.0}
            self.check_columns(t,k,combined,seeds,xv,check,timeout_s=SELECT_CHECK_TIMEOUT_S)
            event['sql_seconds'] += check['sql_seconds']
            event['values_reproduced'] = True
            keys = pkeys if chosen['primary_columns'] else dkeys
            remember_headers(combined, xt, keys)
            remember_headers(combined, xv, keys)
            return combined,xt,xv
        finally:
            event['seconds'] = time.time()-started

    def _select_start(self, t, k, seeds, prog, feats, middle, agent, sid, made):
        e = self.tasks[t]
        ec, yc = e["entity_col"].lower(), e["target_col"].lower()
        higher = metric_of(e["task_type"])[1]
        psql = prog.get("program_sql") or prog.get("sql")
        if not psql:
            return None
        budget = bool(self.arm.get("select_budget"))
        program_timeout = self.arm.get("program_timeout", SELECT_P_TIMEOUT_S)
        rec = {"candidates": [], "audit_seconds": 0.0, "sql_seconds": 0.0, "train_seconds": 0.0, "chosen": None}
        t0 = time.time()
        val_table = f"task.{tname(t)}_val"
        sub = seeds["val"].head(SELECT_CHECK_SEEDS).reset_index(drop=True)
        n_full = len(seeds["train_sample"]) + len(seeds["val"])
        steps = rec.setdefault("steps", {}) if budget else {}

        def run(sql, timeout_s=FEATURE_SQL_TIMEOUT_S, step=None):  # features on the training sample and the validation seeds
            ts = time.time()
            try:
                xtr, s1 = features(self.url, sql, f"task.{tname(t)}_train_sample", seeds["train_sample"], ec, timeout_s=timeout_s)
                xva, s2 = features(self.url, sql, val_table, seeds["val"], ec, timeout_s=timeout_s)
            finally:
                if step:
                    steps[step] = round(time.time() - ts, 1)
            rec["sql_seconds"] += s1 + s2
            return xtr, xva

        def probe(sql, step):
            """Estimated seconds of the SQL on the training sample and the validation seeds, from one run on the check
            seeds (compiled definitions join each seed row laterally, so their time grows with the seed rows)."""
            if not made:
                schema = f"probe_{tname(t)}_k{k}"
                with psycopg.connect(self.url, autocommit=True) as con:
                    con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
                    con.execute(f"CREATE SCHEMA {schema}")
                    con.execute(f"CREATE TABLE {schema}.seeds AS SELECT * FROM {val_table} WHERE false")
                    copy_rows(con, f"{schema}.seeds", sub)
                    con.execute(f"ANALYZE {schema}.seeds")
                made.append(schema)
            ts = time.time()
            try:
                _, s = features(self.url, sql, f"{made[0]}.seeds", sub, ec, timeout_s=SELECT_PROBE_TIMEOUT_S)
            except FeatureError as err:
                raise FeatureError(f"timing run on {len(sub)} seeds: {str(err)[:200]}")
            finally:
                steps[step] = round(time.time() - ts, 1)
            rec["sql_seconds"] += s
            return s * n_full / len(sub)

        def audit(sql):
            ta = time.time()
            r = self.audit(t, k, sql, seeds)
            rec["audit_seconds"] += time.time() - ta
            return r

        def fit(xtr, xev):
            p, imp, tt = self.fit_feature_model(e["task_type"], xtr, seeds["train_sample"][yc], xev, "memory_start")
            rec["train_seconds"] += tt
            return p, imp

        def heads(sql):  # the SQL's own names for its two key columns
            df, _ = read_sql(self.url, f"SELECT * FROM ({sql.strip().rstrip(';').replace('{seeds}', val_table)}) q LIMIT 0")
            return list(df.columns[:2])

        def better(a, b):
            return a > b if higher else a < b

        try:
            pxtr, pxva = run(psql, program_timeout if budget else FEATURE_SQL_TIMEOUT_S, "program")
            pkeys = heads(psql)
        except Exception as err:  # noqa: BLE001 - a program that no longer runs gives no start; the session explores
            dsql_p = prog.get("sql")
            if not (budget and prog.get("program_sql") and dsql_p and dsql_p != psql):
                rec["error"] = f"program: {str(err)[:300]}"
                rec["seconds"] = time.time() - t0
                return rec
            # the program's definitions (each verified to reproduce its column when it was learned) instead of its SQL
            rec["program_sql_error"] = str(err)[:300]
            try:
                est = probe(dsql_p, "program_definitions_timing")
                rec["program_definitions_estimate_s"] = round(est, 1)
                if est > program_timeout:
                    raise FeatureError(f"estimated {est:.0f} s on the training sample and the validation seeds")
                pxtr, pxva = run(dsql_p, min(program_timeout, max(10, 2 * est)), "program_definitions")
                pkeys = heads(dsql_p)
            except Exception as err2:  # noqa: BLE001 - neither runs: no start, the session explores
                rec["error"] = f"program: {str(err)[:200]}; its definitions: {str(err2)[:200]}"
                rec["seconds"] = time.time() - t0
                return rec
            psql = dsql_p
            rec["program_source"] = "definitions"
        p_secs = steps.get("program_definitions", steps.get("program", 0.0))
        leak = audit(psql)
        if leak.get("result") not in ("clean", "leak"):
            rec["error"] = f"program audit: {leak.get('why')}"
            rec["seconds"] = time.time() - t0
            return rec
        bad = set(leak.get("all_columns_differing") or []) if leak["result"] == "leak" else set()
        pcols = [c for c in pxtr.columns if c not in bad]
        if not pcols:
            rec["error"] = "every column of the program reads rows after seed_time on this cutoff"
            rec["seconds"] = time.time() - t0
            return rec
        p_sql = psql if not bad else select_columns_sql(psql, pkeys, pcols)
        pv, pimp = fit(pxtr[pcols], pxva[pcols])
        pval = score(e["task_type"], seeds["val"][yc], pv)
        cands = [{"name": "program", "sql": p_sql, "val": pval, "columns": pcols, "importance": pimp,
                  "dropped_leaking": sorted(bad), "from_cutoff": (prog.get("program") or {}).get("cutoff"),
                  "source": rec.get("program_source", "program SQL")}]
        subset_time_left = [15.0]

        def prune(candidate, xtr, xva, keys):
            if not self.arm.get("subset_selection") or subset_time_left[0] <= 0:
                return
            from feature_selection import select_subset

            selected = select_subset(
                xtr[candidate["columns"]], seeds["train_sample"][yc], xva[candidate["columns"]], seeds["val"][yc],
                candidate["importance"], candidate["val"], higher,
                lambda xt, yt, xv: self.fit_feature_model(e["task_type"], xt, yt, xv, "start_subset"),
                lambda y, p: score(e["task_type"], y, p), budget_seconds=subset_time_left[0])
            subset_time_left[0] -= selected["seconds"]
            rec["train_seconds"] += selected["train_seconds"]
            rec.setdefault("subset_selection", []).append({k2: v for k2, v in selected.items() if k2 != "chosen"})
            chosen = selected["chosen"]
            if chosen["columns"] != candidate["columns"]:
                cands.append({**candidate, "name": candidate["name"] + "_pruned", "val": chosen["val"],
                              "columns": chosen["columns"], "importance": chosen["importance"],
                              "sql": select_columns_sql(candidate["sql"], keys, chosen["columns"])})

        prune(cands[0], pxtr, pxva, pkeys)
        # U: the verified definitions of the entity that the program does not already use
        in_prog = {c.get("key") for c in prog.get("columns") or []}
        keys = [f["key"] for f in feats.get("features") or [] if f.get("key") and f["key"] not in in_prog][:SELECT_MAX_DEFS]
        rec["definitions_offered"] = len(keys)
        if keys and budget and p_secs > SELECT_EXTEND_MAX_P_S:
            rec["extension_skipped"] = (f"the program's SQL took {p_secs:.0f} s (over {SELECT_EXTEND_MAX_P_S} s) and the "
                                        "extension's check runs it again")
            keys = []
        if keys:
            try:
                comp = middle.call("compose_features", agent, sid, sid, {"keys": keys, "seed_key": ec})
                dsql = comp.get("sql")
                if not dsql:
                    raise FeatureError(f"compose_features: {comp.get('error')}")
                d_timeout = FEATURE_SQL_TIMEOUT_S
                if budget:
                    allowed = max(30.0, p_secs)
                    est = probe(dsql, "definitions_timing")
                    rec["definitions_estimate_s"] = round(est, 1)
                    if est > allowed:
                        rec["extension_skipped"] = f"its definitions would take about {est:.0f} s, more than the program's {allowed:.0f} s"
                        raise FeatureError(rec["extension_skipped"])
                    d_timeout = min(FEATURE_SQL_TIMEOUT_S, max(30, 2 * est))
                dxtr, dxva = run(dsql, d_timeout, "definitions")
                dkeys = heads(dsql)
                dleak = audit(dsql)
                if dleak.get("result") not in ("clean", "leak"):
                    raise FeatureError(f"definitions audit: {dleak.get('why')}")
                dbad = set(dleak.get("all_columns_differing") or []) if dleak["result"] == "leak" else set()
                dcols = [c for c in dxtr.columns if c not in dbad and c not in pcols and c not in pkeys]
                if not dcols:
                    raise FeatureError("no definition column beyond the program's")
                _, jimp = fit(pd.concat([pxtr[pcols], dxtr[dcols]], axis=1), pxva[pcols].head(1).join(dxva[dcols].head(1)))
                keep = pcols
                if MAX_FEATURES - len(keep) < SELECT_MIN_ROOM:
                    never = [c for c, g in reversed(jimp) if g == 0 and c in pcols]
                    drop = set(never[:SELECT_MIN_ROOM - (MAX_FEATURES - len(keep))])
                    keep = [c for c in pcols if c not in drop]
                add = [c for c, g in jimp if c in dcols and g > 0][:MAX_FEATURES - len(keep)]
                if not add:
                    raise FeatureError("no definition column with gain in the joint fit")
                uxtr = pd.concat([pxtr[keep], dxtr[add]], axis=1)
                uxva = pd.concat([pxva[keep], dxva[add]], axis=1)
                uv, uimp = fit(uxtr, uxva)
                uval = score(e["task_type"], seeds["val"][yc], uv)
                u_sql = union_sql(psql, pkeys, keep, dsql, dkeys, add)
                cand = {"name": "extended", "sql": u_sql, "val": uval, "columns": keep + add, "importance": uimp,
                        "added": add, "added_keys": [c.get("key") for c in comp.get("columns") or [] if c.get("column") in add],
                        "dropped_never_split": [c for c in pcols if c not in keep], "dropped_leaking": sorted(bad | dbad)}
                if better(uval, pval):
                    # the extended SQL must reproduce the columns that were scored, and pass the leak audit as one SQL
                    tc = time.time()
                    try:
                        self.check_columns(t, k, u_sql, seeds, uxva, rec,
                                           timeout_s=SELECT_CHECK_TIMEOUT_S if budget else FEATURE_SQL_TIMEOUT_S)
                    finally:
                        if budget:
                            steps["check"] = round(time.time() - tc, 1)
                    ua = audit(u_sql)
                    if ua.get("result") != "clean":
                        raise FeatureError(f"extended SQL audit: {ua.get('result')} {ua.get('columns_differing') or ua.get('why')}")
                cands.append(cand)
                if better(uval, pval):
                    prune(cand, uxtr, uxva, pkeys)
            except Exception as err:  # noqa: BLE001 - the program alone still starts the session
                rec["extension_error"] = str(err)[:300]
        if bad:  # the program without its leaking columns is a new SQL: audit it as one before it starts the session
            pa = audit(p_sql)
            if pa.get("result") != "clean":
                cands = [c for c in cands if not c["name"].startswith("program")]
                rec["program_error"] = f"program without leaking columns: {pa.get('result')}"
        best = None
        for c in cands:
            if best is None or better(c["val"], best["val"]):
                best = c
        rec["candidates"] = [{k2: v for k2, v in c.items() if k2 not in ("sql", "importance")} | {"n_features": len(c["columns"])}
                             for c in cands]
        for c in rec["candidates"]:
            c.pop("columns", None)
        if best is not None:
            rec["chosen"] = {"name": best["name"], "val": best["val"], "sql": best["sql"], "columns": best["columns"],
                             "importance": [c for c, _ in best["importance"][:30]], "top": best["importance"][:10],
                             "never_split": sum(1 for _, g in best["importance"] if g == 0)}
        rec["seconds"] = time.time() - t0
        return rec

    def select_message(self, t, k, sel, looked, goal):
        """The session's first message after the task line when the memory chose its start (arm mavra-select)."""
        e = self.tasks[t]
        metric = metric_of(e["task_type"])[0]
        entity = e["entity_table"].lower()
        ch = sel["chosen"]
        if self.arm.get('delta_refinement') and k>1:
            lines = [f"The memory holds a checked complete base for this cutoff: validation {metric}={ch['val']:.5f}.",
                     'Checked feature columns: '+', '.join(ch['columns']),
                     'Top training gains: '+', '.join(f'{c} ({g:g})' for c,g in ch['top']),
                     'Use validate_additions to test at most 12 new numeric feature columns; the memory combines them with this base. '
                     'Keep every seed row and respect seed_time. Prefer complementary signals that are absent from this inventory. '
                     'The complete base stays checked and available; you need not copy its SQL. '
                     'Complete one clean trial within the session budget before submitting without sql.']
            defs = [f['key'] for f in looked.get('find_features',{}).get('features') or [] if f.get('key')]
            if defs:
                lines.append('Other verified definitions available through compose_features: '+', '.join(defs[:20]))
            return '\n'.join(lines)
        lines = ["Prepared for you by the shared memory (validated on this cutoff's data; none of your validations were used):"]
        for c in sel["candidates"]:
            if c["name"].startswith("program"):
                s = (f"- this task's verified program from cutoff {str(c.get('from_cutoff'))[:10]}"
                     + (" as its verified definitions (its complete SQL went over the time limit on this cutoff)"
                        if c.get("source") == "definitions" else "")
                     + f": validation {metric} {c['val']:.5f} ({c['n_features']} features)")
                if c.get("dropped_leaking"):
                    s += f"; columns dropped because they read rows after seed_time on this cutoff: {', '.join(c['dropped_leaking'][:10])}"
            else:
                s = (f"- the program extended with {len(c['added'])} verified definitions that other agents published for {entity}: "
                     f"validation {metric} {c['val']:.5f} ({c['n_features']} features)")
            lines.append(s)
        lines.append(f"Your current best features are the {'extended program' if ch['name'].startswith('extended') else 'program'} "
                     f"(validation {metric} {ch['val']:.5f}{', which reaches the retraining goal' if goal else ''}):")
        lines.append(ch["sql"])
        lines.append("Its top features by gain: " + ", ".join(f"{c} ({g:g})" for c, g in ch["top"]))
        if ch.get("never_split"):
            lines.append(f"{ch['never_split']} of its columns are never split on by the model.")
        tried = looked["find_program"].get("tried") or []
        if tried:
            lines.append("Columns that earlier sessions of this task tried without keeping them: " + ", ".join(map(str, tried)))
        used = set(ch["columns"])
        other = [f["key"] for f in looked["find_features"].get("features") or [] if f.get("key") and f["key"].split(":")[-1] not in used]
        if other:
            lines.append(f"Verified definitions for {entity} not in these features (compose_features compiles them by key): "
                         + ", ".join(other[:30]))
        if goal:
            lines.append(f"You may make one more attempt to improve them: one validate_features within the next {self.post_goal_window(k)} "
                         "model calls, after which the session ends with your best validated features. Call submit without sql to finish now.")
        else:
            lines.append("Improve on them with validate_features; submit without sql keeps your best validated features.")
        return "\n".join(lines)

    def first_message(self, t, found, constant_only=False):
        """The session's first message after the task line when the task has no program yet (arm mavra-select2)."""
        entity = self.tasks[t]["entity_table"].lower()
        status = "has only a checked constant default" if constant_only else "has no verified program yet"
        defs = [f for f in found.get("features") or [] if f.get("key")]
        if not defs:
            return f"Looked up for you in shared memory: this task {status}, and no verified definitions for {entity} have been published yet."
        lines = [f"Looked up for you in shared memory: this task {status}. Verified definitions that other agents "
                 f"published for {entity} (made for other tasks; compose_features compiles any of them by key into a feature SQL):"]
        for f in defs[:FIRST_LIST_DEFS]:
            w = f" (window {f['window_days']} days)" if f.get("window_days") else ""
            lines.append(f"- {f['key']}: {str(f.get('definition') or f.get('name') or '').strip()}{w}")
        if len(defs) > FIRST_LIST_DEFS:
            lines.append(f"({len(defs) - FIRST_LIST_DEFS} more not listed)")
        return "\n".join(lines)

    def slow_message(self, t, k, looked):
        """The session's first message when the task's program went over the selection's time limit (arm mavra-select2)."""
        prog = looked["find_program"]
        cut = str((prog.get("program") or {}).get("cutoff") or "an earlier cutoff")[:10]
        lines = [f"Looked up for you in shared memory: this task's verified program from cutoff {cut} did not finish within the "
                 f"memory's time limit ({SELECT_P_TIMEOUT_S} s per statement) on this cutoff's data, so it was not validated. Its SQL:",
                 prog.get("program_sql") or prog.get("sql") or "",
                 f"Validate a cheaper version of it rather than the SQL as is (validate_features stops a statement after "
                 f"{FEATURE_SQL_TIMEOUT_S} s), keeping its features where you can."]
        tried = prog.get("tried") or []
        if tried:
            lines.append("Columns that earlier sessions of this task tried without keeping them: " + ", ".join(map(str, tried)))
        keys = [f["key"] for f in looked["find_features"].get("features") or [] if f.get("key")]
        if keys:
            lines.append(f"Verified definitions for {self.tasks[t]['entity_table'].lower()} (compose_features compiles them by key): "
                         + ", ".join(keys[:30]))
        return "\n".join(lines)

    def check_columns(self, t, k, sql, seeds, xva, rec, timeout_s=FEATURE_SQL_TIMEOUT_S):
        """The extended SQL, run as one statement on the first validation seeds, gives the columns that were scored."""
        e = self.tasks[t]
        ec = e["entity_col"].lower()
        sub = seeds["val"].head(SELECT_CHECK_SEEDS).reset_index(drop=True)
        schema = f"select_{tname(t)}_k{k}"
        with psycopg.connect(self.url, autocommit=True) as con:
            con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            con.execute(f"CREATE SCHEMA {schema}")
            con.execute(f"CREATE TABLE {schema}.seeds AS SELECT * FROM task.{tname(t)}_val WHERE false")
            copy_rows(con, f"{schema}.seeds", sub)
            con.execute(f"ANALYZE {schema}.seeds")
        try:
            got, secs = features(self.url, sql, f"{schema}.seeds", sub, ec, timeout_s=timeout_s)
        finally:
            with psycopg.connect(self.url, autocommit=True) as con:
                con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        rec["sql_seconds"] += secs
        want = xva.head(SELECT_CHECK_SEEDS).reset_index(drop=True)
        if list(got.columns) != list(want.columns):
            raise FeatureError(f"extended SQL columns differ: {list(got.columns)[:5]} vs {list(want.columns)[:5]}")
        diff = ~np.isclose(got.to_numpy(), want.to_numpy(), rtol=1e-6, atol=1e-9, equal_nan=True)
        if diff.any():
            raise FeatureError(f"extended SQL differs from the scored columns in {int(diff.sum())} cells "
                               f"({[c for c, d in zip(got.columns, diff.any(axis=0)) if d][:5]})")

    def tool_specs(self):
        def fn(name, desc, props, req):
            return {"type": "function", "function": {"name": name, "description": desc,
                                                     "parameters": {"type": "object", "properties": props, "required": req}}}
        s = {"type": "string"}
        return [
            fn("list_tables", "List the tables with estimated row counts and comments.", {}, []),
            fn("describe_table", "Profile a table: columns, types, null ratios, distinct counts, common values, sample rows.", {"table": s}, ["table"]),
            fn("join_path", "Find join paths between two tables, checked on the data.", {"table_a": s, "table_b": s}, ["table_a", "table_b"]),
            fn("check_join", "Check a join between two tables on given column pairs: key uniqueness and match rates.",
               {"left": s, "right": s, "on": {"type": "array", "items": {"type": "array", "items": s}, "description": "[[left_col, right_col], ...]"}},
               ["left", "right", "on"]),
            fn("run_sql", "Run one read-only SQL query on PostgreSQL; returns at most 50 rows.", {"sql": s}, ["sql"]),
            fn("validate_features", "Compute the features of a feature SQL (must use {seeds}) on the training sample and validation seeds, train the fixed model, return the validation score.",
               {"sql": s, **({"bullet_ids": {"type": "array", "items": s, "description": "ids of the playbook bullets you used"}} if self.arm.get("ace") else {})}, ["sql"]),
            fn("submit", "Finish the session with this feature SQL (must use {seeds}). Omit sql to submit your best validated features.",
               {"sql": s, **({"bullet_ids": {"type": "array", "items": s, "description": "ids of the playbook bullets you used"}} if self.arm.get("ace") else {})}, []),
        ] + ([
            fn("find_features", "List verified feature definitions shared by all agents for an entity table (key, name, meaning, aggregated table, measure, look-back window), with a feature SQL of them for this task's seed tables, ready for validate_features.",
               {"entity": s, "query": {"type": "string", "description": "words describing the features you want"}}, ["entity"]),
            fn("compose_features", "Compile verified feature definitions (keys from find_features or find_program) into one feature SQL that uses {seeds}.",
               {"keys": {"type": "array", "items": s}}, ["keys"]),
            fn("find_program", "The latest verified feature program for this task (from an earlier cutoff): its validation score and its still-valid definitions compiled into one feature SQL, ready for validate_features.",
               {}, []),
        ] if self.arm.get("feature_memory") and not self.arm.get("push_memory") else []) + ([
            fn("compose_features", "Compile verified feature definitions (keys from find_features or find_program) into one feature SQL that uses {seeds}.",
               {"keys": {"type": "array", "items": s}}, ["keys"]),
        ] if self.arm.get("push_memory") else []) + ([
            fn("find_program", "The latest successful, audited feature program for this task from an earlier cutoff: "
               "its validation score and complete feature SQL when it still runs, ready for validate_features.", {}, []),
        ] if self.arm.get("sql_memory") else []) + ([
            fn("validate_additions", "Propose at most 12 complementary numeric feature columns with a small SQL using {seeds}. "
               "Compute additions from public tables and the seed keys/time. Return the entity key and seed_time first, "
               "preserving every seed row and all time bounds. The memory joins "
               "these columns with its complete checked base, fits the unchanged model, reproduces the joined SQL and audits it. "
               "Keep this query focused on new signals; the base SQL is already held by the memory.", {"sql":s}, ["sql"]),
        ] if self.arm.get("delta_refinement") else [])

    def find_sql_program(self, t, k):
        """Match MAVRA's 50-seed executability check, without extraction or feature composition."""
        program = self.sql_programs.get(t)
        if not program or program["k"] >= k:
            return {"program": None, "note": "no verified program for this task yet"}
        out = {"program": {key: program[key] for key in ("task", "cutoff", "metric", "val_score")}}
        seeds = f"(select * from task.{tname(t)}_val limit 50)"
        sql = program["sql"].strip().rstrip(";").replace("{seeds}", seeds)
        try:
            read_sql(self.url, f"select count(*) from ({sql}) q", timeout_s=300)
            out["program_sql"] = program["sql"]
        except Exception as err:
            out["program_sql_unavailable"] = f"the program's SQL no longer runs on the current data: {err}"
        return out

    def save_sql_program(self, t, k, rec):
        """Admission uses validation and the clean audit only, with MAVRA's success threshold."""
        ref = (self.refs.get((t, k)) or {}).get("val")
        best = rec.get("best_val")
        beats = best is not None and ref is not None and (best > ref if rec["higher_is_better"] else best < ref)
        if rec.get("stop") == "llm_error" or not rec.get("final_sql") or not beats:
            return {"saved": False, "reason": "no successful completed program"}
        if (rec.get("audit") or {}).get("result") != "clean":
            return {"saved": False, "reason": "program audit is not clean"}
        self.sql_programs[t] = {"task": t, "k": k, "cutoff": self.tasks[t]["cutoffs"][k - 1]["test_timestamp"],
                                "metric": rec["metric"], "val_score": best, "sql": rec["final_sql"]}
        return {"saved": True, "source_cutoff": k, "sql_sha256": hashlib.sha256(rec["final_sql"].encode()).hexdigest()}

    def tecod_question(self, t, k):
        """TeCoD's question for a session and its masked form (the cutoff date is the question's one literal)."""
        date = self.tasks[t]["cutoffs"][k - 1]["test_timestamp"][:10]
        text = f"{self.task_desc[t]['description']} Build features for {t} at cutoff {date}."
        return text, text.replace(date, "_")

    def tecod_add(self, t, k, rec):
        """A verified pair joins the pool: the session beat the reference and its final SQL passed the audit (the
        admission rule of the SQL-only arm and MAVRA's success threshold)."""
        ref = (self.refs.get((t, k)) or {}).get("val")
        best = rec.get("best_val")
        beats = best is not None and ref is not None and (best > ref if rec["higher_is_better"] else best < ref)
        if not rec.get("final_sql") or not beats or (rec.get("audit") or {}).get("result") != "clean":
            return {"added": False, "reason": "not a verified pair", "seconds": 0}
        if self.tecod_names is None:
            rows, _ = read_sql(self.url, "select table_name, column_name from information_schema.columns "
                                      "where table_schema in ('public', 'task')")
            self.tecod_names = (sorted(set(rows["table_name"])), sorted(set(rows["column_name"])))
        text, masked = self.tecod_question(t, k)
        v = self.tecod.send({"op": "add", "text": text, "nlq_masked": masked, "sql": rec["final_sql"],
                             "tables": self.tecod_names[0], "columns": self.tecod_names[1]})
        if v.get("error"):
            return {"added": False, "error": v["error"], "seconds": v.get("seconds", 0)}
        return {"added": True, **{k2: v.get(k2) for k2 in ("t_id", "masking", "new_template", "pool_examples", "pool_templates", "seconds")}}

    def has_program(self, t, k, middle):
        """Whether the memory holds a verified program of task t (find_program, as at the session start)."""
        sid = f"{self.a.arm}-r{self.a.run}-{tname(t)}-k{k}"
        try:
            out = middle.call("find_program", f"{tname(t)}-agent", sid, sid, {"task": t})
        except Exception:  # noqa: BLE001 - unknown: one attempt, as in the other arms
            return True
        return bool(isinstance(out, dict) and (out.get("program_sql") or out.get("sql")))

    def session(self, t, k, seeds, middle):
        """One session of task t at cutoff k. Arm mavra-select2: a task without a verified program (its first session)
        explores FIRST_ATTEMPTS times, one after another from the same start; the attempt with the better validation
        score becomes the session (its test score, its learning) and the others' model calls, tool calls and time are
        charged to it."""
        n = self.arm.get("first_attempts") or 1
        if self.arm.get("subset_selection") and k > 1:
            n = 1  # keep the reuse session's total model/tool budget, even after a missing program
        if n < 2 or self.has_program(t, k, middle):
            return self.finish(t, k, seeds, middle, self.explore(t, k, seeds, middle))
        higher = metric_of(self.tasks[t]["task_type"])[1]
        sts = []
        for i in range(n):
            st = self.explore(t, k, seeds, middle, attempt=i + 1)
            log(f"{t} k{k} attempt {i + 1}: stop={st['rec']['stop']} llm={len(st['rec']['llm'])} val={st['rec']['best_val']}")
            if st["rec"]["stop"] == "llm_error":  # saved with the earlier attempts' work, then the run stops
                return self.finish(t, k, seeds, middle, st, sts)
            sts.append(st)
        pick = None
        for st in sts:
            v = st["rec"]["best_val"] if st["rec"]["final_sql"] else None
            if v is not None and (pick is None or (v > pick[0] if higher else v < pick[0])):
                pick = (v, st)
        chosen = pick[1] if pick else sts[0]
        if self.arm.get("cold_union"):
            self.combine_cold_start(t, k, seeds, chosen, [st for st in sts if st is not chosen])
        return self.finish(t, k, seeds, middle, chosen, [st for st in sts if st is not chosen])

    def combine_cold_start(self, t, k, seeds, primary, others):
        """Try a bounded union of this task's own, independently validated attempts.

        All matrices are from the same seed rows, cutoff and fixed learner. The
        baseline remains the best single attempt unless the union improves
        validation and its SQL passes reproduction and the leakage audit.
        """
        from feature_selection import complementary_pool, select_union

        rec = primary["rec"]
        self._fit_ledger = rec.setdefault("feature_fits", [])
        frames = primary.get("frames")
        alternate = next((st for st in others if st.get("frames") and st["rec"].get("final_sql")), None)
        if frames is None or alternate is None or frames[0] != rec.get("final_sql"):
            return
        other_frames = alternate["frames"]
        if other_frames[0] != alternate["rec"]["final_sql"]:
            return
        started, audit_seconds = time.time(), 0.0
        event = {"source": "independent_own_task_attempts", "selection_split": "validation", "max_features": MAX_FEATURES,
                 "primary_before": {"val": rec["best_val"], "sql": rec["final_sql"]},
                 "secondary_before": {"val": alternate["rec"]["best_val"], "attempt": alternate["rec"].get("attempt")}}
        rec["memory_union"] = event
        e = self.tasks[t]
        yc = e["target_col"].lower()
        task_type = e["task_type"]
        try:
            psql, pxtr, pxva, _ = frames
            dsql, dxtr, dxva, dimp = other_frames
            xt, xv, mapping, duplicates = complementary_pool(pxtr, pxva, dxtr, dxva, dimp)
            event.update(offered=len(mapping), duplicate_columns=duplicates, alternate_columns=mapping)
            selected = select_union(xt, seeds["train_sample"][yc], xv, seeds["val"][yc], list(pxtr),
                                    rec["best_val"], rec["higher_is_better"],
                                    lambda a, b, c: self.fit_feature_model(task_type, a, b, c, "cold_union"),
                                    lambda y, p: score(task_type, y, p), max_features=MAX_FEATURES)
            event.update({key: value for key, value in selected.items() if key != "chosen"})
            best = selected["chosen"]
            event["chosen"] = {key: best.get(key) for key in ("name", "val", "columns")}
            if best["name"] == "single_attempt":
                return
            columns = best["columns"]
            val_table = f"task.{tname(t)}_val"

            def headers(sql):
                result, _ = read_sql(self.url, f"SELECT * FROM ({sql.strip().rstrip(';').replace('{seeds}', val_table)}) q LIMIT 0")
                return list(result.columns[:2])

            pkeys, dkeys = headers(psql), headers(dsql)
            pcols = [c for c in columns if c in pxtr]
            extra = [(original, renamed) for original, renamed in mapping.items() if renamed in columns]
            renamed = [f"q.{quote_ident(original)} AS {quote_ident(name)}" for original, name in extra]
            secondary_sql = (f"SELECT q.{quote_ident(dkeys[0])}, q.{quote_ident(dkeys[1])}, " + ", ".join(renamed)
                             + f" FROM (\n{dsql.strip().rstrip(';')}\n) AS q") if extra else None
            if not extra:
                sql = select_columns_sql(psql, pkeys, pcols)
            elif not pcols:
                sql = secondary_sql
            else:
                sql = union_sql(psql, pkeys, pcols, secondary_sql, dkeys, [name for _, name in extra])
            check = {"sql_seconds": 0.0}
            self.check_columns(t, k, sql, seeds, xv[columns], check, timeout_s=SELECT_CHECK_TIMEOUT_S)
            event["sql_seconds"] = check["sql_seconds"]
            ta = time.time()
            audit = self.audit(t, k, sql, seeds)
            audit_seconds = time.time() - ta
            event["audit"] = audit.get("result")
            if audit.get("result") != "clean":
                event["rejected"] = "combined SQL did not pass the leakage audit"
                return
            rec["final_sql"], rec["best_val"], rec["final_source"] = sql, best["val"], "memory_union"
            rec["validations"].append({"tool_i": None, "val": best["val"], "sql": sql, "leak": False,
                                       "improved": True, "audit_result": "clean", "source": "memory_union",
                                       "n_features": len(columns), "columns": columns,
                                       "importance": [c for c, _ in best["importance"]]})
            primary["frames"] = (sql, xt[columns], xv[columns], best["importance"])
            event["accepted"] = True
            log(f"{t} k{k}: complementary union validation={best['val']:.6f}, features={len(columns)}, no model requests")
        except Exception as err:
            event["error"] = str(err)[:300]
        finally:
            event["elapsed_seconds"] = time.time() - started
            event["audit_seconds"] = audit_seconds
            rec["agent_seconds"] += event["elapsed_seconds"] - audit_seconds
            rec["audit_seconds"] += audit_seconds

    def sanitize_candidate(self, t, k, seeds, sql, xtrain, xvalid, audit):
        """Salvage only an explicitly identified, reproducible clean projection.

        Dropping outputs never grants an execution exemption: the projected SQL
        is checked against the already computed values and audited again. An
        error/unknown audit or a failed check leaves the original rejected.
        """
        if not self.arm.get("sanitize_candidates") or audit.get("result") != "leak":
            return None, None
        bad = {str(c).lower() for c in audit.get("all_columns_differing") or audit.get("columns_differing") or []}
        keep = [c for c in xtrain if str(c).lower() not in bad]
        event = {"removed_columns": [c for c in xtrain if str(c).lower() in bad], "accepted": False,
                 "audit_seconds": 0.0, "sql_seconds": 0.0, "train_seconds": 0.0}
        if not bad or not keep or len(keep) == len(xtrain.columns):
            event["rejected"] = "no explicitly identified clean output subset"
            return event, None
        started = time.time()
        e = self.tasks[t]
        try:
            val_table = f"task.{tname(t)}_val"
            columns, seconds = read_sql(self.url, f"SELECT * FROM ({sql.strip().rstrip(';').replace('{seeds}', val_table)}) q LIMIT 0")
            event["sql_seconds"] += seconds
            projected = select_columns_sql(sql, list(columns.columns[:2]), keep)
            check = {"sql_seconds": 0.0}
            self.check_columns(t, k, projected, seeds, xvalid[keep], check, timeout_s=SELECT_CHECK_TIMEOUT_S)
            event["sql_seconds"] += check["sql_seconds"]
            ta = time.time()
            clean = self.audit(t, k, projected, seeds)
            event["audit_seconds"] += time.time() - ta
            event["audit"] = clean.get("result")
            if clean.get("result") != "clean":
                event["rejected"] = "projected SQL did not pass a fresh leakage audit"
                return event, None
            prediction, importance, seconds = self.fit_feature_model(e["task_type"], xtrain[keep], seeds["train_sample"][e["target_col"].lower()], xvalid[keep], "clean_projection")
            event["train_seconds"] += seconds
            val = score(e["task_type"], seeds["val"][e["target_col"].lower()], prediction)
            event.update(accepted=True, columns=keep, val=val)
            return event, (projected, xtrain[keep], xvalid[keep], importance, val)
        except Exception as err:
            event["error"] = str(err)[:300]
            return event, None
        finally:
            event["seconds"] = time.time() - started

    def explore(self, t, k, seeds, middle, attempt=None):
        """The agent's part of a session: the start, the tool loop and the stopping rule."""
        e = self.tasks[t]
        agent = f"{tname(t)}-agent"
        sid = f"{self.a.arm}-r{self.a.run}-{tname(t)}-k{k}" + (f"-a{attempt}" if attempt else "")
        part = f"{tname(t)}-k{k}" + (f"-a{attempt}" if attempt else "")
        metric, higher = metric_of(e["task_type"])
        if (t, k) not in self.targets:
            self.targets[(t, k)] = self.incumbent(t, k, seeds) if k > 1 else {"val": None, "why": "first cutoff"}
        ec, yc = e["entity_col"].lower(), e["target_col"].lower()
        rec = {"arm": self.a.arm, "run": self.a.run, "task": t, "k": k, "agent": agent, "session": sid, "attempt": attempt,
               "metric": metric, "target": self.target(t, k),
               "target_detail": self.targets.get((t, k)),
               "higher_is_better": higher, "llm": [], "tools": [], "validations": [], "stop": None, "error": None}
        self._fit_ledger = rec.setdefault("feature_fits", []) if self.arm.get("cold_union") else None
        task_line = f"Build features for {t} at cutoff {e['cutoffs'][k - 1]['test_timestamp'][:10]}."
        msgs = [{"role": "system", "content": self.system_prompt(t, k, seeds)}, {"role": "user", "content": task_line}]
        early = self.early_validation_hint(k)
        if early:
            msgs[0]["content"] += "\n\n" + early
        if self.arm.get("subset_selection") and attempt:
            focus = ("Prioritize event history, recency, multiple look-back windows and activity changes."
                     if attempt == 1 else
                     "Prioritize the entity's own attributes and distinct signals tied to this prediction target; "
                     "use past related-entity outcomes only when they were observable at the seed time.")
            msgs[0]["content"] += ("\n\nFeature-search focus for this independent attempt: " + focus
                                    + " Keep a compact, complementary feature set; validate a working SQL early before adding complexity.")
        gmem_tokens = [0, 0]
        if self.gmem:
            g = self.gmem.send({"op": "begin", "task_main": f"{self.task_desc[t]['description']} (task {t}, cutoff {e['cutoffs'][k - 1]['test_timestamp'][:10]})",
                                "task_description": task_line})
            gmem_tokens = [g.get("prompt_tokens", 0), g.get("completion_tokens", 0)]
            if g.get("prompt"):
                msgs[1]["content"] = g["prompt"]
            rec["gmemory_begin"] = {k2: g.get(k2) for k2 in ("n_success", "n_insights", "error")}
        if self.tecod:
            text, _ = self.tecod_question(t, k)
            sel = self.tecod.send({"op": "select", "query": text})
            if sel.get("error"):
                raise RuntimeError(f"TeCoD selection failed: {sel['error']}")
            block = tecod_block(sel)
            if block:  # released prompt order: schema, template, examples, question; here the system prompt stands for the schema
                msgs[1]["content"] = block + "\n\n" + task_line
            rec["tecod"] = {"method": "sgc" if sel["matched"] else ("icl" if sel["icl"] else "zs"), "prompt_chars": len(block),
                            **{k2: sel.get(k2) for k2 in ("matched", "t_id", "nli_label", "entailment", "cosine", "icl_ids", "nli",
                                                          "pool_examples", "pool_templates", "seconds")}}
        best, best_sql, streak, idle, submitted = None, None, 0, 0, None
        goal_hit = None  # model calls made when a validation first reached the goal
        chosen = None  # mavra-select: the start the memory validated
        best_frames = None  # only the current best's matrices, reused by the bounded selector
        fallback = None  # clean constant default, not a successful engineered candidate
        t_start = time.time()
        if self.arm.get("push_memory"):
            # the two lookups the agent used to start with, done by the memory at the session start (inside the
            # measured session time) and put after the task line in the form of their tool outputs
            t0, pushed, looked = time.time(), [], {}
            for name, args in (("find_program", {"task": t}), ("find_features", {"entity": e["entity_table"].lower(), "seed_key": ec})):
                try:
                    cached = self.current_incumbent(t, k, seeds) if name == "find_program" else None
                    if cached:
                        out = {"sql": cached["sql"], "columns": [], "program": {"task": t,
                               "cutoff": e["cutoffs"][k - 2]["test_timestamp"], "metric": metric,
                               "val_score": cached["val"]}, "source": "own current-cutoff audited refit"}
                        rec["memory_current_refit"] = True
                    else:
                        out = middle.call(name, agent, sid, sid, args)
                except Exception as err:
                    out = {"error": f"{err}"}
                looked[name] = out if isinstance(out, dict) else {}
                pushed.append(f"{name}: " + json.dumps(out, ensure_ascii=False, default=str)[:TOOL_OUTPUT_CHARS])
            sel, text = None, None
            if self.arm.get("select_start"):
                rec["tried_before"] = looked["find_program"].get("tried") or []
                try:
                    sel = self.select_start(t, k, seeds, looked["find_program"], looked["find_features"], middle, agent, sid)
                    if sel is not None and sel.get("chosen"):
                        frames = sel.get("_frames")
                        if self.start_is_informative(frames[1] if frames else None):
                            goal = self.target(t, k)
                            v = sel["chosen"]["val"]
                            reached = goal is not None and (v >= goal if higher else v <= goal)
                            text = self.select_message(t, k, sel, looked, reached)
                        else:
                            fallback = {"val": sel["chosen"]["val"], "frames": frames, "source": "own_program"}
                            sel["fallback_only"] = True
                except Exception as err:  # noqa: BLE001 - the session then starts from the plain lookups and the error is kept
                    sel = {"error": f"select_start: {type(err).__name__}: {str(err)[:300]}"}
                    log(f"{t} k{k}: {sel['error']}")
                if sel is not None:
                    rec["memory_select"] = {k2: v for k2, v in sel.items() if k2 not in ("chosen", "_frames")}
                    rec["memory_select"]["chosen"] = {k2: v for k2, v in (sel.get("chosen") or {}).items() if k2 != "sql"} or None
            if text:
                chosen = sel["chosen"]
                best, best_sql = chosen["val"], chosen["sql"]
                best_frames = sel.get("_frames")
                if reached:
                    goal_hit = 0
                    rec["goal_reached"] = {"validation": 0, "llm_calls": 0, "by": "memory"}
                msgs[1]["content"] = task_line + "\n\n" + text
            elif fallback is not None:
                msgs[1]["content"] = (task_line + "\n\n" + self.first_message(t, looked["find_features"], constant_only=True)
                                      + "\n\n" + self.constant_start_message())
            elif self.arm.get("select_budget") and sel and "statement timeout" in str(sel.get("error") or ""):
                # the program went over the selection's time limit: say so, instead of handing it over to be validated as is
                msgs[1]["content"] = task_line + "\n\n" + self.slow_message(t, k, looked)
                rec["memory_push_slow_program"] = True
            elif self.arm.get("first_keys_only") and not (looked["find_program"].get("program_sql") or looked["find_program"].get("sql")):
                # a task's first session: the entity's definitions as keys and meanings, without their SQL (11-09: a first
                # session handed a sibling task's definitions and SQL to validate first stayed anchored on them)
                msgs[1]["content"] = task_line + "\n\n" + self.first_message(t, looked["find_features"])
                rec["memory_push_keys_only"] = True
            else:
                msgs[1]["content"] = task_line + "\n\nLooked up for you in shared memory:\n" + "\n".join(pushed)
            rec["memory_push"] = {"seconds": time.time() - t0, "chars": len(msgs[1]["content"]) - len(task_line),
                                  "program": '"sql"' in pushed[0], "error": any('"error"' in x[:40] for x in pushed)}

        checked_current = self.current_incumbent(t,k,seeds) if self.arm.get('typed_reference') else None
        if self.arm.get('typed_reference') and (chosen is None or checked_current is None or best_sql!=checked_current['sql']):
            ts = time.time()
            try:
                frames,rv,reference = self.typed_reference_start(t,k,seeds)
                rec['memory_reference'] = reference
                if frames is not None:
                    if self.start_is_informative(frames[1]):
                        if best is None or (rv>best if higher else rv<best):
                            best,best_sql,best_frames = rv,frames[0],frames
                            msgs[1]['content'] += (f'\n\nThe method selected a freshly audited entity view on validation ({metric}={rv:.5f}). '
                                                   'Improve it with complementary task features; keep it when additions hurt validation.\n'
                                                   + (', '.join(frames[1].columns) if k>1 else frames[0]))
                        else:
                            rec['memory_reference']['retained_existing_checked_start'] = True
                    else:
                        rec['memory_reference']['fallback_only'] = True
                        if best is None and (fallback is None or (rv>fallback['val'] if higher else rv<fallback['val'])):
                            fallback = {'val':rv,'frames':frames,'source':'entity_reference'}
                            msgs[1]['content'] += '\n\n'+self.constant_start_message()
            except Exception as err:
                rec['memory_reference'] = {'error':str(err)[:300],'audit_seconds':0.0}
            rec['memory_reference']['seconds'] = time.time()-ts

        if self.arm.get("subset_selection") and not self.arm.get('typed_reference') and chosen is None and fallback is None:
            # A candidate search should never throw away a sound entity-table
            # model just because the agent's first relational SQL is weaker.
            # This refit and its audit are inside the measured session.
            ts = time.time()
            try:
                rsql = self.reference_sql(t)
                rxtr, s1 = features(self.url, rsql, f"task.{tname(t)}_train_sample", seeds["train_sample"], ec)
                rxva, s2 = features(self.url, rsql, f"task.{tname(t)}_val", seeds["val"], ec)
                rp, rimp, rt = self.fit_feature_model(e["task_type"], rxtr, seeds["train_sample"][yc], rxva, "reference_start")
                rv = score(e["task_type"], seeds["val"][yc], rp)
                ta = time.time()
                ra = self.audit(t, k, rsql, seeds)
                audit_s = time.time() - ta
                sanitized, repaired = self.sanitize_candidate(t, k, seeds, rsql, rxtr, rxva, ra)
                if sanitized:
                    rec["reference_sanitization"] = sanitized
                    audit_s += sanitized["audit_seconds"]
                    rt += sanitized["train_seconds"]
                    s1 += sanitized["sql_seconds"]
                    if repaired:
                        rsql, rxtr, rxva, rimp, rv = repaired
                        ra = {"result": "clean", "source": "checked_projection"}
                rec["memory_reference"] = {"val": rv, "sql_seconds": s1 + s2, "train_seconds": rt,
                                           "audit_seconds": audit_s, "audit": ra.get("result")}
                if ra.get("result") == "clean":
                    frames = (rsql, rxtr, rxva, rimp)
                    if self.start_is_informative(rxtr):
                        best, best_sql = rv, rsql
                        best_frames = frames
                        msgs[1]["content"] += (f"\n\nThe memory validated an entity-table fallback ({metric}={rv:.5f}). "
                                                "Improve it with features relevant to this task; retain it if new features hurt validation.\n" + rsql)
                    else:
                        fallback = {"val": rv, "frames": frames, "source": "entity_reference"}
                        rec["memory_reference"]["fallback_only"] = True
                        msgs[1]["content"] += "\n\n" + self.constant_start_message()
            except Exception as err:
                rec["memory_reference"] = {"error": str(err)[:300], "audit_seconds": 0.0}
            rec["memory_reference"]["seconds"] = time.time() - ts

        if self.arm.get('delta_refinement') and k>1:
            base = best_frames if best_frames is not None else (fallback or {}).get('frames')
            if base is not None and best_frames is None:
                msgs[1]['content'] = (task_line+'\n\n'+self.constant_start_message()
                                      +'\nChecked base columns: '+', '.join(base[1].columns)
                                      +'\nUse validate_additions to create a varying feature view; no engineered best is preselected.')
            elif base is not None:
                inventory = {'chosen':{'val':best,'columns':list(base[1]),'top':base[3][:10]}}
                msgs[1]['content'] = task_line+'\n\n'+self.select_message(t,k,inventory,looked,False)
            if 'memory_push' in rec:
                rec['memory_push']['chars'] = len(msgs[1]['content'])-len(task_line)
                rec['memory_push']['view'] = 'compact checked inventory'
            msgs[0]['content'] += ('\n\nWarm refinement workflow: when a checked base is available, use validate_additions '
                'to test at most 12 new numeric feature columns. The memory joins them to its cached complete base and '
                'keeps the best checked validation result. A clean trial has priority over immediate submission; '
                'repair SQL or audit errors within the same response/tool budgets. If there is no checked base, '
                'validate_features first creates one. Submit without sql after a clean trial, or let the budget '
                'retain the checked fallback. Do not copy the complete base SQL into an addition query.')

        model_limit = self.arm.get("reuse_llm_limit", MAX_LLM_CALLS) if k > 1 else MAX_LLM_CALLS
        tool_limit = self.arm.get("reuse_tool_limit") if k > 1 else None

        def better(x):
            return best is None or (x > best if higher else x < best)

        while True:
            if goal_hit is not None and len(rec["llm"]) - goal_hit >= POST_GOAL_LLM_CALLS:
                rec["stop"] = "reached_previous"
                break
            if len(rec["llm"]) >= model_limit:
                rec["stop"] = "llm_budget"
                break
            try:
                guidance = self.remaining_budget_message(k, len(rec["llm"]), len(rec["tools"]))
                if guidance and rec["llm"]:
                    msgs.append({"role": "user", "content": guidance})
                early = self.early_validation_hint(k, len(rec["llm"]), len(rec["validations"]))
                if early and rec["llm"] and len(rec["llm"]) >= self.arm["cold_first_validation_by"] - 2:
                    msgs.append({"role": "user", "content": early})
                specs = self.step_tools(k,len(rec['llm']),len(rec['tools']),len(rec['validations']))
                if self.arm.get('delta_refinement'):
                    base = best_frames if best_frames is not None else (fallback or {}).get('frames')
                    clean = any(v.get('source')=='agent_additions' and v.get('audit_result')=='clean'
                                and not v.get('error') for v in rec['validations'])
                    specs = self.delta_step_tools(k,len(rec['llm']),len(rec['tools']),len(rec['validations']),
                                                   base is not None,clean)
                available_names = {s['function']['name'] for s in specs}
                r = self.llm.chat(msgs,specs)
            except LlmUnavailable as err:
                rec["error"] = f"llm: {err}"
                rec["stop"] = "llm_error"
                break
            m = r.pop("message")
            rec["llm"].append({**r, "tool_calls": len(m.get("tool_calls") or []), "content_chars": len(m.get("content") or "")})
            with open(os.path.join(self.a.out, "sessions", f"{part}.partial.json"), "w") as f:
                json.dump({**rec, "messages": msgs}, f, ensure_ascii=False, default=str)
            msgs.append(self.llm.history(m))
            calls = m.get("tool_calls") or []
            if not calls:
                idle += 1
                if idle >= 3:
                    rec["stop"] = "no_tool_calls"
                    break
                msgs.append({"role": "user", "content": "Use a tool, or call submit to finish."})
                continue
            idle = 0
            stop = None
            for c in calls:
                if tool_limit is not None and len(rec["tools"]) >= tool_limit:
                    stop = "reuse_tool_budget"
                    break
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except ValueError:
                    args = {}
                t0 = time.time()
                entry = {"i": len(rec["tools"]), "llm_i": len(rec["llm"]) - 1, "name": name, "args": args}
                if self.arm.get('delta_refinement') and k>1 and name not in available_names:
                    out = {'error':'This tool is unavailable at this refinement step. Use the exposed validation tool before submit.'}
                    entry['category'] = 'validate' if name.startswith('validate_') else 'submit' if name=='submit' else 'other'
                elif stop:
                    out = {"error": "session already ended"}
                elif name == "find_program" and self.arm.get("sql_memory"):
                    out = self.find_sql_program(t, k)
                    entry["category"] = "memory"
                elif name in FEATURE_TOOLS and self.arm.get("feature_memory"):
                    # the harness fills in what the agent cannot know: the seed table's entity column and this task's id
                    if name in ("compose_features", "find_features"):
                        args["seed_key"] = ec
                    if name == "find_program":
                        args["task"] = t
                    try:
                        out = middle.call(name, agent, sid, sid, args)
                    except Exception as err:
                        out = {"error": f"{err}"}
                    entry["category"] = "memory"
                elif name in ("list_tables", "describe_table", "join_path", "check_join", "run_sql"):
                    try:
                        out = middle.call(name, agent, sid, sid, args)
                    except Exception as err:
                        out = {"error": f"{err}"}
                    entry["category"] = "probe" if name == "run_sql" else "schema"
                elif name in ("validate_features","validate_additions"):
                    entry["category"] = "validate"
                    sql = args.get("sql", "")
                    added_sql = sql if name=='validate_additions' else None
                    delta_event = {} if added_sql is not None else None
                    if delta_event is not None:
                        entry['delta'] = delta_event
                    if args.get("bullet_ids"):
                        rec["bullet_ids"] = [str(b) for b in args["bullet_ids"]]
                    try:
                        if added_sql is not None:
                            if not self.arm.get('delta_refinement') or k<=1:
                                raise FeatureError('validate_additions is available only during this method\'s warm refinement')
                            base = best_frames if best_frames is not None else (fallback or {}).get('frames')
                            sql,xtr,xva = self.prepare_delta(t,k,seeds,base,added_sql,delta_event)
                            s1,s2 = delta_event['sql_seconds'],0.0
                        else:
                            xtr, s1 = features(self.url, sql, f"task.{tname(t)}_train_sample", seeds["train_sample"], ec,
                                               timeout_s=self.validation_timeout(k))
                            xva, s2 = features(self.url, sql, f"task.{tname(t)}_val", seeds["val"], ec,
                                               timeout_s=self.validation_timeout(k))
                        p, imp, tt = self.fit_feature_model(e["task_type"], xtr, seeds["train_sample"][yc], xva,
                                                          'agent_additions' if added_sql is not None else 'agent_validation')
                        val = score(e["task_type"], seeds["val"][yc], p)
                        # leak check at validation time (README §1.2, 10-21): a leaking validation does not count, so that
                        # neither the goal nor the best score can be reached with data after seed_time
                        ta = time.time()
                        leak = self.audit(t, k, sql, seeds)
                        audit_s = time.time() - ta
                        requested_sql = sql
                        sanitized, repaired = self.sanitize_candidate(t, k, seeds, sql, xtr, xva, leak)
                        if sanitized:
                            entry["sanitization"] = sanitized
                            audit_s += sanitized["audit_seconds"]
                            tt += sanitized["train_seconds"]
                            s1 += sanitized["sql_seconds"]
                            if repaired:
                                sql, xtr, xva, imp, val = repaired
                                leak = {"result": "clean", "source": "checked_projection"}
                        # A failed audit is not evidence of safety. All arms must pass.
                        leaking = leak.get("result") != "clean"
                        improved = (not leaking) and better(val)
                        if improved:
                            best, best_sql, streak = val, sql, 0
                            if self.arm.get("subset_selection"):
                                best_frames = (sql, xtr, xva, imp)
                        elif not leaking:
                            streak += 1
                        rec["validations"].append({"tool_i": entry["i"], "val": val, "improved": improved, "sql_seconds": s1 + s2,
                                                   "train_seconds": tt, "audit_seconds": audit_s, "leak": leaking,
                                                   "audit_result": leak.get("result"),
                                                   "leaking_columns": leak.get("columns_differing"), "n_features": xtr.shape[1],
                                                   "sql": sql, "importance": [c for c, _ in imp[:30]], "columns": list(xtr.columns)})
                        if self.arm.get("audit_diagnostics") and leak.get("result") not in ("clean", "leak"):
                            rec["validations"][-1]["audit_error"] = leak.get("why")
                        if sanitized:
                            rec["validations"][-1]["sanitization"] = sanitized
                            rec["validations"][-1]["requested_sql"] = requested_sql
                        out = {f"validation_{metric}": round(val, 5), "improved": improved,
                               "n_features": xtr.shape[1], "train_rows": len(xtr), "val_rows": len(xva),
                               "top_features_by_gain": imp[:15],
                               "validations_left": MAX_VALIDATIONS - len(rec["validations"])}
                        if best is not None:
                            out["best_so_far"] = round(best, 5)
                        if sanitized and sanitized.get("accepted"):
                            out["sanitized"] = {"removed_columns": sanitized["removed_columns"],
                                                "note": "Only the remaining outputs passed fresh value reproduction and leakage checks. "
                                                        "Submit without sql to keep the best checked candidate; do not reintroduce these columns."}
                        if leaking:
                            out.update(self.audit_rejection_feedback(leak))
                        entry.update(sql_seconds=s1 + s2, train_seconds=tt, audit_seconds=audit_s)
                    except Exception as err:  # noqa: BLE001 - contract errors and anything unexpected go back to the agent
                        # a failed validation uses one of the validations but does not count as "no improvement"
                        msg = str(err) if isinstance(err, FeatureError) else f"validation failed: {type(err).__name__}: {str(err)[:300]}"
                        out = {"error": msg, "validations_left": MAX_VALIDATIONS - len(rec["validations"]) - 1}
                        rec["validations"].append({"tool_i": entry["i"], "error": msg[:500], "sql": sql})
                    if delta_event is not None:
                        rec['validations'][-1].update(source='agent_additions',delta_sql=added_sql,delta=delta_event)
                    goal = self.target(t, k)
                    if goal_hit is not None:
                        # Previous arms retain rule B. The delta workflow gives
                        # failed attempts bounded repair before its one clean trial.
                        if added_sql is None or rec['validations'][-1].get('audit_result')=='clean':
                            stop = "reached_previous"
                    elif goal is not None and best is not None and (best >= goal if higher else best <= goal):
                        goal_hit = len(rec["llm"])
                        rec["goal_reached"] = {"validation": len(rec["validations"]), "llm_calls": goal_hit}
                        if len(rec["validations"]) >= MAX_VALIDATIONS:
                            stop = "reached_previous"
                        else:
                            window = self.post_goal_window(k, len(rec["llm"]))
                            out["goal_reached"] = ((f"This reaches the goal. You may make one more attempt to improve: one more validate_features "
                                                    f"within the next {window} model calls, after which the session ends with your "
                                                    "best validated features. Call submit to finish now.") if window else
                                                   "This reaches the goal and the session budget is exhausted. The best validated features are retained.")
                    elif len(rec["validations"]) >= MAX_VALIDATIONS:
                        stop = "validation_budget"
                    elif streak >= PATIENCE and best is not None:
                        stop = "patience"
                elif name == "submit":
                    entry["category"] = "submit"
                    sql = args.get("sql") or best_sql
                    ta = time.time()
                    rejected_unvalidated = self.arm.get("budget_guidance") and self.arm.get("subset_selection") and sql != best_sql
                    leak = self.audit(t, k, sql, seeds) if sql and sql != best_sql and not rejected_unvalidated else {}
                    entry["audit_seconds"] = time.time() - ta
                    if not sql:
                        out = {"error": "nothing validated yet; validate features first or pass sql"}
                    elif self.arm.get("subset_selection") and sql != best_sql:
                        out = {"error": "validate this exact SQL first, or submit the current best validated features"}
                    elif leak.get("result") == "leak":
                        out = {"error": "not submitted: these features read rows after seed_time",
                               "columns_reading_data_after_seed_time": leak.get("columns_differing")}
                    else:
                        submitted, stop = sql, "submitted"
                        if args.get("bullet_ids"):
                            rec["bullet_ids"] = [str(b) for b in args["bullet_ids"]]
                        out = {"ok": True}
                else:
                    out = {"error": f"unknown tool {name}"}
                entry["seconds"] = time.time() - t0
                text = json.dumps(out, ensure_ascii=False, default=str)
                entry["output_chars"] = len(text)
                entry["error"] = bool(isinstance(out, dict) and out.get("error"))
                rec["tools"].append(entry)
                if self.gmem:
                    g = self.gmem.send({"op": "step", "agent": agent, "action": f"{name}: {json.dumps(args, ensure_ascii=False)[:GMEMORY_OBS_CHARS]}",
                                        "observation": text[:GMEMORY_OBS_CHARS], "reward": -1 if entry["error"] else 0})
                    gmem_tokens = [gmem_tokens[0] + g.get("prompt_tokens", 0), gmem_tokens[1] + g.get("completion_tokens", 0)]
                msgs.append({"role": "tool", "tool_call_id": c["id"], "content": text[:TOOL_OUTPUT_CHARS]})
            if stop:
                rec["stop"] = stop
                break
        if best_sql is None and submitted is None and fallback is not None:
            best, best_frames = fallback["val"], fallback["frames"]
            best_sql = best_frames[0]
            rec["used_checked_fallback"] = {"source": fallback["source"], "val": best}
        if self.arm.get("subset_selection") and best_frames is not None and submitted in (None, best_sql):
            from feature_selection import select_subset

            ts = time.time()
            psql, pxtr, pxva, pimp = best_frames
            try:
                used = sum(x.get("seconds", 0) for x in (rec.get("memory_select") or {}).get("subset_selection", []))
                if (rec.get("memory_select") or {}).get("pruning_closed"):
                    used = 15.0  # the current-refit planner already made its one bounded projection decision
                subset = select_subset(pxtr, seeds["train_sample"][yc], pxva, seeds["val"][yc], pimp, best, higher,
                                       lambda xt, yt, xv: self.fit_feature_model(e["task_type"], xt, yt, xv, "final_subset"),
                                       lambda y, p: score(e["task_type"], y, p), budget_seconds=max(0.0, 15.0 - used))
                rec["memory_prune"] = {k2: v for k2, v in subset.items() if k2 != "chosen"}
                sub = subset["chosen"]
                if sub["columns"] != list(pxtr.columns):
                    headers, _ = read_sql(self.url, f"SELECT * FROM ({psql.strip().rstrip(';').replace('{seeds}', f'task.{tname(t)}_val')}) q LIMIT 0")
                    q = select_columns_sql(psql, list(headers.columns[:2]), sub["columns"])
                    check = {"sql_seconds": 0}
                    self.check_columns(t, k, q, seeds, pxva[sub["columns"]], check, timeout_s=SELECT_CHECK_TIMEOUT_S)
                    ta = time.time()
                    qa = self.audit(t, k, q, seeds)
                    rec["memory_prune"]["audit_seconds"] = time.time() - ta
                    rec["memory_prune"]["audit"] = qa.get("result")
                    if qa.get("result") == "clean":
                        best, best_sql = sub["val"], q
                        best_frames = (q, pxtr[sub["columns"]], pxva[sub["columns"]], sub["importance"])
                        if submitted is not None:
                            submitted = q
                        rec["validations"].append({"tool_i": None, "val": best, "sql": q, "leak": False,
                                                   "improved": True, "audit_result": "clean", "source": "memory_prune",
                                                   "n_features": len(sub["columns"]), "columns": sub["columns"],
                                                   "importance": [c for c, _ in sub["importance"]]})
            except Exception as err:
                rec.setdefault("memory_prune", {})["error"] = str(err)[:300]
            rec.setdefault("memory_prune", {})["elapsed_seconds"] = time.time() - ts
        # leak audits (at every validation and at submit) are the harness's checks, not the agent's work
        rec["audit_seconds"] = (sum(x.get("audit_seconds", 0) for x in rec["tools"])
                                + sum((rec.get(name) or {}).get("audit_seconds", 0)
                                      for name in ("memory_select", "memory_reference", "memory_prune")))
        rec["agent_seconds"] = time.time() - t_start - rec["audit_seconds"]
        self.charge_incumbent_work(t, k, rec)
        rec["final_sql"] = submitted or best_sql
        rec["final_source"] = ("submitted" if submitted else "checked_constant_fallback" if rec.get("used_checked_fallback")
                               else "best_validated" if best_sql else None)
        rec["best_val"] = best
        state = {"rec": rec, "msgs": msgs, "chosen": chosen, "gmem_tokens": gmem_tokens, "part": part}
        if self.arm.get("cold_union"):
            state["frames"] = best_frames
        return state

    def finish(self, t, k, seeds, middle, st, others=()):
        """The rest of a session after the agent's part: test score, audit, the goal of the next cutoff, learning and the
        record. `others`: the attempts that were not kept (arm mavra-select2); their work is charged to this session."""
        rec, msgs, chosen, gmem_tokens = st["rec"], st["msgs"], st["chosen"], st["gmem_tokens"]
        agent, sid, metric, higher = rec["agent"], rec["session"], rec["metric"], rec["higher_is_better"]
        best = rec["best_val"]
        if others:
            rec["attempts"] = []
            for o in [st, *others]:
                orec = o["rec"]
                row = {"attempt": orec["attempt"], "kept": o is st, "best_val": orec["best_val"], "stop": orec["stop"],
                       "llm_calls": len(orec["llm"]), "tool_calls": len(orec["tools"]), "validations": len(orec["validations"]),
                       "tokens": sum(x["input_tokens"] + x["output_tokens"] for x in orec["llm"]),
                       "agent_seconds": orec["agent_seconds"]}
                if (orec.get("memory_union") or {}).get("accepted"):
                    row["best_val"] = orec["memory_union"]["primary_before"]["val"]
                    row["combined_validation"] = orec["best_val"]
                if o is not st and orec["final_sql"] and self.a.eval_now:
                    try:  # for the record only; the choice used validation scores
                        row["test"] = self.evaluate(t, k, orec["final_sql"], seeds).get("test")
                    except Exception as err:  # noqa: BLE001
                        row["test_error"] = str(err)[:200]
                rec["attempts"].append(row)
            for o in others:
                orec = o["rec"]
                # the other attempts' model calls go with the session's calls in tokens, calls and cost (as sub-calls)
                rec["llm_sub"] = (rec.get("llm_sub") or []) + [{**x, "role": f"attempt {orec['attempt']} (not kept)"} for x in orec["llm"]]
                rec["agent_seconds"] += orec["agent_seconds"]
                rec["audit_seconds"] += orec["audit_seconds"]
            rec["other_attempts"] = [{**o["rec"], "messages": o["msgs"]} for o in others]
        if rec["final_sql"]:
            if self.a.eval_now:
                try:
                    rec["eval"] = self.evaluate(t, k, rec["final_sql"], seeds)
                except Exception as err:
                    rec["eval"] = {"error": str(err)[:500]}
            else:
                rec["eval"] = {"pending": True}
            # the final SQL is usually one already audited at its validation (same SQL, same seeds): that result is kept.
            # Auditing it again can fail on its own, e.g. a division the query plan evaluates before its guard (pilot 3).
            seen = next((v for v in reversed(rec["validations"]) if v.get("sql") == rec["final_sql"] and "val" in v and v.get("leak") is False), None)
            if seen is not None:
                rec["audit"] = {"result": "clean", "from_validation": seen["tool_i"]}
            elif chosen and rec["final_sql"] == chosen["sql"]:
                rec["audit"] = {"result": "clean", "from_memory_select": chosen["name"]}
            else:
                try:
                    rec["audit"] = self.audit(t, k, rec["final_sql"], seeds)
                except Exception as err:
                    rec["audit"] = {"result": "error", "why": str(err)[:300]}
        if rec["final_sql"] and (rec.get("audit") or {}).get("result") == "clean":
            self.prev_sql[t] = (k, rec["final_sql"])
        cut_short = rec["stop"] == "llm_error"  # the run stops after this session is saved; nothing is learned from it
        if self.arm.get("sql_memory"):
            t0 = time.time()
            rec["sql_memory"] = self.save_sql_program(t, k, rec)
            rec["sql_memory"]["seconds"] = time.time() - t0
        if self.tecod and not cut_short:
            try:
                rec["learning"] = self.tecod_add(t, k, rec)
            except Exception as err:
                rec["learning"] = {"error": str(err)[:500]}
            if rec["learning"].get("error"):
                log(f"{t} k{k}: TeCoD could not add the verified pair: {rec['learning']['error']}")
        if self.arm.get("feature_memory") and rec["final_sql"] and not cut_short:
            try:
                rec["learning"] = self.learn(t, k, rec, seeds, middle, agent, sid, chosen)
            except LlmUnavailable:
                raise
            except Exception as err:
                rec["learning"] = {"error": str(err)[:500]}
        if self.arm.get("ace") and not cut_short:
            try:
                rec["learning"] = self.ace_update(t, k, rec, msgs, agent)
            except LlmUnavailable:
                raise
            except Exception as err:
                rec["learning"] = {"error": str(err)[:500]}
        if self.arm.get("awm") and not cut_short:
            try:
                rec["learning"] = self.awm_update(t, k, rec, msgs, agent)
            except LlmUnavailable:
                raise
            except Exception as err:
                rec["learning"] = {"error": str(err)[:500]}
        if self.gmem and not cut_short:
            ref = self.refs.get((t, k)) or {}
            best = rec["best_val"]
            label = best is not None and ref.get("val") is not None and (best > ref["val"] if higher else best < ref["val"])
            t0 = time.time()
            g = self.gmem.send({"op": "end", "label": label, "feedback": f"best validation {metric} {best}; reference {ref.get('val')}; "
                                f"session ended by {rec['stop']}"})
            gmem_tokens = [gmem_tokens[0] + g.get("prompt_tokens", 0), gmem_tokens[1] + g.get("completion_tokens", 0)]
            rec["learning"] = {"seconds": time.time() - t0, "input_tokens": gmem_tokens[0], "output_tokens": gmem_tokens[1],
                               "label": label, "memory_size": g.get("memory_size"), "error": g.get("error")}
        sub_calls = rec.get("llm_sub") or []
        rec["totals"] = {
            "llm_calls": len(rec["llm"]) + len(sub_calls),
            "planner_llm_calls": len(rec["llm"]),
            "tool_calls": len(rec["tools"]) + sum(x.get("sub_tool_calls", 0) for x in rec["tools"]),
            "tool_calls_by_category": {c: sum(1 for x in rec["tools"] if x.get("category") == c) for c in ("schema", "probe", "validate", "memory", "submit")},
            "input_tokens": sum(x["input_tokens"] for x in rec["llm"] + sub_calls),
            "output_tokens": sum(x["output_tokens"] for x in rec["llm"] + sub_calls),
            "llm_seconds": sum(x["seconds"] for x in rec["llm"] + sub_calls),
            "llm_retry_seconds": sum(x.get("retry_seconds", 0) for x in rec["llm"] + sub_calls),
            "tool_seconds": sum(x["seconds"] - x.get("audit_seconds", 0) for x in rec["tools"]),
            "validation_sql_seconds": sum(x.get("sql_seconds", 0) for x in rec["validations"]),
            "validation_train_seconds": sum(x.get("train_seconds", 0) for x in rec["validations"]),
        }
        if self.arm.get("cold_union"):
            fits = [*rec.get("feature_fits", []), *(f for o in others for f in o["rec"].get("feature_fits", []))]
            rec["totals"]["feature_fit_calls"] = len(fits)
            rec["totals"]["feature_fit_seconds"] = sum(f["seconds"] for f in fits)
        for o in others:
            ot = o["rec"]["tools"]
            rec["totals"]["tool_calls"] += len(ot)
            for c in rec["totals"]["tool_calls_by_category"]:
                rec["totals"]["tool_calls_by_category"][c] += sum(1 for x in ot if x.get("category") == c)
            rec["totals"]["tool_seconds"] += sum(x["seconds"] - x.get("audit_seconds", 0) for x in ot)
            rec["totals"]["validation_sql_seconds"] += sum(x.get("sql_seconds", 0) for x in o["rec"]["validations"])
            rec["totals"]["validation_train_seconds"] += sum(x.get("train_seconds", 0) for x in o["rec"]["validations"])
        rec["totals"]["tokens"] = rec["totals"]["input_tokens"] + rec["totals"]["output_tokens"]
        lr = rec.get("learning") or {}
        # learning is charged to the session that triggered it (README §1.4); its time is background work, reported apart
        rec["totals"]["learn_tokens"] = lr.get("input_tokens", 0) + lr.get("output_tokens", 0)
        rec["totals"]["learn_seconds"] = lr.get("seconds", 0)
        rec["totals"]["tokens_with_learning"] = rec["totals"]["tokens"] + rec["totals"]["learn_tokens"]
        rec["messages"] = msgs
        with open(os.path.join(self.a.out, "sessions", f"{tname(t)}-k{k}.json"), "w") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1, default=str)
        for o in [st, *others]:
            partial = os.path.join(self.a.out, "sessions", f"{o['part']}.partial.json")
            if os.path.exists(partial):
                os.remove(partial)
        ev = rec.get("eval") or {}
        log(f"{t} k{k}: stop={rec['stop']} llm={rec['totals']['llm_calls']} tools={rec['totals']['tool_calls']} "
            f"tok={rec['totals']['tokens']} t={rec['agent_seconds']:.0f}s val={best} test={ev.get('test')} audit={(rec.get('audit') or {}).get('result')}")
        if cut_short:
            raise LlmUnavailable(f"{sid}: {rec['error']}")
        return rec

    def evaluate_after_run(self, ks):
        """Test scores of every session, after the last cutoff, on the database as it was at the session's cutoff: views
        that keep the rows with time <= that cutoff's test timestamp, which are exactly the rows the database held then
        (the template holds time <= test_1 without null times, every append adds (previous, current]). The seed tables
        of the cutoff are rebuilt and the final SQL is scored as `evaluate` scores it at the end of a session."""
        t0 = time.time()
        for k in ks:
            todo = [(f, json.load(open(f))) for f in glob.glob(os.path.join(self.a.out, "sessions", f"*-k{k}.json"))]
            todo = [(f, r) for f, r in todo if r.get("final_sql") and (r.get("eval") or {}).get("pending")]
            if not todo:
                continue
            cut = next(iter(self.tasks.values()))["cutoffs"][k - 1]["test_timestamp"]
            schema = f"replay_k{k}"
            seeds = self.seed_tables(k)
            with psycopg.connect(self.url, autocommit=True) as con:
                con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
                con.execute(f"CREATE SCHEMA {schema}")
                for name, spec in self.manifest["tables"].items():
                    tc = spec.get("time_col")
                    cond = f" WHERE {tc.lower()} <= '{pd.Timestamp(cut)}'" if tc else ""
                    con.execute(f"CREATE VIEW {schema}.{name.lower()} AS SELECT * FROM public.{name.lower()}{cond}")

            def score_one(f, r):
                sql = in_schema(r["final_sql"], schema)
                try:
                    r["eval"] = {**self.evaluate(r["task"], k, sql, seeds[r["task"]], search_path=f"{schema}, public"), "after_run": True}
                except Exception as err:
                    r["eval"] = {"error": str(err)[:500], "after_run": True}
                with open(f, "w") as fh:
                    json.dump(r, fh, ensure_ascii=False, indent=1, default=str)
                log(f"{r['task']} k{k}: test={r['eval'].get('test')}")

            try:
                # the sessions of one cutoff are scored side by side (each on its own connections; scores do not depend on it)
                with cf.ThreadPoolExecutor(len(todo)) as ex:
                    for fut in [ex.submit(score_one, f, r) for f, r in todo]:
                        fut.result()
            finally:
                with psycopg.connect(self.url, autocommit=True) as con:
                    con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        log(f"test scores after the run: {time.time() - t0:.0f}s")

    def tried_columns(self, t, rec, chosen):
        """Columns of this session's validations that are not in its final SQL (no gain, or leaking), after the ones
        earlier sessions of the task recorded and the final SQL does not use; at most 40 (arm mavra-select)."""
        final = next((v.get("columns") for v in reversed(rec["validations"]) if v.get("sql") == rec["final_sql"] and v.get("columns")), None)
        if final is None and chosen and chosen["sql"] == rec["final_sql"]:
            final = chosen["columns"]
        final = set(final or [])
        out = []
        for v in rec["validations"]:
            for c in v.get("columns") or []:
                tag = f"{c} (leaked)" if v.get("leak") and c in set(v.get("leaking_columns") or []) else c
                if c not in final and tag not in out and c not in out:
                    out.append(tag)
        for c in rec.get("tried_before") or []:  # what the task's program recorded (find_program at the session start)
            if str(c).split(" ")[0] not in final and c not in out:
                out.append(c)
        return out[:40]

    def learn(self, t, k, rec, seeds, middle, agent, sid, chosen=None):
        """Learning after a session (README §1.6, amended before any P2 result): when the submission beats the reference.
        Columns the audit found leaking are left out of the extractor's input; every definition still has to pass F1-F4,
        and a leaking column cannot pass F3 (the compiled SQL is bounded by seed_time) or F4."""
        e = self.tasks[t]
        ec = e["entity_col"].lower()
        ref = self.refs.get((t, k)) or {}
        best, higher = rec["best_val"], rec["higher_is_better"]
        beats = best is not None and ref.get("val") is not None and (best > ref["val"] if higher else best < ref["val"])
        audit = rec.get("audit") or {}
        select = self.arm.get("select_start")
        if not beats and not (select and audit.get("result") == "clean"):
            return {"skipped": "validation score not better than the reference"}
        leaking = {c.lower() for c in audit.get("columns_differing") or []}
        imp = next((v.get("importance") for v in reversed(rec["validations"]) if v.get("sql") == rec["final_sql"] and v.get("importance")), [])
        if not imp and chosen and chosen["sql"] == rec["final_sql"]:
            imp = chosen.get("importance") or []
        imp = [c for c in imp if c.lower() not in leaking]
        tstar = seeds["train_sample"]["seed_time"].max()
        sub = seeds["train_sample"][seeds["train_sample"]["seed_time"] == tstar].sort_values(ec).head(AUDIT_SEEDS)
        schema = f"learn_{tname(t)}_k{k}"
        with psycopg.connect(self.url, autocommit=True) as con:
            con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            con.execute(f"CREATE SCHEMA {schema}")
            for name, spec in self.manifest["tables"].items():
                tc = spec.get("time_col")
                cond = f" WHERE {tc.lower()} <= '{tstar}'" if tc else ""
                con.execute(f"CREATE VIEW {schema}.{name.lower()} AS SELECT * FROM public.{name.lower()}{cond}")
            con.execute(f"CREATE TABLE {schema}.seeds AS SELECT * FROM task.{tname(t)}_train_sample WHERE false")
            copy_rows(con, f"{schema}.seeds", sub)
        body = {"agent": agent, "session": sid, "task": t, "description": self.task_desc[t]["description"],
                "cutoff": e["cutoffs"][k - 1]["test_timestamp"], "seed_key": ec, "entity_table": e["entity_table"].lower(),
                "entity_key": self.manifest["tables"][e["entity_table"]]["pkey"].lower(), "sql": rec["final_sql"], "importance": imp,
                "seeds": f"(select * from task.{tname(t)}_train_sample order by {ec}, seed_time limit {AUDIT_SEEDS})",
                "audit_schema": schema, "audit_seeds": f"(select * from {schema}.seeds)", "val_score": best, "metric": rec["metric"],
                "audit_clean": audit.get("result") == "clean", "val_table": f"task.{tname(t)}_val"}
        if select:
            # below the single-table reference the session still leaves its audited SQL as the task's program, without
            # extraction or published definitions; the program keeps the columns the task's sessions tried without keeping
            body["program_only"] = not beats
            body["tried"] = self.tried_columns(t, rec, chosen)
        t0 = time.time()
        try:
            r = middle.post("/v1/learn_features", body)
        finally:
            with psycopg.connect(self.url, autocommit=True) as con:
                con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        ex = r.get("extraction") or {}
        events = [{k2: f.get(k2) for k2 in ("event", "key", "revision", "failed_gate", "reason")} for f in r.get("features") or []]
        log(f"{t} k{k}: learning {len(events)} drafts -> {sum(1 for x in events if x['event'] in ('promoted', 'corroborated'))} published")
        return {"seconds": time.time() - t0, "input_tokens": ex.get("input_tokens", 0), "output_tokens": ex.get("output_tokens", 0),
                "events": events, "program": r.get("program"), "error": r.get("error"), "audit": audit.get("result"),
                "excluded_leaking_columns": sorted(leaking), "raw": r}


    def ace_update(self, t, k, rec, msgs, agent):
        """ACE after a session (online, no ground truth): Reflector (REFLECTOR_PROMPT_NO_GT), counters, Curator
        (CURATOR_PROMPT_NO_GT, ADD operations), each one call to the agent's model at temperature 0."""
        playbook = self.playbooks.get(agent, ACE_EMPTY_PLAYBOOK)
        self.ace_steps[agent] = self.ace_steps.get(agent, 0) + 1
        e = self.tasks[t]
        question = f"{self.task_desc[t]['description']} (task {t}, cutoff {e['cutoffs'][k - 1]['test_timestamp'][:10]})"
        parts = []
        for m in msgs[1:]:
            if m["role"] == "assistant":
                if m.get("content"):
                    parts.append(f"ASSISTANT: {m['content']}")
                for c in m.get("tool_calls") or []:
                    parts.append(f"TOOL CALL {c['function']['name']}: {c['function'].get('arguments', '')}")
            elif m["role"] == "tool":
                parts.append(f"TOOL OUTPUT: {m['content'][:TOOL_OUTPUT_CHARS]}")
            else:
                parts.append(f"{m['role'].upper()}: {m['content']}")
        trace = "\n".join(parts)
        vals = [f"validation {i + 1}: " + (f"{rec['metric']} = {v['val']:.5f}" if "val" in v else f"error: {v.get('error')}")
                for i, v in enumerate(rec["validations"])]
        feedback = "\n".join(vals + [f"best validation {rec['metric']}: {rec['best_val']}", f"session ended by: {rec['stop']}"])
        bullets = ace_pb.extract_playbook_bullets(playbook, rec.get("bullet_ids") or [])
        t0, tok_in, tok_out = time.time(), 0, 0
        r = self.llm.chat([{"role": "user", "content": ace_reflector.REFLECTOR_PROMPT_NO_GT.format(
            question, trace, rec.get("final_sql") or "(no features submitted)", feedback, bullets)}], temperature=0)
        tok_in, tok_out = tok_in + r["input_tokens"], tok_out + r["output_tokens"]
        reflection = r["message"].get("content") or ""
        parsed = ace_pb.extract_json_from_text(reflection) or {}
        tags = parsed.get("bullet_tags") or [] if isinstance(parsed, dict) else []
        if tags:
            playbook = ace_pb.update_bullet_counts(playbook, tags)
        r = self.llm.chat([{"role": "user", "content": ace_curator.CURATOR_PROMPT_NO_GT.format(
            current_step=self.ace_steps[agent], total_samples=self.timeline["K"], token_budget=ACE_TOKEN_BUDGET,
            playbook_stats=json.dumps(ace_pb.get_playbook_stats(playbook), indent=2), recent_reflection=reflection,
            current_playbook=playbook, question_context=question)}], temperature=0)
        tok_in, tok_out = tok_in + r["input_tokens"], tok_out + r["output_tokens"]
        cur = ace_pb.extract_json_from_text(r["message"].get("content") or "") or {}
        ops = [o for o in (cur.get("operations") or []) if isinstance(o, dict) and o.get("type") == "ADD"] if isinstance(cur, dict) else []
        if ops:
            playbook, _ = ace_pb.apply_curator_operations(playbook, ops, ace_pb.get_next_global_id(playbook))
        self.playbooks[agent] = playbook
        os.makedirs(os.path.join(self.a.out, "playbooks"), exist_ok=True)
        with open(os.path.join(self.a.out, "playbooks", f"{agent}-k{k}.txt"), "w") as f:
            f.write(playbook)
        n = ace_pb.get_playbook_stats(playbook)["total_bullets"]
        log(f"{t} k{k}: ACE {len(tags)} tags, {len(ops)} additions, playbook {n} bullets")
        return {"seconds": time.time() - t0, "input_tokens": tok_in, "output_tokens": tok_out, "bullet_tags": tags,
                "operations": ops, "playbook_bullets": n}

    def awm_experience(self, t, k, msgs):
        """Reconstruct the exact experience used by online induction from its saved messages."""
        out_of = {m["tool_call_id"]: m["content"] for m in msgs if m["role"] == "tool"}
        steps = []
        for m in msgs:
            if m["role"] != "assistant" or not m.get("tool_calls"):
                continue
            acts = []
            for c in m["tool_calls"]:
                try:
                    failed = "error" in json.loads(out_of.get(c["id"], "{}"))
                except ValueError:
                    failed = False
                if not failed:
                    acts.append(f"{c['function']['name']}({c['function'].get('arguments') or '{}'})"[:TOOL_OUTPUT_CHARS])
            if acts:
                steps.append(((m.get("content") or m.get("reasoning_content") or "").strip(), acts))
        query = f"{self.task_desc[t]['description']} (cutoff {self.tasks[t]['cutoffs'][k - 1]['test_timestamp'][:10]})"
        return {"template": t, "query": query, "steps": steps}

    def restore_awm(self, source, first):
        """Restore both accumulated experiences and the last nonempty workflows, without LLM calls."""
        records = []
        for f in glob.glob(os.path.join(source, "sessions", "*.json")):
            if not f.endswith(".partial.json"):
                rec = json.load(open(f))
                if rec["k"] < first:
                    records.append(rec)
        for rec in sorted(records, key=lambda r: (r["k"], r["task"])):
            agent, t, k = rec["agent"], rec["task"], rec["k"]
            learning = rec.get("learning") or {}
            if learning.get("success"):
                if not rec.get("messages"):
                    raise ValueError(f"Cannot restore AWM: missing messages for {t} k{k}")
                self.awm_pool.setdefault(agent, []).append(self.awm_experience(t, k, rec["messages"]))
            pool = self.awm_pool.get(agent) or []
            if pool:
                if learning.get("experiences") != len(pool) or learning.get("error"):
                    raise ValueError(f"Cannot restore AWM: incomplete induction for {t} k{k}")
                path = os.path.join(source, "workflows", f"{agent}-k{k}.txt")
                workflows = open(path).read()
                if len(workflows) != learning.get("workflow_chars"):
                    raise ValueError(f"Cannot restore AWM: workflow mismatch for {t} k{k}")
                if workflows:
                    self.awm_workflows[agent] = workflows
        log(f"restored AWM: {sum(map(len, self.awm_pool.values()))} experiences, {len(self.awm_workflows)} workflows")

    def awm_update(self, t, k, rec, msgs, agent):
        """AWM after a session, as its online WebArena pipeline (pipeline.py, induce_prompt.py): a successful session joins
        the agent's experience; then workflows are induced again from all successful experiences, at most
        AWM_PER_TEMPLATE per task template (here: the task) sampled at random, with AWM's instruction, a one-shot example
        in its format and the examples (`Query:` with `<think>`/`<action>` steps, actions only, failed calls left out as
        AWM drops invalid steps). Success = the study's signal (validation better than the reference), as AWM's "gt"
        criterion; test labels are never used."""
        ref = self.refs.get((t, k)) or {}
        best, higher = rec["best_val"], rec["higher_is_better"]
        success = best is not None and ref.get("val") is not None and (best > ref["val"] if higher else best < ref["val"])
        if success:
            self.awm_pool.setdefault(agent, []).append(self.awm_experience(t, k, msgs))
        pool = self.awm_pool.get(agent) or []
        if not pool:
            return {"success": success, "skipped": "no successful experience yet"}
        rng = random.Random(self.a.run * 1000 + k)
        by_template = {}
        for ex in pool:
            by_template.setdefault(ex["template"], []).append(ex)
        chosen = [ex for v in by_template.values() for ex in rng.sample(v, min(AWM_PER_TEMPLATE, len(v)))]
        instruction = open(os.path.join(AWM_DIR, "instruction.txt")).read()
        for old, new in AWM_OVERRIDES:
            assert old in instruction, old
            instruction = instruction.replace(old, new)
        one_shot = open(os.path.join(AWM_DIR, "one_shot_relbench.txt")).read()
        examples = []
        for ex in chosen:
            traj = "\n\n".join(f"<think>\n{th}\n</think>\n<action>\n" + "\n".join(acts) + "\n</action>" for th, acts in ex["steps"])
            examples.append(f"Query: {ex['query']}\nActions:\n{traj}")
        prompt = "\n\n".join([instruction, one_shot, "\n\n".join(["## Concrete Examples"] + examples + ["## Summary Workflows"])])
        t0 = time.time()
        r = self.llm.chat([{"role": "user", "content": prompt}], temperature=AWM_TEMPERATURE, max_tokens=AWM_MAX_TOKENS, thinking=AWM_THINKING)
        workflows = (r["message"].get("content") or "").strip()
        if workflows:
            self.awm_workflows[agent] = workflows
        os.makedirs(os.path.join(self.a.out, "workflows"), exist_ok=True)
        with open(os.path.join(self.a.out, "workflows", f"{agent}-k{k}.txt"), "w") as f:
            f.write(workflows)
        log(f"{t} k{k}: AWM {len(pool)} successful experiences, {len(chosen)} in the prompt, workflows {len(workflows)} chars")
        return {"success": success, "seconds": time.time() - t0, "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
                "experiences": len(pool), "examples": len(chosen), "workflow_chars": len(workflows), "finish_reason": r.get("finish_reason")}

    def main(self):
        a = self.a
        arm = ARMS[a.arm]
        log(f"run {a.arm} r{a.run}: database {self.db_name} from {a.template}")
        with open(os.path.join(a.out, "harness.pid"), "w") as f:  # run-queue.py: is this cell still running?
            f.write(str(os.getpid()))
        create_run_db(self.url_admin, a.template, self.db_name)
        middle = None
        summary = {"arm": a.arm, "run": a.run, "db": self.db_name, "template": a.template, "smoke": a.smoke, "settings": {
            "MAX_LLM_CALLS": MAX_LLM_CALLS, "MAX_VALIDATIONS": MAX_VALIDATIONS, "PATIENCE": PATIENCE, "SAMPLE_SIZE": SAMPLE_SIZE,
            "LGB_PARAMS": LGB_PARAMS, "model": self.llm.model, "llm": self.llm.provider, "reasoning_effort": self.llm.effort,
            "thinking": self.llm.thinking,
            "base_url": self.llm.base, "require_model": self.llm.require, "arm_config": arm,
            "harness_sha256": hashlib.sha256(open(__file__, "rb").read()).hexdigest(),
            "test_scores": "now" if a.eval_now else "after the run"}, "cutoffs": list(self.kept_cutoffs)}
        if a.targets_from:
            summary["resumed"] = {"from": a.targets_from, "at_cutoff": min(int(x) for x in a.cutoffs) if a.cutoffs else 1}
        try:
            middle = Middle(self.url, arm["middle_mode"], a.out, a.port or free_port(), a.llm if arm.get("extractor") else None, self.llm.effort, self.llm.prefix)
            if arm.get("gmemory"):
                self.gmem = GMemoryService(self.env, a.out, self.llm)
            if arm.get("tecod"):
                self.tecod = TecodService(a.out)
            ks = range(1, self.timeline["K"] + 1) if not a.cutoffs else [int(x) for x in a.cutoffs]
            prev = None
            for k in ks:
                cut = next(iter(self.tasks.values()))["cutoffs"][k - 1]
                rec = {"k": k, "test_timestamp": cut["test_timestamp"]}
                if prev is not None:
                    rec["append"] = self.append(pd.Timestamp(prev), pd.Timestamp(cut["test_timestamp"]))
                    log(f"k{k}: appended {rec['append']['rows']}")
                elif k > 1:
                    first = next(iter(self.tasks.values()))["cutoffs"][0]["test_timestamp"]
                    rec["append"] = self.append(pd.Timestamp(first), pd.Timestamp(cut["test_timestamp"]))
                prev = cut["test_timestamp"]
                seeds = self.seed_tables(k)
                rec["reference"] = {}
                for t in self.tasks:
                    try:
                        rec["reference"][t] = self.evaluate(t, k, self.reference_sql(t), seeds[t])
                    except Exception as err:
                        rec["reference"][t] = {"error": str(err)[:300]}
                log(f"k{k}: reference {json.dumps({t: (v.get('val'), v.get('test')) for t, v in rec['reference'].items()})}")
                self.refs.update({(t, k): v for t, v in rec["reference"].items()})
                if k > 1:
                    with cf.ThreadPoolExecutor(len(self.tasks)) as ex:
                        goals = {t: ex.submit(self.incumbent, t, k, seeds[t]) for t in self.tasks}
                        self.targets.update({(t, k): g.result() for t, g in goals.items()})
                    log(f"k{k}: goals {json.dumps({t: (self.targets[(t, k)] or {}).get('val') for t in self.tasks})}")
                order = list(self.tasks)
                random.Random(a.run * 1000 + k).shuffle(order)
                rec["order"] = order
                if arm["parallel_ok"] and a.parallel > 1:
                    with cf.ThreadPoolExecutor(a.parallel) as ex:
                        futs = [ex.submit(self.session, t, k, seeds[t], middle) for t in order]
                        for f in futs:
                            f.result()
                else:
                    for t in order:
                        self.session(t, k, seeds[t], middle)
                summary["cutoffs"].append(rec)
                with open(os.path.join(a.out, "run.json"), "w") as f:
                    json.dump(summary, f, indent=1, default=str)
            if not a.eval_now:
                self.evaluate_after_run(range(1, self.timeline["K"] + 1))  # a resumed run: the copied sessions too
            summary["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")  # every cutoff and every test score done
        except Exception:
            traceback.print_exc()
            summary["error"] = traceback.format_exc()[-2000:]
            raise
        finally:
            with open(os.path.join(a.out, "run.json"), "w") as f:
                json.dump(summary, f, indent=1, default=str)
            if self.gmem:
                self.gmem.close()
            if self.tecod:
                try:
                    with open(os.path.join(a.out, "tecod-pool.json"), "w") as f:
                        json.dump(self.tecod.send({"op": "dump"}), f, ensure_ascii=False, indent=1)
                except Exception as err:
                    log(f"could not export the TeCoD pool: {err}")
                self.tecod.close()
            if middle:
                if arm.get("sql_memory"):
                    with open(os.path.join(a.out, "sql-programs.json"), "w") as f:
                        json.dump(self.sql_programs, f, ensure_ascii=False, indent=1)
                if arm.get("feature_memory"):
                    try:
                        with open(os.path.join(a.out, "features.json"), "w") as f:
                            json.dump(middle.get("/v1/features"), f, ensure_ascii=False, indent=1)
                    except Exception as err:
                        log(f"could not export features: {err}")
                middle.close()
            if not a.keep_db:
                drop_db(self.url_admin, self.db_name)
        log("run done")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=list(ARMS))
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--prep", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tasks", nargs="*")
    ap.add_argument("--cutoffs", nargs="*", help="subset of cutoffs (smoke tests; with --targets-from, resume a run at a cutoff)")
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--port", type=int)
    ap.add_argument("--keep-db", action="store_true")
    ap.add_argument("--targets-from", help="run folder whose sessions at the cutoff before the first one give the retraining goals")
    ap.add_argument("--llm", default="deepseek", choices=list(PROVIDERS), help="model service (pilot: river; since 10-21: deepseek)")
    ap.add_argument("--reasoning-effort", help="reasoning effort of the agents and of MAVRA's extractor (default: the .env setting; "
                    "since 10-21 low with thinking on; DeepSeek's API offers low/high/max and treats medium as high)")
    ap.add_argument("--eval-now", action="store_true", help="score each session on the test seeds right after it (default: after the run)")
    ap.add_argument("--smoke", action="store_true", help="pipeline check only: 8 LLM calls, 2 validations; results are not used")
    a = ap.parse_args()
    if a.arm in ("sql-only", "tecod") and a.targets_from:
        ap.error(f"{a.arm} must start from an empty memory; --targets-from does not restore it")
    if a.smoke:
        global MAX_LLM_CALLS, MAX_VALIDATIONS
        MAX_LLM_CALLS, MAX_VALIDATIONS = 8, 2
    os.makedirs(a.out, exist_ok=True)

    def stop(signum, frame):  # a stopped cell still closes its middle layer and drops its database (Run.main's finally)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, stop)
    try:
        Run(a).main()
    except SystemExit as err:
        sys.stdout.flush()
        os._exit(err.code if isinstance(err.code, int) else 1)  # sessions in worker threads would keep the process alive


if __name__ == "__main__":
    main()
