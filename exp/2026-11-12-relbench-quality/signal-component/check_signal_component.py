"""Check only training feature variation on actual k1 seed rows, without fitting or scoring."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import os
import sys
import time

root = Path('/root/agentdb-quality-signal-20261112')
os.chdir(root)
sys.path.insert(0, str(root / 'tools/relbench'))
import harness as h
import psycopg
import yaml

cfg = h.load_env()
admin = h.base_url(cfg['AGENTDB_URL']) + '/postgres'
report = {'purpose':'training-only initialization check, not quality evidence', 'test_labels_decoded':False,
          'validation_labels_decoded':False, 'model_service_calls':0, 'learner_fits':0, 'tasks':[],
          'harness_sha256':hashlib.sha256((root/'tools/relbench/harness.py').read_bytes()).hexdigest()}
for dataset in ('rel-stack', 'rel-trial'):
    data = root / 'results/relbench-data' / dataset
    prep = data.with_name(dataset+'-prep')
    run = h.Run.__new__(h.Run)
    run.arm = h.ARMS['mavra-signal']
    run.a = SimpleNamespace(data=str(data))
    run.tasks = json.loads((prep/'timeline.json').read_text())['tasks']
    run.manifest = yaml.safe_load((data/'manifest.yaml').read_text())
    dbname = f'quality_signal_component_{os.getpid()}_{time.time_ns()}'
    run.url = h.base_url(cfg['AGENTDB_URL']) + '/' + dbname
    template = 'relbench_' + dataset.replace('rel-', '') + '_t1'
    with psycopg.connect(admin, autocommit=True) as con:
        con.execute(f'CREATE DATABASE {dbname} TEMPLATE {template}')
    try:
        with psycopg.connect(run.url, autocommit=True) as con:
            con.execute('CREATE SCHEMA task')
        for task, e in run.tasks.items():
            ec, tc = e['entity_col'].lower(), e['time_col'].lower()
            frame = h.pd.read_parquet(prep/'tasks'/task/'k1/train.parquet', columns=[e['entity_col'], e['time_col']])
            frame.columns = [c.lower() for c in frame]
            frame = frame.rename(columns={tc:'seed_time'})
            rng = h.np.random.RandomState(h.SAMPLE_SEED)
            if len(frame) > h.SAMPLE_SIZE:
                frame = frame.iloc[rng.permutation(len(frame))[:h.SAMPLE_SIZE]].reset_index(drop=True)
            keytype = 'bigint' if h.pd.api.types.is_integer_dtype(frame[ec]) else 'text'
            table = f'task.{h.tname(task)}_train_sample'
            with psycopg.connect(run.url, autocommit=True) as con:
                con.execute(f'CREATE TABLE {table} ({ec} {keytype}, seed_time timestamp)')
                h.copy_rows(con, table, frame[[ec,'seed_time']])
                con.execute(f'ANALYZE {table}')
            sql = run.reference_sql(task)
            values, seconds = h.features(run.url, sql, table, frame, ec)
            varying = [c for c in values if values[c].nunique(dropna=False) > 1]
            informative = run.start_is_informative(values)
            assert informative == bool(varying)
            report['tasks'].append({'dataset':dataset, 'task':task,'train_rows':len(frame),
                                    'n_columns':len(values.columns),'varying_columns':varying,
                                    'informative_start':informative, 'sql_seconds':seconds,
                                    'sql_sha256':hashlib.sha256(sql.encode()).hexdigest()})
    finally:
        with psycopg.connect(admin, autocommit=True) as con:
            con.execute(f'DROP DATABASE {dbname} WITH (FORCE)')
report['passed'] = len(report['tasks']) == 6
Path('/root/agentdb-quality-20261112-tools/signal-component.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
