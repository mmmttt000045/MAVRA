"""Cost for sequential agents on TPC-DS, and accuracy against cost after the restatement.

Panels (a)-(c): lines show means across runs; capped error bars show the per-agent
minimum and maximum across runs; the per-question panel keeps its logarithmic axis.
Panel (d): after the restatement, accuracy against tokens per question for every
method, including example retrieval (shared SQL without maintenance); bars span
the run range on both axes. Every plotted value is checked against gen/population.tex.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matplotlib.lines import Line2D  # noqa: E402
import mplstyle  # noqa: E402
import style  # noqa: E402

NAME = 'population'
W, H = style.COLUMN, 74.0  # single-column 2x2 grid
DATA = style.ROOT / 'exp/2026-10-12-population/population-stats.json'
METHODS = [('middle-alone', 'None', '^'), ('metric-private', 'Private', 'D'), ('metric-global-snap', 'Mavra', 'o')]
CHANGE = [('middle-alone', 'None', '^'), ('metric-private', 'Private', 'D'), ('traj-global', 'Traj', 's'),
          ('metric-global-snap', 'Mavra', 'o')]
TEXT = {
    'en': {'y': ['Tokens (M)', 'Agent time (min)', 'Tokens per question (k)', 'Accuracy (%)'],
           'x': ['Agents arrived', 'Agents arrived', 'Agent (arrival order)', 'Tokens per question (k)'],
           'panels': ['(a) Cumulative tokens', '(b) Cumulative time', '(c) Per-question tokens', '(d) After the restatement']},
    'zh': {'y': ['token（百万）', '智能体时间（分钟）', '每题 token（千）', '正确率（%）'],
           'x': ['已到来的智能体数', '已到来的智能体数', '智能体（到来顺序）', '每题 token（千）'],
           'panels': ['(a) 累计 token', '(b) 累计时间', '(c) 每题 token', '(d) 数据更正之后']},
}


def load():
    d = json.loads(DATA.read_text(encoding='utf-8'))['methods']
    pp = style.macros('population')
    out = {}
    for mode, key, _ in METHODS:
        if mode not in d:
            continue
        cells = d[mode]['cells']
        curves = []
        for c in cells:
            tok, s, per, ct, cs = [], [], [], 0.0, 0.0
            for a in c['per_agent']:
                ct += a['tok']
                cs += a['s']
                tok.append(ct / 1e6)
                s.append(cs / 60)
                per.append(a['tok'] / max(a['tasks'], 1) / 1e3)
            curves.append((tok, s, per))
        n = len(curves[0][0])
        mean_tok = [sum(c[0][i] for c in curves) / len(curves) for i in range(n)]
        mean_s = [sum(c[1][i] for c in curves) / len(curves) for i in range(n)]
        acc = d[mode]['v1']['acc']['mean'] * 100
        style.agree(f'Pp{key}TotalTokM', f'{mean_tok[-1]:.2f}', pp[f'Pp{key}TotalTokM'])
        style.agree(f'Pp{key}Acc', f'{acc:.0f}', pp[f'Pp{key}Acc'])
        mean_per = [sum(c[2][i] for c in curves) / len(curves) for i in range(n)]
        out[mode] = dict(curves=curves, tok=mean_tok, s=mean_s, per=mean_per, acc=f'{acc:.0f}')
    change = {}
    for mode, key, _ in CHANGE:
        c = d[mode]['change']
        style.agree(f'Pp{key}ChangeAcc', f"{c['acc']['mean'] * 100:.0f}", pp[f'Pp{key}ChangeAcc'])
        style.agree(f'Pp{key}ChangeTokK', f"{c['tok']['mean'] / 1e3:.1f}", pp[f'Pp{key}ChangeTokK'])
        change[mode] = {k: {x: c[k][x] * (100 if k == 'acc' else 1e-3) for x in ('mean', 'min', 'max')} for k in ('acc', 'tok')}
    out['_change'] = change
    gain = (pp['PpMavraTokSaveNone'], pp['PpMavraSpeedupNone'])
    return out, gain


def figure(lang):
    data, _ = load()
    T = TEXT[lang]
    fig = mplstyle.figure(W, H)
    axes = fig.subplots(2, 2, gridspec_kw=dict(left=.17, right=.985, top=.85, bottom=.16,
                                               wspace=.65, hspace=.88)).flatten()
    methods = [m for m in METHODS if m[0] in data]
    linestyles = {'middle-alone': '--', 'metric-private': '-.', 'traj-global': ':', 'metric-global-snap': '-'}
    handles = [
        Line2D([], [], color=mplstyle.color(mode), marker=marker, mfc='white', mew=.6,
               linestyle=linestyles[mode], label=mplstyle.name(mode, lang))
        for mode, _, marker in CHANGE
    ]
    # Two columns, read row by row: No memory, single-agent memory / example retrieval, MAVRA.
    fig.legend(handles=[handles[i] for i in (0, 2, 1, 3)], loc='upper center', bbox_to_anchor=(.52, 1.0),
               ncol=2, handlelength=1.8, columnspacing=1.2)
    n = len(data['middle-alone']['tok'])
    xs = list(range(1, n + 1))
    for k, ax in enumerate(axes[:3]):
        for mode, _, marker in methods:
            d, color = data[mode], mplstyle.color(mode)
            ys = (d['tok'], d['s'], d['per'])[k]
            lo = [min(c[k][i] for c in d['curves']) for i in range(n)]
            hi = [max(c[k][i] for c in d['curves']) for i in range(n)]
            ax.errorbar(xs, ys, yerr=[[y - low for y, low in zip(ys, lo)],
                                     [high - y for high, y in zip(hi, ys)]],
                        fmt='none', ecolor=color, elinewidth=.4, capsize=1.2,
                        capthick=.4, alpha=.7, zorder=2)
            ax.plot(xs, ys, color=color, ls=linestyles[mode], marker=marker,
                    mfc='white', mew=.6, ms=2.8,
                    markevery=sorted({0, *range(3, n, 4), n - 1}), zorder=3)
        ax.set_ylabel(T['y'][k])
        ax.set_xlabel(T['x'][k])
        if k == 2:
            ax.set_yscale('log')
            ax.set_ylim(4, 200)
            ax.set_yticks([5, 10, 20, 50, 100])
            ax.set_yticklabels(['5', '10', '20', '50', '100'])
            ax.minorticks_off()
        else:
            ax.set_ylim(bottom=0)
        ax.set_xlim(.7, n + .3)
        ax.set_xticks([1, 4, 8, 12, 16] if n == 16 else xs[::max(1, n // 4)])
        ax.yaxis.grid(True)
        panel_title(fig, ax, T['panels'][k])
    ax = axes[3]
    for mode, _, marker in CHANGE:
        c, color = data['_change'][mode], mplstyle.color(mode)
        x, y = c['tok']['mean'], c['acc']['mean']
        ax.errorbar([x], [y], xerr=[[x - c['tok']['min']], [c['tok']['max'] - x]],
                    yerr=[[y - c['acc']['min']], [c['acc']['max'] - y]], color=color, marker=marker,
                    mfc='white', mew=.7, ms=4, elinewidth=.5, capsize=1.4, capthick=.5, zorder=3)
        if mode == 'middle-alone':
            ax.annotate(f'{y:.0f}%', (x, y), xytext=(-8, 0), textcoords='offset points',
                        fontsize=6, color=color, ha='right', va='center')
        else:
            ax.annotate(f'{y:.0f}%', (x, y), xytext=(4, -1 if y < 97 else -6), textcoords='offset points',
                        fontsize=6, color=color, ha='left', va='top' if y >= 97 else 'center')
    ax.set_xscale('log')
    ax.set_xlim(5, 150)
    ax.set_xticks([5, 10, 20, 50, 100])
    ax.set_xticklabels(['5', '10', '20', '50', '100'])
    ax.minorticks_off()
    ax.set_ylim(40, 103)
    ax.set_yticks([40, 60, 80, 100])
    ax.set_ylabel(T['y'][3])
    ax.set_xlabel(T['x'][3])
    ax.grid(True)
    panel_title(fig, ax, T['panels'][3])
    return fig


def panel_title(fig, ax, text):
    """Panel title centred below the panel's x-axis label."""
    box = ax.get_position()
    fig.text((box.x0 + box.x1) / 2, box.y0 - .144, text, ha='center', va='bottom', fontsize=mplstyle.TITLE)


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
