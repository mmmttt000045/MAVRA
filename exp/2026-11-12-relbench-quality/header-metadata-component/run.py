"""Replay both preregistered header failures on train/validation only, without model-service calls."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path('/root/agentdb-quality-headers-checks-20261112')
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / 'tools/relbench'))
import harness as h
import psycopg
import yaml


def sql_strings(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from sql_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from sql_strings(child)
    elif isinstance(value, str) and '{seeds}' in value and re.match(r'\s*(with|select)\b', value, re.I):
        yield value


out = ROOT / 'results/header-component'
out.mkdir(parents=True, exist_ok=True)
plan_path = ROOT / 'exp/2026-11-12-relbench-quality/v9-plan.json'
plan = json.loads(plan_path.read_text())
cases = plan['component']['selected_cases']
cutoffs = {case['k'] for case in cases}
if len(cases) != 2 or len(cutoffs) != 1:
    raise RuntimeError('the planned two-case same-cutoff component changed')
cutoff = cutoffs.pop()
source = Path('/root/agentdb-quality-delta-20261112/results/quality-20261112-v8/mavra-delta-rel-stack-r1/sessions')
data = Path('/root/agentdb-mid/results/relbench-data/rel-stack')
prep = Path('/root/agentdb-mid/results/relbench-data/rel-stack-prep')
timeline = json.loads((prep / 'timeline.json').read_text())
cfg = h.load_env('/root/agentdb-mid/.env')
admin = h.base_url(cfg['AGENTDB_URL']) + '/postgres'
db = f'quality_header_component_{os.getpid()}_{time.time_ns()}'
if not db.startswith('quality_header_component_') or not all(c.isalnum() or c == '_' for c in db):
    raise RuntimeError('invalid isolated component database')
report = {'started_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'purpose': 'post-hoc implementation replay only; no new benchmark test quality or optimizer input',
          'plan_sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(),
          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'harness_sha256': hashlib.sha256((ROOT / 'tools/relbench/harness.py').read_bytes()).hexdigest(),
          'model_service_calls': 0, 'test_parquet_opened': False, 'records': [],
          'isolated_database_removed': False}
started = time.time()
with psycopg.connect(admin, autocommit=True) as con:
    con.execute(f'CREATE DATABASE {db} TEMPLATE relbench_stack_t1')
try:
    run = h.Run.__new__(h.Run)
    run.url, run.arm = h.base_url(cfg['AGENTDB_URL']) + '/' + db, h.ARMS['mavra-delta-headers']
    run.a = SimpleNamespace(data=str(data), prep=str(prep))
    run.manifest = yaml.safe_load((data / 'manifest.yaml').read_text())
    run.tasks = timeline['tasks']
    bounds = next(iter(run.tasks.values()))['cutoffs']
    run.append(h.pd.Timestamp(bounds[0]['test_timestamp']), h.pd.Timestamp(bounds[cutoff - 1]['test_timestamp']))
    all_seeds = {}
    with psycopg.connect(run.url, autocommit=True) as con:
        con.execute('CREATE SCHEMA task')
        for task, e in run.tasks.items():
            ec, tc, yc = e['entity_col'].lower(), e['time_col'].lower(), e['target_col'].lower()
            seeds = {}
            for split in ('train', 'val'):
                frame = h.pd.read_parquet(prep / 'tasks' / task / f'k{cutoff}' / f'{split}.parquet')
                frame.columns = [c.lower() for c in frame]
                frame = frame.rename(columns={tc: 'seed_time'})
                frame['seed_time'] = h.pd.to_datetime(frame.seed_time)
                seeds[split] = frame
            train = seeds['train']
            rng = h.np.random.RandomState(h.SAMPLE_SEED)
            seeds['train_sample'] = train.iloc[rng.permutation(len(train))[:h.SAMPLE_SIZE]].reset_index(drop=True) if len(train) > h.SAMPLE_SIZE else train
            key_type = 'bigint' if h.pd.api.types.is_integer_dtype(train[ec]) else 'text'
            for split, frame in seeds.items():
                table = f'task.{h.tname(task)}_{split}'
                con.execute(f'CREATE TABLE {table} ({ec} {key_type}, seed_time timestamp, {yc} double precision)')
                h.copy_rows(con, table, frame[[ec, 'seed_time', yc]])
                con.execute(f'ANALYZE {table}')
            all_seeds[task] = seeds
    for case in cases:
        row = {'task': case['task'], 'cutoff': cutoff, 'validation_index': case['validation_index']}
        began = time.time()
        try:
            path = source / case['source_file']
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != case['source_sha256']:
                raise RuntimeError('frozen failed session changed')
            failed = json.loads(raw)['validations'][case['validation_index']]
            base_path = source / case['base_sources'][0]['file']
            prior = json.loads(base_path.read_bytes())
            base_sql = next(sql for sql in sql_strings(prior) if hashlib.sha256(sql.encode()).hexdigest() == case['base_sql_sha256'])
            added_sql = failed['delta_sql']
            task = case['task']
            e = run.tasks[task]
            ec, yc = e['entity_col'].lower(), e['target_col'].lower()
            seeds = all_seeds[task]
            row.update(source_sha256=case['source_sha256'], base_source_sha256=hashlib.sha256(base_path.read_bytes()).hexdigest(),
                       base_sql_sha256=case['base_sql_sha256'], added_sql_sha256=hashlib.sha256(added_sql.encode()).hexdigest())
            original_probe = f"SELECT * FROM ({base_sql.strip().rstrip(';').replace('{seeds}', f'task.{h.tname(task)}_val')}) q LIMIT 0"
            probe_start = time.time()
            try:
                h.read_sql(run.url, original_probe, timeout_s=5)
                row['original_five_second_probe'] = 'completed'
            except Exception as err:
                row['original_five_second_probe'] = f'{type(err).__name__}: {str(err)[:200]}'
            row['original_probe_seconds'] = time.time() - probe_start
            bx, s1 = h.features(run.url, base_sql, f'task.{h.tname(task)}_train_sample', seeds['train_sample'], ec, timeout_s=45)
            bv, s2 = h.features(run.url, base_sql, f'task.{h.tname(task)}_val', seeds['val'], ec, timeout_s=45)
            row['base_read_seconds'] = s1 + s2
            _, importance, fit_seconds = h.train_predict(e['task_type'], bx, seeds['train_sample'][yc], bv)
            row['base_fit_seconds'] = fit_seconds
            event = {}
            with patch.object(h, 'read_sql', wraps=h.read_sql) as reads:
                combined, xt, xv = run.prepare_delta(task, cutoff, seeds, (base_sql, bx, bv, importance), added_sql, event)
            row['header_probe_queries'] = sum('q LIMIT 0' in call.args[1] for call in reads.call_args_list)
            row['corrected_trial'] = event
            prediction, _, fit_seconds = h.train_predict(e['task_type'], xt, seeds['train_sample'][yc], xv)
            row.update(validation=h.score(e['task_type'], seeds['val'][yc], prediction), candidate_fit_seconds=fit_seconds)
            audit_start = time.time()
            row['audit'] = run.audit(task, cutoff, combined, seeds)
            row['audit_seconds'] = time.time() - audit_start
            row['passed'] = (row['header_probe_queries'] == 0 and event.get('values_reproduced')
                             and row['audit'].get('result') == 'clean')
        except Exception as err:
            row.update(passed=False, error=f'{type(err).__name__}: {str(err)[:500]}')
        row['seconds'] = time.time() - began
        report['records'].append(row)
        (out / 'results.json').write_text(json.dumps(report, indent=2, default=str) + '\n')
        print(json.dumps({k: row.get(k) for k in ('task', 'passed', 'validation', 'header_probe_queries', 'error')}, default=str), flush=True)
except Exception as err:
    report['setup_error'] = f'{type(err).__name__}: {str(err)[:500]}'
finally:
    with psycopg.connect(admin, autocommit=True) as con:
        con.execute(f'DROP DATABASE {db} WITH (FORCE)')
        report['isolated_database_removed'] = con.execute('SELECT 1 FROM pg_database WHERE datname=%s', (db,)).fetchone() is None
    report.update(finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), seconds=time.time() - started)
    report['passed'] = len(report['records']) == 2 and all(r['passed'] for r in report['records']) and report['isolated_database_removed']
    (out / 'results.json').write_text(json.dumps(report, indent=2, default=str) + '\n')
    print(json.dumps({'passed': report['passed'], 'cases': len(report['records']), 'seconds': report['seconds'],
                      'isolated_database_removed': report['isolated_database_removed'], 'model_calls': 0}), flush=True)
