#!/usr/bin/env python3
"""Aggregate or display the 2x2 feature-representation mechanism study (Part A).

When run without `--results-dir`, loads archived `representation-summary.json` and prints
the summary table without overwriting tracked files. When `--results-dir` is supplied,
aggregates all eight factorial cells and writes `--out`.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TARGETS = [
    {'name': 'cross-task', 'task': 'user-engagement', 'cutoff': 1},
    {'name': 'same-task-later', 'task': 'user-badge', 'cutoff': 2},
]
ARMS = ['none', 'program', 'definition', 'full']
LABELS = {
    'none': 'No memory',
    'program': 'Program only',
    'definition': 'Definitions only',
    'full': 'Program + definitions',
}


def exact(sql):
    return (sql or '').replace('\r\n', '\n').strip().rstrip(';').rstrip()


def render_table(data: dict) -> str:
    lines = [
        '# Part A: Feature Representation Ablation (2x2)',
        '',
        f"Status: {'complete' if data.get('complete') else 'incomplete'}",
        '',
        '| Target | Arm | Validation AUC | Target Audit | Agent Tokens | Amortized Tokens | Exact Memory Match |',
        '| --- | --- | ---: | --- | ---: | ---: | --- |',
    ]
    for r in data['rows']:
        if r.get('status') != 'complete':
            lines.append(f"| {r['target']['name']} | {LABELS[r['arm']]} | pending | -- | -- | -- | -- |")
            continue
        auc = f"{r['validation_auc']:.4f}" if r.get('validation_auc') is not None else 'no valid SQL'
        match = '/'.join(r.get('exact_final_memory_matches') or []) or 'adapted / new'
        lines.append(
            f"| {r['target']['name']} | {LABELS[r['arm']]} | {auc} | "
            f"{'clean' if r.get('valid') else 'failed'} | {r['agent_tokens']:,} | "
            f"{r['amortized_tokens']:,.0f} | {match} |"
        )
    src = data['source']
    lines += [
        '',
        f"Source historical exploration: {src['historical_exploration_tokens']:,} tokens; "
        f"definition extraction: {src['new_extraction_tokens']:,} tokens "
        f"({src['published']} / {src['drafts']} candidates admitted).",
    ]
    return '\n'.join(lines)


def aggregate_live(base: Path) -> dict:
    source = json.loads((base / 'source/source.json').read_text(encoding='utf-8'))
    setup = source['new_learning']
    archived = json.loads((HERE / 'source-input.json').read_text(encoding='utf-8'))
    historical = archived.get('historical_exploration_tokens', source['totals']['tokens'])
    extraction = setup['input_tokens'] + setup['output_tokens']
    rows = []
    for target in TARGETS:
        for arm in ARMS:
            name = target['name'] + '-' + arm
            file = base / name / 'sessions' / f"{target['task'].replace('-', '_')}-k{target['cutoff']}.json"
            if not file.is_file():
                raise SystemExit(f'Missing session file {file}; refusing to overwrite summary')
            d = json.loads(file.read_text(encoding='utf-8'))
            totals = d['totals']
            clean = (d.get('audit') or {}).get('result') == 'clean'
            valid = bool(clean and d.get('final_sql') and d.get('best_val') is not None)
            returned = []
            for entry in d.get('memory_outputs', []):
                out = entry['output']
                if entry['tool'] == 'retrieve_programs':
                    returned.extend(('program', x['sql']) for x in out.get('programs', []) if x.get('sql'))
                elif out.get('sql'):
                    returned.append(('compiled', out['sql']))
            prov = lambda sql: sorted({kind for kind, s in returned if exact(s) == exact(sql) and exact(sql)})  # noqa: E731
            alloc_src = historical / len(TARGETS) if arm != 'none' else 0
            alloc_ext = extraction / len(TARGETS) if arm in ('definition', 'full') else 0
            flags = d.get('evaluation_flags') or {'test_labels_read': False, 'test_scored': False, 'target_writeback': False}
            test_score = (d.get('eval') or {}).get('test')
            assert test_score is None
            assert flags['test_labels_read'] is False and flags['test_scored'] is False
            rows.append({
                'name': name,
                'arm': arm,
                'target': target,
                'status': 'complete',
                'valid': valid,
                'validation_auc': d.get('best_val'),
                'audit': d.get('audit'),
                'stop': d.get('stop'),
                'agent_tokens': totals['tokens'],
                'historical_source_allocated_tokens': alloc_src,
                'new_extraction_allocated_tokens': alloc_ext,
                'amortized_tokens': totals['tokens'] + alloc_src + alloc_ext,
                'agent_seconds': d.get('agent_seconds'),
                'tools': totals['tool_calls_by_category'],
                'memory_calls': [x['name'] for x in d['tools'] if x.get('category') == 'memory'],
                'exact_final_memory_matches': prov(d.get('final_sql')),
                'validation_memory_matches': [
                    {
                        'tool_i': v.get('tool_i'),
                        'memory_match': prov(v.get('sql')),
                        'val': v.get('val'),
                        'leak': v.get('leak'),
                        'error': v.get('error'),
                    }
                    for v in d.get('validations', [])
                ],
                'evaluation_flags': flags,
                'test_score': test_score,
            })
    for r in rows:
        baseline = next(x for x in rows if x['target'] == r['target'] and x['arm'] == 'none')
        threshold = baseline['validation_auc'] - 0.01 if baseline.get('valid') else None
        r['paired_validation_threshold'] = threshold
        r['qualified_on_validation'] = bool(r.get('valid') and r['validation_auc'] >= threshold) if threshold is not None else None
    audits = {}
    for target in TARGETS:
        f = base / (target['name'] + '-full') / 'source-target-audit.json'
        if f.is_file():
            audits[target['name']] = json.loads(f.read_text(encoding='utf-8'))
    return {
        'study': 'controlled 2x2 feature representation ablation (validation only)',
        'complete': all(r['status'] == 'complete' for r in rows),
        'source': {
            'historical_exploration_tokens': historical,
            'new_extraction_tokens': extraction,
            'drafts': len(setup['events']),
            'published': sum(e['event'] == 'promoted' for e in setup['events']),
        },
        'rows': rows,
        'source_target_audits': audits,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--results-dir', type=Path, default=None, help='Live representation run directory')
    ap.add_argument('--out', type=Path, default=HERE / 'representation-summary.json', help='Summary JSON path')
    args = ap.parse_args()

    if args.results_dir is None:
        data = json.loads(args.out.read_text(encoding='utf-8'))
        assert data['complete'] and len(data['rows']) == 8
        print(render_table(data))
        return

    data = aggregate_live(args.results_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(render_table(data))


if __name__ == '__main__':
    main()
