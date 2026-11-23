#!/usr/bin/env python3
"""Aggregate or inspect the controlled system mechanism benchmarks (Parts B and C).

When run without `--results-dir`, loads archived `system-summary.json` and verifies
the 72-cell condition-overlap sweep (Part B) and 30-trial TOCTOU barrier check (Part C).
When `--results-dir` is passed, recomputes `system-summary.json` from live reports.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def interval(xs):
    return {'n': len(xs), 'median': st.median(xs), 'min': min(xs), 'max': max(xs), 'raw': xs}


def aggregate_live(base: Path) -> dict:
    data = {'study': 'controlled condition-overlap and TOCTOU barrier supplements', 'B': {}, 'C': {}}
    reports = {}
    for kind in ['B', 'C']:
        for p in sorted(base.glob(kind + '-*/report.json')):
            r = json.loads(p.read_text(encoding='utf-8'))
            if r.get('report', {}).get('error'):
                data[kind].setdefault('failed_attempts', []).append(r['report'])
            else:
                assert kind not in reports, 'Multiple successful reports need an explicit inclusion rule'
                reports[kind] = r['report']
    if not reports:
        raise SystemExit(f'No B-*/report.json or C-*/report.json found under {base}')

    if 'C' in reports:
        rows = reports['C']['rows']
        groups = []
        for case in ['benign_after_check', 'violation_after_check', 'violation_before_call']:
            for mode in ['tx-precheck', 'tx-bound']:
                rs = [r for r in rows if r['case'] == case and r['mode'] == mode]
                groups.append({
                    'case': case,
                    'mode': mode,
                    'n': len(rs),
                    **{k: sum(r['outcome'] == k for r in rs) for k in ['served', 'violation', 'rejected', 'error']},
                })
        gate = (
            len(rows) == 30
            and all(g['n'] == 5 and not g['error'] for g in groups)
            and all(not g['violation'] for g in groups if g['mode'] == 'tx-bound')
            and all(g['rejected'] == 5 for g in groups if g['case'] == 'violation_before_call')
            and all(g['served'] == 5 for g in groups if g['case'] == 'benign_after_check')
            and all(g['violation'] == 5 for g in groups if g['mode'] == 'tx-precheck' and g['case'] == 'violation_after_check')
        )
        data['C'].update(complete=len(rows) == 30, groups=groups, gate_passed=gate)

    if 'B' in reports:
        cells = reports['B']['cells']
        expected = {
            (r, k, p, a)
            for r in range(3)
            for k in [1, 2, 4, 8]
            for p in ['definition', 'definition-cache', 'condition']
            for a in ['staggered', 'burst']
        }
        observed = {(c['repeat'], c['reuse_factor'], c['policy'], c['arrival']) for c in cells}
        assert len(observed) == len(cells) and observed <= expected
        assert all(c['definitions'] == 16 and c['agents'] == 8 and c['rows_per_fact'] == 100000 and len(c['uses']) == 128 for c in cells)
        extra_refresh = []
        for c in cells:
            events = [e for e in c['events'] if e['event'] == 'maintenance']
            counts = Counter(e['key'] for e in events)
            if counts and max(counts.values()) > 1:
                extra_refresh.append({
                    **{k: c[k] for k in ['repeat', 'reuse_factor', 'policy', 'arrival']},
                    'maintenance_events': len(events),
                    'refreshes_per_key': dict(counts),
                })
        groups = []
        for arrival in ['staggered', 'burst']:
            for reuse in [1, 2, 4, 8]:
                for policy in ['definition', 'definition-cache', 'condition']:
                    rs = sorted(
                        [r for r in cells if r['arrival'] == arrival and r['reuse_factor'] == reuse and r['policy'] == policy],
                        key=lambda r: r['repeat'],
                    )
                    if not rs:
                        continue
                    bases = [
                        next(
                            b for b in cells
                            if b['arrival'] == arrival and b['reuse_factor'] == reuse
                            and b['repeat'] == r['repeat'] and b['policy'] == 'definition'
                        )
                        for r in rs
                    ]
                    qcount = lambda r: sum(r['db']['by_kind'][k][0] for k in ['check', 'guard', 'metric'])  # noqa: E731
                    groups.append({
                        'arrival': arrival,
                        'reuse_factor': reuse,
                        'policy': policy,
                        'db_ms': interval([r['db']['db_ms'] for r in rs]),
                        'paired_db_ratio': interval([r['db']['db_ms'] / b['db']['db_ms'] for r, b in zip(rs, bases)]),
                        'validation_queries': interval([qcount(r) for r in rs]),
                        'wall_seconds': interval([r['wall_seconds'] for r in rs]),
                        'unavailable': sum(r['unavailable'] for r in rs),
                        'requests': sum(len(r['uses']) for r in rs),
                    })
        data['B'].update(
            complete=(observed == expected),
            groups=groups,
            extra_refresh_cells=extra_refresh,
            unavailable=sum(r['unavailable'] for r in cells),
            requests=sum(len(r['uses']) for r in cells),
        )
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--results-dir', type=Path, default=None, help='Live B-*/C-* report directory')
    ap.add_argument('--out', type=Path, default=HERE / 'system-summary.json', help='Output summary JSON')
    args = ap.parse_args()

    if args.results_dir is None:
        data = json.loads(args.out.read_text(encoding='utf-8'))
    else:
        data = aggregate_live(args.results_dir)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(json.dumps({
        k: {x: v for x, v in data[k].items() if x in ['complete', 'gate_passed', 'unavailable', 'requests']}
        for k in ['B', 'C']
    }, indent=2))


if __name__ == '__main__':
    main()
