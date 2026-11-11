"""Checked publication: parameters, the join tree, and derived conditions (Sections IV-B, IV-C), single column.

Top: Agent 1's verified session. G3 splits its literals: the filter on a
dimension other than the time dimension, free of the question's literals,
stays in the definition as phi (a fixed predicate on item.i_category); the
filters on date_dim become the period parameter p (a slot on d_year, d_moy).
Middle: I drawn as its join tree over the tables' columns, with crow's feet
for the N:1 joins. Markers place each derived condition on what it guards:
the fact's grain key K (1), each dimension's key, which makes a join's one
side (2, 4), and the unmatched fraction of the inner and the date join (3, 5).
Below: the statistics each condition measured at publication. Key checks
need rows = keys; for an unmatched fraction the measured value becomes the
baseline b and the gauge shows the band up to the bound b + 0.1 points.
Bottom: answer reproduction, where G7 rejects a draft I without phi.
Purple tags mark where each gate acts (G1, G2 on the session's support, G5
on its SQL, G3 on I, G4 on condition 1, G6 and G7 at the bottom).

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
from style import EDGE, INK, MUTED, RED, RULE, SLATE, WHITE  # noqa: E402
from smallparts import (BLUE, BLUE_FIELD, BLUE_PALE, BLUE_TXT, CODE_T, GAUGE_BAND, HEAD_T, LEARN,  # noqa: E402
                        LEARN_PALE, LINE, RED_PALE, SMALL, arrow, baseline, card, crow, db_table, gauge, gauge_icon,
                        gate, key_icon, mark, one_bar, person, step, structure, swatch)

NAME = 'extraction'
W, H = style.COLUMN, 49.0
COL = 5.2                                  # column names in the join tree
ANSWER, DRAFT = 2754299.60, 13532799.00

LABELS = {
    'en': {
        'session': "Agent 1's verified session", 'answer': 'answer', 'cat': 'Electronics',
        'impl': 'Implementation $I$', 'inner': 'inner',
        'conds': (('Conditions ', 'bold'), (r'$C(m^r)$', 'bold'), (' measured at publication', 'bold')),
        'conds_note': r'kept in $\mathcal{H}$ at $(\mathrm{id}(c),V(\mathrm{dep}(c)))$',
        'ku': 'KeyUnique: rows = keys', 'um': r'Unmatched: loss $\leq b+0.1$ pt',
        'legend': (r'$b$ at publication', '+0.1 pt', 'fails'),
        'g6': 'session SQL', 'g7': r'Compile($I,p_0$)', 'draft': r'draft $I$ without $\varphi$',
    },
    'zh': {
        'session': '智能体 1 经核验的会话', 'answer': '答案', 'cat': 'Electronics',
        'impl': '实现 $I$', 'inner': '内连接',
        'conds': (('发布时测得的条件 ', 'bold'), (r'$C(m^r)$', 'bold')),
        'conds_note': r'存于 $\mathcal{H}$ 的 $(\mathrm{id}(c),V(\mathrm{dep}(c)))$',
        'ku': 'KeyUnique：行数 = 键数', 'um': r'Unmatched：未匹配 $\leq b+0.1$ 个百分点',
        'legend': (r'发布时的 $b$', '+0.1 个百分点', '不通过'),
        'g6': '会话 SQL', 'g7': r'Compile($I,p_0$)', 'draft': r'缺 $\varphi$ 的草稿 $I$',
    },
}

# Conditions measured at publication: (marker, table or join, statistics).
KEYS = ((1, '`store_sales.`$K$', '$10^6$'), (2, '`item.i_item_sk`', '`1,000`'),
        (4, '`date_dim.d_date_sk`', '`1,096`'))
LOSS = ((3, r'`store_sales`$\rightarrow$`item`', 0.0), (5, r'`store_sales`$\rightarrow$`date_dim`', 1.0305))


def marker(s, x, yc, i, r=.85, halo=False):
    """Condition marker i (a slate disc), the same in the join tree, the list below, and Figs. 4-5."""
    if halo:
        s.circle(x, yc, r + .22, WHITE)
    s.circle(x, yc, r, SLATE)
    s.text(x, baseline(yc, 4.6), f'{i}', 4.6, WHITE, 'bold', 'center')


def draw(s, lang):
    L = LABELS[lang]
    text = s.text
    x0, x1 = 1.0, 83.6

    # The verified session (step 1); G1, G2 check its support, G5 its SQL.
    sy, sband, lp = 1.0, 3.1, 2.4
    sh = sband + .45 + 2 * lp + .25
    card(s, x0, sy, x1 - x0, sh, sband, LEARN_PALE)
    yb = sy + .15 + sband / 2
    step(s, x0 + 1.2, yb, 1, r=1.05)
    person(s, x0 + 4.0, yb, LEARN)
    end = x0 + 5.8 + text(x0 + 5.8, baseline(yb, SMALL), L['session'], SMALL, INK, 'bold') + 1.2
    for g in ('G1', 'G2'):
        end += gate(s, end, yb, g) + .5
    aw = text(x1 - 1.0, baseline(yb, CODE_T), '`2,754,299.60`', CODE_T, INK, align='right')
    text(x1 - 2.0 - aw, baseline(yb, SMALL), L['answer'], SMALL, MUTED, align='right')
    y1 = sy + sband + .45 + lp * .75
    w1 = text(x0 + 1.0, y1, '`SELECT SUM(ss_net_paid) FROM store_sales JOIN item ... JOIN date_dim ...`', CODE_T, INK)
    gate(s, x0 + 1.0 + w1 + 1.0, y1 - .65, 'G5')
    y2 = y1 + lp
    x = x0 + 1.0 + text(x0 + 1.0, y2, '`WHERE `', CODE_T, INK)
    spans = []
    for label, tagl, fill, edge in ((f"`i_category = '{L['cat']}'`", r'$\varphi$', BLUE_PALE, BLUE),
                                    ('`d_year = 2001 AND d_moy = 1`', '$p$', LEARN_PALE, LEARN)):
        w = measure(label, CODE_T)
        s.rect(x - .3, y2 - 1.72, w + .6, 2.3, fill, edge, .14, r=.35)
        spans.append((x - .3, x + w + .3))
        text(x, y2, label, CODE_T, INK)
        x += w + .5
        x += text(x, y2 - .7, tagl, SMALL, edge, 'bold') + .4
        if tagl != '$p$':
            x += text(x, y2, '` AND `', CODE_T, INK)
    assert x < x1 - 1.0, x
    box_bottom = y2 + .58

    # I as a join tree over the tables' columns; G3 checks its tables, columns, joins and the phi/p split.
    by = sy + sh + 1.6
    th = 13.4
    s.rect(x0, by, x1 - x0, th, BLUE_FIELD, EDGE, LINE, r=.5)
    rh = 2.25
    ty = by + 1.0
    item, fact, date = (2.0, 18.6), (27.2, 48.8), (58.4, x1 - 1.0)
    ys_f = db_table(s, fact[0], ty, fact[1] - fact[0], '`store_sales`', 4, note='$F$')
    ys_i = db_table(s, item[0], ty + rh, item[1] - item[0], '`item`', 2)
    ys_d = db_table(s, date[0], ty, date[1] - date[0], '`date_dim`', 3)
    cx = fact[0] + .6
    for k, (name, key) in enumerate((('`ss_sold_date_sk`', False), ('`ss_item_sk`', True),
                                     ('`ss_ticket_number`', True), ('`ss_net_paid`', False))):
        if key:
            key_icon(s, cx, ys_f[k], INK)
        w = text(cx + 2.6, baseline(ys_f[k], COL), name, COL, INK, width=fact[1] - cx - 3.0)
        if k == 3:
            text(cx + 2.6 + w + .9, baseline(ys_f[k], SMALL), r'$\Sigma$', SMALL, BLUE_TXT)
    # item: its key (one side of the inner join) and the fixed filter phi.
    key_icon(s, item[0] + .6, ys_i[0], INK)
    text(item[0] + 3.2, baseline(ys_i[0], COL), '`i_item_sk`', COL, INK)
    w = text(item[0] + 3.2, baseline(ys_i[1], COL), '`i_category`', COL, INK)
    px = item[0] + 3.2 + w + .7
    s.rect(px, ys_i[1] - .95, 2.3, 1.9, BLUE, None, r=.5)
    text(px + 1.15, baseline(ys_i[1], SMALL) - .1, r'$\varphi$', SMALL, WHITE, align='center')
    assert px + 2.3 < item[1] - .3, px
    # date_dim: its key (the date mapping) and the parameter slot p on year and month.
    key_icon(s, date[0] + .6, ys_d[0], INK)
    text(date[0] + 3.2, baseline(ys_d[0], COL), '`d_date_sk`', COL, INK)
    for k, name in ((1, '`d_year`'), (2, '`d_moy`')):
        text(date[0] + 3.2, baseline(ys_d[k], COL), name, COL, INK)
    sx = date[0] + 3.2 + measure('`d_year`', COL) + 1.0
    s.rect(sx, ys_d[1] - .95, 2.6, ys_d[2] - ys_d[1] + 1.9, LEARN_PALE, LEARN, .16, r=.5, dash=(.55, .35))
    text(sx + 1.3, baseline((ys_d[1] + ys_d[2]) / 2, SMALL) - .15, '$p$', SMALL, LEARN, 'bold', 'center')
    # Joins: crow's foot at the fact (N), a bar at the dimension (1); the unmatched fraction sits on the edge.
    for (a, b), yc, lab, i in (((item[1], fact[0]), ys_f[1], L['inner'], 3), ((fact[1], date[0]), ys_f[0], r'$\tau$', 5)):
        s.line(a, yc, b, yc, EDGE, .2)
        left_is_fact = a == fact[1]
        crow(s, a if left_is_fact else b, yc, 1 if left_is_fact else -1, EDGE, .18)
        one_bar(s, b if left_is_fact else a, yc, -1 if left_is_fact else 1, EDGE, .18)
        w = text((a + b) / 2, yc - 1.25, lab, COL, MUTED, 'sans', 'center')
        assert w < b - a - 1.2, (lab, w)
        marker(s, (a + b) / 2, yc, i, r=.8, halo=True)
    marker(s, fact[1] - 1.35, (ys_f[1] + ys_f[2]) / 2, 1, r=.8)        # the grain key K: both key columns
    marker(s, item[1] - 1.25, ys_i[0], 2, r=.8)
    marker(s, date[1] - 1.25, ys_d[0], 4, r=.8)
    # The session's literals go where G3 puts them: phi into item, the period into the slot p.
    for xa, (lo, hi), target, color in ((10.6, spans[0], ty + rh, BLUE), (61.6, spans[1], ty, LEARN)):
        assert lo + .6 < xa < hi - .6, (xa, lo, hi)
        arrow(s, [(xa, box_bottom), (xa, target)], color, .2)
    lab_y = by + th - .95
    w = text(x0 + 1.0, lab_y, L['impl'], SMALL, BLUE_TXT, 'bold')
    gate(s, x0 + 1.0 + w + 1.0, lab_y - .68, 'G3')

    # The derived conditions with their statistics at publication (step 2), grouped by acceptance rule.
    cy = by + th + 1.6
    band, hdr, cp = 2.9, 2.45, 2.45
    ch = band + .3 + hdr + 3 * cp + .3
    yb = structure(s, x0, cy, x1 - x0, ch, band, L['conds'], L['conds_note'], BLUE_PALE, INK, inset=2.4)
    step(s, x0 + 1.4, cy + band / 2 + .05, 2, r=1.0)
    colw = (x1 - x0) / 2
    xr = x0 + colw
    s.line(xr, yb + .4, xr, cy + ch - .4, RULE, .12)
    hy = yb + .3 + hdr / 2
    w = key_icon(s, x0 + 1.0, hy, MUTED)
    text(x0 + 1.0 + w + .8, baseline(hy, HEAD_T), L['ku'], HEAD_T, MUTED)
    w = gauge_icon(s, xr + 1.0, hy)
    text(xr + 1.0 + w + .8, baseline(hy, HEAD_T), L['um'], HEAD_T, MUTED, width=colw - w - 2.6)
    for k, (i, where, n) in enumerate(KEYS):
        yc = yb + .3 + hdr + cp * (k + .5)
        marker(s, x0 + 1.7, yc, i, r=.82)
        text(x0 + 3.1, baseline(yc, CODE_T), where, CODE_T, INK)
        nx = x0 + 22.0
        nx += text(nx, baseline(yc, CODE_T), n, CODE_T, INK)
        nx += text(nx, baseline(yc, SMALL), ' = ', SMALL, BLUE_TXT, 'bold')
        nx += text(nx, baseline(yc, CODE_T), n, CODE_T, INK)
        if i == 1:
            nx += 1.0 + gate(s, nx + 1.0, yc, 'G4')
        assert nx < xr - .5, nx
    gx, gw, vmax = xr + 24.6, 9.0, 1.5
    for k, (i, where, loss) in enumerate(LOSS):
        yc = yb + .3 + hdr + cp * (k + .5)
        marker(s, xr + 1.7, yc, i, r=.82)
        w = text(xr + 3.1, baseline(yc, CODE_T), where, CODE_T, INK)
        assert xr + 3.1 + w < gx - .4, w
        gauge(s, gx, yc, gw, loss, .1, vmax)
        end = gx + gw + .8 + text(gx + gw + .8, baseline(yc, CODE_T), f'`{loss:.2f}%`', CODE_T, INK)
        assert end < x1 - .5, end
    # Legend of the gauge, in the free third row.
    yc = yb + .3 + hdr + cp * 2.5
    lx = xr + 3.1
    for color, label in zip((BLUE, GAUGE_BAND, RED_PALE), L['legend']):
        lx += swatch(s, lx, yc, color, edge=EDGE if color == RED_PALE else None) + .6
        lx += text(lx, baseline(yc, HEAD_T), label, HEAD_T, MUTED) + 1.6
    assert lx < x1, lx

    # Answer reproduction: the session SQL (G6) and Compile(I, p0) (G7) give the verified answer; a draft without phi
    # sums every category and G7 rejects it.
    dy = cy + ch + 1.3
    ax, scale = x0 + 22.0, 42.0 / DRAFT
    pitch = 2.45
    rows = (('G6', L['g6'], ANSWER, True), ('G7', L['g7'], ANSWER, True), (None, L['draft'], DRAFT, False))
    for k, (g, label, v, ok) in enumerate(rows):
        yc = dy + 1.15 + k * pitch
        if g:
            gate(s, x0 + .4, yc, g)
        text(x0 + 5.2, baseline(yc, SMALL), label, SMALL, INK if ok else RED, width=ax - x0 - 5.8)
        s.rect(ax, yc - .62, v * scale, 1.24, BLUE if ok else RED, None)
        vx = ax + v * scale + .8
        vx += text(vx, baseline(yc, CODE_T), f'`{v:,.2f}`', CODE_T, BLUE_TXT if ok else RED)
        mark(s, vx + 1.1, yc, ok, k=.72)
        assert vx + 2.0 < x1, vx
    s.line(ax, dy + .1, ax, dy + 2 * pitch + 2.2, EDGE, .14)
    assert dy + 2 * pitch + 2.3 < H - .1, dy + 2 * pitch + 2.3
