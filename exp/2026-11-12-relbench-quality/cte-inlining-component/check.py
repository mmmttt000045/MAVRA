"""Check a conservative execution rewrite in an isolated first-cutoff DB."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path('/root/agentdb-quality-early-20261112')
os.chdir(ROOT)
sys.path.insert(0,str(ROOT/'tools/relbench'))
import harness as h
import psycopg
import yaml
from inline_ctes import inline_grouped_ctes

HERE = Path(__file__).parent
TYPED = HERE.parent/'typed-attributes-component'
DEST = HERE/'results.json'
report = {'purpose':'execution component, not a full candidate or test-quality result',
          'model_service_calls':0,'held_out_label_files_opened':False,
          'test_scores_used':False, 'queue_status':'waiting_for_typed_component_and_slot',
          'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (
              Path(__file__),HERE/'inline_ctes.py',HERE/'plan.json',ROOT/'tools/relbench/harness.py')}}


def save():
    DEST.write_text(json.dumps(report,indent=2)+'\n')


def formal_cells():
    n = 0
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args = path.read_bytes().split(b'\x00')
        except OSError:
            continue
        if (any(arg.endswith(b'tools/relbench/harness.py') for arg in args)
                and any(b'results/quality-20261112-' in arg for arg in args)):
            n += 1
    return n


save()
while True:
    try:
        previous = json.loads((TYPED/'results.json').read_text())
    except (OSError,ValueError):
        previous = {}
    if previous.get('finished_at_utc') and formal_cells()<4:
        break
    time.sleep(15)
report['queue_status'] = 'started'
report['active_formal_cells_at_start'] = formal_cells()
report['started_at_utc'] = time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime())
save()

cfg = h.load_env('/root/agentdb-mid/.env')
admin = h.base_url(cfg['AGENTDB_URL'])+'/postgres'
data = Path('/root/agentdb-mid/results/relbench-data/rel-trial')
prep = Path('/root/agentdb-mid/results/relbench-data/rel-trial-prep')
task = 'study-adverse'
timeline = json.loads((prep/'timeline.json').read_text())
e = timeline['tasks'][task]
old = Path('/root/agentdb-quality-signal-20261112/results/quality-20261112-v5/mavra-signal-rel-trial-r1/sessions/study_adverse-k1.json')
archived = json.loads(old.read_text())
original = archived['final_sql']
rewritten,detail = inline_grouped_ctes(original)
report.update(source_session_sha256=hashlib.sha256(old.read_bytes()).hexdigest(),
              original_sql=original,rewritten_sql=rewritten,rewrite=detail,
              archived_validation=archived['best_val'],queries=[],input_sha256={})
db = f'quality_cte_component_{os.getpid()}_{time.time_ns()}'
url = h.base_url(cfg['AGENTDB_URL'])+'/'+db
with psycopg.connect(admin,autocommit=True) as con:
    con.execute(f'CREATE DATABASE {db} TEMPLATE relbench_trial_t1')
try:
    run = h.Run.__new__(h.Run)
    run.url,run.arm,run.tasks = url,h.ARMS['mavra-early'],timeline['tasks']
    run.manifest = yaml.safe_load((data/'manifest.yaml').read_text())
    run.a = SimpleNamespace(data=str(data),prep=str(prep))
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
    latest = seeds['train_sample'].seed_time.max()
    seeds['component_sample'] = (seeds['train_sample'][seeds['train_sample'].seed_time==latest]
                                  .sort_values(ec).head(1000).reset_index(drop=True))
    with psycopg.connect(url,autocommit=True) as con:
        con.execute('CREATE SCHEMA task')
        key_type = 'bigint' if h.pd.api.types.is_integer_dtype(train[ec]) else 'text'
        for split in ('train_sample','val','component_sample'):
            table = f'task.{h.tname(task)}_{split}'
            con.execute(f'CREATE TABLE {table} ({ec} {key_type},seed_time timestamp,{yc} double precision)')
            h.copy_rows(con,table,seeds[split][[ec,'seed_time',yc]])
            con.execute(f'ANALYZE {table}')

    def query(sql,split,kind):
        item = {'kind':kind,'split':split,'timeout_seconds':45}
        report['queries'].append(item)
        started = time.time()
        try:
            frame,seconds = h.features(url,sql,f'task.{h.tname(task)}_{split}',seeds[split],ec,timeout_s=45)
            item['sql_seconds'] = seconds
            return frame,seconds
        except Exception as err:
            item['error'] = str(err)[:500]
            raise
        finally:
            item['elapsed_seconds'] = time.time()-started
            save()

    try:
        before,s1 = query(original,'component_sample','original')
        after,s2 = query(rewritten,'component_sample','rewritten')
        report['sample_exact_values'] = before.equals(after)
        report['sample_speedup'] = s1/s2
        report['sample_rows'] = len(before)
    except Exception as err:
        report['sample_error'] = str(err)[:500]
        report['sample_exact_values'] = False
    xt,s3 = query(rewritten,'train_sample','rewritten')
    xv,s4 = query(rewritten,'val','rewritten')
    report['full_sql_seconds'] = s3+s4
    fit_started = time.time()
    report['fit_attempts'] = 1
    try:
        pred,_,seconds = h.train_predict(e['task_type'],xt,seeds['train_sample'][yc],xv)
    finally:
        report['fit_wall_seconds'] = time.time()-fit_started
        save()
    val = h.score(e['task_type'],seeds['val'][yc],pred)
    report.update(validation=val,validation_reproduced=abs(val-archived['best_val'])<=1e-8,
                  fit_seconds=seconds,feature_count=len(xt.columns))
    report['audit'] = run.audit(task,1,rewritten,seeds)
    report['component_pass'] = bool(detail['changed_ctes'] and report.get('sample_exact_values')
                                    and report.get('sample_speedup',0)>=2
                                    and report['full_sql_seconds']<=45
                                    and report['validation_reproduced']
                                    and report['audit'].get('result')=='clean')
except Exception as err:
    report['error'] = f'{type(err).__name__}: {str(err)[:500]}'
    report['component_pass'] = False
finally:
    with psycopg.connect(admin,autocommit=True) as con:
        con.execute(f'DROP DATABASE {db} WITH (FORCE)')
    report['finished_at_utc'] = time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime())
    save()
print(json.dumps({k:report.get(k) for k in ('component_pass','sample_exact_values','sample_speedup',
                 'full_sql_seconds','validation_reproduced','error')}),flush=True)
