#!/usr/bin/env python3
"""Aggregate the change study (no model calls).

Reads every cell's task journal (or report), checks that each completed cell asked
exactly its frozen bank, and writes study-stats.json, summary.md and the LaTeX macros
(overleaf/gen/change-study.tex). Groups follow protocol.json. Accuracy is pooled over
the answers of a group (per schema, and over both schemas), averaged over runs with
the range over runs. Tokens per scored question include the agent session (memory
lookups included) and the method's online memory update after the answer.
Usage: analyse.py [--results DIR] [--arm-results ARM=DIR ...] [--tex PATH]
--arm-results takes one method's cells from another results directory (the final-binary
MAVRA rerun; TeCoD, which is not in the protocol's original method list); the other
methods' cells come from --results.
"""
import argparse
import glob
import json
from pathlib import Path
from statistics import mean, median

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P = json.loads((HERE / 'protocol.json').read_text())
NAMES = {'ace': 'ACE', 'awm': 'AWM', 'gmemory': 'G-Memory', 'mavra': 'MAVRA', 'tecod': 'TeCoD'}
# the protocol's methods, plus any method that only --arm-results supplies (TeCoD, added 2026-11-06)
ARMS = list(P['arms'])
GROUPS = {**P['groups'], 'all': ['holdout', *P['changes']]}


def records(cell):
    reports = glob.glob(str(cell / 'metric-*/report.json'))
    if reports:
        rep = json.loads(Path(reports[0]).read_text())
        return rep['cells'][0]['records'] if rep.get('cells') else [], True
    journals = glob.glob(str(cell / 'metric-*/task-journal.jsonl'))
    rows = [json.loads(x) for x in Path(journals[0]).read_text().splitlines() if x] if journals else []
    return rows, False


def tokens(r):
    run = r.get('run') or {}
    pm = r.get('published_memory') or {}
    return (run.get('input_tokens') or 0) + (run.get('output_tokens') or 0) + (pm.get('input_tokens') or 0) + (pm.get('output_tokens') or 0)


