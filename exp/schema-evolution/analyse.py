#!/usr/bin/env python3
"""Aggregate the 11-update schema and data evolution study (no model calls).

When live cell directories are supplied via `--results` or `--cells-dir`, reads every
cell's task journal or report, verifies that each completed cell asked the exact frozen
question bank, and writes `--out` (`study-stats.json`) and `--tex` (`results/gen/change-study.tex`).

When run without live cell directories, loads archived `study-stats.json` directly and
emits all `Cs*` LaTeX macros to `--tex` without overwriting `study-stats.json`.
"""
import argparse
import glob
import json
from pathlib import Path
from statistics import mean, median

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CFG = {
    'datasets': ['synthetic', 'tpch'],
    'arms': ['ace', 'awm', 'gmemory', 'mavra'],
    'changes': ['append', 'backfill', 'correct', 'addcol', 'status', 'revision', 'dupload', 'dimhist', 'latekey', 'unit', 'mirror'],
    'groups': {
        'holdout': ['holdout'],
        'non_breaking': ['append', 'backfill', 'correct', 'addcol'],
        'covered_breaks': ['status', 'revision', 'dupload', 'dimhist', 'latekey'],
        'outside_conditions': ['unit', 'mirror'],
    },
    'results': 'results/schema-evolution',
}
NAMES = {
    'ace': 'ACE',
    'awm': 'AWM',
    'gmemory': 'G-Memory',
    'mavra': 'MAVRA',
    'tecod': 'TeCoD',
    'recheck': 'Shared recheck',
    'template_schema': 'Template + schema hash',
    'template_revoke': 'Template + write invalidate',
}
CONTROLS = {'mavra', 'recheck', 'template_schema', 'template_revoke'}
GROUPS = {**CFG['groups'], 'all': ['holdout', *CFG['changes']]}


def records(cell: Path):
    reports = glob.glob(str(cell / 'metric-*/report.json'))
    if reports:
        rep = json.loads(Path(reports[0]).read_text(encoding='utf-8'))
        return rep['cells'][0]['records'] if rep.get('cells') else [], True
    journals = glob.glob(str(cell / 'metric-*/task-journal.jsonl'))
    rows = [json.loads(x) for x in Path(journals[0]).read_text(encoding='utf-8').splitlines() if x] if journals else []
    return rows, False


def tokens(r):
    run = r.get('run') or {}
    pm = r.get('published_memory') or {}
    return (run.get('input_tokens') or 0) + (run.get('output_tokens') or 0) + (pm.get('input_tokens') or 0) + (pm.get('output_tokens') or 0)


def summarize(rows):
    n = len(rows)
    out = {k: sum(r['outcome'] == k for r in rows) for k in ('correct', 'clarify', 'wrong', 'error')}
    out.update(
        n=n,
        accuracy=100 * out['correct'] / n if n else None,
        wrong_pct=100 * out['wrong'] / n if n else None,
        clarify_pct=100 * out['clarify'] / n if n else None,
        tokens=mean(tokens(r) for r in rows) if n else None,
        seconds=mean((r.get('run') or {}).get('seconds') or 0 for r in rows) if n else None,
        median_seconds=median((r.get('run') or {}).get('seconds') or 0 for r in rows) if n else None,
        calls=mean((r.get('run') or {}).get('steps') or 0 for r in rows) if n else None,
    )
    return out


