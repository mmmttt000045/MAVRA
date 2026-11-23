#!/usr/bin/env python3
"""Build a frozen question bank from model-free scenario evaluation output.

Rule: for the held-out phase and for every database update phase, select the single-month
question (P1, September of the held-out year) and the period-difference question (T1, that
month minus June of the learning year) of every metric reading a modified table; backfill
selects the corresponding forms in the learning year (suffix -B).
Usage: select-bank.py CANDIDATES_JSON OUT_JSON
"""
import argparse
import json
from pathlib import Path

METRICS = ('M1', 'M3', 'M5')
CHANGES = ('append', 'backfill', 'correct', 'addcol', 'status', 'revision', 'dupload', 'dimhist', 'latekey', 'unit', 'mirror')
FORMS = ('P1', 'T1')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('candidates', type=Path, help='Model-free candidate evaluation JSON')
    ap.add_argument('out', type=Path, help='Output frozen bank JSON')
    args = ap.parse_args()

    rows = json.loads(args.candidates.read_text(encoding='utf-8'))
    bank, detail = {}, {}
    for r in rows:
        if r['task'].split('-')[1] not in FORMS:
            continue
        bank.setdefault(r['phase'], []).append(r['task'])
        detail.setdefault(r['phase'], []).append({k: r[k] for k in ('task', 'metric', 'ask', 'v1', 'gold', 'stale', 'stale_correct')})
    for ph in bank:
        order = sorted(range(len(bank[ph])), key=lambda i: (FORMS.index(bank[ph][i].split('-')[1]), bank[ph][i]))
        bank[ph] = [bank[ph][i] for i in order]
        detail[ph] = [detail[ph][i] for i in order]
    missing = [c for c in ['holdout', *CHANGES] if c not in bank]
    assert not missing, f'candidates JSON lacks phases {missing}'
    learn = [f'{m}-L{i}' for m in METRICS for i in (1, 2)]
    out = {
        'rule': __doc__.split('Usage:')[0].strip(),
        'phases': bank,
        'all_tasks': learn + [t for ph in bank.values() for t in ph],
        'counts': {ph: len(v) for ph, v in bank.items()},
        'scored': sum(len(v) for v in bank.values()),
        'detail': detail,
    }
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(out['counts']), 'scored', out['scored'])


if __name__ == '__main__':
    main()
