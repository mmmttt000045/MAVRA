"""Accurate lookup (Section IV-C), single column: decide before, verify after.

Top: the equivalence graph, written whenever a verified computation is at hand
(after a miss, after an audit, at publication). Three definitions on
store_sales, drawn by the three fields that matter here (measure e, filter
phi, time binding tau): Electronics revenue (ER), its key-range revision
(ER r1), and Electronics revenue including tax (ET). ER and ER r1 are joined
by an equivalence edge whose premise is a data condition (rule R3: date keys
contiguous by month); ER and ET by a difference edge labelled with the one
field in which they differ. Below, the proven phrasings: the masked question
of the publishing session, a second wording proven equivalent after a miss,
and ET's own wording, which together with the difference edge is a contrast.

Bottom: the decision for a new request. Each constraint of the request must
be explained by a proven phrasing, a parameter, a supported derivation, or a
contrast; what is left is residue. Four requests show the four outcomes: a
proven hit, a hit on the neighbour through a contrast, a partial hit with
residue, and two surviving candidates settled by running both (equal values
are returned, different ones become one question on delta). Last row: a
tentative hit is served without audit only while the upper confidence bound
U_g of its stratum's false-hit rate is at most alpha.

Nothing here is measured: the figure shows the mechanism of Section IV-C on
the running example (definitions and columns as in Figs. 2-4). The bars of
the audit row are illustrative positions, not data.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import INK, MUTED, RED, RULE, WHITE  # noqa: E402
from smallparts import (BLUE, BLUE_PALE, BLUE_TXT, CODE_T, EXEC_C, HEAD_T, KEYC, LEARN, LEARN_PALE,  # noqa: E402
                        MAINT_C, RED_PALE, SMALL, baseline, db_table, key_icon, mark, step, structure)

NAME = 'lookup'
W, H = style.COLUMN, 45.6

# Colour of each way a constraint is explained.
C_PHRASE, C_PARAM, C_DERIV, C_CONTRAST, C_RES = BLUE_TXT, LEARN, EXEC_C, KEYC, RED
SAME = '='
# (name key, e, phi, tau, highlighted field)
DEFS = (('er1', SAME, SAME, 'key range', 2),
        ('er', '`ss_net_paid`', "`i_category='Electronics'`", '`date_dim` join', None),
        ('et', '`ss_net_paid_inc_tax`', SAME, SAME, 0))

LABELS = {
    'en': {
        'graph': (('Equivalence graph', 'bold'),), 'graph_note': 'written after misses, audits, publication',
        'er1': '`ER` r1', 'er': '`ER` electronics revenue', 'et': '`ET` incl. tax',
        'tau': {'key range': 'key range', '`date_dim` join': '`date_dim` join'},
        'premise': 'R3 if date keys contiguous', 'delta': r'$\delta=\{e\}$',
        'phi_er': (('“electronics revenue in $\\langle p\\rangle$”', C_PHRASE),),
        'phi_er2': (('“electronics turnover in $\\langle p\\rangle$”', C_PHRASE),),
        'after_miss': 'proven after a miss',
        'phi_et': (('“electronics revenue ', C_PHRASE), ('incl. tax', C_CONTRAST), (' in $\\langle p\\rangle$”', C_PHRASE)),
        'contrast': 'contrast',
        'decide': (('Lookup: every constraint of a request must be explained', 'bold'),),
        'legend': (('phrasing', C_PHRASE), ('parameter', C_PARAM), ('derivation', C_DERIV), ('contrast', C_CONTRAST),
                   ('residue', C_RES)),
        'rows': (
            ((('highest month of ', C_DERIV), ('electronics turnover', C_PHRASE), (' in 2002', C_PARAM)),
             (('hit `ER`', BLUE_TXT),), True),
            ((('electronics revenue ', C_PHRASE), ('incl. tax', C_CONTRAST), (' in Jan.', C_PARAM)),
             (('hit `ET`, not `ER`', BLUE_TXT),), True),
            ((('electronics revenue ', C_PHRASE), ('net of returns', C_RES), (' in Jan.', C_PARAM)),
             (('partial: `ER` + residue', INK),), None),
            ((('electronics sales', MUTED), (' in Jan.', C_PARAM)),
             (('run `ER`, `ET`: equal, return; else ask $\\delta$', INK),), None),
        ),
        'audit': 'tentative hit of stratum $g$', 'serve': 'serve', 'aud': 'audit: explore, label',
    },
    'zh': {
        'graph': (('等价图', 'bold'),), 'graph_note': '在未命中、审计与发布之后写入',
        'er1': '`ER` r1', 'er': '`ER` 电子品类营业额', 'et': '`ET` 含税',
        'tau': {'key range': '键范围', '`date_dim` join': '连接 `date_dim`'},
        'premise': 'R3，前提：日期键连续', 'delta': r'$\delta=\{e\}$',
        'phi_er': (('“$\\langle p\\rangle$ 的电子品类营业额”', C_PHRASE),),
        'phi_er2': (('“$\\langle p\\rangle$ 的电子品类流水”', C_PHRASE),),
        'after_miss': '未命中后证明',
        'phi_et': (('“$\\langle p\\rangle$ 的', C_PHRASE), ('含税', C_CONTRAST), ('电子品类营业额”', C_PHRASE)),
        'contrast': '对照',
        'decide': (('查找：请求的每个约束都必须被解释', 'bold'),),
        'legend': (('说法', C_PHRASE), ('参数', C_PARAM), ('派生', C_DERIV), ('对照', C_CONTRAST), ('残余', C_RES)),
        'rows': (
            ((('2002 年', C_PARAM), ('电子品类流水', C_PHRASE), ('最高的月份', C_DERIV)),
             (('命中 `ER`', BLUE_TXT),), True),
            ((('1 月', C_PARAM), ('含税', C_CONTRAST), ('电子品类营业额', C_PHRASE)),
             (('命中 `ET`，而非 `ER`', BLUE_TXT),), True),
            ((('1 月', C_PARAM), ('扣除退货后的', C_RES), ('电子品类营业额', C_PHRASE)),
             (('部分命中：`ER` 加残余', INK),), None),
            ((('1 月', C_PARAM), ('电子品类销售', MUTED)),
             (('执行 `ER`、`ET`：相等则返回，否则问 $\\delta$', INK),), None),
        ),
        'audit': '层 $g$ 的试探命中', 'serve': '提供', 'aud': '审计：探索并标注',
    },
}


def pieces(s, x, yc, items, size, underline=()):
    """(text, colour) pieces on one line; pieces whose colour is in `underline` get a tinted box. Returns end x."""
    for label, color in items:
        w = measure(label, size)
        boxed = color in underline
        if boxed:
            x += .75
            tint = {C_CONTRAST: '#F6ECD9', C_RES: RED_PALE}[color]
            s.rect(x - .4, yc - 1.15, w + .8, 2.3, tint, color, .12, r=.4)
        s.text(x, baseline(yc, size), label, size, color)
        x += w + (.75 if boxed else 0)
    return x


def draw(s, lang):
    L = LABELS[lang]
    text = s.text
    x0, x1 = 1.0, 83.6
    band = 2.9

    # ---- The equivalence graph: definitions by the fields that matter, an equivalence and a difference edge.
    ay = 1.0
    head, row = 2.5, 2.25
    cards_y = ay + band + 1.1
    card_h = head + 3 * row
    ah = band + 1.1 + card_h + 3.0 + 2 * 2.6 + .9
    structure(s, x0, ay, x1 - x0, ah, band, L['graph'], L['graph_note'])
    geom = {'er1': (x0 + 1.0, 15.4), 'er': (x0 + 22.4, 29.4), 'et': (x0 + 58.6, 23.0)}
    ys = {}
    for key, e, phi, tau, hot in DEFS:
        cx, cw = geom[key]
        ys[key] = db_table(s, cx, cards_y, cw, L[key], 3, head, row)
        for k, (sym, val) in enumerate(((r'$e$', e), (r'$\varphi$', phi), (r'$\tau$', tau))):
            yc = ys[key][k]
            if hot == k:
                s.rect(cx + .3, yc - row / 2 + .15, cw - .6, row - .3, '#F6ECD9' if key == 'et' else BLUE_PALE, None, r=.3)
            text(cx + 1.0, baseline(yc, CODE_T), sym, CODE_T, MUTED)
            val = L['tau'].get(val, val)
            if val == SAME:
                text(cx + 3.6, baseline(yc, CODE_T), '=', CODE_T, MUTED)
            else:
                color = KEYC if (key == 'et' and hot == k) else INK
                text(cx + 3.6, baseline(yc, CODE_T), val, CODE_T, color, width=cw - 4.2)
    # Equivalence edge (ER r1 -- ER) on the tau row; difference edge (ER -- ET) on the e row.
    a_end, b_start = geom['er1'][0] + geom['er1'][1], geom['er'][0]
    yt = ys['er'][2]
    mid = (a_end + b_start) / 2
    for dy in (-.28, .28):
        s.line(a_end, yt + dy, b_start, yt + dy, BLUE, .2)
    s.circle(mid, yt, 1.25, WHITE, BLUE, .2)
    text(mid, baseline(yt, 5.6), r'$\equiv$', 5.6, BLUE_TXT, align='center')
    b_end, c_start = geom['er'][0] + geom['er'][1], geom['et'][0]
    ye = ys['er'][0]
    mid2 = (b_end + c_start) / 2
    s.line(b_end, ye, c_start, ye, KEYC, .2, dash=(.7, .5))
    s.circle(mid2, ye, 1.25, WHITE, KEYC, .2)
    text(mid2, baseline(ye, 5.6), r'$\neq$', 5.6, KEYC, align='center')
    # Edge labels under the cards: the premise of the equivalence, the differing field.
    ly = cards_y + card_h + 1.5
    end = x0 + 1.0 + key_icon(s, x0 + 1.0, ly, BLUE_TXT, k=.85) + .6
    end += text(end, baseline(ly, SMALL), L['premise'], SMALL, BLUE_TXT)
    assert end < geom['er'][0] + 8.0, end
    text(mid2, baseline(ly, SMALL), L['delta'], SMALL, KEYC, align='center')
    s.line(x0, ly + 1.5, x1, ly + 1.5, RULE, .14)
    # Proven phrasings.
    py = ly + 1.5 + 1.4
    lab = text(x0 + 1.0, baseline(py, SMALL), r'$\Phi$(`ER`)', SMALL, INK) + 1.2
    end = pieces(s, x0 + 1.0 + lab, py, L['phi_er'], SMALL)
    step(s, end + 1.7, py, 2, r=1.0)
    end = pieces(s, end + 4.2, py, L['phi_er2'], SMALL)
    end += .9
    mark(s, end + .6, py, True, k=.65)
    end += 1.8 + text(end + 1.8, baseline(py, SMALL), L['after_miss'], SMALL, MUTED)
    assert end < x1 - .6, end
    py2 = py + 2.6
    text(x0 + 1.0, baseline(py2, SMALL), r'$\Phi$(`ET`)', SMALL, INK)
    end = pieces(s, x0 + 1.0 + lab, py2, L['phi_et'], SMALL, underline=(C_CONTRAST,))
    end += 1.6 + text(end + 1.6, baseline(py2, SMALL), L['contrast'], SMALL, KEYC, 'bold')
    end += .8 + text(end + .8, baseline(py2, SMALL), r'$\leftrightarrow\ e$', SMALL, KEYC)
    assert end < x1 - .6, end
    assert py2 + 1.5 < ay + ah, (py2, ay + ah)

    # ---- The decision for a new request.
    by = ay + ah + 1.4
    pitch = 2.75
    n = len(L['rows'])
    legend_h = 2.7
    bh = band + legend_h + n * pitch + .5 + 3.3
    structure(s, x0, by, x1 - x0, bh, band, L['decide'], None, LEARN_PALE, INK)
    step(s, x1 - 2.2, by + band / 2 + .05, 3, r=1.05)
    hy = by + band + legend_h / 2 + .1
    lx = x0 + 1.0
    for label, color in L['legend']:
        s.rect(lx, hy - .5, 1.6, 1.0, color, None, r=.2)
        lx += 2.1 + text(lx + 2.1, baseline(hy, HEAD_T), label, HEAD_T, MUTED) + 2.2
    assert lx < x1 - 3.0, lx
    top = by + band + legend_h
    s.line(x0, top, x1, top, RULE, .14)
    ox = x0 + 45.6                                  # outcomes column
    for i, (req, out, ok) in enumerate(L['rows']):
        yc = top + pitch * (i + .5)
        end = pieces(s, x0 + 1.0, yc, req, SMALL, underline=(C_CONTRAST, C_RES))
        assert end < ox - 3.4, (i, end)
        s.route([(ox - 3.0, yc), (ox - .9, yc)], MUTED, .18, length=.9)
        xx = ox
        if ok:
            mark(s, xx + .7, yc, True, k=.7)
            xx += 2.0
        end = pieces(s, xx, yc, out, SMALL)
        assert end < x1 - .6, (i, end)
    bot = top + n * pitch + .25
    s.line(x0, bot, x1, bot, RULE, .14)
    # Audit row: serve a tentative hit only while the stratum's upper bound is at most alpha.
    yc = bot + 1.7
    end = x0 + 1.0 + text(x0 + 1.0, baseline(yc, SMALL), L['audit'], SMALL, INK) + 1.6
    bw, a_at = 9.0, .55                             # bar width, position of alpha along it
    for u_at, label, color in ((.34, L['serve'], BLUE_TXT), (.82, L['aud'], MAINT_C)):
        s.rect(end, yc - .6, bw, 1.2, WHITE, None)
        s.rect(end + a_at * bw, yc - .6, (1 - a_at) * bw, 1.2, RED_PALE, None)
        s.rect(end, yc - .6, u_at * bw, 1.2, BLUE if u_at < a_at else '#B8B5AE', None)
        s.rect(end, yc - .6, bw, 1.2, None, style.EDGE, .12)
        s.line(end + a_at * bw, yc - .95, end + a_at * bw, yc + .95, RED, .2)
        text(end + a_at * bw, baseline(yc - 1.75, 4.6), r'$\alpha$', 4.6, RED, align='center')
        text(end + u_at * bw - .2, baseline(yc + .05, 4.4), r'$U_g$', 4.4, WHITE, align='right')
        end += bw + 1.0
        end += text(end, baseline(yc, SMALL), label, SMALL, color, 'bold') + 2.4
    assert end - 2.4 < x1 - .6, end
    assert by + bh < H - .25, (by + bh, H)
