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
from style import EDGE, INK, MUTED, RED, RULE  # noqa: E402
from smallparts import BLUE_TXT, BODY, CODE, LINE, SMALL, baseline, box  # noqa: E402

NAME = 'maintenance'
W, H = style.COLUMN, 24.6

LABELS = {
    'en': {
        'event': ('ETL load:', '`item`', r'version 0 $\rightarrow$ 1'),
        'defs_head': 'Definitions', 'store_head': 'Stored check outcomes',
        'cols': ('check', 'table version', 'result'),
        'defs': ('Store revenue', '`spend_90d`', 'Electronics revenue'),
        'checks': ('date key unique', 'item key unique', 'item key unique'),
        'results': ('pass, reused', 'pass (old)', 'fail, run once'),
    },
    'zh': {
        'event': ('ETL 载入：', '`item`', r'版本 0 $\rightarrow$ 1'),
        'defs_head': '定义', 'store_head': '存储的检查结果',
        'cols': ('检查', '表版本', '结果'),
        'defs': ('门店营业额', '`spend_90d`', '电子品类营业额'),
        'checks': ('日期键唯一', 'item 键唯一', 'item 键唯一'),
        'results': ('通过，复用', '通过（旧）', '失败，只跑一次'),
    },
}


def draw(s, lang):
    L = LABELS[lang]
    text = s.text

    # The write that changes item's version.
    x = 1.2
    for j, part in enumerate(L['event']):
        x += text(x, 3.0, part, BODY, INK, 'bold' if j == 0 else 'sans') + .9

    # Column heads.
    tx0, tx1 = 33.0, 83.6
    col = (tx0 + .8, tx0 + 18.4, tx0 + 31.2)
    text(1.2, 7.0, L['defs_head'], SMALL, MUTED, 'bold')
    text(tx0 + .8, 7.0, L['store_head'], SMALL, MUTED, 'bold')
    for c, label in zip(col, L['cols']):
        text(c, 10.0, label, SMALL, MUTED)
    s.line(tx0, 11.0, tx1, 11.0, EDGE, LINE)

    # Outcome rows: date_dim (reused), item at version 0 (left behind), item at version 1 (new).
    pitch, top = 3.7, 11.0
    rows_y = [top + pitch * i + pitch / 2 for i in range(3)]
    versions = ('`date_dim 0`', '`item 0`', '`item 1`')
    for i, yc in enumerate(rows_y):
        if i == 2:
            s.rect(tx0, yc - pitch / 2 + .3, tx1 - tx0, pitch - .6, None, RED, LINE, r=.4, dash=(.7, .45))
        elif i == 0:
            s.line(tx0, yc + pitch / 2, tx1, yc + pitch / 2, RULE, .14)
        ink = MUTED if i == 1 else INK
        text(col[0], baseline(yc, BODY), L['checks'][i], BODY, ink, width=col[1] - col[0] - .6)
        text(col[1], baseline(yc, CODE), versions[i], CODE, ink, width=col[2] - col[1] - .6)
        rc = (BLUE_TXT, MUTED, RED)[i]
        text(col[2], baseline(yc, BODY), L['results'][i], BODY, rc, 'sans' if i == 1 else 'bold',
             width=tx1 - col[2] - .4)

    # Definitions and the outcomes they use.
    dw, dh = 22.6, 3.1
    def_y = (rows_y[0], (rows_y[0] + rows_y[2]) / 2 + .6, rows_y[2])
    for i, (label, yc) in enumerate(zip(L['defs'], def_y)):
        hot = i == 2
        box(s, 1.0, yc - dh / 2, dw, dh, RED if hot else EDGE)
        text(2.2, baseline(yc, BODY), label, BODY, INK, width=dw - 2.0)
    x0, x1 = 1.0 + dw, tx0 - .3
    for yc in def_y:
        s.line(x0, yc, x1, rows_y[0], EDGE, LINE)
    s.line(x0, def_y[2], x1, rows_y[2], RED, LINE)
    for yc in def_y:
        s.circle(x0, yc, .35, EDGE)
    for yc in (rows_y[0], rows_y[2]):
        s.circle(x1, yc, .35, EDGE if yc == rows_y[0] else RED)
    assert rows_y[2] + pitch / 2 < H


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
