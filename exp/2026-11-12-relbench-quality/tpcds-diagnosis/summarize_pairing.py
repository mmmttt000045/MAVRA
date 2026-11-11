import collections
import hashlib
import json
from pathlib import Path
import statistics

root = Path('/root/agentdb-mid/results/pop-tpcds-20261013')
arms = collections.defaultdict(dict)
sources = {}
for path in sorted(root.rglob('cell-pop-*.json')):
    raw = path.read_bytes()
    d = json.loads(raw)
    if d.get('mode') not in ('traj-global','metric-global-snap'):
        continue
    sources[str(path)] = hashlib.sha256(raw).hexdigest()
    for r in d['records']:
        if r['phase'] != 'pop-v1' or int(r['agent'][1:]) <= d['agents']//2 or r['outcome']=='error':
            continue
        key = (d['repeat'],r['agent'],r['order'])
        if key in arms[d['mode']]:
            raise RuntimeError('duplicate paired task')
        arms[d['mode']][key] = r
assert set(arms['traj-global']) == set(arms['metric-global-snap'])
paired = []
for key, ours in arms['metric-global-snap'].items():
    theirs = arms['traj-global'][key]
    assert ours['question']==theirs['question'], key
    row = {'repeat':key[0],'agent':key[1],'order':key[2],'metric':ours['metric'], 'question':ours['question']}
    for label, item in (('mavra',ours),('examples',theirs)):
        run = item['run']
        learn = ((item.get('learning') or {}).get('extraction') or {})
        row[label] = {'correct':item['outcome']=='correct','input_tokens':run['input_tokens'],
                      'output_tokens':run['output_tokens'],
                      'learning_tokens':learn.get('input_tokens',0)+learn.get('output_tokens',0),
                      'finds':item['metric_use']['finds'],'found':item['metric_use']['found']}
        row[label]['agent_tokens'] = row[label]['input_tokens']+row[label]['output_tokens']
        row[label]['tokens'] = row[label]['agent_tokens']+row[label]['learning_tokens']
    row['excess_tokens'] = row['mavra']['tokens']-row['examples']['tokens']
    paired.append(row)
report = {'purpose':'post-hoc diagnosis of the already published TPC-DS population table; no optimizer input',
          'pairs':len(paired),'source_sha256':sources,'methods':{},'by_metric':{},
          'mavra_failures':[p for p in paired if not p['mavra']['correct']],
          'largest_excess':sorted(paired,key=lambda p:p['excess_tokens'],reverse=True)[:10]}
for arm in ('mavra','examples'):
    report['methods'][arm] = {k:statistics.mean(p[arm][k] for p in paired)
                              for k in ('tokens','input_tokens','output_tokens','agent_tokens','learning_tokens')}
    report['methods'][arm]['correct'] = sum(p[arm]['correct'] for p in paired)
for metric in sorted({p['metric'] for p in paired}):
    rows = [p for p in paired if p['metric']==metric]
    report['by_metric'][metric] = {'pairs':len(rows),'mean_excess_tokens':statistics.mean(p['excess_tokens'] for p in rows),
                                  'mavra_correct':sum(p['mavra']['correct'] for p in rows),
                                  'examples_correct':sum(p['examples']['correct'] for p in rows)}
report['excess_tokens_mean'] = statistics.mean(p['excess_tokens'] for p in paired)
report['excess_on_mavra_failures'] = sum(p['excess_tokens'] for p in paired if not p['mavra']['correct'])
destination = Path('/root/agentdb-quality-20261112-tools/tpcds-paired-diagnosis.json')
destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('source_sha256','largest_excess','mavra_failures')},ensure_ascii=False,indent=2))
cell = next(root.glob('r4-metric-global-snap/*/cell-pop-*.json'))
print('r4 sibling files:', [p.name for p in cell.parent.iterdir()][:18])
