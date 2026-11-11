"""Train/validation-only ablation on archived own programs; no candidate run.

Uses separate fresh databases and never initializes an optimizer with those
archived programs. No held-out label file or label-generation SQL is read.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

root = Path('/root/agentdb-quality-outcomes-20261112')
os.chdir(root)
sys.path.insert(0, str(root / 'tools/relbench'))
import harness as h
from feature_selection import complementary_pool, select_union
from outcome_history import compile_history_features, interval_sql, relation
import psycopg
from psycopg import sql as psql
import yaml

cfg = h.load_env('/root/agentdb-mid/.env')
admin = h.base_url(cfg['AGENTDB_URL']) + '/postgres'
data_root = Path('/root/agentdb-mid/results/relbench-data')
old_root = Path('/root/agentdb-quality-20261112/results/quality-20261112-v1')
destination = Path('/root/agentdb-quality-20261112-tools/history-component.json')
report = {'purpose': 'train/validation diagnostic, not full-run test evidence or optimizer input',
          'held_out_labels_decoded': False, 'label_generation_sql_read': False, 'model_service_calls': 0,
          'history_source': 'full labelled train split available to all benchmark arms',
          'learner_sample': 50000, 'tasks': {},
          'module_sha256': hashlib.sha256((root / 'tools/relbench/outcome_history.py').read_bytes()).hexdigest()}

def save():
    destination.write_text(json.dumps(report, indent=2) + '\n')

for dataset in ('rel-stack', 'rel-trial'):
    data, prep = data_root / dataset, data_root / (dataset + '-prep')
    timeline = json.loads((prep / 'timeline.json').read_text())
    name = f"quality_history_component_{os.getpid()}_{time.time_ns()}"
    url = h.base_url(cfg['AGENTDB_URL']) + '/' + name
    template = 'relbench_' + dataset.replace('rel-', '') + '_t1'
    with psycopg.connect(admin, autocommit=True) as con:
        con.execute(f'CREATE DATABASE {name} TEMPLATE {template}')
    try:
        run = h.Run.__new__(h.Run)
        run.url, run.arm = url, h.ARMS['mavra-cached']
        run.a = SimpleNamespace(data=str(data), prep=str(prep))
        run.tasks = timeline['tasks']
        run.manifest = yaml.safe_load((data / 'manifest.yaml').read_text())
        all_seeds = {}
        with psycopg.connect(url, autocommit=True) as con:
            con.execute('CREATE SCHEMA task')
            for task, e in run.tasks.items():
                ec, yc, tc = e['entity_col'].lower(), e['target_col'].lower(), e['time_col'].lower()
                seeds = {}
                for split in ('train', 'val'):
                    frame = h.pd.read_parquet(prep / 'tasks' / task / 'k1' / (split + '.parquet'))
                    frame.columns = [c.lower() for c in frame]
                    frame = frame.rename(columns={tc: 'seed_time'})
                    frame['seed_time'] = h.pd.to_datetime(frame['seed_time'])
                    seeds[split] = frame
                train = seeds['train']
                rng = h.np.random.RandomState(h.SAMPLE_SEED)
                seeds['train_sample'] = train.iloc[rng.permutation(len(train))[:h.SAMPLE_SIZE]].reset_index(drop=True) if len(train) > h.SAMPLE_SIZE else train
                key_type = 'bigint' if h.pd.api.types.is_integer_dtype(train[ec]) else 'text'
                for split in ('train', 'train_sample', 'val'):
                    table = f'task.{h.tname(task)}_{split}'
                    con.execute(f'CREATE TABLE {table} ({ec} {key_type},seed_time timestamp,{yc} double precision)')
                    h.copy_rows(con, table, seeds[split][[ec, 'seed_time', yc]])
                    con.execute(f'ANALYZE {table}')
                all_seeds[task] = seeds
        for task, e in run.tasks.items():
            started = time.time()
            item = {'dataset': dataset, 'selection_split': 'validation', 'fits': []}
            report['tasks'][task] = item
            try:
                seeds = all_seeds[task]
                ec, yc, kind = e['entity_col'].lower(), e['target_col'].lower(), e['task_type']
                old = json.loads((old_root / f'mavra-budgeted-{dataset}-r1/sessions' / f'{h.tname(task)}-k1.json').read_text())
                base_sql = old['final_sql']
                item['source_sql_sha256'] = hashlib.sha256(base_sql.encode()).hexdigest()
                bx, bs1 = h.features(url, base_sql, f'task.{h.tname(task)}_train_sample', seeds['train_sample'], ec)
                bv, bs2 = h.features(url, base_sql, f'task.{h.tname(task)}_val', seeds['val'], ec)
                def fit(xt, yt, xv):
                    ts = time.time()
                    try:
                        return h.train_predict(kind, xt, yt, xv)
                    finally:
                        item['fits'].append({'columns': xt.shape[1], 'seconds': time.time()-ts})
                baseline_prediction, _, _ = fit(bx, seeds['train_sample'][yc], bv)
                baseline = h.score(kind, seeds['val'][yc], baseline_prediction)
                item.update(baseline_validation=baseline, archived_validation=old['best_val'],
                            control_reproduced=abs(baseline-old['best_val'])<1e-8,
                            baseline_features=len(bx.columns), baseline_sql_seconds=bs1+bs2)
                horizon = (int(h.pd.Timedelta(e['timedelta']).value) + 999) // 1000
                hist_sql = compile_history_features('task', h.tname(task)+'_train', ec, yc, horizon)
                hx, hs1 = h.features(url, hist_sql, f'task.{h.tname(task)}_train_sample', seeds['train_sample'], ec, timeout_s=30)
                hv, hs2 = h.features(url, hist_sql, f'task.{h.tname(task)}_val', seeds['val'], ec, timeout_s=30)
                audited = run.audit(task, 1, hist_sql, seeds)
                item.update(history_sql_seconds=hs1+hs2, public_audit=audited.get('result'),
                            validation_rows_with_history=float((hv.oh_count>0).mean()))
                # A second audit censors training targets by their maturity time.
                tstar = seeds['train_sample'].seed_time.max()
                sub = seeds['train_sample'][seeds['train_sample'].seed_time==tstar].sort_values(ec).head(5000).reset_index(drop=True)
                guard = 'history_guard_' + h.tname(task)
                with psycopg.connect(url, autocommit=True) as con:
                    con.execute(f'CREATE SCHEMA {guard}')
                    con.execute(psql.SQL('CREATE VIEW {}.history AS SELECT * FROM {} WHERE seed_time+{}<={}').format(
                        psql.Identifier(guard), psql.Identifier('task', h.tname(task)+'_train'),
                        psql.SQL(interval_sql(horizon)), psql.Literal(tstar.to_pydatetime())))
                    con.execute(f'CREATE TABLE {guard}.seeds AS SELECT * FROM task.{h.tname(task)}_train_sample WHERE false')
                    h.copy_rows(con, f'{guard}.seeds', sub)
                normal, _ = h.features(url, hist_sql, f'{guard}.seeds', sub, ec, timeout_s=30)
                censored_sql = hist_sql.replace(relation('task', h.tname(task)+'_train'), relation(guard, 'history'))
                hidden, _ = h.features(url, censored_sql, f'{guard}.seeds', sub, ec, timeout_s=30)
                item['training_label_audit'] = bool(h.np.isclose(normal.to_numpy(),hidden.to_numpy(),rtol=1e-6,atol=1e-9,equal_nan=True).all())
                if audited.get('result')!='clean' or not item['training_label_audit'] or not item['control_reproduced']:
                    raise RuntimeError('control reproduction or temporal audit failed')
                xt, xv, mapping, duplicates = complementary_pool(bx,bv,hx,hv,[(c,1.) for c in hx])
                selected = select_union(xt,seeds['train_sample'][yc],xv,seeds['val'][yc],list(bx),baseline,
                                        h.metric_of(kind)[1],fit,lambda y,p:h.score(kind,y,p),budget_seconds=15)
                item.update(selected_validation=selected['chosen']['val'], chosen=selected['chosen']['name'],
                            chosen_features=len(selected['chosen']['columns']), offered=len(mapping), duplicates=duplicates,
                            selection_seconds=selected['seconds'], selection_fits=selected['fits'],
                            useful=selected['chosen']['name']!='single_attempt',
                            sql_admission='matrix component only; a full candidate still requires combined SQL reproduction and fresh audits')
                print(json.dumps({task:{k:item.get(k) for k in ('baseline_validation','selected_validation','chosen','history_sql_seconds','selection_seconds','useful')}}),flush=True)
            except Exception as err:
                item['error'] = f'{type(err).__name__}: {str(err)[:500]}'
                print(json.dumps({task:{'error':item['error']}}),flush=True)
            finally:
                item['elapsed_seconds'] = time.time()-started
                save()
    finally:
        with psycopg.connect(admin,autocommit=True) as con:
            con.execute(f'DROP DATABASE {name} WITH (FORCE)')
report['component_pass'] = len(report['tasks'])==6 and all('error' not in r for r in report['tasks'].values()) and sum(r.get('useful',False) for r in report['tasks'].values())>=2
save()
print(json.dumps({'component_pass':report['component_pass'],'useful_tasks':[k for k,v in report['tasks'].items() if v.get('useful')]}),flush=True)
