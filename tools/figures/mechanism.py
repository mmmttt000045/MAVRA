"""Generate overleaf/gen/mechanism.tex from the archived mechanism-pilot summary."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / 'exp/2026-10-29-mechanism-pilot'


def read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def numbers() -> dict[str, str]:
    a = read(STUDY / 'pilot-summary.json')
    s = read(STUDY / 'system-summary.json')
    assert a['complete'] and len(a['rows']) == 8
    assert all(r['test_score'] is None for r in a['rows'])
    assert s['B']['complete'] and s['B']['requests'] == 9216 and s['B']['unavailable'] == 0
    assert s['C']['complete'] and s['C']['gate_passed']

    def row(arm: str):
        return next(r for r in a['rows'] if r['target']['name'] == 'same-task-later' and r['arm'] == arm)

    d = {}
    for arm, name in [('none', 'None'), ('program', 'Program'), ('definition', 'Definition'), ('full', 'Both')]:
        d['MeA' + name + 'AUC'] = f"{row(arm)['validation_auc']:.4f}"
    d.update(
        MeAValid=str(sum(r['valid'] for r in a['rows'])),
        MeASourceK=f"{a['source']['historical_exploration_tokens'] / 1000:.1f}",
        MeAExtractK=f"{a['source']['new_extraction_tokens'] / 1000:.1f}",
        MeABothOnlineK=f"{row('full')['agent_tokens'] / 1000:.1f}",
        MeANoneOnlineK=f"{row('none')['agent_tokens'] / 1000:.1f}",
        MeABothTotalK=f"{row('full')['amortized_tokens'] / 1000:.1f}",
    )
    for arrival, tag in [('staggered', 'Stag'), ('burst', 'Burst')]:
        for policy, p in [('condition', 'Mavra'), ('definition-cache', 'Cache')]:
            r = next(g for g in s['B']['groups'] if g['arrival'] == arrival and g['reuse_factor'] == 8 and g['policy'] == policy)
            d['MeB' + tag + p] = f"{100 * r['paired_db_ratio']['median']:.1f}"
    d['MeBRequests'] = f"{s['B']['requests']:,}".replace(',', '{,}')
    return d


if __name__ == '__main__':
    out = ROOT / 'overleaf/gen/mechanism.tex'
    out.write_text(
        '% Generated from the frozen 2026-10-29 mechanism evidence.\n'
        + ''.join(f'\\newcommand{{\\{k}}}{{{v}}}\n' for k, v in numbers().items()),
        encoding='utf-8',
    )
    print(out)