def render_markdown(stats: dict, arms: list[str]) -> list[str]:
    full = stats['complete_runs']
    arm_runs = stats['arm_runs']
    problems = stats.get('problems') or []
    extra = [x for x in arms if x not in CFG['arms'] and x in arm_runs]
    lines = [f'# Schema Evolution Study: {len(full)} complete run(s) {full}' + ''.join(f'; {NAMES[x]} runs {arm_runs[x]}' for x in extra), '']
    if problems:
        lines += ['**Problems:** ' + '; '.join(problems), '']
    for scope in [*CFG['datasets'], 'both']:
        lines += [f'## {scope}', '', '| Group | ' + ' | '.join(NAMES[a] for a in arms) + ' |', '|---' * (len(arms) + 1) + '|']
        for g in GROUPS:
            row = stats['groups'][g][scope]
            lines.append(
                f'| {g} | '
                + ' | '.join(
                    f"{row[a]['accuracy']:.1f}% [{row[a]['min']:.0f}–{row[a]['max']:.0f}] · {row[a]['tokens']/1000:.1f}k tok · {row[a]['seconds']:.0f}s"
                    if a in row else '–'
                    for a in arms
                )
                + ' |'
            )
        lines.append('')
    lines += [
        '## Per change (correct / clarify / wrong over complete runs)',
        '',
        '| Schema/change | ' + ' | '.join(NAMES[a] for a in arms) + ' |',
        '|---' * (len(arms) + 1) + '|',
    ]
    for k, v in stats['per_change'].items():
        lines.append(f'| {k} | ' + ' | '.join(f"{v[a]['correct']}/{v[a]['clarify']}/{v[a]['wrong']} of {v[a]['n']}" for a in arms if a in v) + ' |')
    return lines


