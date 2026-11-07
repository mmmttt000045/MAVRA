"""Stored check outcomes after a write (Section IV-D), single column.

What the shared store holds after the item-history load of Fig. 2: check
outcomes keyed by the check and the versions of the tables it reads, and the
definitions that use them. Three definitions use the one date_dim outcome,
which the load does not touch; Electronics revenue also uses the item key
check, whose key changes with item's version, so that check runs once at item
version 1 and fails (key 17 repeats); the item version 0 outcome stays behind.

Values follow Fig. 2 and the TPC-DS fixture. Which definitions use which
outcome is schematic, as in Fig. 2 (three definitions share the date_dim key
check); Store revenue and spend_90d read no item table.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import EDGE, INK, MUTED, RED, RULE, WHITE  # noqa: E402
from smallparts import (BLUE, BLUE_PALE, BLUE_TXT, BODY, CODE, LINE, RED_PALE, SMALL,  # noqa: E402
                        baseline, box, parts, step)

NAME = 'maintenance'
W, H = style.COLUMN, 26.2

LABELS = {
    'en': {
        'event': (('ETL job loads item history: ', 'bold'), ('`item`', 'sans'), (r' version 0 $\rightarrow$ 1', 'sans')),
        'defs_head': 'Definitions', 'store_head': 'Shared check outcomes', 'key': 'key: check + table version',
        'cols': ('check', 'table version', 'result'),
        'defs': ('Store revenue', '`spend_90d`', 'Electronics revenue'),
        'checks': ('date key unique', 'item key unique', 'item key unique'),
        'results': ('pass, reused by 3', 'pass (old version)', 'fail, run once'),
    },
    'zh': {
        'event': (('ETL 作业载入 item 历史：', 'bold'), ('`item`', 'sans'), (r' 版本 0 $\rightarrow$ 1', 'sans')),
        'defs_head': '定义', 'store_head': '共享的检查结果', 'key': '键：检查 + 表版本',
        'cols': ('检查', '表版本', '结果'),
        'defs': ('门店营业额', '`spend_90d`', '电子品类营业额'),
        'checks': ('日期键唯一', 'item 键唯一', 'item 键唯一'),
        'results': ('通过，三个定义复用', '通过（旧版本）', '失败，只跑一次'),
    },
}


def draw(s, lang):
    L = LABELS[lang]
    text = s.text

    # Step 5: the write that changes item's version.
    step(s, 2.4, 2.6, 5)
    parts(s, 4.4, baseline(2.6, BODY), [(t, INK, st) for t, st in L['event']], BODY)

    # The shared store: a blue title band (as in Fig. 2), column heads, three outcome rows.
    tx0, tx1, ty0, band = 31.0, 83.6, 5.6, 3.1
    col = (tx0 + .9, tx0 + 17.6, tx0 + 30.4)
    pitch, top = 4.0, ty0 + band + 3.4
    rows_y = [top + pitch * i + pitch / 2 for i in range(3)]
    bottom = top + 3 * pitch + .3
    s.rect(tx0, ty0, tx1 - tx0, bottom - ty0, WHITE, EDGE, LINE, r=.5)
    s.rect(tx0, ty0, tx1 - tx0, band, BLUE, None, r=.5)
    s.rect(tx0, ty0 + band / 2, tx1 - tx0, band / 2, BLUE, None)
    hb = baseline(ty0 + band / 2, SMALL)
    tw = text(tx0 + .9, hb, L['store_head'], SMALL, WHITE, 'bold')
    text(tx1 - .9, hb, L['key'], SMALL, WHITE, align='right', width=tx1 - tx0 - tw - 3.0)
    for c, label in zip(col, L['cols']):
        text(c, top - 1.0, label, SMALL, MUTED)
    s.line(tx0, top, tx1, top, RULE, .14)

    versions = ('`date_dim 0`', '`item 0`', '`item 1`')
    for i, yc in enumerate(rows_y):
        y0 = yc - pitch / 2
        if i == 0:
            s.rect(tx0 + .3, y0 + .3, tx1 - tx0 - .6, pitch - .6, BLUE_PALE, None, r=.4)
        elif i == 2:
            s.rect(tx0 + .3, y0 + .3, tx1 - tx0 - .6, pitch - .6, RED_PALE, RED, LINE, r=.4, dash=(.7, .45))
        ink = MUTED if i == 1 else INK
        text(col[0], baseline(yc, BODY), L['checks'][i], BODY, ink, width=col[1] - col[0] - .6)
        text(col[1], baseline(yc, CODE), versions[i], CODE, ink, width=col[2] - col[1] - .6)
        room = tx1 - .6 - col[2]
        if i == 2:
            step(s, col[2] + 1.25, yc, 6)
            text(col[2] + 3.2, baseline(yc, BODY), L['results'][i], BODY, RED, 'bold', width=room - 3.2)
        else:
            text(col[2], baseline(yc, BODY), L['results'][i], BODY, BLUE_TXT if i == 0 else MUTED,
                 'bold' if i == 0 else 'sans', width=room)

    # Definitions, one per outcome row, and the outcomes they use.
    dx, dw, dh = 1.0, 22.4, 3.0
    text(dx + .2, top - 1.0, L['defs_head'], SMALL, MUTED, 'bold')
    for i, (label, yc) in enumerate(zip(L['defs'], rows_y)):
        box(s, dx, yc - dh / 2, dw, dh, RED if i == 2 else EDGE)
        text(dx + 1.2, baseline(yc, BODY), label, BODY, INK, width=dw - 2.0)
        assert i == 0 or rows_y[i] - rows_y[i - 1] - dh >= .9
    x0, bus, x1 = dx + dw, dx + dw + 3.6, tx0
    up, down = rows_y[2] - .75, rows_y[2] + .75       # Electronics revenue: date link, item link
    s.line(x0, rows_y[0], x1, rows_y[0], EDGE, LINE)
    s.route([(x0, up), (bus, up), (bus, rows_y[0])], EDGE, LINE, heads=None, radius=.6)
    s.line(x0, rows_y[1], bus, rows_y[1], EDGE, LINE)
    s.line(x0, down, x1, down, RED, LINE)
    for y in (rows_y[0], rows_y[1]):
        s.circle(bus, y, .38, EDGE)
    s.circle(x1, rows_y[0], .38, BLUE)
    s.circle(x1, down, .38, RED)
    assert bottom < H - .3 and measure(L['store_head'], SMALL, 'bold') < tx1 - tx0
