#!/usr/bin/env python3
"""Replay of exp/2026-11-11-maint-hardening (A null conditions, B history gate G9, C scale conditions).

Inputs: RUN_DIR with {schema}-main/replay-*/report.json (condition, schema, revoke, tabletest on all twelve
changes) and {schema}-nog9/replay-*/report.json (condition without G9 on dimhist and reclass), and the 11-01
final MAVRA run (exp/2026-11-01-replay-rerun/rerun-final-reports.tgz) for the before/after audit.
Writes replay-hardening.json next to this script and, with --tex, the Rp* macros of Table VI
(premise changes now include reclass; RpOld* keep the 11-01 MAVRA numbers for the text).
Usage: analyse-replay.py RUN_DIR [--old-tgz PATH] [--tex PATH]
"""
import argparse
from collections import Counter
import glob
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCHEMAS = ['tpcds', 'tpch', 'ssb', 'financial']
SCOPES = {'Benign': ['append', 'backfill', 'correct', 'addcol'],
          'Break': ['status', 'revision', 'dupload', 'dimhist', 'latekey'],
          'Outside': ['unit', 'mirror', 'reclass']}
POLICIES = [('revoke', 'Revoke'), ('schema', 'Schema'), ('tabletest', 'Tests'), ('condition', 'Mavra')]
CLASS = {'correct': 'C', 'served_wrong': 'W', 'unavailable_needed': 'R', 'unavailable_unneeded': 'R'}


def key(r):
    return (r['lib'].split('/')[-1], r['change'], r['entry'], r['task'])


def report(path_glob):
    files = glob.glob(path_glob)
    assert len(files) == 1, (path_glob, files)
    return json.loads(Path(files[0]).read_text())


def old_mavra(tgz):
    out = {}
    with tarfile.open(tgz) as t:
        for m in t.getmembers():
            if m.name.endswith('report.json'):
                ds = m.name.split('/')[1]
                d = json.load(io.TextIOWrapper(t.extractfile(m), encoding='utf-8'))
                out[ds] = {key(r): r for r in d['outcomes'] if (r['policy'], r['oracle']) == ('condition', 'snapshot')}
    return out


