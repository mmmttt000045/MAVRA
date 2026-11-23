#!/usr/bin/env python3
"""Plot the 2x2 feature-representation mechanism ablation (Part A)."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools/figures'))
import mplstyle  # noqa: E402
import style  # noqa: E402
from matplotlib import colors, pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--summary', type=Path, default=HERE / 'representation-summary.json')
    ap.add_argument('--out', type=Path, default=ROOT / 'results/figures')
    args = ap.parse_args()

    d = json.loads(args.summary.read_text(encoding='utf-8'))
    assert d['complete'] and len(d['rows']) == 8, 'Summary must contain all eight completed cells'
    args.out.mkdir(parents=True, exist_ok=True)

    mplstyle.setup('en')
    arms = ['none', 'program', 'definition', 'full']
    labels = ['None', 'Program', 'Definition', 'Both']
    palette = {a: style.PAPER_COLORS[c] for a, c in zip(arms, ['mNoShare', 'mTraj', 'mCondCur', 'mCond'])}
    fig = mplstyle.figure(178, 132)
    axs = fig.subplots(2, 2)
    fig.subplots_adjust(left=0.095, right=0.98, top=0.85, bottom=0.22, hspace=0.55, wspace=0.27)
    for col, (target, title) in enumerate([
        ('cross-task', 'Cross-task: user-engagement k1'),
        ('same-task-later', 'Later cutoff: user-badge k2'),
    ]):
        rs = [next(r for r in d['rows'] if r['target']['name'] == target and r['arm'] == a) for a in arms]
        ax = axs[0, col]
        for i, r in enumerate(rs):
            if r['valid']:
                ax.plot(i, r['validation_auc'], marker=['^', 's', 'D', 'o'][i], color=palette[r['arm']], mfc='white', mew=0.8, ms=4)
                ax.text(i, r['validation_auc'] + 0.017, f"{r['validation_auc']:.3f}", ha='center', fontsize=6.5)
            else:
                ax.text(i, 0.59, 'No valid\nsolution', ha='center', fontsize=6.5)
        base = rs[0]
        if base['valid']:
            ax.axhline(base['validation_auc'] - 0.01, color='black', lw=0.6, ls='--')
        ax.set(
            title=f"({'ab'[col]}) {title}",
            ylabel='Validation AUC',
            xticks=range(4),
            xticklabels=labels,
            xlim=(-0.5, 3.5),
            ylim=(0.55, 1.0),
        )
        ax.grid(axis='y')
        ax = axs[1, col]
        for i, r in enumerate(rs):
            rgb = colors.to_rgb(palette[r['arm']])
            fill = tuple(0.35 * x + 0.65 for x in rgb)
            online = r['agent_tokens'] / 1000
            source = r['historical_source_allocated_tokens'] / 1000
            extract = r['new_extraction_allocated_tokens'] / 1000
            ax.bar(i, online, 0.6, color=fill, edgecolor='black', linewidth=0.4)
            ax.bar(i, source, 0.6, bottom=online, color='white', hatch='//', edgecolor='black', linewidth=0.4)
            ax.bar(i, extract, 0.6, bottom=online + source, color='#D4D4D4', hatch='xx', edgecolor='black', linewidth=0.4)
            ax.text(i, online + source + extract + 5, f'{online + source + extract:.0f}', ha='center', fontsize=6.5)
        ax.set(
            title=f"({'cd'[col]}) Cost including source setup",
            ylabel='Tokens (thousands)',
            xticks=range(4),
            xticklabels=labels,
            xlim=(-0.5, 3.5),
            ylim=(0, max(r['amortized_tokens'] / 1000 for r in d['rows']) * 1.18),
        )
        ax.grid(axis='y')
    fig.suptitle('Feature Representation Ablation: Program Access x Definition Access', fontsize=9, y=0.985)
    fig.legend(
        handles=[
            Patch(facecolor='#C0C0C0', edgecolor='black', linewidth=0.4, label='Target session'),
            Patch(facecolor='white', edgecolor='black', linewidth=0.4, hatch='//', label='Source exploration / 2'),
            Patch(facecolor='#D4D4D4', edgecolor='black', linewidth=0.4, hatch='xx', label='Definition extraction / 2'),
        ],
        loc='upper center',
        bbox_to_anchor=(0.53, 0.925),
        ncol=3,
        fontsize=7,
    )
    out_pdf = args.out / 'mechanism-representation.pdf'
    fig.savefig(out_pdf, facecolor='white')
    plt.close(fig)
    print(out_pdf)


if __name__ == '__main__':
    main()
