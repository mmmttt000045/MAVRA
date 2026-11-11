"""Read run metadata only: learner/model settings and dispatch order."""
import hashlib
import json
from pathlib import Path

fields = ('SAMPLE_SIZE','LGB_PARAMS','model','llm','reasoning_effort','thinking')
roots = [Path('/root/agentdb-mid/results/relbench-pilot3'),Path('/root/agentdb-mid/results/relbench-main'),
         Path('/root/agentdb-quality-20261112/results/quality-20261112-v1'),
         Path('/root/agentdb-quality-portfolio-20261112/results/quality-20261112-v2'),
         Path('/root/agentdb-quality-directed-20261112/results/quality-20261112-v3b'),
         Path('/root/agentdb-quality-cached-safe-20261112/results/quality-20261112-v4b'),
         Path('/root/agentdb-quality-signal-20261112/results/quality-20261112-v5')]
arms = ('none','ace','gmemory','awm','tecod','featpilot','mavra-push','mavra-budgeted','mavra-portfolio','mavra-directed','mavra-cached','mavra-signal')
report = {'purpose':'metadata-only protocol audit; no feature/label/quality input','settings_groups':{},'order_mismatches':[]}
reference_orders = {}
for root in roots:
    for path in sorted(root.glob('*/run.json')):
        if not path.parent.name.endswith('-r1'):
            continue
        arm = path.parent.name.rsplit('-rel-',1)[0]
        if arm not in arms:
            continue
        row = json.loads(path.read_text())
        settings = {f:row['settings'].get(f) for f in fields}
        key = hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest()
        group = report['settings_groups'].setdefault(key,{'settings':settings,'runs':[]})
        group['runs'].append(str(path))
        dataset = 'rel-stack' if 'rel-stack' in path.parent.name else 'rel-trial'
        for cut in row.get('cutoffs',[]):
            order = cut.get('order')
            label = (dataset,cut['k'])
            if label not in reference_orders:
                reference_orders[label] = order
            if order != reference_orders[label]:
                report['order_mismatches'].append({'run':str(path),'cutoff':cut['k'],
                                                    'order':order,'reference':reference_orders[label]})
report['all_available_dispatch_orders_match'] = not report['order_mismatches']
report['non_llm_model_fields'] = 'FeatPilot has no language-model settings; its learner parameters are compared normally.'
Path('/root/agentdb-quality-20261112-tools/protocol-equivalence.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'settings_groups':[{'settings':g['settings'],'runs':len(g['runs'])} for g in report['settings_groups'].values()],
                  'all_available_dispatch_orders_match':report['all_available_dispatch_orders_match'],
                  'order_mismatches':report['order_mismatches']},indent=2))
