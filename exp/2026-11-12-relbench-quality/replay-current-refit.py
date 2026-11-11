"""Component diagnosis on a separate k2 database; no model service or test labels.

This reuses an archived candidate only as a component test, never as an input
to any from-empty candidate run or as new benchmark quality evidence.
"""
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import time

root = Path('/root/agentdb-quality-cached-20261112')
os.chdir(root)
sys.path.insert(0, str(root / 'tools/relbench'))
import harness as h
import psycopg
import yaml

original = Path('/root/agentdb-quality-20261112/results/quality-20261112-v1/mavra-budgeted-rel-trial-r1/sessions')
prior = json.loads((original / 'study_outcome-k1.json').read_text())
failed = json.loads((original / 'study_outcome-k2.json').read_text())
dataset = Path('/root/agentdb-mid/results/relbench-data/rel-trial')
prep = Path('/root/agentdb-mid/results/relbench-data/rel-trial-prep')
timeline = json.loads((prep / 'timeline.json').read_text())
cfg = h.load_env('/root/agentdb-mid/.env')
name = f'quality_refit_component_{os.getpid()}_{time.time_ns()}'
url = h.base_url(cfg['AGENTDB_URL']) + '/' + name
if not prior.get('final_sql') or (prior.get('audit') or {}).get('result') != 'clean':
    raise RuntimeError('component source was not a clean archived program')
with psycopg.connect(h.base_url(cfg['AGENTDB_URL']) + '/postgres', autocommit=True) as con:
    con.execute(f'CREATE DATABASE {name} TEMPLATE relbench_trial_t1')
report = {'purpose': 'current-refit component diagnosis only; not an optimization input or full-run quality claim',
          'held_out_labels_decoded': False, 'model_service_calls': 0,
          'source_sql_sha256': hashlib.sha256(prior['final_sql'].encode()).hexdigest(),
          'harness_sha256': hashlib.sha256((root / 'tools/relbench/harness.py').read_bytes()).hexdigest(),
          'old_validation_target': failed['target'], 'old_fallback_validation': failed['best_val']}
try:
    run = h.Run.__new__(h.Run)
    run.url, run.arm = url, h.ARMS['mavra-cached']
    run.a = SimpleNamespace(data=str(dataset), prep=str(prep))
    run.manifest = yaml.safe_load((dataset / 'manifest.yaml').read_text())
    run.tasks = timeline['tasks']
    e = run.tasks['study-outcome']
    prev_cut, cut = e['cutoffs'][:2]
    run.append(h.pd.Timestamp(prev_cut['test_timestamp']), h.pd.Timestamp(cut['test_timestamp']))
    ec, yc, tc = e['entity_col'].lower(), e['target_col'].lower(), e['time_col']
    seeds = {}
    for split in ('train', 'val'):
        frame = h.pd.read_parquet(prep / 'tasks/study-outcome/k2' / f'{split}.parquet')
        frame.columns = [c.lower() for c in frame]
        frame = frame.rename(columns={tc.lower(): 'seed_time'})
        frame['seed_time'] = h.pd.to_datetime(frame['seed_time'])
        seeds[split] = frame
    train = seeds['train']
    rng = h.np.random.RandomState(h.SAMPLE_SEED)
    seeds['train_sample'] = train.iloc[rng.permutation(len(train))[:h.SAMPLE_SIZE]].reset_index(drop=True) if len(train) > h.SAMPLE_SIZE else train
    key_type = 'bigint' if h.pd.api.types.is_integer_dtype(train[ec]) else 'text'
    report['seed_key_type'] = key_type
    with psycopg.connect(url, autocommit=True) as con:
        con.execute('CREATE SCHEMA task')
        for split in ('train', 'train_sample', 'val'):
            con.execute(f'CREATE TABLE task.study_outcome_{split} ({ec} {key_type}, seed_time timestamp, {yc} double precision)')
            h.copy_rows(con, f'task.study_outcome_{split}', seeds[split][[ec, 'seed_time', yc]])
            con.execute(f'ANALYZE task.study_outcome_{split}')
    run.prev_sql = {'study-outcome': (1, prior['final_sql'])}
    run.incumbent_frames, run.incumbent_work = {}, {}
    run._fit_ledger = []
    original_features = h.features
    reads = []
    def traced_features(*args, **kwargs):
        started = time.time()
        try:
            return original_features(*args, **kwargs)
        finally:
            reads.append({'seeds': args[2], 'seconds': time.time() - started})
    h.features = traced_features
    goal = run.incumbent('study-outcome', 2, seeds)
    report['new_goal'] = goal
    cached = run.current_incumbent('study-outcome', 2, seeds)
    if not cached:
        raise RuntimeError('current refit did not produce a clean reusable candidate')
    calls_before = len(reads)
    started = time.time()
    selected = run.select_start('study-outcome', 2, seeds, {'program_sql': prior['final_sql']}, {}, None, 'component', 'component')
    elapsed = time.time() - started
    record = {'agent_seconds': elapsed - selected['audit_seconds'], 'feature_fits': run._fit_ledger}
    run.charge_incumbent_work('study-outcome', 2, record)
    report.update(selected_validation=selected['chosen']['val'], selected_features=len(selected['chosen']['columns']),
                  selected_source=selected['chosen']['source'], preflight_feature_queries=calls_before,
                  selection_feature_queries=len(reads) - calls_before, charged_agent_seconds=record['agent_seconds'],
                  charged_preflight=record['charged_current_refit'], feature_queries=reads,
                  validated_complete_sql_retained=selected['chosen']['sql'] == prior['final_sql'])
    if selected['chosen']['val'] + 1e-12 < failed['target']:
        raise AssertionError('the retained current refit is below the original validation target')
    report['passed'] = True
except Exception as err:
    report.update(passed=False, error=f'{type(err).__name__}: {str(err)[:400]}')
    raise
finally:
    destination = Path('/root/agentdb-quality-20261112-tools/current-refit-component.json')
    destination.write_text(json.dumps(report, indent=2) + '\n')
    with psycopg.connect(h.base_url(cfg['AGENTDB_URL']) + '/postgres', autocommit=True) as con:
        con.execute(f'DROP DATABASE {name} WITH (FORCE)')
    print(json.dumps({key: report.get(key) for key in ('passed', 'new_goal', 'selected_validation', 'selected_features',
                       'selection_feature_queries', 'charged_agent_seconds', 'validated_complete_sql_retained', 'error')}, indent=2))
