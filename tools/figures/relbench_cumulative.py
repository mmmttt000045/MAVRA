"""RelBench tokens: cutoff-1 learning bars and cutoff-2..5 cumulative reuse lines."""
import json
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
ARMS = [('none', 'No memory', '无记忆', 'mNoShare', '^'),
        ('ace', 'ACE', 'ACE', 'mACE', 'v'),
        ('gmemory', 'G-Memory', 'G-Memory', 'mGMem', 'P'),
        ('awm', 'AWM', 'AWM', 'mAWM', 'X'),
        ('tecod', 'TeCoD', 'TeCoD', 'mTeCoD', 's'),
        ('mavra', 'MAVRA (ours)', 'MAVRA（本文）', 'mCond', 'o')]
TEXT = {'en': {'y': 'Tokens (M)',
               'first': 'C1: learn',
               'later': 'C2\u20135: reuse (cumulative)',
               'cutoffs': ['C2', 'C3', 'C4', 'C5']},
        'zh': {'y': 'Token（百万）',
               'first': '截点 1：学习',
               'later': '截点 2\u20135：累计复用',
               'cutoffs': ['C2', 'C3', 'C4', 'C5']}}


def draw(lang, data_path=DATA, out_dir=None):
    data = json.loads(Path(data_path).read_text(encoding='utf-8'))
    mplstyle.setup(lang)
    fig = mplstyle.figure(W, H)
    dbs = [db for db in ('rel-stack', 'rel-trial') if db in data]
    gs = fig.add_gridspec(len(dbs), 2, width_ratios=[40.25, 167.71], wspace=0.06, hspace=0.55,
                          left=0.135, right=0.985, bottom=0.075, top=0.80)
    for panel, db in enumerate(dbs):
        ax_bar = fig.add_subplot(gs[panel, 0])
        ax_line = fig.add_subplot(gs[panel, 1], sharey=ax_bar)
        sequence = [row['k'] for row in data[db]['mavra']]
        first_end = next(i for i in range(1, len(sequence)) if sequence[i] != sequence[i - 1])
        c25_ends = {}
        ymax = 0.0
        for idx, (arm, en, zh, color, marker) in enumerate(ARMS):
            rows = data[db].get(arm)
            if not rows:
                continue
            assert [row['k'] for row in rows] == sequence, (db, arm)
            c1 = sum(row['tokens'] for row in rows[:first_end]) / 1e6
            is_mavra = arm == 'mavra'
            col = style.PAPER_COLORS[color]
            ax_bar.bar(idx, c1, width=0.74, color=col,
                       edgecolor=INK if is_mavra else 'none',
                       linewidth=0.5 if is_mavra else 0, zorder=3)
            ax_bar.plot(idx, c1, marker=marker, color=col, ms=2.8, mew=0,
                        linestyle='none', zorder=4)
            running = 0.0
            xs, ys = [0.5], [0.0]
            for j, row in enumerate(rows[first_end:], start=1):
                running += row['tokens'] / 1e6
                xs.append(j)
                ys.append(running)
            c25_ends[arm] = running
            ymax = max(ymax, c1, running)
            if is_mavra:
                ax_line.plot(xs, ys, color='white', lw=2.7, zorder=4)
            ax_line.plot(xs, ys, color=col, lw=1.5 if is_mavra else 0.95,
                         marker=marker, markevery=slice(1, None), ms=2.8, mew=0,
                         label=en if lang == 'en' else zh,
                         zorder=5 if is_mavra else 3)
        for boundary in (3.5, 6.5, 9.5):
            ax_line.axvline(boundary, color=style.GRID, lw=0.45, zorder=1)
        ax_bar.set_xlim(-0.6, len(ARMS) - 0.4)
        ax_bar.set_xticks([(len(ARMS) - 1) / 2])
        ax_bar.set_xticklabels([TEXT[lang]['first']], fontsize=6.5, color=MUTED)
        ax_bar.tick_params(axis='x', length=0)
        ax_bar.tick_params(axis='y', labelsize=6.5, direction='in', length=2.2)
        ax_bar.set_ylim(0, ymax * 1.08)
        ax_bar.yaxis.set_major_locator(MaxNLocator(nbins=4, min_n_ticks=3))
        for spine in ('top', 'right'):
            ax_bar.spines[spine].set_visible(True)
            ax_line.spines[spine].set_visible(True)
        ax_line.set_xlim(0.5, 16.4)
        ax_line.set_xticks([2, 5, 8, 11])
        ax_line.set_xticklabels(TEXT[lang]['cutoffs'], fontsize=6.5)
        ax_line.tick_params(axis='x', length=0)
        ax_line.tick_params(axis='y', labelleft=False, direction='in', length=2.2)
        ax_bar.set_title(f"({'ab'[panel]}) {db}", loc='left', fontsize=8, color=INK, pad=3.5)
        ax_line.text(0.02, 0.94, TEXT[lang]['later'], transform=ax_line.transAxes,
                     ha='left', va='top', fontsize=6.5, color=MUTED)
        y0 = c25_ends['mavra']
        for bx, ref_arm, col_key in ((12.65, 'tecod', 'mTeCoD'), (14.45, 'none', 'mNoShare')):
            y1 = c25_ends[ref_arm]
            pct = round(100 * (1 - y0 / y1))
            bc = style.PAPER_COLORS[col_key]
            ax_line.plot([bx - 0.22, bx, bx, bx - 0.22], [y0, y0, y1, y1], color=bc, lw=0.6)
            ax_line.text(bx + 0.18, (y0 + y1) / 2, f'\u2212{pct}%',
                         va='center', ha='left', fontsize=6.5, color=MUTED)
    fig.text(0.015, 0.431, TEXT[lang]['y'], rotation=90, va='center', fontsize=7, color=INK)
    handles, labels = ax_line.get_legend_handles_labels()
    legend = fig.legend(handles, labels, loc='upper center', ncol=3, bbox_to_anchor=(0.53, 0.99),
                        fontsize=7, handlelength=1.8, columnspacing=0.8, labelspacing=0.35)
    for label in legend.get_texts():
        if label.get_text().startswith('MAVRA'):
            label.set_weight('bold')
    out = Path(out_dir or style.OUT) / (f'{NAME}.pdf' if lang == 'en' else f'{NAME}-zh.pdf')
    mplstyle.save(fig, out)
    print(out)


if __name__ == '__main__':
    for lang in ('en', 'zh'):
        draw(lang, *(sys.argv[1:3]))