def main():
    a = argparse.ArgumentParser()
    a.add_argument('run')
    a.add_argument('--old-tgz', default=str(ROOT / 'exp/2026-11-01-replay-rerun/rerun-final-reports.tgz'))
    a.add_argument('--tex')
    a = a.parse_args()
    old = old_mavra(a.old_tgz)
    table = {p: {s: Counter() for s in SCOPES} for p, _ in POLICIES}
    old_table = {s: Counter() for s in SCOPES}
    new_archived = {s: Counter() for s in SCOPES}  # MAVRA now, on the eleven archived changes only
    per_change, audit, ablation, g9_events = {}, {}, {}, Counter()
    for ds in SCHEMAS:
        main_r = report(f'{a.run}/{ds}-main/replay-*/report.json')
        rows = {p: {key(r): r for r in main_r['outcomes'] if r['policy'] == p} for p, _ in POLICIES}
        common = set.intersection(*[set(v) for v in rows.values()])
        for p, _ in POLICIES:
            for k in sorted(common):
                r = rows[p][k]
                scope = next(s for s, cs in SCOPES.items() if r['change'] in cs)
                table[p][scope][CLASS[r['class']]] += 1
                table[p][scope]['n'] += 1
                per_change.setdefault(f'{ds}/{r["change"]}', {}).setdefault(p, Counter())[CLASS[r['class']]] += 1
        # before/after audit against the 11-01 final MAVRA run (eleven archived changes)
        changed = Counter()
        examples = []
        for k, r in rows['condition'].items():
            o = old.get(ds, {}).get(k)
            if o is None:
                continue
            scope = next(s for s, cs in SCOPES.items() if r['change'] in cs)
            old_table[scope][CLASS[o['class']]] += 1
            old_table[scope]['n'] += 1
            new_archived[scope][CLASS[r['class']]] += 1
            new_archived[scope]['n'] += 1
            if o['class'] != r['class']:
                changed[(r['change'], o['class'], r['class'])] += 1
                if len(examples) < 6:
                    examples.append({'change': r['change'], 'entry': r['entry'], 'task': r['task'], 'old': o['class'], 'new': r['class'],
                                     'gold': r['gold'], 'old_value': o.get('value'), 'new_value': r.get('value')})
        audit[ds] = {'common': len(common), 'mavra_class_changes': {f'{c}: {x} -> {y}': v for (c, x, y), v in sorted(changed.items())},
                     'examples': examples}
        # ablation without G9
        nog9 = report(f'{a.run}/{ds}-nog9/replay-*/report.json')
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
    out = {'table': {p: {s: dict(c) for s, c in v.items()} for p, v in table.items()},
           'old_mavra_on_archived_changes': {s: dict(c) for s, c in old_table.items()},
           'new_mavra_on_archived_changes': {s: dict(c) for s, c in new_archived.items()},
           'per_change': {k: {p: dict(c) for p, c in v.items()} for k, v in sorted(per_change.items())},
           'ablation_no_g9': {k: dict(c) for k, c in sorted(ablation.items())},
           'g9_events': {f'{d}/{c}/{x}': v for (d, c, x), v in sorted(g9_events.items())},
           'audit': audit}
    (HERE / 'replay-hardening.json').write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
    for p, tag in POLICIES:
        print(tag.ljust(7), '  '.join(f"{s}: {table[p][s]['C']}/{table[p][s]['W']}/{table[p][s]['R']} of {table[p][s]['n']}" for s in SCOPES))
    print('old MAVRA (11 archived changes):', {s: f"{c['C']}/{c['W']}/{c['R']} of {c['n']}" for s, c in old_table.items()})
    print('no-G9 ablation:', json.dumps(out['ablation_no_g9']))
    print('G9 events:', json.dumps(out['g9_events']))
    print(json.dumps(audit, indent=1, ensure_ascii=False))
    if a.tex:
        mac = {}
        for p, tag in POLICIES:
            for s in SCOPES:
                c = table[p][s]
                for cls in 'CWR':
                    mac[f'Rp{tag}{s}{cls}'] = f'{c[cls]:,}'.replace(',', '{,}')
                mac[f'Rp{s}N'] = f"{c['n']:,}".replace(',', '{,}')
        mac['RpTotal'] = f"{sum(table['condition'][s]['n'] for s in SCOPES):,}".replace(',', '{,}')
        m = table['condition']['Break']
        mac['RpMavraBreakCPct'] = f"{100 * m['C'] / m['n']:.0f}"
        mac['RpSchemaBreakWPct'] = f"{100 * table['schema']['Break']['W'] / table['schema']['Break']['n']:.0f}"
        for s in SCOPES:
            for cls in 'CWR':
                mac[f'RpOldMavra{s}{cls}'] = f'{old_table[s][cls]:,}'.replace(',', '{,}')
                mac[f'RpNewMavraArch{s}{cls}'] = f'{new_archived[s][cls]:,}'.replace(',', '{,}')
        g9 = Counter()
        for (d, c, x), v in g9_events.items():
            g9[x + ('Reclass' if c == 'reclass' else '')] += v
        mac['RpMavraAllW'] = str(sum(table['condition'][s]['W'] for s in SCOPES))
        mac['RpOldMavraAllW'] = str(sum(old_table[s]['W'] for s in SCOPES))
        mac['RpGNinePass'] = str(g9['pass'] + g9['vacuous'])
        mac['RpGNineImplied'] = str(g9['implied'])
        mac['RpGNineMoved'] = str(g9['moved'])
        mac['RpGNineReclassMoved'] = str(g9['movedReclass'])
        mac['RpGNineReclassPass'] = str(g9['passReclass'] + g9['vacuousReclass'])
        rc = Counter()
        for k, v in per_change.items():
            if k.endswith('/reclass'):
                rc.update(v['condition'])
        ra = Counter()
        for k, v in ablation.items():
            if k.endswith('/reclass'):
                ra.update(v)
        for cls in 'CWR':
            mac[f'RpReclassMavra{cls}'] = str(rc[cls])
            mac[f'RpReclassNogNine{cls}'] = str(ra[cls])
        mac['RpReclassN'] = str(sum(rc[c] for c in 'CWR'))
        tex = ['% Generated by exp/2026-11-11-maint-hardening/analyse-replay.py; do not edit.']
        tex += [f'\\newcommand{{\\{k}}}{{{v}}}' for k, v in sorted(mac.items())]
        Path(a.tex).write_text('\n'.join(tex) + '\n')


if __name__ == '__main__':
    main()
