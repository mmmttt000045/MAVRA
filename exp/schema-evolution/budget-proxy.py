#!/usr/bin/env python3
"""Loopback-only relay to an OpenAI-compatible API with a durable token-cost ledger.

Every model call of the study (agents, extraction, optimization, ACE/AWM/G-Memory
memory updates) passes through this relay. A call is admitted only if the
conservative charge of all calls so far, open reservations, and this call's
worst case stay below the configured cap.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time

UPSTREAM = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').rstrip('/') + '/chat/completions'
LOCAL_TOKEN = 'mavra-local-relay'
DEFAULT_MODEL = 'deepseek-flash'
DEFAULT_MAX_OUTPUT_TOKENS = 16384
DEFAULT_CAP = 39.4
RATE_UNITS = {'hit': 0.04, 'miss': 2.0, 'output': 8.0}  # conservative rate units per million tokens


def charge(usage, r):
    total = int(usage.get('prompt_tokens', 0))
    hit = int(usage.get('prompt_cache_hit_tokens', (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 0)))
    hit = max(0, min(total, hit))
    return (hit * r['hit'] + (total - hit) * r['miss'] + int(usage.get('completion_tokens', 0)) * r['output']) / 1e6


def reservation(body, r):
    n = len(json.dumps(body, ensure_ascii=False).encode('utf-8')) + 4096
    return (n * r['miss'] + body['max_tokens'] * r['output']) / 1e6


class Budget:
    def __init__(self, directory, key_file=None, cap=None, model=DEFAULT_MODEL):
        self.model = model
        self.max_output_tokens = DEFAULT_MAX_OUTPUT_TOKENS
        self.cap = float(DEFAULT_CAP if cap is None else cap)
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / 'budget-state.json'
        key = (
            Path(key_file).read_text(encoding='utf-8').strip()
            if key_file and key_file != '-'
            else (os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('OPENAI_API_KEY') or '').strip()
        )
        if not key:
            raise RuntimeError('Set DEEPSEEK_API_KEY (or OPENAI_API_KEY) or pass --key-file')
        self.headers = {'Authorization': 'Bearer ' + key}
        self.lock = threading.Lock()
        self.reserved = 0.0
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding='utf-8'))
            self.state['charged'] = self.state.get('charged', 0.0) + self.state.get('reserved', 0.0)
        else:
            self.state = {
                'cap': self.cap,
                'charged': 0.0,
                'calls': 0,
                'errors': 0,
                'models': {},
            }
        self.save()

    def save(self):
        self.state['reserved'] = self.reserved
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.state, indent=2) + '\n', encoding='utf-8')
        tmp.replace(self.path)

    def acquire(self, body):
        with self.lock:
            if (self.dir / 'STOP').exists():
                raise RuntimeError('study stop requested')
            need = reservation(body, RATE_UNITS)
            if self.state['charged'] + self.reserved + need > self.cap:
                self.state['status'] = 'budget_limit'
                self.save()
                raise RuntimeError('study spending limit reached')
            self.reserved += need
            self.save()
            return need

    def finish(self, need, status, data, seconds, arm, body):
        usage = data.get('usage') or {}
        cost = charge(usage, RATE_UNITS) if usage else need
        with self.lock:
            self.reserved -= need
            self.state['charged'] += cost
            self.state['calls'] += 1
            self.state['errors'] += int(status != 200)
            model = data.get('model', 'unreported')
            self.state['models'][model] = self.state['models'].get(model, 0) + 1
            row = {
                'arm': arm,
                'status': status,
                'model': model,
                'usage': usage,
                'charged': cost,
                'seconds': seconds,
                'response_id': data.get('id'),
            }
            with (self.dir / 'api-usage.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(row) + '\n')
            self.save()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, data):
        raw = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.reply(200 if self.path == '/health' else 404, {'ok': self.path == '/health'})

    def do_POST(self):
        import requests

        b = self.server.budget
        parts = self.path.strip('/').split('/')
        arm = parts[1] if len(parts) >= 4 and parts[0] == 'arm' else 'unassigned'
        route = '/' + '/'.join(parts[2:]) if arm != 'unassigned' else self.path
        if route not in ('/chat/completions', '/v1/chat/completions'):
            return self.reply(404, {'error': 'unknown route'})
        if self.headers.get('Authorization') != 'Bearer ' + LOCAL_TOKEN:
            return self.reply(401, {'error': 'local study token required'})
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 4_000_000:
                raise ValueError('request size outside study limit')
            body = json.loads(self.rfile.read(size))
            if body.get('model') != b.model or body.get('stream'):
                raise ValueError('only the configured model and non-streaming requests are allowed')
            body['max_tokens'] = min(int(body.get('max_tokens') or b.max_output_tokens), b.max_output_tokens)
            need = b.acquire(body)
        except Exception as e:
            with b.lock, (b.dir / 'denied-requests.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps({'arm': arm, 'error': str(e)}) + '\n')
            return self.reply(402, {'error': {'message': str(e), 'type': 'study_limit'}})
        t0 = time.monotonic()
        try:
            with requests.Session() as s:
                s.trust_env = False
                r = s.post(UPSTREAM, json=body, headers=b.headers, timeout=300)
                status, data = r.status_code, r.json()
        except Exception:
            status, data = 503, {'error': {'message': 'upstream API transport failure', 'type': 'upstream'}}
        b.finish(need, status, data, time.monotonic() - t0, arm, body)
        self.reply(status, data)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--port', type=int, default=19530)
    p.add_argument('--out', required=True)
    p.add_argument('--key-file', default='-')
    p.add_argument('--cap', type=float, default=None, help='spending cap in rate units for this ledger')
    p.add_argument('--model', default=DEFAULT_MODEL)
    a = p.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
    server.budget = Budget(a.out, a.key_file, a.cap, a.model)
    server.serve_forever()
