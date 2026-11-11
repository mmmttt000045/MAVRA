"""Site-success train/validation ablation of useful columns from inferior views."""
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import time

root = Path('/root/agentdb-quality-cached-safe-20261112')
os.chdir(root)
sys.path.insert(0, str(root / 'tools/relbench'))
import harness as h
from feature_selection import complementary_pool, select_union
import psycopg
import yaml

cfg = h.load_env('/root/agentdb-mid/.env')
admin = h.base_url(cfg['AGENTDB_URL']) + '/postgres'
data = Path('/root/agentdb-mid/results/relbench-data/rel-trial')
prep = Path('/root/agentdb-mid/results/relbench-data/rel-trial-prep')
path = Path('/root/agentdb-quality-portfolio-20261112/results/quality-20261112-v2/mavra-portfolio-rel-trial-r1/sessions/site_success-k1.json')
old = json.loads(path.read_text())
meta = json.loads((prep / 'timeline.json').read_text())['tasks']
task, e = 'site-success', meta['site-success']
ec, yc, tc = e['entity_col'].lower(),e['target_col'].lower(),e['time_col'].lower()
seeds = {}
for split in ('train','val'):
    frame = h.pd.read_parquet(prep / 'tasks' / task / 'k1' / (split+'.parquet'))
    frame.columns = [c.lower() for c in frame]
    frame = frame.rename(columns={tc:'seed_time'})
    frame['seed_time'] = h.pd.to_datetime(frame['seed_time'])
    seeds[split] = frame
rng = h.np.random.RandomState(h.SAMPLE_SEED)
train = seeds['train']
seeds['train_sample'] = train.iloc[rng.permutation(len(train))[:h.SAMPLE_SIZE]].reset_index(drop=True) if len(train)>h.SAMPLE_SIZE else train
name = f'quality_view_pool_{os.getpid()}_{time.time_ns()}'
url = h.base_url(cfg['AGENTDB_URL'])+'/'+name
with psycopg.connect(admin,autocommit=True) as con:
    con.execute(f'CREATE DATABASE {name} TEMPLATE relbench_trial_t1')
report = {'purpose':'validation component only, not benchmark test evidence or optimizer initialization',
          'held_out_labels_decoded':False,'model_service_calls':0,'fits':[],'views':[],'passed':False}
