#!/usr/bin/env python3
"""Aggregate 12-change replay outcomes with value conditions and historical gate G9 (Table 6).

When run without `--run-dir`, loads archived `replay-guards.json` directly and emits all
`Rp*` LaTeX macros to `--tex` without overwriting `replay-guards.json`. When `--run-dir`
is supplied, aggregates `{schema}-main/replay-*/report.json` and `{schema}-nog9/replay-*/report.json`
across TPC-DS, TPC-H, SSB, and BIRD `financial`.
"""
import argparse
from collections import Counter
import glob
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCHEMAS = ['tpcds', 'tpch', 'ssb', 'financial']
SCOPES = {
    'Benign': ['append', 'backfill', 'correct', 'addcol'],
    'Break': ['status', 'revision', 'dupload', 'dimhist', 'latekey'],
    'Outside': ['unit', 'mirror', 'reclass'],
}
POLICIES = [('revoke', 'Revoke'), ('schema', 'Schema'), ('tabletest', 'Tests'), ('condition', 'Mavra')]
CLASS = {'correct': 'C', 'served_wrong': 'W', 'unavailable_needed': 'R', 'unavailable_unneeded': 'R'}


def key(r):
    return (r['lib'].split('/')[-1], r['change'], r['entry'], r['task'])


def report(path_glob):
    files = glob.glob(path_glob)
    if len(files) != 1:
        raise SystemExit(f'Expected 1 report matching {path_glob}, found {files}')
    return json.loads(Path(files[0]).read_text(encoding='utf-8'))


def aggregate_live(run_dir: Path, baseline_summary: Path) -> dict:
    base_table = (
        json.loads(baseline_summary.read_text(encoding='utf-8'))['table']['condition']
        if baseline_summary.is_file()
        else {s: {} for s in SCOPES}
    )
    table = {p: {s: Counter() for s in SCOPES} for p, _ in POLICIES}
    new_archived = {s: Counter() for s in SCOPES}
    per_change, ablation, g9_events = {}, {}, Counter()
    for ds in SCHEMAS:
        main_r = report(f'{run_dir}/{ds}-main/replay-*/report.json')
        rows = {p: {key(r): r for r in main_r['outcomes'] if r['policy'] == p} for p, _ in POLICIES}
        common = set.intersection(*[set(v) for v in rows.values()])
        for p, _ in POLICIES:
            for k in sorted(common):
                r = rows[p][k]
                scope = next(s for s, cs in SCOPES.items() if r['change'] in cs)
                table[p][scope][CLASS[r['class']]] += 1
                table[p][scope]['n'] += 1
                per_change.setdefault(f'{ds}/{r["change"]}', {}).setdefault(p, Counter())[CLASS[r['class']]] += 1
        for k, r in rows['condition'].items():
            if r['change'] == 'reclass' or k not in common:
                continue
            scope = next(s for s, cs in SCOPES.items() if r['change'] in cs)
            new_archived[scope][CLASS[r['class']]] += 1
            new_archived[scope]['n'] += 1
        nog9 = report(f'{run_dir}/{ds}-nog9/replay-*/report.json')
        for r in nog9['outcomes']:
            ablation.setdefault(f'{ds}/{r["change"]}', Counter())[CLASS[r['class']]] += 1
        for m in main_r['maintenance']:
            if m['policy'] != 'condition':
                continue
            for e in m['events']:
                if e.get('event') == 'history_checked':
                    g9_events[(ds, m['change'], 'moved' if e['moved'] else ('vacuous' if e['compared'] == 0 else 'pass'))] += 1
                elif e.get('event') == 'history_implied':
                    g9_events[(ds, m['change'], 'implied')] += 1
    return {
        'table': {p: {s: dict(c) for s, c in v.items()} for p, v in table.items()},
        'old_mavra_on_archived_changes': base_table,
        'new_mavra_on_archived_changes': {s: dict(c) for s, c in new_archived.items()},
        'per_change': {k: {p: dict(c) for p, c in v.items()} for k, v in sorted(per_change.items())},
        'ablation_no_g9': {k: dict(c) for k, c in sorted(ablation.items())},
        'g9_events': {f'{d}/{c}/{x}': v for (d, c, x), v in sorted(g9_events.items())},
    }


