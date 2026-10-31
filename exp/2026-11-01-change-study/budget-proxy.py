#!/usr/bin/env python3
"""Loopback-only relay to the official DeepSeek API with a durable spending cap.

Every model call of the study (agents, extraction, optimization, ACE/AWM/G-Memory
memory updates) passes through this relay. A call is admitted only if the
conservative charge of all calls so far, the open reservations and this call's
worst case stay below the study cap, and the account balance confirms it. Usage is
priced at the official peak or off-peak rate for the Beijing time of the call.
The API key is read from a private file and never written to the ledger.
"""
import argparse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

HERE = Path(__file__).resolve().parent
UPSTREAM = 'https://api.deepseek.com/chat/completions'
OFF_PEAK = {'hit': .02, 'miss': 1.0, 'output': 4.0}  # CNY per million tokens
PEAK = {k: 2 * v for k, v in OFF_PEAK.items()}
BEIJING = timezone(timedelta(hours=8))


def rates(now=None):
    t = (now or datetime.now(timezone.utc)).astimezone(BEIJING)
    peak = t.weekday() < 5 and (9 <= t.hour < 12 or 14 <= t.hour < 18)
    return PEAK if peak else OFF_PEAK


def charge(usage, r):
    total = int(usage.get('prompt_tokens', 0))
    hit = int(usage.get('prompt_cache_hit_tokens', (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 0)))
    hit = max(0, min(total, hit))
    return (hit * r['hit'] + (total - hit) * r['miss'] + int(usage.get('completion_tokens', 0)) * r['output']) / 1e6


def reservation(body, r):
    n = len(json.dumps(body, ensure_ascii=False).encode('utf-8')) + 4096
    return (n * r['miss'] + body['max_tokens'] * r['output']) / 1e6


class Budget:
    def __init__(self, directory, key_file):
        import requests
        self.protocol = json.loads((HERE / 'protocol.json').read_text())
        self.cap = float(self.protocol['budget_cny'])
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / 'budget-state.json'
        self.headers = {'Authorization': 'Bearer ' + Path(key_file).read_text().strip()}
        self.http = requests.Session()
        self.http.trust_env = False
        self.lock = threading.Lock()
        self.reserved = 0.0
        self.balance_at = (0.0, None)
        if self.path.exists():
            self.state = json.loads(self.path.read_text())
            # reservations open at an unclean stop stay charged
            self.state['charged_cny'] += self.state.get('reserved_cny', 0.0)
        else:
            start = self.balance(force=True)
            self.state = {'started_utc': datetime.now(timezone.utc).isoformat(), 'initial_balance_cny': start,
                          'cap_cny': self.cap, 'charged_cny': 0.0, 'calls': 0, 'errors': 0, 'models': {}}
        self.save()

    def balance(self, force=False):
        at, value = self.balance_at
        if not force and value is not None and time.monotonic() - at < 15:
            return value
        r = self.http.get('https://api.deepseek.com/user/balance', headers=self.headers, timeout=20)
        r.raise_for_status()
        values = [float(x['total_balance']) for x in r.json()['balance_infos'] if x['currency'] == 'CNY']
        if not values:
            raise RuntimeError('CNY balance unavailable')
        self.balance_at = (time.monotonic(), sum(values))
        return self.balance_at[1]

    def save(self):
        self.state['reserved_cny'] = self.reserved
        self.state['updated_utc'] = datetime.now(timezone.utc).isoformat()
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.state, indent=2) + '\n')
        tmp.replace(self.path)

    def acquire(self, body):
        with self.lock:
            if (self.dir / 'STOP').exists():
                raise RuntimeError('study stop requested')
            need = reservation(body, rates())
            bal = self.balance()
            spent = max(0.0, self.state['initial_balance_cny'] - bal)
            self.state['observed_decrease_cny'] = spent
            if max(spent, self.state['charged_cny']) + self.reserved + need > self.cap or bal < self.reserved + need:
                self.state['status'] = 'budget_limit'
                self.save()
                raise RuntimeError('study spending limit reached')
            self.reserved += need
            self.save()
            return need

    def finish(self, need, status, data, seconds, arm, body):
        usage = data.get('usage') or {}
        cost = charge(usage, rates()) if usage else need
        with self.lock:
            self.reserved -= need
            self.state['charged_cny'] += cost
            self.state['calls'] += 1
            self.state['errors'] += int(status != 200)
            model = data.get('model', 'unreported')
            self.state['models'][model] = self.state['models'].get(model, 0) + 1
            row = {'utc': datetime.now(timezone.utc).isoformat(), 'arm': arm, 'status': status, 'model': model,
                   'usage': usage, 'charged_cny': cost, 'seconds': seconds, 'response_id': data.get('id')}
            with (self.dir / 'api-usage.jsonl').open('a') as f:
                f.write(json.dumps(row) + '\n')
            with (self.dir / 'api-transcripts.jsonl').open('a') as f:
                f.write(json.dumps({'utc': row['utc'], 'arm': arm, 'request': body, 'response': data}, ensure_ascii=False) + '\n')
            self.save()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, data):
        raw = json.dumps(data).encode()
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
        if self.headers.get('Authorization') != 'Bearer ' + b.protocol['local_token']:
            return self.reply(401, {'error': 'local study token required'})
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 4_000_000:
                raise ValueError('request size outside study limit')
            body = json.loads(self.rfile.read(size))
            if body.get('model') != b.protocol['model'] or body.get('stream'):
                raise ValueError('only the study model and non-streaming requests are allowed')
            body['max_tokens'] = min(int(body.get('max_tokens') or b.protocol['max_output_tokens']), b.protocol['max_output_tokens'])
            need = b.acquire(body)
        except Exception as e:
            with b.lock, (b.dir / 'denied-requests.jsonl').open('a') as f:
                f.write(json.dumps({'utc': datetime.now(timezone.utc).isoformat(), 'arm': arm, 'error': str(e)}) + '\n')
            return self.reply(402, {'error': {'message': str(e), 'type': 'study_limit'}})
        t0 = time.monotonic()
        try:
            with requests.Session() as s:
                s.trust_env = False
                r = s.post(UPSTREAM, json=body, headers=b.headers, timeout=300)
                status, data = r.status_code, r.json()
        except Exception:
            status, data = 503, {'error': {'message': 'official API transport failure', 'type': 'upstream'}}
        b.finish(need, status, data, time.monotonic() - t0, arm, body)
        self.reply(status, data)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=19530)
    p.add_argument('--out', required=True)
    p.add_argument('--key-file', required=True)
    a = p.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
    server.budget = Budget(a.out, a.key_file)
    server.serve_forever()
