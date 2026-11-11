"""Check whether a late-arriving agent actually had the requested metric in memory."""
import json
from pathlib import Path

root = Path('/root/agentdb-mid/results/pop-tpcds-20261013')
out = {'purpose':'post-hoc lookup coverage diagnosis, not new benchmark evidence', 'failures':[], 'timelines':{}}
for path in sorted(root.glob('r*-metric-global-snap/*/cell-pop-*.json')):
    d = json.loads(path.read_text())
    events = []
    for row in d['records']:
        submit = (row.get('learning') or {}).get('submit') or {}
        if row['phase']=='pop-v1' and submit.get('event') == 'promoted':
            events.append({'metric':row['metric'],'agent':row['agent'],'order':row['order'],'key':submit['key']})
    out['timelines'][str(d['repeat'])] = events
    for row in d['records']:
        if row['phase']!='pop-v1' or int(row['agent'][1:])<=d['agents']//2 or row['outcome'] in ('correct','error'):
            continue
        position = (int(row['agent'][1:]),row['order'])
        earlier = [e for e in events if e['metric']==row['metric'] and (int(e['agent'][1:]),e['order'])<position]
        later = [e for e in events if e['metric']==row['metric'] and (int(e['agent'][1:]),e['order'])>=position]
        out['failures'].append({'repeat':d['repeat'],'agent':row['agent'],'order':row['order'],'metric':row['metric'],
                                'requested_metric_published_before_question':bool(earlier),
                                'later_publications':later,'returned_entries':row['metric_use']['found']})
out['all_five_failures_before_requested_metric_publication'] = len(out['failures'])==5 and all(
    not f['requested_metric_published_before_question'] for f in out['failures'])
Path('/root/agentdb-quality-20261112-tools/tpcds-availability-diagnosis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='timelines'},ensure_ascii=False,indent=2))