try:
    with psycopg.connect(url,autocommit=True) as con:
        con.execute('CREATE SCHEMA task')
        key_type = 'bigint' if h.pd.api.types.is_integer_dtype(train[ec]) else 'text'
        for split in ('train','train_sample','val'):
            table = 'task.site_success_'+split
            con.execute(f'CREATE TABLE {table}({ec} {key_type},seed_time timestamp,{yc} double precision)')
            h.copy_rows(con,table,seeds[split][[ec,'seed_time',yc]])
            con.execute(f'ANALYZE {table}')
    run = h.Run.__new__(h.Run)
    run.url,run.arm,run.tasks = url,h.ARMS['mavra-cached'],meta
    run.a = SimpleNamespace(data=str(data),prep=str(prep))
    run.manifest = yaml.safe_load((data/'manifest.yaml').read_text())
    def fit(xt,yt,xv):
        ts=time.time()
        try:
            return h.train_predict(e['task_type'],xt,yt,xv)
        finally:
            report['fits'].append({'columns':len(xt.columns),'seconds':time.time()-ts})
    def matrix(sql):
        xt,s1=h.features(url,sql,'task.site_success_train_sample',seeds['train_sample'],ec)
        xv,s2=h.features(url,sql,'task.site_success_val',seeds['val'],ec)
        return xt,xv,s1+s2
    base=old['final_sql']
    bx,bv,seconds=matrix(base)
    prediction,_,_=fit(bx,seeds['train_sample'][yc],bv)
    baseline=h.score(e['task_type'],seeds['val'][yc],prediction)
    report.update(baseline=baseline,archived_baseline=old['best_val'],base_columns=list(bx),base_sql_seconds=seconds)
    if abs(baseline-old['best_val'])>1e-8:
        raise AssertionError('fallback control failed to reproduce')
    pool_t,pool_v=bx,bv
    used=0.
    sources=[]
    for attempt in [old,*old.get('other_attempts',[])]:
        valid=[v for v in attempt.get('validations',[]) if v.get('val') is not None and v.get('leak') is False
               and v.get('sql')!=base and v.get('sql_seconds',999)<=30]
        if not valid:
            continue
        v=min(valid,key=lambda x:x['val'])
        if used+v['sql_seconds']>50:
            continue
        used+=v['sql_seconds']
        xt,xv,secs=matrix(v['sql'])
        prediction,importance,_=fit(xt,seeds['train_sample'][yc],xv)
        raw=h.score(e['task_type'],seeds['val'][yc],prediction)
        if abs(raw-v['val'])>1e-8:
            raise AssertionError('view control failed to reproduce')
        pool_t,pool_v,mapping,duplicates=complementary_pool(pool_t,pool_v,xt,xv,importance,max_extra=8)
        sources.append((v['sql'],mapping))
        report['views'].append({'val':raw,'sql_seconds':secs,'offered':len(mapping),'mapping':mapping,'duplicates':duplicates,
                                'sql_sha256':hashlib.sha256(v['sql'].encode()).hexdigest()})
    selected=select_union(pool_t,seeds['train_sample'][yc],pool_v,seeds['val'][yc],list(bx),baseline,False,fit,
                          lambda y,p:h.score(e['task_type'],y,p),budget_seconds=15)
    report['selection']={k:v for k,v in selected.items() if k!='chosen'}
    chosen=selected['chosen']
    report['chosen']={k:chosen.get(k) for k in ('name','val','columns')}
    def headers(sql):
        df,_=h.read_sql(url,'SELECT * FROM ('+sql.strip().rstrip(';').replace('{seeds}','task.site_success_val')+') q LIMIT 0')
        return list(df.columns[:2])
    if chosen['name']!='single_attempt':
        columns=chosen['columns']
        keys=headers(base)
        base_cols=[c for c in columns if c in bx]
        combined=h.select_columns_sql(base,keys,base_cols) if base_cols else None
        combined_cols=base_cols
        for source,mapping in sources:
            pairs=[(c,name) for c,name in mapping.items() if name in columns]
            if not pairs:
                continue
            skeys=headers(source)
            parts=[f'q.{h.quote_ident(c)} AS {h.quote_ident(alias)}' for c,alias in pairs]
            projected=f'SELECT q.{h.quote_ident(skeys[0])},q.{h.quote_ident(skeys[1])},'+','.join(parts)+' FROM (\n'+source.strip().rstrip(';')+'\n) q'
            added=[alias for _,alias in pairs]
            if combined:
                combined=h.union_sql(combined,keys,combined_cols,projected,skeys,added)
            else:
                combined,keys=projected,skeys
            combined_cols+=added
        check={'sql_seconds':0.}
        run.check_columns(task,1,combined,seeds,pool_v[columns],check,timeout_s=120)
        audit=run.audit(task,1,combined,seeds)
        report.update(sql_reproduction=check,audit=audit,combined_sql=combined)
        report['passed']=audit.get('result')=='clean'
except Exception as err:
    report['error']=f'{type(err).__name__}: {str(err)[:500]}'
    raise
finally:
    Path('/root/agentdb-quality-20261112-tools/view-pool-component.json').write_text(json.dumps(report,indent=2)+'\n')
    with psycopg.connect(admin,autocommit=True) as con:
        con.execute(f'DROP DATABASE {name} WITH (FORCE)')
    print(json.dumps({k:report.get(k) for k in ('passed','baseline','base_columns','chosen','audit','error')},indent=2),flush=True)
