"""RelBench tokens per method, including memory operations, one row per database.

Left: tokens of the learning cutoff (cutoff 1, three sessions), which for MAVRA include extracting definitions. Right: cumulative tokens over the reuse cutoffs 2-5 (twelve sessions in arrival order) from
zero, the reuse-stage cost of Table III. Brackets compare MAVRA's reuse total with the cheapest baseline's and with
No memory's; their percentages are checked against the macros the text prints (overleaf/gen/relbench.tex).
Data and arrival order are unchanged from paper-sessions.json.

    python3 tools/figures/relbench_cumulative.py [paper-sessions.json [out_dir]]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mplstyle  # noqa: E402
import style  # noqa: E402
from style import INK, MUTED  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

NAME = 'relbench-cumulative'
W, H = 88.9, 69.5
DATA = style.ROOT / 'exp/2026-10-20-relbench/paper-sessions.json'
ARMS = [('none', 'No memory', '无记忆', 'mNoShare', '^'), ('ace', 'ACE', 'ACE', 'mACE', 'v'),
        ('gmemory', 'G-Memory', 'G-Memory', 'mGMem', 'P'), ('awm', 'AWM', 'AWM', 'mAWM', 'X'),
        ('tecod', 'TeCoD', 'TeCoD', 'mTeCoD', 's'),
        ('mavra', 'MAVRA (ours)', 'MAVRA（本文）', 'mCond', 'o')]   # 11-06 (user): DeepPrep dropped, TeCoD added
BASELINES = ('ace', 'gmemory', 'awm', 'tecod')   # the cheapest of these is the bracket's reference, as in paper-stats.py
PREFIX = {'rel-stack': 'Stack', 'rel-trial': 'Trial'}
TEXT = {'en': {'y': 'Tokens (M)', 'learn': 'C1: learn', 'reuse': 'C2–5: reuse (cumulative)'},
        'zh': {'y': 'token（百万）', 'learn': '截点 1：学习', 'reuse': '截点 2–5：复用（累计）'}}


def printed():
    """Values of overleaf/gen/relbench.tex (\\providecommand + \\renewcommand pairs)."""
    text = (style.PAPER / 'gen/relbench.tex').read_text(encoding='utf-8')
    return dict(re.findall(r'\\renewcommand\{\\(\w+)\}\{([^{}]*)\}', text))


def bracket(ax, x, y0, y1, label, color):
    """Vertical bracket right of the curves, from MAVRA's end (y0) to a baseline's end (y1)."""
    tick = .22
    ax.plot([x - tick, x, x, x - tick], [y0, y0, y1, y1], color=color, lw=.6, clip_on=False, zorder=4,
            solid_joinstyle='miter')
    ax.text(x + .2, (y0 + y1) / 2, label, ha='left', va='center', fontsize=6.5, color=color, clip_on=False)


def draw(lang, data_path=DATA, out_dir=None):
    data = json.loads(Path(data_path).read_text(encoding='utf-8'))
    macros = printed()
    mplstyle.setup(lang)
    fig = mplstyle.figure(W, H)
    dbs = [db for db in ('rel-stack', 'rel-trial') if db in data]
    grid = fig.add_gridspec(len(dbs), 2, width_ratios=[1.2, 5], left=.135, right=.985, bottom=.075, top=.80,
                            hspace=.55, wspace=.06)
    for panel, db in enumerate(dbs):
        learn_ax = fig.add_subplot(grid[panel, 0])
        reuse_ax = fig.add_subplot(grid[panel, 1], sharey=learn_ax)
        sequence = [row['k'] for row in data[db]['mavra']]
        assert sequence[:3] == [1, 1, 1] and all(k >= 2 for k in sequence[3:]), (db, sequence)
        reuse_k = sequence[3:]
        boundaries = [i + .5 for i in range(1, len(reuse_k)) if reuse_k[i] != reuse_k[i - 1]]
        assert len(boundaries) == 3, (db, reuse_k)
        for boundary in boundaries:
            reuse_ax.axvline(boundary, color=style.GRID, lw=.45, zorder=1)
        ends, learned = {}, {}
        for i, (arm, en, zh, color, marker) in enumerate(ARMS):
            rows = data[db].get(arm)
            if not rows:
                continue
            assert [row['k'] for row in rows] == sequence, (db, arm)
            ink = style.PAPER_COLORS[color]
            ours = arm == 'mavra'
            learned[arm] = sum(row['tokens'] for row in rows if row['k'] == 1) / 1e6
            learn_ax.bar(i, learned[arm], width=.74, color=ink, edgecolor=INK if ours else 'none', lw=.5, zorder=2)
            learn_ax.plot(i, learned[arm], marker=marker, ms=2.8, mew=0, color=ink, zorder=3, clip_on=False,
                          transform=learn_ax.transData)
            total, ys = 0.0, [0.0]
            for row in rows[3:]:
                total += row['tokens'] / 1e6
                ys.append(total)
            ends[arm] = total
            xs = [.5] + list(range(1, len(ys)))
            if ours:   # a white casing keeps MAVRA readable where baselines cross it
                reuse_ax.plot(xs, ys, color='white', lw=2.7, zorder=2.9, solid_capstyle='round')
            reuse_ax.plot(xs, ys, color=ink, lw=1.5 if ours else .95, marker=marker, ms=2.8, mew=0,
                          markevery=list(range(1, len(ys))), label=en if lang == 'en' else zh,
                          zorder=3 if ours else 2)
        # brackets: MAVRA against the cheapest baseline and against No memory, as the text states them
        pre = PREFIX[db]
        best = min((arm for arm in BASELINES if arm in ends), key=ends.get)
        vs_best = f"{100 * (1 - ends['mavra'] / ends[best]):.0f}"
        vs_none = f"{100 * (1 - ends['mavra'] / ends['none']):.0f}"
        style.agree(f'{db} MAVRA vs cheapest baseline', vs_best, macros[f'Rb{pre}MavraVsBest'])
        style.agree(f'{db} MAVRA vs No memory', vs_none, macros[f'Rb{pre}MavraTokSave'])
        style.agree(f'{db} MAVRA reuse tokens', f"{ends['mavra']:.2f}", macros[f'Rb{pre}MavraTok'])
        last = len(reuse_k)
        bracket(reuse_ax, last + .7, ends['mavra'], ends[best], f'−{vs_best}%',
                style.PAPER_COLORS[dict((a, c) for a, _, _, c, _ in ARMS)[best]])
        bracket(reuse_ax, last + 2.55, ends['mavra'], ends['none'], f'−{vs_none}%', style.PAPER_COLORS['mNoShare'])
        # axes
        learn_ax.set_xlim(-.6, len(ARMS) - .4)
        learn_ax.set_xticks([])
        learn_ax.set_xlabel(TEXT[lang]['learn'], fontsize=6.5, color=MUTED, labelpad=3)
        learn_ax.set_ylim(0, max(max(ends.values()), max(learned.values())) * 1.08)
        learn_ax.yaxis.set_major_locator(MaxNLocator(nbins=4, min_n_ticks=3))
        learn_ax.tick_params(labelsize=6.5)
        learn_ax.set_title(f"({'ab'[panel]}) {db}", loc='left', fontsize=8, color=INK, pad=3)
        reuse_ax.set_xlim(.5, last + 4.1)   # room for the brackets right of the last session
        centers = [(lo + hi) / 2 for lo, hi in zip([.5] + boundaries, boundaries + [last + .5])]
        reuse_ax.set_xticks(centers, ['C2', 'C3', 'C4', 'C5'])
        reuse_ax.tick_params(axis='x', length=0, labelsize=6.5, pad=3)
        reuse_ax.tick_params(axis='y', labelleft=False)
        reuse_ax.text(.02, .97, TEXT[lang]['reuse'], transform=reuse_ax.transAxes, ha='left', va='top',
                      fontsize=6.5, color=MUTED)
    fig.text(.015, .44, TEXT[lang]['y'], rotation=90, va='center', fontsize=7, color=INK)
    handles, labels = fig.axes[1].get_legend_handles_labels()
    legend = fig.legend(handles, labels, loc='upper center', ncol=3, bbox_to_anchor=(.53, .99),
                        fontsize=7, handlelength=1.8, columnspacing=.8, labelspacing=.35)
    for label in legend.get_texts():
        if label.get_text().startswith('MAVRA'):
            label.set_weight('bold')
    out = Path(out_dir or style.OUT) / (f'{NAME}.pdf' if lang == 'en' else f'{NAME}-zh.pdf')
    mplstyle.save(fig, out)
    print(out)


if __name__ == '__main__':
    for lang in ('en', 'zh'):
        draw(lang, *(sys.argv[1:3]))
