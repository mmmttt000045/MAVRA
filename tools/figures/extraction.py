"""Checked publication: parameters, the join tree, and derived conditions (Sections IV-B, IV-C), single column.

Top: Agent 1's verified session. Its literals are split by G3: a filter on a
dimension other than the time dimension, free of the question's literals,
stays in the definition as phi; filters on date_dim and literals of the
question become the period parameter p.
Middle: I drawn as its join tree, rooted at the fact table, with the
conditions derived from each node and edge: the fact's grain key (c1); per
edge the one-side key (c2, c4: join cardinality and date mapping) and, for an
inner or date join, the unmatched fraction (c3, c5).
Then each condition's query statistics at publication, which become its
baseline b (Unmatched accepts loss <= b + 0.1 points), and the gates.

Values: the fixture of src/metricbench.rs at 1M sales rows (1,000,000 unique
(item, ticket) pairs; every item key matches; 10,305 rows of tickets
divisible by 97 have no sale date), so b = 0.00% and 1.03%, as recorded for
M5-L1 in exp/2026-10-08-lifecycle/cell-mavra.json (orphan_ratio 0,
time.loss_ratio 0.010305). The verified answer is that task's; the rejected
draft's 13,532,799.00 is from exp/2026-10-31-diverse-scenarios/case-evidence.json
(M5-L1, G7). Names in English as in Fig. 2.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import EDGE, FACE, INK, MUTED, RED, RULE, SLATE, WHITE  # noqa: E402
from smallparts import (BLUE, BLUE_PALE, BLUE_TXT, CODE_T, LEARN, LEARN_PALE, SMALL,  # noqa: E402
                        arrow, baseline, box, card, mark, parts, person, step, structure)

NAME = 'extraction'
W, H = style.COLUMN, 50.8
NOTE = 5.2                                 # labels on the join tree
R = r'$\rightarrow$'

LABELS = {
    'en': {
        'session': "Agent 1's verified session", 'answer': 'answer', 'cat': 'Electronics',
        'split': r"G3 keeps $\varphi$ in $I$; filters on `date_dim` and the question's literals become $p$",
        'tree': (('Implementation ', 'bold'), ('$I$', 'bold'), (' as a join tree', 'bold')),
        'tree_note': r'$c_i$: derived conditions',
        'edge1': 'N:1, inner', 'edge2': r'N:1, $\tau$',
        'conds': (('Conditions ', 'bold'), (r'$C(m^r)$', 'bold'), (' measured at publication', 'bold')),
        'conds_note': r'kept in $\mathcal{H}$ at $(\mathrm{id}(c),V(\mathrm{dep}(c)))$',
        'fam': ('grain', 'join cardinality', 'join completeness', 'date mapping', 'date coverage'),
        'accept': ('accept', r'KeyUnique: rows = keys;', r'Unmatched: loss $\leq b+0.1$ pt'),
        'stats': ('`1,000,000` rows, `1,000,000` keys', '`1,000` rows, `1,000` keys', r'`0` of $10^6$: $b=$`0.00%`',
                  '`1,096` rows, `1,096` keys', r'`10,305` of $10^6$: $b=$`1.03%`'),
        'gates': r'G1 basis $\cdot$ G2 chain $\cdot$ G3 verified joins, $\varphi$ vs. $p$, baselines $b$ $\cdot$ G4 = $c_1$ $\cdot$ G5 read-only',
        'g67': r'G6 session SQL, G7 Compile($I,p_0$) $\rightarrow$',
        'draft': r'draft without $\varphi$ $\rightarrow$',
    },
    'zh': {
        'session': '智能体 1 经核验的会话', 'answer': '答案', 'cat': 'Electronics',
        'split': r'G3 把 $\varphi$ 留在 $I$ 中；`date_dim` 上的过滤与题目字面量成为参数 $p$',
        'tree': (('实现 ', 'bold'), ('$I$', 'bold'), (' 的连接树', 'bold')),
        'tree_note': r'$c_i$：派生的数据条件',
        'edge1': 'N:1，内连接', 'edge2': r'N:1，$\tau$',
        'conds': (('发布时测得的条件 ', 'bold'), (r'$C(m^r)$', 'bold')),
        'conds_note': r'存于 $\mathcal{H}$ 的 $(\mathrm{id}(c),V(\mathrm{dep}(c)))$',
        'fam': ('粒度', '连接基数', '连接完整性', '日期映射', '日期覆盖'),
        'accept': ('判定', r'KeyUnique：行数 = 键数；', r'Unmatched：未匹配 $\leq b+0.1$ 个百分点'),
        'stats': ('`1,000,000` 行，`1,000,000` 个键', '`1,000` 行，`1,000` 个键', r'$10^6$ 中 `0` 行：$b=$`0.00%`',
                  '`1,096` 行，`1,096` 个键', r'$10^6$ 中 `10,305` 行：$b=$`1.03%`'),
        'gates': r'G1 依据 $\cdot$ G2 计算链 $\cdot$ G3 已验证连接、$\varphi$ 与 $p$、基线 $b$ $\cdot$ G4 = $c_1$ $\cdot$ G5 只读',
        'g67': r'G6 会话 SQL、G7 Compile($I,p_0$) $\rightarrow$',
        'draft': r'缺 $\varphi$ 的草稿 $\rightarrow$',
    },
}

# Derived conditions c1-c5 (their statistics at publication are in LABELS['stats']).
CONDS = ('`KeyUnique(store_sales.`$K$`)`', '`KeyUnique(item.i_item_sk)`', f'`Unmatched(store_sales`{R}`item)`',
         '`KeyUnique(date_dim.d_date_sk)`', f'`Unmatched(store_sales`{R}`date_dim)`')


def marker(s, x, yc, i, r=.95):
    """Condition marker c_i, used on the join tree and in the list."""
    s.circle(x, yc, r, SLATE)
    s.text(x, baseline(yc, 4.6), f'{i}', 4.6, WHITE, 'bold', 'center')


def draw(s, lang):
    L = LABELS[lang]
    text = s.text
    x0, x1 = 1.0, 83.6
    band = 2.9

    # The verified session; G3 splits its literals into the definition filter and the period parameter.
    sy, sband, lp = 1.0, 3.1, 2.4
    sh = sband + .45 + 3 * lp + .2
    card(s, x0, sy, x1 - x0, sh, sband, LEARN_PALE)
    yb = sy + .15 + sband / 2
    step(s, x0 + 1.2, yb, 1, r=1.05)
    person(s, x0 + 4.0, yb, LEARN)
    text(x0 + 5.8, baseline(yb, SMALL), L['session'], SMALL, INK, 'bold')
    aw = text(x1 - 1.0, baseline(yb, CODE_T), '`2,754,299.60`', CODE_T, INK, align='right')
    text(x1 - 2.0 - aw, baseline(yb, SMALL), L['answer'], SMALL, MUTED, align='right')
    y1 = sy + sband + .45 + lp * .75
    text(x0 + 1.0, y1, '`SELECT SUM(ss_net_paid) FROM store_sales JOIN item ... JOIN date_dim ...`',
         CODE_T, INK, width=x1 - x0 - 2.0)
    y2 = y1 + lp
    x = x0 + 1.0 + text(x0 + 1.0, y2, '`WHERE `', CODE_T, INK)
    for label, tagl, fill, edge in ((f"`i_category = '{L['cat']}'`", r'$\varphi$', BLUE_PALE, BLUE),
                                    ('`d_year = 2001 AND d_moy = 1`', '$p$', LEARN_PALE, LEARN)):
        w = measure(label, CODE_T)
        s.rect(x - .3, y2 - 1.72, w + .6, 2.3, fill, edge, .14, r=.35)
        text(x, y2, label, CODE_T, INK)
        x += w + .5
        x += text(x, y2 - .7, tagl, SMALL, edge, 'bold') + .4
        if tagl != '$p$':
            x += text(x, y2, '` AND `', CODE_T, INK)
    assert x < x1 - 1.0, x
    text(x0 + 1.0, y2 + lp, L['split'], SMALL, MUTED, width=x1 - x0 - 2.0)

    # I as a join tree rooted at the fact table, with the conditions each node and edge yields.
    ty = sy + sh + 1.6
    th = band + 9.0
    yb = structure(s, x0, ty, x1 - x0, th, band, L['tree'], L['tree_note'], BLUE_PALE, INK)
    ny, nh = yb + 1.0, 5.0                        # node boxes
    item = (x0 + 1.0, 14.6)
    fact = (28.4, 55.6)
    date = (71.0, x1 - 1.0)
    for (a, b), name, second in ((item, '`item`', '`i_item_sk`'), (fact, '`store_sales` ($F$)', 'SUM(`ss_net_paid`)'),
                                 (date, '`date_dim`', '`d_date_sk`')):
        box(s, a, ny, b - a, nh, EDGE, FACE)
        text(a + .8, ny + 2.05, name, CODE_T, INK, width=b - a - 2.6)
        text(a + .8, ny + 4.25, second, CODE_T, MUTED if a != fact[0] else INK, width=b - a - 1.6)
    yc = ny + nh / 2
    arrow(s, [(fact[0], yc), (item[1], yc)], EDGE)
    arrow(s, [(fact[1], yc), (date[0], yc)], EDGE)
    for (a, b), key, lab in (((item[1], fact[0]), '`ss_item_sk`', L['edge1']),
                             ((fact[1], date[0]), '`ss_sold_date_sk`', L['edge2'])):
        w = text((a + b) / 2, yc - 1.15, key, NOTE, INK, 'sans', 'center')
        assert w < b - a - .4, (key, w, b - a)
        w = text((a + b) / 2, yc + 2.15, lab, NOTE, MUTED, 'sans', 'center')
        assert w < b - a - .4, (lab, w, b - a)
    # Under the boxes: phi on item, the grain key K on the fact, the parameter p on the date dimension.
    ay = ny + nh + 2.15
    parts(s, item[0], ay, [(r'$\varphi$ ', BLUE, 'bold'), (f"`i_category='{L['cat']}'`", INK)], NOTE)
    parts(s, fact[0] + .3, ay, [('$K$ ', INK), ('`(ss_item_sk,ss_ticket_number)`', INK)], NOTE)
    end = parts(s, date[0] - 2.0, ay, [('$p$ ', LEARN, 'bold'), ('`d_year`, `d_moy`', INK)], NOTE)
    assert end < x1 - .5, end
    # Markers: grain on the fact, one-side keys on the dimensions, unmatched fractions on the edges.
    marker(s, fact[1] - 1.2, ny + 1.4, 1)
    marker(s, item[1] - 1.2, ny + 1.4, 2)
    marker(s, date[1] - 1.2, ny + 1.4, 4)
    for xm, i in (((item[1] + fact[0]) / 2, 3), ((fact[1] + date[0]) / 2, 5)):
        s.circle(xm, yc, 1.0, WHITE)
        marker(s, xm, yc, i, r=.8)

    # The derived conditions with their statistics at publication (baselines b), two per row.
    cy = ty + th + 1.6
    cp = 4.75
    ch = band + .3 + 3 * cp + .2
    yb = structure(s, x0, cy, x1 - x0, ch, band, L['conds'], L['conds_note'], BLUE_PALE, INK, inset=2.4)
    step(s, x0 + 1.4, cy + band / 2 + .05, 2, r=1.0)
    colw = (x1 - x0) / 2
    s.line(x0 + colw, yb + .4, x0 + colw, cy + ch - .4, RULE, .12)
    for i, (cid, stat) in enumerate(zip(CONDS, L['stats'])):
        col, row = i % 2, i // 2
        cx = x0 + col * colw
        top = yb + .3 + row * cp
        marker(s, cx + 1.6, top + 1.35, i + 1, r=.85)
        text(cx + 3.0, baseline(top + 1.35, CODE_T), cid, CODE_T, INK, width=colw - 3.6)
        end = text(cx + 3.0, baseline(top + 3.55, SMALL), L['fam'][i] + ': ', SMALL, MUTED)
        text(cx + 3.0 + end, baseline(top + 3.55, CODE_T), stat, CODE_T, INK, width=colw - 3.6 - end)
    # The free sixth cell: the acceptance rules.
    ax, at = x0 + colw + 3.0, yb + .3 + 2 * cp
    text(ax, baseline(at + 1.35, SMALL), L['accept'][0], SMALL, INK, 'bold')
    text(ax + measure(L['accept'][0], SMALL, 'bold') + 1.2, baseline(at + 1.35, SMALL), L['accept'][1], SMALL, INK,
         width=colw - 4.0 - measure(L['accept'][0], SMALL, 'bold'))
    text(ax, baseline(at + 3.55, SMALL), L['accept'][2], SMALL, INK, width=colw - 3.6)

    # Gates: what each checks, and the answer-reproduction pair (G6, G7) with the draft G7 rejects.
    gy = cy + ch + 2.0
    text(x0 + .2, baseline(gy, SMALL), L['gates'], SMALL, INK, width=x1 - x0)
    y2 = gy + 2.5
    end = x0 + .2 + text(x0 + .2, baseline(y2, SMALL), L['g67'] + ' ', SMALL, INK)
    end += text(end, baseline(y2, CODE_T), '`2,754,299.60`', CODE_T, BLUE_TXT)
    mark(s, end + 1.2, y2, True, k=.75)
    end += 2.6
    end += text(end, baseline(y2, SMALL), L['draft'] + ' ', SMALL, RED)
    end += text(end, baseline(y2, CODE_T), '`13,532,799.00`', CODE_T, RED)
    mark(s, end + 1.1, y2, False, k=.7)
    assert end + 2.2 < x1, end
    assert y2 + 1.2 < H - .2, y2
