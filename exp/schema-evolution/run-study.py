#!/usr/bin/env python3
"""Run the schema-evolution benchmark: methods x two schemas x repeated runs on frozen question banks.

Starts the loopback budget relay and the published-memory service, then runs one
`mavra metric-bench` process per (schema, method, run) cell. Cells of one run start
together; the next run starts after every cell of the previous run finishes.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
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
CFG = {
    'local_token': 'mavra-local-relay',
    'model': 'deepseek-flash',
    'reasoning_effort': 'low',
    'max_steps': 20,
    'sql_timeout_seconds': 120,
    'synthetic_rows': 1000000,
    'datasets': ['synthetic', 'tpch'],
    'arms': ['ace', 'awm', 'gmemory', 'mavra'],
    'modes': {
        'ace': 'paper-ace',
        'awm': 'paper-awm',
        'gmemory': 'paper-gmemory',
        'mavra': 'metric-global-full',
        'tecod': 'paper-tecod',
        'recheck': 'metric-global-recheck',
        'template_schema': 'metric-template-schema',
        'template_revoke': 'metric-template-revoke',
    },
    'metrics': ['M1', 'M3', 'M5'],
    'changes': ['append', 'backfill', 'correct', 'addcol', 'status', 'revision', 'dupload', 'dimhist', 'latekey', 'unit', 'mirror'],
    'results': 'results/schema-evolution',
}


def save(path: Path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def bank_path(ds: str) -> Path:
    return HERE / f'bank-{ds}.json'


def mavra_bin() -> Path:
    return Path(os.environ.get('MAVRA_BIN', str(ROOT / 'target/release/mavra')))


def build_command(ds: str, arm: str, run: int, out: Path, pool: int = 8) -> list[str]:
    bank = json.loads(bank_path(ds).read_text(encoding='utf-8'))
    changes = [c for c in CFG['changes'] if c in bank['phases']]
    args = [
        str(mavra_bin()), '--pool', str(pool), '--out', str(out), 'metric-bench',
        '--agent', 'openai', '--extractor', 'openai', '--modes', CFG['modes'][arm],
        '--metrics', ','.join(CFG['metrics']),
        '--phrasings', 'named', '--question-set', 'v2', '--bank', str(bank_path(ds)),
        '--holdout-agents', 'A', '--changes', ','.join(changes), '--repeats', '1', '--first-repeat', str(run),
        '--max-steps', str(CFG['max_steps']), '--sql-timeout-secs', str(CFG['sql_timeout_seconds']),
        '--concurrency', '1', '--trace', '--no-explain',
    ]
    if ds == 'tpch':
        args += ['--spec', 'exp/multi-schema-generality/schemas/tpch.json', '--defs', 'exp/multi-schema-generality/e2e/tpch-defs.json']
    else:
        args += ['--rows', str(CFG['synthetic_rows'])]
    return args


def wait_health(port: int, proc, seconds: int = 60):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if proc.poll() is not None:
            raise RuntimeError(f'service on {port} exited')
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as r:
                if r.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f'service on {port} did not start')


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument('--key-file', default='-', help='Optional path to API key file (defaults to DEEPSEEK_API_KEY / OPENAI_API_KEY)')
    a.add_argument('--runs', default='1')
    a.add_argument('--arms', default=','.join(CFG['arms']))
    a.add_argument('--datasets', default=','.join(CFG['datasets']))
    a.add_argument('--parallel', type=int, default=8)
    a.add_argument('--pool', type=int, default=8, help='database connections per cell')
    a.add_argument('--concurrent-runs', action='store_true', help='start all listed runs together instead of sequentially')
    a.add_argument('--results', default=CFG['results'], help='results directory (relative to repository root)')
    a.add_argument('--cap', type=float, default=None, help='spending cap for this results directory')
    a = a.parse_args()

    out = ROOT / a.results
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / 'execution-state.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'cells': []}
    state['status'] = 'starting'
    save(state_path, state)

    env_file = {}
    if (ROOT / '.env').exists():
        for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k, v = line.split('=', 1)
                env_file[k.strip()] = v.strip().strip('"\'')
    db_url = os.environ.get('MAVRA_DB_URL') or os.environ.get('AGENTDB_URL') or env_file.get('MAVRA_DB_URL') or env_file.get('AGENTDB_URL')
    if not db_url:
        raise SystemExit('Set MAVRA_DB_URL in environment or .env')

    env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower() and not k.startswith(('OPENAI_', 'DEEPSEEK_'))}
    env.update(
        MAVRA_DB_URL=db_url,
        AGENTDB_URL=db_url,
        NO_PROXY='127.0.0.1,localhost',
        FIG6_PRESERVE_REASONING='1',
        FIG6_MEMORY_URL='http://127.0.0.1:19531/memory',
        OPENAI_API_KEY=CFG['local_token'],
        OPENAI_MODEL=CFG['model'],
        OPENAI_REQUIRE_MODEL=CFG['model'],
        OPENAI_HEDGE='1',
        OPENAI_REASONING_EFFORT=CFG['reasoning_effort'],
        OPENAI_THINKING='enabled',
        OMP_NUM_THREADS='4',
        OPENBLAS_NUM_THREADS='4',
        MKL_NUM_THREADS='4',
        MALLOC_ARENA_MAX='2',
    )
    totals = ','.join(f'{ds}={len(json.loads(bank_path(ds).read_text(encoding="utf-8"))["all_tasks"])}' for ds in a.datasets.split(','))
    services, logs = [], []
    try:
        if 'tecod' in a.arms.split(','):
            log = (out / 'tecod-server.log').open('a', encoding='utf-8')
            logs.append(log)
            tenv = dict(env)
            tenv.update(HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false', TECOD_THREADS='24')
            tecod_py = os.environ.get('TECOD_PYTHON', str(ROOT / 'results/ext/venv-tecod/bin/python'))
            tecod_models = os.environ.get('TECOD_MODELS', str(ROOT / 'results/ext/tecod-models'))
            proc = subprocess.Popen(
                [tecod_py, '-u', str(ROOT / 'tools/relbench/tecod_server.py'), '--models', tecod_models, '--port', '19532'],
                cwd=ROOT, env=tenv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            )
            services.append(proc)
            wait_health(19532, proc, 600)
        cap = [] if a.cap is None else ['--cap', str(a.cap)]
        for name, port, extra in [
            ('budget-proxy', 19530, ['--key-file', a.key_file, '--out', str(out / 'budget'), *cap]),
            ('memory-service', 19531, ['--out', str(out / 'memory'), '--total-tasks', totals]),
        ]:
            log = (out / f'{name}.log').open('a', encoding='utf-8')
            logs.append(log)
            proc = subprocess.Popen(
                ['python3', '-u', str(HERE / f'{name}.py'), '--port', str(port), *extra],
                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            )
            services.append(proc)
            wait_health(port, proc)
        state['status'] = 'running'
        save(state_path, state)

        def run_cell(ds, arm, run):
            key = f'{ds}-r{run}-{arm}'
            folder = out / 'cells' / key
            folder.mkdir(parents=True, exist_ok=False)
            args_list = build_command(ds, arm, run, folder, a.pool)
            rec = {'key': key, 'dataset': ds, 'arm': arm, 'run': run}
            save(folder / 'launch.json', rec)
            cell_env = {**env, 'FIG6_CELL_KEY': key, 'OPENAI_BASE_URL': f'http://127.0.0.1:19530/arm/{key}'}
            with (folder / 'console.log').open('x', encoding='utf-8') as log:
                proc = subprocess.Popen(args_list, cwd=ROOT, env=cell_env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                rec['returncode'] = proc.wait()
            reports = list(folder.glob('metric-*/report.json'))
            rec['completed'] = rec['returncode'] == 0 and len(reports) == 1
            if reports:
                report = json.loads(reports[0].read_text(encoding='utf-8'))
                rows = report['cells'][0]['records'] if report.get('cells') else []
                rec['tasks'] = len(rows)
                bank = json.loads(bank_path(ds).read_text(encoding='utf-8'))
                expected = [('learn', t) for t in bank['all_tasks'][:len(CFG['metrics']) * 2]]
                expected += [(ph, t) for ph, ts in bank['phases'].items() for t in ts]
                asked = [(r['phase'], r['task']) for r in rows]
                if sorted(asked) != sorted(expected):
                    rec.update(completed=False, bank_mismatch=True)
                if report.get('database_cleaned_up') is not True:
                    rec.update(completed=False, database_not_cleaned=True)
                infra = [
                    r['error'] for r in rows
                    if r.get('error') and any(x in r['error'].lower() for x in ['http 402', 'http 5', 'error sending request', 'connection', 'timed out'])
                ]
                if infra:
                    rec.update(completed=False, infrastructure_errors=infra[:5])
            denied = out / 'budget' / 'denied-requests.jsonl'
            if denied.exists() and any(json.loads(x)['arm'] == key for x in denied.read_text(encoding='utf-8').splitlines() if x):
                rec.update(completed=False, budget_or_configuration_denial=True)
            try:
                data = json.dumps({'op': 'close', 'key': key, 'arm': arm}).encode('utf-8')
                urllib.request.urlopen(
                    urllib.request.Request('http://127.0.0.1:19531/memory', data=data, headers={'Content-Type': 'application/json'}),
                    timeout=45,
                ).read()
            except Exception as e:
                rec['memory_close_error'] = type(e).__name__
            save(folder / 'completion.json', rec)
            print(json.dumps(rec), flush=True)
            return rec

        runs = [int(x) for x in a.runs.split(',')]
        for run in ([runs] if a.concurrent_runs else [[r] for r in runs]):
            if (out / 'budget' / 'STOP').exists():
                state['stop_reason'] = 'stop requested'
                break
            if shutil.disk_usage(ROOT).free < 25 * 1024 ** 3:
                state['stop_reason'] = 'disk reserve'
                break
            cells = [
                (ds, arm, r)
                for r in run
                for arm in a.arms.split(',')
                for ds in a.datasets.split(',')
                if not (out / 'cells' / f'{ds}-r{r}-{arm}').exists()
            ]
            with ThreadPoolExecutor(max_workers=a.parallel) as pool:
                done = list(pool.map(lambda c: run_cell(*c), cells))
            state['cells'] += done
            save(state_path, state)
            budget = json.loads((out / 'budget' / 'budget-state.json').read_text(encoding='utf-8'))
            if budget.get('status') == 'budget_limit':
                state['stop_reason'] = 'budget limit'
                break
            if not all(c['completed'] for c in done):
                state['stop_reason'] = f'incomplete cell in run {run}'
                break
        state['status'] = 'finished'
        save(state_path, state)
    except Exception as e:
        state.update(status='failed', error=f'{type(e).__name__}: {e}')
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