def build_macros(out: dict) -> dict[str, str]:
    table = out['table']
    old_table = out['old_mavra_on_archived_changes']
    new_archived = out['new_mavra_on_archived_changes']
    per_change = out['per_change']
    ablation = out['ablation_no_g9']
    mac = {}
    for p, tag in POLICIES:
        for s in SCOPES:
            c = table[p][s]
            for cls in 'CWR':
                mac[f'Rp{tag}{s}{cls}'] = f'{c.get(cls, 0):,}'.replace(',', '{,}')
            mac[f'Rp{s}N'] = f"{c['n']:,}".replace(',', '{,}')
    mac['RpTotal'] = f"{sum(table['condition'][s]['n'] for s in SCOPES):,}".replace(',', '{,}')
    m = table['condition']['Break']
    mac['RpMavraBreakCPct'] = f"{100 * m.get('C', 0) / m['n']:.0f}"
    mac['RpSchemaBreakWPct'] = f"{100 * table['schema']['Break'].get('W', 0) / table['schema']['Break']['n']:.0f}"
    for s in SCOPES:
        for cls in 'CWR':
            mac[f'RpOldMavra{s}{cls}'] = f'{old_table.get(s, {}).get(cls, 0):,}'.replace(',', '{,}')
            mac[f'RpNewMavraArch{s}{cls}'] = f'{new_archived.get(s, {}).get(cls, 0):,}'.replace(',', '{,}')
    g9 = Counter()
    for k_str, v in out['g9_events'].items():
        _, c, x = k_str.split('/')
        g9[x + ('Reclass' if c == 'reclass' else '')] += v
    mac['RpMavraAllW'] = str(sum(table['condition'][s].get('W', 0) for s in SCOPES))
    mac['RpOldMavraAllW'] = str(sum(old_table.get(s, {}).get('W', 0) for s in SCOPES))
    mac['RpGNinePass'] = str(g9['pass'] + g9['vacuous'])
    mac['RpGNineImplied'] = str(g9['implied'])
    mac['RpGNineMoved'] = str(g9['moved'])
    mac['RpGNineReclassMoved'] = str(g9['movedReclass'])
    mac['RpGNineReclassPass'] = str(g9['passReclass'] + g9['vacuousReclass'])
    rc = Counter()
    for k_str, v in per_change.items():
        if k_str.endswith('/reclass'):
            rc.update(v['condition'])
    ra = Counter()
    for k_str, v in ablation.items():
        if k_str.endswith('/reclass'):
            ra.update(v)
    for cls in 'CWR':
        mac[f'RpReclassMavra{cls}'] = str(rc[cls])
        mac[f'RpReclassNogNine{cls}'] = str(ra[cls])
    mac['RpReclassN'] = str(sum(rc[c] for c in 'CWR'))
    return mac


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--run-dir', type=Path, default=None, help='Live replay directory containing <schema>-main and <schema>-nog9')
    ap.add_argument('--baseline-summary', type=Path, default=ROOT / 'exp/policy-replay/replay-policies.json')
    ap.add_argument('--out', type=Path, default=HERE / 'replay-guards.json', help='Summary JSON path')
    ap.add_argument('--tex', type=Path, default=ROOT / 'results/gen/replay-guards.tex', help='Output LaTeX macro path')
    a = ap.parse_args()

    if a.run_dir is None:
        if not a.out.is_file():
            raise SystemExit(f'Missing archived {a.out}')
        out = json.loads(a.out.read_text(encoding='utf-8'))
    else:
        out = aggregate_live(a.run_dir, a.baseline_summary)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    table = out['table']
    for p, tag in POLICIES:
        print(tag.ljust(7), '  '.join(
            f"{s}: {table[p][s].get('C', 0)}/{table[p][s].get('W', 0)}/{table[p][s].get('R', 0)} of {table[p][s]['n']}"
            for s in SCOPES
        ))
    mac = build_macros(out)
    tex = ['% Generated by exp/maintenance-guards/analyse-replay.py; do not edit.']
    tex += [f'\\newcommand{{\\{k}}}{{{v}}}' for k, v in sorted(mac.items())]
    a.tex.parent.mkdir(parents=True, exist_ok=True)
    a.tex.write_text('\n'.join(tex) + '\n', encoding='utf-8')
    print(f'wrote {len(mac)} macros to {a.tex}')


if __name__ == '__main__':
    main()
