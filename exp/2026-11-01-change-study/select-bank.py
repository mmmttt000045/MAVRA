#!/usr/bin/env python3
"""Freeze the question bank of each schema from the model-free probe (metric-bench --bank-probe).

Rule (fixed before any paid call, independent of every method's output): for the held-out
phase and for every change, ask the single-month question (P1, September of the held-out
year) and the period-difference question (T1, that month minus June of the learning year)
of every metric that reads a written table; backfill asks the same two forms in the
learning year (suffix -B). All eleven generators write rows of the held-out September or
the year around it, so these forms see every change. The probe's reference values (v1,
gold after the business change, reference SQL after the representation change) are kept
with the bank for the record.
Usage: select-bank.py PROBE_JSON OUT_JSON
"""
import json
import sys
from pathlib import Path

P = json.loads((Path(__file__).resolve().parent / 'protocol.json').read_text())
FORMS = ('P1', 'T1')


def main():
    rows = json.loads(Path(sys.argv[1]).read_text())
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
    missing = [c for c in ['holdout', *P['changes']] if c not in bank]
    assert not missing, f'probe lacks phases {missing}'
    learn = [f'{m}-L{i}' for m in P['metrics'] for i in (1, 2)]
    out = {'rule': __doc__.split('Usage:')[0].strip(), 'phases': bank,
           'all_tasks': learn + [t for ph in bank.values() for t in ph],
           'counts': {ph: len(v) for ph, v in bank.items()}, 'scored': sum(len(v) for v in bank.values()), 'detail': detail}
    Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(out['counts']), 'scored', out['scored'])


if __name__ == '__main__':
    main()
