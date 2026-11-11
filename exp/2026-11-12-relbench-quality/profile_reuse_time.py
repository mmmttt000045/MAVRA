"""Disjoint recorded agent-time components, not a reconstructed wall clock."""
from pathlib import Path
import hashlib
import json

roots = {'directed':Path('/root/agentdb-quality-directed-20261112/results/quality-20261112-v3b'),
         'cached':Path('/root/agentdb-quality-cached-safe-20261112/results/quality-20261112-v4b')}
report = {'purpose':'post-run timing diagnosis only; no optimizer input',
          'scope':'Reported agent seconds; phase sums are not end-to-end wall time. Different cold programs prevent a causal cross-arm interpretation.',
          'runs':{}}
for arm,root in roots.items():
    for directory in sorted(p for p in root.glob('mavra-*') if p.is_dir()):
        rows=[]
        for path in sorted((directory/'sessions').glob('*.json')):
            if path.name.endswith('.partial.json'):
                continue
            s=json.loads(path.read_text())
            if s['k']<=1:
                continue
            select=s.get('memory_select') or {}
            ref=s.get('memory_reference') or {}
            prune=s.get('memory_prune') or {}
            components={'charged_current_refit':(s.get('charged_current_refit') or {}).get('agent_seconds',0.),
                        'memory_push':(s.get('memory_push') or {}).get('seconds',0.)-select.get('audit_seconds',0.),
                        'reference_start':ref.get('seconds',0.)-ref.get('audit_seconds',0.),
                        'final_prune':prune.get('elapsed_seconds',0.)-prune.get('audit_seconds',0.),
                        'agent_llm':sum(x.get('seconds',0.) for x in s.get('llm',[])),
                        'agent_tools':sum(x.get('seconds',0.)-x.get('audit_seconds',0.) for x in s.get('tools',[]))}
            residual=s['agent_seconds']-sum(components.values())
            rows.append({'task':s['task'],'cutoff':s['k'],'agent_seconds':s['agent_seconds'],
                         'components':components,'residual_seconds':residual,
                         'separately_recorded_learning_seconds':(s.get('learning') or {}).get('seconds',0.),
                         'separately_recorded_session_audit_seconds':s.get('audit_seconds'),
                         'uncharged_common_goal_seconds':0. if s.get('charged_current_refit') else (s.get('target_detail') or {}).get('seconds',0.),
                         'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        assert len(rows)==12,(directory,len(rows))
        aggregate={key:sum(r['components'][key] for r in rows) for key in rows[0]['components']}
        report['runs'][directory.name]={'agent_seconds':sum(r['agent_seconds'] for r in rows),'components':aggregate,
                                        'residual_seconds':sum(r['residual_seconds'] for r in rows),
                                        'learning_seconds':sum(r['separately_recorded_learning_seconds'] for r in rows),
                                        'rows':rows}
destination=Path('/root/agentdb-quality-20261112-tools/reuse-time-profile.json')
destination.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({name:{k:v for k,v in run.items() if k!='rows'} for name,run in report['runs'].items()},indent=2))
