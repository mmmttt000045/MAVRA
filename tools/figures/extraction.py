"""Checked publication and the stored layout of one revision (Sections IV-A, IV-B), single column.

Top: Publish turns Agent 1's verified session into a revision: the LLM drafts
B and I, the server derives the conditions C, the version map V_x and the
provenance E, and gates G1-G7 decide (step 2 writes the result). Middle: the
definition entry metric:Electronics revenue, rev 0, field group by field
group with the running example's stored values. Bottom: the two kinds of
shared entries it points to. The join entry is referenced by key and
revision; a condition is referenced by its signature id(c), and its outcome
lives in H under (id(c), V(dep(c))) with raw statistics, so Accept compares
the measured loss (1.03%) with this definition's own bound (1.13%).

Values: definition, filters, grain, join and time binding of the M5-L1
revision on the 1M-row retail fixture (exp/2026-10-08-lifecycle/cell-mavra.json:
metric, evidence.versions, time.loss_ratio 0.010305, join orphan_ratio 0);
10,305 of the 1,000,000 sales rows have no sale date, so 989,695 join;
bounds add the 0.1-point tolerance of Section IV-C. The verified answer
2,754,299.60 is that task's (exp/2026-10-01-workload-characterization).
Names are shown in English as in Fig. 2.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import EDGE, INK, MUTED, RULE  # noqa: E402
from smallparts import (BAND, BLUE, BLUE_PALE, BLUE_TXT, CODE_T, KEYC, LEARN, LEARN_PALE, LINE,  # noqa: E402
                        SMALL, arrow, baseline, mark, parts, sparkle, stamp, step, structure)

NAME = 'extraction'
W, H = style.COLUMN, 45.6

V_X = (('`date_dim`', stamp('1d5b', '1096', '0')), ('`item`', stamp('9662', '1000', '0')),
       ('`store_sales`', stamp('5a15', '$10^6$', '0')))

LABELS = {
    'en': {
        'flow': ('verified session', ('LLM drafts $B$, $I$',), r'derive $C$, $V_x$, $E$', 'gates G1–G7'),
        'entry': (('Definition entry ', 'bold'), ('`metric:Electronics revenue`', 'sans')),
        'entry_note': 'rev 0, valid, by Agent 1',
        'fields': ('$B$', '$I$', '$C$', '$V_x$', '$E$'),
        'B': "net paid of store sales whose item category is `Electronics`, by sale date",
        'cat': 'Electronics',
        'keys': '`KeyUnique`:',
        'unmatched': '`Unmatched`:',
        'E': ('task `M5-L1`, verified answer `2,754,299.60`, example SQL, G1–G7 passed',),
        'join': (('`join:item|store_sales`', 'sans'),), 'join_note': 'rev 0',
        'join_rows': ('`store_sales`$\\rightarrow$`item`, N:1, inner', '`on ss_item_sk = i_item_sk`',
                      'guard `KeyUnique(item.i_item_sk)`'),
        'outcome': (('Outcome entry in $H$', 'bold'),), 'out_key': r'key $(\mathrm{id}(c),V(\mathrm{dep}(c)))$',
        'out_rows': (r'$\mathrm{id}(c)$', r'$V(\mathrm{dep}(c))$', 'stats'),
        'accept': r'Accept: loss 1.03% $\leq$ 1.13%',
    },
    'zh': {
        'flow': ('经核验的会话', ('LLM 起草 $B$、$I$',), r'推导 $C$、$V_x$、$E$', '门槛 G1–G7'),
        'entry': (('定义条目 ', 'bold'), ('`metric:Electronics revenue`', 'sans')),
        'entry_note': '修订版 0，有效，智能体 1',
        'fields': ('$B$', '$I$', '$C$', '$V_x$', '$E$'),
        'B': '品类为 `Electronics` 的商品的门店销售净支付额，按销售日期归属期间',
        'cat': 'Electronics',
        'keys': '`KeyUnique`：',
        'unmatched': '`Unmatched`：',
        'E': ('源问题 `M5-L1`，核验答案 `2,754,299.60`，示例 SQL，G1–G7 通过',),
        'join': (('`join:item|store_sales`', 'sans'),), 'join_note': 'rev 0',
        'join_rows': ('`store_sales`$\\rightarrow$`item`，N:1，内连接', '`on ss_item_sk = i_item_sk`',
                      '守卫 `KeyUnique(item.i_item_sk)`'),
        'outcome': (('$H$ 中的检查结果', 'bold'),), 'out_key': r'键 $(\mathrm{id}(c),V(\mathrm{dep}(c)))$',
        'out_rows': (r'$\mathrm{id}(c)$', r'$V(\mathrm{dep}(c))$', '统计'),
        'accept': r'Accept：未匹配 1.03% $\leq$ 1.13%',
    },
}


def draw(s, lang):
    L = LABELS[lang]
    text = s.text
    x0, x1 = 1.0, 83.6
    pitch = 2.42

    # Publish (steps 1-2): session -> LLM draft -> server derivation -> gates -> write.
    fy, fh = 1.0, 3.6
    fyc = fy + fh / 2
    step(s, 2.2, fyc, 1)
    x = 4.3
    chips = L['flow']
    for k, label in enumerate(chips):
        llm = isinstance(label, tuple)
        label = label[0] if llm else label
        w = measure(label, SMALL, 'bold') + (4.4 if llm else 2.4)
        s.rect(x, fy, w, fh, LEARN_PALE, LEARN, LINE, r=fh / 2)
        tx = x + 1.2
        if llm:
            sparkle(s, x + 1.9, fyc, .95, LEARN)
            tx = x + 3.3
        text(tx, baseline(fyc, SMALL), label, SMALL, INK, 'bold')
        x += w
        arrow(s, [(x, fyc), (x + 2.2, fyc)], LEARN)
        x += 2.2
    step(s, x + 1.3, fyc, 2)
    assert x + 2.6 < x1, x

    # The definition entry, one field group per row block.
    ey, band = fy + fh + 2.0, 2.9
    rows = {'B': 1, 'I': 3, 'C': 2, 'V': 1, 'E': 1}
    eh = band + .5 + pitch * sum(rows.values()) + .5
    yb = structure(s, x0, ey, x1 - x0, eh, band, L['entry'], L['entry_note'], BLUE_PALE, INK)
    fx0, fx1, vx = x0 + .25, x0 + 6.4, x0 + 7.4          # field column; values start at vx
    y = yb + .5
    blocks = []
    for k, n in rows.items():
        blocks.append((k, y, y + n * pitch))
        y += n * pitch
    for i, (k, a, b) in enumerate(blocks):
        s.rect(fx0, a + .12, fx1 - fx0, b - a - .24, BAND, None, r=.3)
        text((fx0 + fx1) / 2, baseline((a + b) / 2, SMALL), L['fields'][i], SMALL, INK, 'bold', 'center')
        if i:
            s.line(fx0, a, x1 - .25, a, RULE, .12)

    def line(n, block, items):
        a = dict((k, a) for k, a, _ in blocks)[block]
        yc = a + pitch * (n + .5)
        end = parts(s, vx, baseline(yc, CODE_T), items, CODE_T)
        assert end < x1 - .8, (block, n, end)
        return yc, end

    line(0, 'B', [(L['B'], INK, 'sans')])
    line(0, 'I', [('`fact` ', KEYC), ('`store_sales`  ', INK), ('`measure` ', KEYC), ('`sum(ss_net_paid)`', INK)])
    line(1, 'I', [('`grain` ', KEYC), ('`(ss_item_sk, ss_ticket_number)`  ', INK), ('`time` ', KEYC),
                  ('`ss_sold_date_sk`$\\rightarrow$`date_dim`', INK)])
    y_join, _ = line(2, 'I', [('`joins` ', KEYC), ('`join:item|store_sales`@`0`  ', INK), ('`filters` ', KEYC),
                              (f"`item: i_category = '{L['cat']}'`", INK)])
    line(0, 'C', [(L['keys'] + ' ', MUTED, 'sans'), ('`store_sales.`$K$`, item.i_item_sk, date_dim.d_date_sk`', INK)])
    y_c, c_end = line(1, 'C', [(L['unmatched'] + ' ', MUTED, 'sans'), ('`store_sales`$\\rightarrow$`item` ', INK),
                               (r'$\leq$0.10%, ', INK, 'sans'), ('`store_sales`$\\rightarrow$`date_dim` ', INK),
                               (r'$\leq$1.13%', BLUE_TXT, 'bold')])
    items = []
    for name, st in V_X:
        items += [(name + ' ', INK), (st + '   ', INK)]
    line(0, 'V', items)
    line(0, 'E', [(L['E'][0], INK, 'sans')])

    # Shared entries it points to: the join entry (by key and revision), an outcome entry (by id(c) and versions).
    by = ey + eh + 3.2
    jx1 = 33.6
    bh = band + .4 + 3 * pitch + .4
    yb = structure(s, x0, by, jx1 - x0, bh, band, L['join'], L['join_note'], BLUE_PALE, INK)
    for j, label in enumerate(L['join_rows']):
        text(x0 + 1.0, baseline(yb + .4 + pitch * (j + .5), CODE_T), label, CODE_T if j == 1 else SMALL, INK,
             width=jx1 - x0 - 1.6)
    ox0 = jx1 + 1.6
    yb = structure(s, ox0, by, x1 - ox0, bh, band, L['outcome'], L['out_key'])
    lab_w = max(measure(t, SMALL) for t in L['out_rows']) + 1.4
    vals = ('`Unmatched(store_sales`$\\rightarrow$`date_dim)`',
            f"{V_X[2][1]} {V_X[0][1]}",
            '`n_left 1,000,000  n_join 989,695`')
    for j, (label, value) in enumerate(zip(L['out_rows'], vals)):
        yc = yb + .4 + pitch * (j + .5)
        text(ox0 + 1.0, baseline(yc, SMALL), label, SMALL, MUTED)
        text(ox0 + 1.0 + lab_w, baseline(yc, CODE_T), value, CODE_T, INK, width=x1 - ox0 - 2.0 - lab_w)

    # References: joins -> join entry, down the gap between the field column and the values; the coverage
    # condition -> its outcome, down the record's right margin; Accept uses this definition's own bound.
    gxj = fx1 + .5
    s.circle(gxj, y_join, .36, EDGE)
    s.route([(gxj, y_join), (gxj, by)], EDGE, LINE + .02, length=.8)
    gxc = x1 - 1.0
    s.circle(c_end + .9, y_c, .36, BLUE)
    s.route([(c_end + .9, y_c), (gxc, y_c), (gxc, by)], BLUE, LINE + .02, length=.8, radius=.5)
    aw = measure(L['accept'], SMALL, 'bold')
    ay = (ey + eh + by) / 2
    mark(s, gxc - aw - 2.4, ay, True, k=.75)
    text(gxc - 1.2, baseline(ay, SMALL), L['accept'], SMALL, BLUE_TXT, 'bold', align='right')
    assert c_end + 1.4 < gxc, c_end
    assert by + bh < H - .3, by + bh