def summarize(rows):
    n = len(rows)
    out = {k: sum(r['outcome'] == k for r in rows) for k in ('correct', 'clarify', 'wrong', 'error')}
    out.update(n=n, accuracy=100 * out['correct'] / n if n else None, wrong_pct=100 * out['wrong'] / n if n else None,
               clarify_pct=100 * out['clarify'] / n if n else None,
               tokens=mean(tokens(r) for r in rows) if n else None,
               seconds=mean((r.get('run') or {}).get('seconds') or 0 for r in rows) if n else None,
               median_seconds=median((r.get('run') or {}).get('seconds') or 0 for r in rows) if n else None,
               calls=mean((r.get('run') or {}).get('steps') or 0 for r in rows) if n else None)
    return out


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--results', default=str(ROOT / P['results']))
    a.add_argument('--arm-results', action='append', default=[], metavar='ARM=DIR')
    a.add_argument('--tex', default=str(ROOT / 'overleaf/gen/change-study.tex'))
    a = a.parse_args()
    res = Path(a.results)
    override = dict(x.split('=', 1) for x in a.arm_results)
    ARMS.extend(arm for arm in override if arm not in ARMS)
    banks = {ds: json.loads((HERE / f'bank-{ds}.json').read_text()) for ds in P['datasets']}
    cells, problems = {}, []
    folders = [c for c in sorted((res / 'cells').glob('*')) if c.name.split('-r', 1)[1].split('-', 1)[1] not in override]
    for arm, d in override.items():
        folders += [c for c in sorted((Path(d) / 'cells').glob('*')) if c.name.endswith(f'-{arm}')]
    for cell in folders:
        ds, rest = cell.name.split('-r', 1)
        run, arm = rest.split('-', 1)
        rows, complete = records(cell)
        scored = [r for r in rows if r['phase'] != 'learn']
        expected = [(ph, t) for ph, ts in banks[ds]['phases'].items() for t in ts]
        asked = [(r['phase'], r['task']) for r in scored]
        if complete and sorted(asked) != sorted(expected):
            problems.append(f'{cell.name}: asked questions differ from the frozen bank')
        cells[(ds, arm, int(run))] = {'rows': scored, 'learn': [r for r in rows if r['phase'] == 'learn'], 'complete': complete}
    runs = sorted({k[2] for k, v in cells.items() if v['complete']})
    # complete runs are decided by the protocol's methods; an added method must cover every one of them, so adding it
    # can never silently drop runs of the others
    full = [r for r in runs if all(cells.get((ds, arm, r), {}).get('complete') for ds in P['datasets'] for arm in P['arms'])]
    for arm in ARMS[len(P['arms']):]:
        lacking = [r for r in full if not all(cells.get((ds, arm, r), {}).get('complete') for ds in P['datasets'])]
        if lacking:
            raise SystemExit(f'{arm} lacks complete cells for runs {lacking}')
    stats = {'complete_runs': full, 'problems': problems, 'per_cell': {}, 'groups': {}, 'per_change': {},
             'sources': {'results': str(res), 'arm_results': override}}
    for (ds, arm, run), c in cells.items():
        stats['per_cell'][f'{ds}-r{run}-{arm}'] = {
            'complete': c['complete'], 'scored': len(c['rows']),
            'groups': {g: summarize([r for r in c['rows'] if r['phase'] in phases]) for g, phases in GROUPS.items()},
            'learn': summarize(c['learn'])}
    for g, phases in GROUPS.items():
        stats['groups'][g] = {}
        for scope in [*P['datasets'], 'both']:
            dss = P['datasets'] if scope == 'both' else [scope]
            stats['groups'][g][scope] = {}
            for arm in ARMS:
                per_run = [summarize([r for ds in dss for r in cells[(ds, arm, run)]['rows'] if r['phase'] in phases]) for run in full]
                if not per_run:
                    continue
                acc = [x['accuracy'] for x in per_run]
                wrong = [x['wrong_pct'] for x in per_run]
                pooled = [r for run in full for ds in dss for r in cells[(ds, arm, run)]['rows'] if r['phase'] in phases]
                stats['groups'][g][scope][arm] = {
                    'accuracy': mean(acc), 'min': min(acc), 'max': max(acc), 'per_run': acc,
                    'wrong_pct': mean(wrong), 'wrong_min': min(wrong), 'wrong_max': max(wrong), 'wrong_per_run': wrong,
                    'clarify': sum(x['clarify'] for x in per_run),
                    'clarify_pct': mean(x['clarify_pct'] for x in per_run),
                    'n_per_run': per_run[0]['n'], 'tokens': mean(x['tokens'] for x in per_run),
                    'seconds': mean(x['seconds'] for x in per_run), 'calls': mean(x['calls'] for x in per_run),
                    'median_seconds': median((r.get('run') or {}).get('seconds') or 0 for r in pooled),
                    'seconds_per_run': [x['seconds'] for x in per_run]}
    for ds in P['datasets']:
        for ph in ['holdout', *P['changes']]:
            stats['per_change'][f'{ds}/{ph}'] = {
                arm: {k: sum(summarize([r for r in cells[(ds, arm, run)]['rows'] if r['phase'] == ph])[k] for run in full)
                      for k in ('correct', 'clarify', 'wrong', 'error', 'n')} for arm in ARMS if full}
    budget = res / 'budget' / 'budget-state.json'
    stats['cost'] = json.loads(budget.read_text()) if budget.exists() else None
    if stats['cost']:
        stats['cost'] = {k: stats['cost'][k] for k in ('charged_cny', 'calls', 'errors', 'models', 'observed_decrease_cny') if k in stats['cost']}
    (HERE / 'study-stats.json').write_text(json.dumps(stats, indent=2, ensure_ascii=False) + '\n')

    lines = [f'# Change study: {len(full)} complete run(s) {full}', '']
    if problems:
        lines += ['**Problems:** ' + '; '.join(problems), '']
    for scope in [*P['datasets'], 'both']:
        lines += [f'## {scope}', '', '| Group | ' + ' | '.join(NAMES[a] for a in ARMS) + ' |', '|---' * (len(ARMS) + 1) + '|']
        for g in GROUPS:
            row = stats['groups'][g][scope]
            lines.append(f'| {g} | ' + ' | '.join(
                f"{row[a]['accuracy']:.1f}% [{row[a]['min']:.0f}–{row[a]['max']:.0f}] · {row[a]['tokens']/1000:.1f}k tok · {row[a]['seconds']:.0f}s"
                if a in row else '–' for a in ARMS) + ' |')
        lines.append('')
    lines += ['## Per change (correct / clarify / wrong over complete runs)', '', '| Schema/change | ' + ' | '.join(NAMES[a] for a in ARMS) + ' |',
              '|---' * (len(ARMS) + 1) + '|']
    for k, v in stats['per_change'].items():
        lines.append(f'| {k} | ' + ' | '.join(f"{v[a]['correct']}/{v[a]['clarify']}/{v[a]['wrong']} of {v[a]['n']}" for a in ARMS if a in v) + ' |')
    if stats['cost']:
        lines += ['', f"Cost: CNY {stats['cost']['charged_cny']:.2f} charged over {stats['cost']['calls']} calls ({stats['cost']['errors']} errors)."]
    (HERE / 'summary.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))

    if not full:
        return
    g = stats['groups']
    mac = {}
    tag = {'ace': 'Ace', 'awm': 'Awm', 'gmemory': 'Gmem', 'mavra': 'Mavra', 'tecod': 'Tecod'}
    gt = {'holdout': 'Hold', 'non_breaking': 'Benign', 'covered_breaks': 'Break', 'outside_conditions': 'Outside', 'all': 'All'}
    st = {'synthetic': 'Syn', 'tpch': 'Tpch', 'both': ''}
    for gname, gtag in gt.items():
        for scope, stag in st.items():
            for arm in ARMS:
                x = g[gname][scope].get(arm)
                if x:
                    mac[f'Cs{gtag}{stag}{tag[arm]}'] = f"{x['accuracy']:.1f}"
                    mac[f'Cs{gtag}{stag}{tag[arm]}Min'] = f"{x['min']:.1f}"
                    mac[f'Cs{gtag}{stag}{tag[arm]}Max'] = f"{x['max']:.1f}"
                    mac[f'Cs{gtag}{stag}{tag[arm]}Wrong'] = f"{x['wrong_pct']:.1f}"
                    mac[f'Cs{gtag}{stag}{tag[arm]}TokK'] = f"{x['tokens']/1000:.1f}"
                    mac[f'Cs{gtag}{stag}{tag[arm]}S'] = f"{x['seconds']:.0f}"
                    mac[f'Cs{gtag}{stag}{tag[arm]}MedS'] = f"{x['median_seconds']:.0f}"
            base = {arm: g[gname][scope][arm] for arm in ARMS if arm != 'mavra' and arm in g[gname][scope]}
            if base and 'mavra' in g[gname][scope]:
                m = g[gname][scope]['mavra']
                best = max(base.values(), key=lambda x: x['accuracy'])
                cheap = min(base.values(), key=lambda x: x['tokens'])
                mac[f'Cs{gtag}{stag}Gain'] = f"{m['accuracy'] - best['accuracy']:.1f}"
                mac[f'Cs{gtag}{stag}BaseMin'] = f"{min(x['accuracy'] for x in base.values()):.1f}"
                mac[f'Cs{gtag}{stag}BaseMax'] = f"{max(x['accuracy'] for x in base.values()):.1f}"
                mac[f'Cs{gtag}{stag}BaseWrongMin'] = f"{min(x['wrong_pct'] for x in base.values()):.0f}"
                mac[f'Cs{gtag}{stag}BaseWrongMax'] = f"{max(x['wrong_pct'] for x in base.values()):.0f}"
                mac[f'Cs{gtag}{stag}BaseTokMinK'] = f"{cheap['tokens']/1000:.1f}"
                mac[f'Cs{gtag}{stag}BaseTokMaxK'] = f"{max(x['tokens'] for x in base.values())/1000:.1f}"
                mac[f'Cs{gtag}{stag}BaseSMax'] = f"{max(x['seconds'] for x in base.values()):.0f}"
                mac[f'Cs{gtag}{stag}BaseSMin'] = f"{min(x['seconds'] for x in base.values()):.0f}"
                mac[f'Cs{gtag}{stag}TokSave'] = f"{100 * (1 - m['tokens'] / cheap['tokens']):.0f}"
    # per-change counts over both schemas and all runs (correct, wrong, total)
    for ph in ['holdout', *P['changes']]:
        for arm in ARMS:
            rows = [stats['per_change'][f'{ds}/{ph}'][arm] for ds in P['datasets'] if f'{ds}/{ph}' in stats['per_change']]
            if rows:
                mac[f'Cs{ph.capitalize()}{tag[arm]}C'] = str(sum(x['correct'] for x in rows))
                mac[f'Cs{ph.capitalize()}{tag[arm]}W'] = str(sum(x['wrong'] for x in rows))
                mac[f'Cs{ph.capitalize()}N'] = str(sum(x['n'] for x in rows))
    lk = stats['per_change'].get('tpch/latekey', {}).get('mavra')
    if lk:
        mac['CsTpchLatekeyClarify'] = str(lk['clarify'])
        mac['CsTpchLatekeyN'] = str(lk['n'])
    # the text claims MAVRA uses the fewest tokens in every group of every schema: check it
    fewest = all(g[gn][sc]['mavra']['tokens'] <= min(g[gn][sc][a]['tokens'] for a in ARMS if a != 'mavra')
                 for gn in GROUPS for sc in [*P['datasets'], 'both'])
    stats['mavra_fewest_tokens_every_group'] = fewest
    (HERE / 'study-stats.json').write_text(json.dumps(stats, indent=2, ensure_ascii=False) + '\n')
    print('MAVRA fewest tokens in every group:', fewest)
    mac['CsRuns'] = str(len(full))
    mac['CsScoredPerRun'] = str(sum(banks[ds]['scored'] for ds in P['datasets']) * len(ARMS))
    scored = sum(banks[ds]['scored'] for ds in P['datasets']) * len(ARMS) * len(full)
    mac['CsScored'] = f'{scored:,}'
    mac['CsQuestions'] = str(sum(banks[ds]['scored'] for ds in P['datasets']))
    if stats['cost']:
        mac['CsCostCny'] = f"{stats['cost']['charged_cny']:.1f}"
    tex = ['% Generated by exp/2026-11-01-change-study/analyse.py; do not edit.']
    tex += [f'\\newcommand{{\\{k}}}{{{v}}}' for k, v in sorted(mac.items())]
    Path(a.tex).write_text('\n'.join(tex) + '\n')
    print(f'wrote {len(mac)} macros to {a.tex}')


if __name__ == '__main__':
    main()
