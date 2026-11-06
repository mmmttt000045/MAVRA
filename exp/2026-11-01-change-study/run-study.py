#!/usr/bin/env python3
"""Run the change study: four methods x two schemas x repeated runs on the frozen question banks.

Starts the loopback budget relay and the published-memory service, then runs one
metric-bench process per (schema, method, run) cell. Cells of one run start
together; the next run starts only after every cell of the previous one ended, so
run 1 doubles as the pilot. Every cell, completed or not, stays in the results.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P = json.loads((HERE / 'protocol.json').read_text())


def utc():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    tmp.replace(path)


def bank_path(ds, smoke):
    return HERE / (f'bank-{ds}-smoke.json' if smoke else f'bank-{ds}.json')


def command(ds, arm, run, out, smoke, pool=8):
    bank = json.loads(bank_path(ds, smoke).read_text())
    changes = [c for c in P['changes'] if c in bank['phases']]
    cmd = [str(ROOT / 'target/release/agentdb-mid'), '--pool', str(pool), '--out', str(out), 'metric-bench',
           '--agent', 'openai', '--extractor', 'openai', '--modes', P['modes'][arm], '--metrics', ','.join(P['metrics']),
           '--phrasings', 'named', '--question-set', 'v2', '--bank', str(bank_path(ds, smoke)),
           '--holdout-agents', 'A', '--changes', ','.join(changes), '--repeats', '1', '--first-repeat', str(run),
           '--max-steps', str(P['max_steps']), '--sql-timeout-secs', str(P['sql_timeout_seconds']),
           '--concurrency', '1', '--trace', '--no-explain']
    if ds == 'tpch':
        cmd += ['--spec', 'exp/2026-10-11-generality/schemas/tpch.json', '--defs', 'exp/2026-10-11-generality/e2e/tpch-defs.json']
    else:
        cmd += ['--rows', str(P['synthetic_rows'])]
    return cmd


def wait_health(port, proc, seconds=60):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if proc.poll() is not None:
            raise RuntimeError(f'service on {port} exited')
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as r:
                if r.status == 200:
                    return
        except OSError:
            time.sleep(.5)
    raise RuntimeError(f'service on {port} did not start')


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--key-file', required=True)
    a.add_argument('--runs', default='1')
    a.add_argument('--arms', default=','.join(P['arms']))
    a.add_argument('--datasets', default=','.join(P['datasets']))
    a.add_argument('--parallel', type=int, default=8)
    a.add_argument('--smoke', action='store_true', help='tiny banks bank-*-smoke.json, separate results directory')
    a.add_argument('--pool', type=int, default=8, help='database connections per cell (agent SQL runs one at a time)')
    a.add_argument('--concurrent-runs', action='store_true', help='start all listed runs together instead of one after another')
    a.add_argument('--results', default=P['results'], help='results directory (relative to the repository)')
    a.add_argument('--cap', type=float, default=None, help='spending cap of this results directory in CNY (default: protocol)')
    a = a.parse_args()
    out = ROOT / (a.results + ('-smoke' if a.smoke else ''))
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / 'execution-state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'cells': []}
    # the binary and sources must be the committed ones: no tracked change in the working copy
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, capture_output=True, text=True).stdout
    if dirty.strip():
        raise SystemExit(f'tracked files modified; commit or stash first:\n{dirty}')
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    binary = hashlib.sha256((ROOT / 'target/release/agentdb-mid').read_bytes()).hexdigest()
    state.setdefault('launches', []).append({'utc': utc(), 'head': head, 'binary_sha256': binary, 'runs': a.runs, 'arms': a.arms,
                                             'datasets': a.datasets, 'parallel': a.parallel, 'pool': a.pool,
                                             'concurrent_runs': a.concurrent_runs, 'cap': a.cap})
    state.update(status='starting', started_utc=utc())
    save(state_path, state)
    db_url = next(line.split('=', 1)[1].strip().strip('"\'') for line in (ROOT / '.env').read_text().splitlines()
                  if line.startswith('AGENTDB_URL='))
    env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower() and not k.startswith(('OPENAI_', 'DEEPSEEK_'))}
    env.update(AGENTDB_URL=db_url, PYTHONPATH=str(ROOT / '.pydeps-relbench'), NO_PROXY='127.0.0.1,localhost',
               FIG6_PRESERVE_REASONING='1', FIG6_MEMORY_URL='http://127.0.0.1:19531/memory',
               OPENAI_API_KEY=P['local_token'], OPENAI_MODEL=P['model'], OPENAI_REQUIRE_MODEL=P['model'], OPENAI_HEDGE='1',
               OPENAI_REASONING_EFFORT=P['reasoning_effort'], OPENAI_THINKING='enabled',
               OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4', MKL_NUM_THREADS='4', MALLOC_ARENA_MAX='2')
    totals = ','.join(f'{ds}={len(json.loads(bank_path(ds, a.smoke).read_text())["all_tasks"])}'
                      for ds in a.datasets.split(','))
    services, logs = [], []
    try:
        if 'tecod' in a.arms.split(','):  # TeCoD's selection server: its own Python environment, models loaded once (~35 GB)
            log = (out / 'tecod-server.log').open('a')
            logs.append(log)
            tenv = {k: v for k, v in env.items() if k != 'PYTHONPATH'}
            tenv.update(HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false', TECOD_THREADS='24')
            proc = subprocess.Popen([str(ROOT / 'results/ext/venv-tecod/bin/python'), '-u', str(ROOT / 'tools/relbench/tecod_server.py'),
                                     '--models', str(ROOT / 'results/ext/tecod-models'), '--port', '19532'],
                                    cwd=ROOT, env=tenv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            services.append(proc)
            wait_health(19532, proc, 600)
        cap = [] if a.cap is None else ['--cap', str(a.cap)]
        for name, port, extra in [('budget-proxy', 19530, ['--key-file', a.key_file, '--out', str(out / 'budget'), *cap]),
                                  ('memory-service', 19531, ['--out', str(out / 'memory'), '--total-tasks', totals])]:
            log = (out / f'{name}.log').open('a')
            logs.append(log)
            proc = subprocess.Popen(['python3', '-u', str(HERE / f'{name}.py'), '--port', str(port), *extra], cwd=ROOT, env=env,
                                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            services.append(proc)
            wait_health(port, proc)
        state['status'] = 'running'
        save(state_path, state)

        def run_cell(ds, arm, run):
            key = f'{ds}-r{run}-{arm}'
            folder = out / 'cells' / key
            folder.mkdir(parents=True, exist_ok=False)
            cmd = command(ds, arm, run, folder, a.smoke, a.pool)
            rec = {'key': key, 'dataset': ds, 'arm': arm, 'run': run, 'started_utc': utc(), 'command': cmd}
            save(folder / 'launch.json', rec)
            cell_env = {**env, 'FIG6_CELL_KEY': key, 'OPENAI_BASE_URL': f'http://127.0.0.1:19530/arm/{key}'}
            with (folder / 'console.log').open('x') as log:
                proc = subprocess.Popen(cmd, cwd=ROOT, env=cell_env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                (folder / 'process.pid').write_text(str(proc.pid))
                rec['returncode'] = proc.wait()
            reports = list(folder.glob('metric-*/report.json'))
            rec['completed'] = rec['returncode'] == 0 and len(reports) == 1
            if reports:
                report = json.loads(reports[0].read_text())
                rows = report['cells'][0]['records'] if report.get('cells') else []
                rec['tasks'] = len(rows)
                rec['report'] = str(reports[0].relative_to(ROOT))
                bank = json.loads(bank_path(ds, a.smoke).read_text())
                expected = [('learn', t) for t in bank['all_tasks'][:len(P['metrics']) * 2]]
                expected += [(ph, t) for ph, ts in bank['phases'].items() for t in ts]
                asked = [(r['phase'], r['task']) for r in rows]
                if sorted(asked) != sorted(expected):
                    rec.update(completed=False, bank_mismatch=True)
                if report.get('database_cleaned_up') is not True:
                    rec.update(completed=False, database_not_cleaned=True)
                infra = [r['error'] for r in rows if r.get('error') and any(
                    x in r['error'].lower() for x in ['http 402', 'http 5', 'error sending request', 'connection', 'timed out'])]
                if infra:
                    rec.update(completed=False, infrastructure_errors=infra[:5])
            denied = out / 'budget' / 'denied-requests.jsonl'
            if denied.exists() and any(json.loads(x)['arm'] == key for x in denied.read_text().splitlines() if x):
                rec.update(completed=False, budget_or_configuration_denial=True)
            try:
                data = json.dumps({'op': 'close', 'key': key, 'arm': arm}).encode()
                urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:19531/memory', data=data,
                                                              headers={'Content-Type': 'application/json'}), timeout=45).read()
            except Exception as e:
                rec['memory_close_error'] = type(e).__name__
            rec['finished_utc'] = utc()
            save(folder / 'completion.json', rec)
            print(json.dumps({k: v for k, v in rec.items() if k != 'command'}), flush=True)
            return rec

        runs = [int(x) for x in a.runs.split(',')]
        for run in ([runs] if a.concurrent_runs else [[r] for r in runs]):
            if (out / 'budget' / 'STOP').exists():
                state['stop_reason'] = 'stop requested'
                break
            if shutil.disk_usage(ROOT).free < 25 * 1024 ** 3:
                state['stop_reason'] = 'disk reserve'
                break
            cells = [(ds, arm, r) for r in run for arm in a.arms.split(',') for ds in a.datasets.split(',')
                     if not (out / 'cells' / f'{ds}-r{r}-{arm}').exists()]
            with ThreadPoolExecutor(max_workers=a.parallel) as pool:
                done = list(pool.map(lambda c: run_cell(*c), cells))
            state['cells'] += done
            save(state_path, state)
            budget = json.loads((out / 'budget' / 'budget-state.json').read_text())
            if budget.get('status') == 'budget_limit':
                state['stop_reason'] = 'budget limit'
                break
            # pilot rule: a run with any incomplete cell stops the queue for inspection
            if not all(c['completed'] for c in done):
                state['stop_reason'] = f'incomplete cell in run {run}'
                break
        state.update(status='finished', finished_utc=utc())
        save(state_path, state)
    except Exception as e:
        state.update(status='failed', error=f'{type(e).__name__}: {e}', finished_utc=utc())
        save(state_path, state)
        raise
    finally:
        for proc in reversed(services):
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(35)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
        for log in logs:
            log.close()


if __name__ == '__main__':
    main()
