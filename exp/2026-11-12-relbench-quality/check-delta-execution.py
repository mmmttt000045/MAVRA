"""Audit actual delta-run budgets and fit ledgers after execution; never select features."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = {'purpose': 'post-run execution audit; no quality-based selection', 'panels': {}}
    for db in ('rel-stack', 'rel-trial'):
        run = args.run_root / f'mavra-delta-{db}-r1'
        records = []
        for path in sorted((run / 'sessions').glob('*.json')):
            if path.name.endswith('.partial.json'):
                continue
            raw = path.read_bytes()
            row = json.loads(raw)
            if row['k'] == 1:
                continue
            additions = [v for v in row.get('validations', []) if v.get('source') == 'agent_additions']
            clean = [v for v in additions if v.get('audit_result') == 'clean']
            fits = row.get('feature_fits', [])
            totals = row.get('totals', {})
            checks = {
                'model_budget': len(row.get('llm', [])) <= 4,
                'agent_tool_budget': len(row.get('tools', [])) <= 6,
                'validation_budget': len(row.get('validations', [])) <= 8,
                'fit_count_accounted': totals.get('feature_fit_calls') == len(fits),
                'fit_seconds_accounted': abs(totals.get('feature_fit_seconds', -1)
                                             - sum(f.get('seconds', 0) for f in fits)) < 1e-6,
                'clean_addition_values_reproduced': all(v.get('delta', {}).get('values_reproduced') for v in clean),
                'clean_addition_size': all(len(v.get('delta', {}).get('added_columns', {})) <= 12
                                           and v.get('n_features', 101) <= 100 for v in clean),
                'refit_seconds_in_total': row.get('agent_seconds', -1)
                                         >= (row.get('charged_current_refit') or {}).get('agent_seconds', 0),
            }
            records.append({'file': path.name, 'sha256': hashlib.sha256(raw).hexdigest(),
                            'model_calls': len(row.get('llm', [])), 'agent_tools': len(row.get('tools', [])),
                            'addition_attempts': len(additions), 'clean_additions': len(clean),
                            'addition_errors': sum(bool(v.get('error')) for v in additions),
                            'addition_timeouts': sum('timeout' in str(v.get('error', '')).lower() for v in additions),
                            'addition_nonvarying': sum('no varying complementary columns' in str(v.get('error', '')) for v in additions),
                            'addition_audit_rejections': sum(v.get('audit_result') in ('leak', 'error') for v in additions),
                            'repaired_after_error': bool(clean) and any(v.get('error') for v in additions),
                            'improving_clean_additions': sum(bool(v.get('improved')) for v in clean),
                            'fit_calls': len(fits), 'checks': checks, 'passed': all(checks.values())})
        report['panels'][db] = {'warm_sessions': len(records), 'complete': len(records) == 12,
                                'records': records, 'checks_passed': all(r['passed'] for r in records)}
    report['complete'] = all(p['complete'] for p in report['panels'].values())
    report['passed'] = report['complete'] and all(p['checks_passed'] for p in report['panels'].values())
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'complete': report['complete'], 'passed': report['passed'],
                      'panels': {db: {k: p[k] for k in ('warm_sessions', 'checks_passed')}
                                 for db, p in report['panels'].items()}}))


if __name__ == '__main__':
    main()
