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
         Path('/root/agentdb-quality-signal-20261112/results/quality-20261112-v5'),
         Path('/root/agentdb-quality-refine-20261112/results/quality-20261112-v6'),
         Path('/root/agentdb-quality-early-20261112/results/quality-20261112-v7'),
         Path('/root/agentdb-quality-delta-20261112/results/quality-20261112-v8')]
arms = ('none','ace','gmemory','awm','tecod','featpilot','mavra-push','mavra-budgeted','mavra-portfolio','mavra-directed','mavra-cached','mavra-signal','mavra-refine','mavra-early','mavra-delta')
report = {'purpose':'metadata-only protocol audit; no feature/label/quality input',
          'settings_groups':{},'order_mismatches':[], 'metadata_sha256':{},
          'run_cutoffs':{}, 'settings_mismatches':[]}
reference_orders = {}
reference_settings = None
for root in roots:
    for path in sorted(root.glob('*/run.json')):
        if not path.parent.name.endswith('-r1'):
            continue
        arm = path.parent.name.rsplit('-rel-',1)[0]
        if arm not in arms:
            continue
        raw = path.read_bytes()
        row = json.loads(raw)
        report['metadata_sha256'][str(path)] = hashlib.sha256(raw).hexdigest()
        report['run_cutoffs'][str(path)] = [c['k'] for c in row.get('cutoffs', [])]
        settings = {f:row['settings'].get(f) for f in fields}
        if reference_settings is None:
            reference_settings = settings
        compared_fields = fields[:2] if arm == 'featpilot' else fields
        different = {f:{'actual':settings[f], 'reference':reference_settings[f]}
                     for f in compared_fields if settings[f] != reference_settings[f]}
        if different:
            report['settings_mismatches'].append({'run':str(path),'fields':different})
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
report['all_available_settings_match'] = not report['settings_mismatches']
report['all_available_runs_have_five_cutoffs'] = all(
    sorted(cutoffs) == [1, 2, 3, 4, 5] for cutoffs in report['run_cutoffs'].values())
report['expected_run_metadata_count'] = len(arms) * 2
report['available_run_metadata_count'] = len(report['metadata_sha256'])
report['missing_metadata'] = sorted(f'{arm}-{db}-r1' for arm in arms for db in ('rel-stack','rel-trial')
                                    if not any(Path(p).parent.name == f'{arm}-{db}-r1'
                                               for p in report['metadata_sha256']))
report['non_llm_model_fields'] = 'FeatPilot has no language-model settings; its learner parameters are compared normally.'
report['intentional_incomplete_runs'] = {
    'mavra-early-rel-trial-r1':'administratively cancelled after completed Stack failed all3 quality gates; partials retained; no complete Trial rank/cost claim'
}
Path('/root/agentdb-quality-20261112-tools/protocol-equivalence.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'settings_groups':[{'settings':g['settings'],'runs':len(g['runs'])} for g in report['settings_groups'].values()],
                  'all_available_dispatch_orders_match':report['all_available_dispatch_orders_match'],
                  'all_available_settings_match':report['all_available_settings_match'],
                  'all_available_runs_have_five_cutoffs':report['all_available_runs_have_five_cutoffs'],
                  'available_run_metadata_count':report['available_run_metadata_count'],
                  'expected_run_metadata_count':report['expected_run_metadata_count'],
                  'missing_metadata':report['missing_metadata'],
                  'order_mismatches':report['order_mismatches'],
                  'settings_mismatches':report['settings_mismatches']},indent=2))
