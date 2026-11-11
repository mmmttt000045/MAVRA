"""A bounded, train/validation-only entity-attribute component experiment."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path('/root/agentdb-quality-early-20261112')
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / 'tools/relbench'))
import harness as h
import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from typed_attributes import compile_view, project_columns

DEST = Path('/root/agentdb-quality-20261112-tools/typed-attributes-component/results.json')
DATA = Path('/root/agentdb-mid/results/relbench-data')
HERE = Path(__file__).parent
report = {'purpose':'train-validation-only component; not a full candidate or test result',
          'started_at_utc':time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
          'model_service_calls':0, 'held_out_files_opened':False,
          'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (Path(__file__), HERE/'typed_attributes.py', HERE/'plan.json',
                                     ROOT/'tools/relbench/harness.py')},
          'tasks':{}, 'input_sha256':{}}


def save():
    DEST.write_text(json.dumps(report, indent=2)+'\n')


def live_formal_runs():
    count = 0
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args = path.read_bytes().split(b'\x00')
        except OSError:
            continue
        if (any(arg.endswith(b'tools/relbench/harness.py') for arg in args)
                and any(b'results/quality-20261112-' in arg for arg in args)):
            count += 1
    return count


def queues_pending():
    base = ROOT/'results/quality-20261112-v7'
    for db in ('rel-stack','rel-trial'):
        path = base/f'mavra-early-{db}-r1-launch.json'
        try:
            state = json.loads(path.read_text())
        except (OSError, ValueError):
            return True
        if state.get('status') == 'waiting_for_matching_v5_cell':
            return True
    return False


report['queue_status'] = 'waiting_for_available_slot_after_v7_starts'
save()
while live_formal_runs() >= 4 or queues_pending():
    time.sleep(15)
report['queue_status'] = 'started'
report['active_formal_cells_at_start'] = live_formal_runs()
report['component_started_at_utc'] = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
save()

cfg = h.load_env('/root/agentdb-mid/.env')
admin = h.base_url(cfg['AGENTDB_URL']) + '/postgres'


def kind(dtype):
    if pa.types.is_dictionary(dtype):
        dtype = dtype.value_type
    if pa.types.is_boolean(dtype):
        return 'boolean'
    if pa.types.is_integer(dtype) or pa.types.is_floating(dtype) or pa.types.is_decimal(dtype):
        return 'numeric'
    if pa.types.is_timestamp(dtype) or pa.types.is_date(dtype):
        return 'date'
    if pa.types.is_string(dtype) or pa.types.is_large_string(dtype):
        return 'string'
    return 'other'


def checked_view(run, task, sql, seeds, item):
    ec = run.tasks[task]['entity_col'].lower()
    audit = run.audit(task,1,sql,seeds)
    item['audits'] = [audit]
    if audit.get('result') == 'leak' and audit.get('columns_differing'):
        first, _ = h.features(run.url,sql,f'task.{h.tname(task)}_train_sample',seeds['train_sample'],ec,timeout_s=15)
        bad = set(audit['columns_differing'])
        keep = [c for c in first if c not in bad]
        item['removed_columns'] = sorted(bad)
        sql = project_columns(sql,ec,keep)
        audit = run.audit(task,1,sql,seeds)
        item['audits'].append(audit)
    if audit.get('result') != 'clean':
        raise RuntimeError('fresh public-table audit not clean')
    item['sql'], item['sql_sha256'] = sql, hashlib.sha256(sql.encode()).hexdigest()
    xt,s1 = h.features(run.url,sql,f'task.{h.tname(task)}_train_sample',seeds['train_sample'],ec,timeout_s=15)
    xv,s2 = h.features(run.url,sql,f'task.{h.tname(task)}_val',seeds['val'],ec,timeout_s=15)
    item['sql_seconds'] = s1+s2
    item['features'] = list(xt)
    yc = run.tasks[task]['target_col'].lower()
    task_type = run.tasks[task]['task_type']
    started = time.time()
    item['fit_attempts'] = 1
    try:
        prediction, _, seconds = h.train_predict(task_type,xt,seeds['train_sample'][yc],xv)
    finally:
        item['fit_wall_seconds'] = time.time()-started
    item['fit_seconds'] = seconds
    item['validation'] = h.score(task_type,seeds['val'][yc],prediction)


for dataset in ('rel-stack','rel-trial'):
    data,prep = DATA/dataset,DATA/(dataset+'-prep')
    timeline = json.loads((prep/'timeline.json').read_text())
    manifest = yaml.safe_load((data/'manifest.yaml').read_text())
    db = f'quality_typed_component_{os.getpid()}_{time.time_ns()}'
    url = h.base_url(cfg['AGENTDB_URL'])+'/'+db
    with psycopg.connect(admin,autocommit=True) as con:
        con.execute(f'CREATE DATABASE {db} TEMPLATE relbench_{dataset.removeprefix("rel-")}_t1')
    try:
        run = h.Run.__new__(h.Run)
        run.url,run.arm,run.tasks,run.manifest = url,h.ARMS['mavra-early'],timeline['tasks'],manifest
        run.a = SimpleNamespace(data=str(data),prep=str(prep))
        with psycopg.connect(url,autocommit=True) as con:
            con.execute('CREATE SCHEMA task')
        for task,e in run.tasks.items():
            started = time.time()
            item = {'dataset':dataset,'cutoff':1,'selection_split':'validation','views':{}}
            report['tasks'][task] = item
            try:
                ec,yc,tc = e['entity_col'].lower(),e['target_col'].lower(),e['time_col'].lower()
                seeds = {}
                for split in ('train','val'):
                    path = prep/'tasks'/task/'k1'/(split+'.parquet')
                    report['input_sha256'][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
                    frame = h.pd.read_parquet(path)
                    frame.columns = [c.lower() for c in frame]
                    frame = frame.rename(columns={tc:'seed_time'})
                    frame['seed_time'] = h.pd.to_datetime(frame.seed_time)
                    seeds[split] = frame
                train = seeds['train']
                rng = h.np.random.RandomState(h.SAMPLE_SEED)
                seeds['train_sample'] = (train.iloc[rng.permutation(len(train))[:h.SAMPLE_SIZE]].reset_index(drop=True)
                                         if len(train)>h.SAMPLE_SIZE else train)
                with psycopg.connect(url,autocommit=True) as con:
                    key_type = 'bigint' if h.pd.api.types.is_integer_dtype(train[ec]) else 'text'
                    for split in ('train_sample','val'):
                        table = f'task.{h.tname(task)}_{split}'
                        con.execute(f'CREATE TABLE {table} ({ec} {key_type},seed_time timestamp,{yc} double precision)')
                        h.copy_rows(con,table,seeds[split][[ec,'seed_time',yc]])
                        con.execute(f'ANALYZE {table}')
                spec = manifest['tables'][e['entity_table']]
                schema = pq.read_schema(data/'db'/(e['entity_table']+'.parquet'))
                columns = [(field.name,kind(field.type)) for field in schema]
                item['schema_types'] = columns
                for expanded,name in ((False,'numeric_date'),(True,'typed')):
                    view = item['views'][name] = {}
                    sql,_ = compile_view(e['entity_table'],spec['pkey'],ec,spec.get('time_col'),
                                         list(spec.get('fkeys') or {}),columns,expanded)
                    checked_view(run,task,sql,seeds,view)
                old,new = (item['views'][name]['validation'] for name in ('numeric_date','typed'))
                higher = h.metric_of(e['task_type'])[1]
                margin = 0.0005 if higher else max(abs(old)*0.002,1e-8)
                item['margin'] = margin
                item['useful'] = new>old+margin if higher else new<old-margin
                print(json.dumps({task:{'control':old,'typed':new,'useful':item['useful']}}),flush=True)
            except Exception as err:
                item['error'] = f'{type(err).__name__}: {str(err)[:500]}'
                print(json.dumps({task:{'error':item['error']}}),flush=True)
            finally:
                item['elapsed_seconds'] = time.time()-started
                save()
    finally:
        with psycopg.connect(admin,autocommit=True) as con:
            con.execute(f'DROP DATABASE {db} WITH (FORCE)')
report['component_pass'] = (len(report['tasks'])==6 and all('error' not in row for row in report['tasks'].values())
                            and sum(row.get('useful',False) for row in report['tasks'].values())>=2)
report['finished_at_utc'] = time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime())
save()
print(json.dumps({'component_pass':report['component_pass']}),flush=True)