def build_macros(stats: dict, arms: list[str], banks: dict) -> dict[str, str]:
    g = stats['groups']
    full = stats['complete_runs']
    arm_runs = stats['arm_runs']
    mac = {}
    tag = {
        'ace': 'Ace',
        'awm': 'Awm',
        'gmemory': 'Gmem',
        'mavra': 'Mavra',
        'tecod': 'Tecod',
        'recheck': 'Recheck',
        'template_schema': 'Tschema',
        'template_revoke': 'Trevoke',
    }
    gt = {'holdout': 'Hold', 'non_breaking': 'Benign', 'covered_breaks': 'Break', 'outside_conditions': 'Outside', 'all': 'All'}
    st = {'synthetic': 'Syn', 'tpch': 'Tpch', 'both': ''}
    for gname, gtag in gt.items():
        for scope, stag in st.items():
            for arm in arms:
                x = g[gname][scope].get(arm)
                if x:
                    mac[f'Cs{gtag}{stag}{tag[arm]}'] = f"{x['accuracy']:.1f}"
                    mac[f'Cs{gtag}{stag}{tag[arm]}Min'] = f"{x['min']:.1f}"
                    mac[f'Cs{gtag}{stag}{tag[arm]}Max'] = f"{x['max']:.1f}"
                    mac[f'Cs{gtag}{stag}{tag[arm]}Wrong'] = f"{x['wrong_pct']:.1f}"
                    mac[f'Cs{gtag}{stag}{tag[arm]}Clarify'] = f"{x['clarify_pct']:.1f}"
                    mac[f'Cs{gtag}{stag}{tag[arm]}TokK'] = f"{x['tokens']/1000:.1f}"
                    mac[f'Cs{gtag}{stag}{tag[arm]}S'] = f"{x['seconds']:.0f}"
                    mac[f'Cs{gtag}{stag}{tag[arm]}MedS'] = f"{x['median_seconds']:.0f}"
            base = {arm: g[gname][scope][arm] for arm in arms if arm not in CONTROLS and arm in g[gname][scope]}
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
    for ph in ['holdout', *CFG['changes']]:
        for arm in arms:
            rows = [
                stats['per_change'][f'{ds}/{ph}'][arm]
                for ds in CFG['datasets']
                if f'{ds}/{ph}' in stats['per_change'] and arm in stats['per_change'][f'{ds}/{ph}']
            ]
            if rows:
                mac[f'Cs{ph.capitalize()}{tag[arm]}C'] = str(sum(x['correct'] for x in rows))
                mac[f'Cs{ph.capitalize()}{tag[arm]}W'] = str(sum(x['wrong'] for x in rows))
                if arm in CFG['arms']:
                    mac[f'Cs{ph.capitalize()}N'] = str(sum(x['n'] for x in rows))
                else:
                    mac[f'Cs{ph.capitalize()}{tag[arm]}N'] = str(sum(x['n'] for x in rows))
    lk = stats['per_change'].get('tpch/latekey', {}).get('mavra')
    if lk:
        mac['CsTpchLatekeyClarify'] = str(lk['clarify'])
        mac['CsTpchLatekeyN'] = str(lk['n'])
    mac['CsRuns'] = str(len(full))
    for x in [arm for arm in arms if arm not in CFG['arms'] and arm in arm_runs]:
        mac[f'Cs{tag[x]}Runs'] = str(len(arm_runs[x]))
    mac['CsScoredPerRun'] = str(sum(banks[ds]['scored'] for ds in CFG['datasets']) * len(arms))
    scored = sum(banks[ds]['scored'] for ds in CFG['datasets']) * sum(len(arm_runs[x]) for x in arms if x in arm_runs)
    mac['CsScored'] = f'{scored:,}'
    mac['CsQuestions'] = str(sum(banks[ds]['scored'] for ds in CFG['datasets']))
    return mac


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', default=None, help='Live results directory (defaults to archived study-stats.json)')
    parser.add_argument('--cells-dir', default=None, help='Optional direct path to a cells/ directory')
    parser.add_argument('--arm-results', action='append', default=[], metavar='ARM=DIR')
    parser.add_argument('--out', type=Path, default=HERE / 'study-stats.json', help='Output JSON path when aggregating live cells')
    parser.add_argument('--tex', type=Path, default=ROOT / 'results/gen/change-study.tex', help='Output LaTeX macro file')
    parser.add_argument('--partial-arm', action='append', default=[], metavar='ARM')
    a = parser.parse_args()

    banks = {ds: json.loads((HERE / f'bank-{ds}.json').read_text(encoding='utf-8')) for ds in CFG['datasets']}
    explicit_live = a.results is not None or a.cells_dir is not None or bool(a.arm_results)

    if not explicit_live:
        archived_path = HERE / 'study-stats.json'
        if not archived_path.is_file():
            raise SystemExit(f'Missing archived {archived_path}')
        stats = json.loads(archived_path.read_text(encoding='utf-8'))
        arms = list(stats['arm_runs'].keys())
        lines = render_markdown(stats, arms)
        print('\n'.join(lines))
        mac = build_macros(stats, arms, banks)
        tex = ['% Generated by exp/schema-evolution/analyse.py; do not edit.']
        tex += [f'\\newcommand{{\\{k}}}{{{v}}}' for k, v in sorted(mac.items())]
        a.tex.parent.mkdir(parents=True, exist_ok=True)
        a.tex.write_text('\n'.join(tex) + '\n', encoding='utf-8')
        print(f'wrote {len(mac)} macros to {a.tex}')
        return

    res = Path(a.results) if a.results else (ROOT / CFG['results'])
    cells_root = Path(a.cells_dir) if a.cells_dir else (res / 'cells')
    arms = list(CFG['arms'])
    override = dict(x.split('=', 1) for x in a.arm_results)
    arms.extend(arm for arm in override if arm not in arms)
    folders = (
        [c for c in sorted(cells_root.glob('*')) if c.is_dir() and '-r' in c.name and c.name.split('-r', 1)[1].split('-', 1)[1] not in override]
        if cells_root.is_dir()
        else []
    )
    for arm, d in override.items():
        d_cells = Path(d) / 'cells' if (Path(d) / 'cells').is_dir() else Path(d)
        folders += [c for c in sorted(d_cells.glob('*')) if c.is_dir() and c.name.endswith(f'-{arm}')]
    if not folders:
        raise SystemExit(f'No cell directories found under {cells_root}; refusing to overwrite {a.out}')

    cells, problems = {}, []
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
    full = [r for r in runs if all(cells.get((ds, arm, r), {}).get('complete') for ds in CFG['datasets'] for arm in CFG['arms'])]
    if not full:
        raise SystemExit(f'No complete run across core arms {CFG["arms"]} in {cells_root}; refusing to overwrite {a.out}')

    arm_runs = {arm: full for arm in CFG['arms']}
    for arm in arms[len(CFG['arms']):]:
        lacking = [r for r in full if not all(cells.get((ds, arm, r), {}).get('complete') for ds in CFG['datasets'])]
        if lacking and arm not in a.partial_arm:
            raise SystemExit(f'{arm} lacks complete cells for runs {lacking} (pass --partial-arm {arm} to report it over fewer runs)')
        arm_runs[arm] = [r for r in full if r not in lacking]
        if not arm_runs[arm]:
            raise SystemExit(f'{arm} has no complete run')

    stats = {
        'complete_runs': full,
        'arm_runs': arm_runs,
        'problems': problems,
        'per_cell': {},
        'groups': {},
        'per_change': {},
    }
    for (ds, arm, run), c in cells.items():
        stats['per_cell'][f'{ds}-r{run}-{arm}'] = {
            'complete': c['complete'],
            'scored': len(c['rows']),
            'groups': {g: summarize([r for r in c['rows'] if r['phase'] in phases]) for g, phases in GROUPS.items()},
            'learn': summarize(c['learn']),
        }
    for g, phases in GROUPS.items():
        stats['groups'][g] = {}
        for scope in [*CFG['datasets'], 'both']:
            dss = CFG['datasets'] if scope == 'both' else [scope]
            stats['groups'][g][scope] = {}
            for arm in arms:
                per_run = [summarize([r for ds in dss for r in cells[(ds, arm, run)]['rows'] if r['phase'] in phases]) for run in arm_runs[arm]]
                if not per_run:
                    continue
                acc = [x['accuracy'] for x in per_run]
                wrong = [x['wrong_pct'] for x in per_run]
                pooled = [r for run in arm_runs[arm] for ds in dss for r in cells[(ds, arm, run)]['rows'] if r['phase'] in phases]
                stats['groups'][g][scope][arm] = {
                    'accuracy': mean(acc), 'min': min(acc), 'max': max(acc), 'per_run': acc,
                    'wrong_pct': mean(wrong), 'wrong_min': min(wrong), 'wrong_max': max(wrong), 'wrong_per_run': wrong,
                    'clarify': sum(x['clarify'] for x in per_run),
                    'clarify_pct': mean(x['clarify_pct'] for x in per_run),
                    'n_per_run': per_run[0]['n'], 'tokens': mean(x['tokens'] for x in per_run),
                    'seconds': mean(x['seconds'] for x in per_run), 'calls': mean(x['calls'] for x in per_run),
                    'median_seconds': median((r.get('run') or {}).get('seconds') or 0 for r in pooled),
                    'seconds_per_run': [x['seconds'] for x in per_run],
                }
    for ds in CFG['datasets']:
        for ph in ['holdout', *CFG['changes']]:
            stats['per_change'][f'{ds}/{ph}'] = {
                arm: {
                    k: sum(summarize([r for r in cells[(ds, arm, run)]['rows'] if r['phase'] == ph])[k] for run in arm_runs[arm])
                    for k in ('correct', 'clarify', 'wrong', 'error', 'n')
                }
                for arm in arms
            }
    g = stats['groups']
    fewest = all(
        g[gn][sc]['mavra']['tokens'] <= min(g[gn][sc][x]['tokens'] for x in arms if x not in CONTROLS)
        for gn in GROUPS for sc in [*CFG['datasets'], 'both']
    )
    stats['mavra_fewest_tokens_every_group'] = fewest
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    lines = render_markdown(stats, arms)
    print('\n'.join(lines))
    print('MAVRA fewest tokens in every group:', fewest)

    mac = build_macros(stats, arms, banks)
    tex = ['% Generated by exp/schema-evolution/analyse.py; do not edit.']
    tex += [f'\\newcommand{{\\{k}}}{{{v}}}' for k, v in sorted(mac.items())]
    a.tex.parent.mkdir(parents=True, exist_ok=True)
    a.tex.write_text('\n'.join(tex) + '\n', encoding='utf-8')
    print(f'wrote {len(mac)} macros to {a.tex}')


if __name__ == '__main__':
    main()
