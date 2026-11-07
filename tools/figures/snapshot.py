"""Snapshot-bound execution (Section IV-E), single column.

A timeline around the item-history load of Fig. 2. The ETL transaction adds
the history rows and advances item's transactional version in the same
transaction. Checking in one transaction and running the SQL in another lets
the commit fall in between: the check saw one row per item, the query counts
item 17 twice. MAVRA reads the versions, reuses the stored outcome for those
versions, and runs the SQL in one read-only snapshot, which does not see the
later commit. A request after the commit reads item version 1, finds no
outcome for it, and enters maintenance (step 6).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from style import ACC, ACC_DK, EDGE, INK, MUTED, RED, RULE, WHITE  # noqa: E402
from smallparts import (EXEC_C, EXEC_PALE, MAINT_C, MAINT_PALE, SMALL, THIN,  # noqa: E402
                        Kit, baseline)

NAME = 'snapshot'
W, H = style.COLUMN, 39.0
FLOOR = 5.6

LABELS = {
    'en': {
        'lanes': ((('ETL write', 5), None), ('Check, then run', 'two transactions'), ('MAVRA', 'one transaction'),
                  ('Later request', 'after the commit')),
        'etl': ('adds item history rows,', ('`item`', r'version 0 $\rightarrow$ 1')), 'commit': 'commit',
        'check': ('check item key', 'unique'), 'run': ('run SQL', 'counts item 17 twice'),
        'snap': 'one read-only snapshot',
        'read': ('read version', '`item 0`'), 'reuse': ('reuse outcome', ('for', '`item 0`')),
        'run2': ('run SQL', 'counts each item once'), 'hidden': 'commit unseen',
        'later': (('reads', '`item 1`', ', no outcome'), ('for it', r'$\rightarrow$', 'maintain', 6)),
        'time': 'time',
    },
    'zh': {
        'lanes': ((('ETL 写入', 5), None), ('先检查后执行', '两个事务'), ('MAVRA', '同一事务'),
                  ('之后的请求', '提交之后')),
        'etl': ('写入 item 历史行，', ('`item`', r'版本 0 $\rightarrow$ 1')), 'commit': '提交',
        'check': ('检查 item', '键唯一'), 'run': ('执行 SQL', '商品 17 被算两次'),
        'snap': '同一只读快照',
        'read': ('读取表版本', '`item 0`'), 'reuse': ('复用检查结果', ('版本', '`item 0`')),
        'run2': ('执行 SQL', '每个商品只算一次'), 'hidden': '看不到提交',
        'later': (('读到', '`item 1`', '，无对应'), ('检查结果', r'$\rightarrow$', '维护', 6)),
        'time': '时间',
    },
}

X0, X1, XC = 20.0, 83.4, 54.4        # timeline start and end, ETL commit
LANE = (2.4, 11.0, 19.8, 30.0)        # top of each lane
LH = (6.0, 6.4, 8.6, 5.2)             # lane heights


def draw(s, lang):
    L = LABELS[lang]
    k = Kit(s)
    text = s.text

    def two(x, y_top, h, lines, size, colors, style_=('sans', 'sans'), align='left'):
        """Two text lines centred in a band; a line may be a tuple of rich tokens."""
        for j, line in enumerate(lines):
            yc = y_top + h / 2 + (j - .5) * 2.4
            c = colors[j] if isinstance(colors, tuple) else colors
            k.rich(x, yc, line, size, c, style_[j], align=align)

    # Lane labels.
    for i, (title, note) in enumerate(L['lanes']):
        y, h = LANE[i], LH[i]
        yc = y + h / 2
        k.rich(1.2, yc - (1.25 if note else 0), title, SMALL, ACC_DK if i == 2 else INK, 'bold')
        if i:
            s.line(1.0, y - 1.0, X1, y - 1.0, RULE, .12)
        if not note:
            continue
        text(1.2, baseline(yc + 1.35, FLOOR), note, FLOOR, EXEC_C if i == 2 else MUTED)

    # The ETL commit: a vertical line through every lane.
    s.line(XC, LANE[0] + LH[0], XC, LANE[3] + LH[3] + 1.0, MAINT_C, .22, dash=(.7, .45))

    # Lane 0: the ETL transaction writes rows and the version in one commit.
    y, h = LANE[0], LH[0]
    ex0 = 29.0
    s.rect(ex0, y, XC - ex0, h, MAINT_PALE, MAINT_C, .16, r=.5)
    two(ex0 + 1.0, y, h, L['etl'], FLOOR, MAINT_C)
    s.circle(XC, y + h / 2, .7, MAINT_C)
    text(XC + 1.3, baseline(y + h / 2, SMALL - .3), L['commit'], SMALL - .3, MAINT_C, 'bold')

    # Lane 1: check and query in separate transactions; the commit falls between.
    y, h = LANE[1], LH[1]
    b1 = (X0 + 1.0, X0 + 16.0)
    k.box(b1[0], y, b1[1] - b1[0], h, WHITE, EDGE, .14, r=.4)
    two(b1[0] + 1.0, y, h, L['check'], FLOOR, INK)
    k.mark(b1[1] - 1.6, y + h / 2 + 1.2, 'ok', ACC, .85)
    b2 = (XC + 2.0, XC + 23.8)
    k.box(b2[0], y, b2[1] - b2[0], h, WHITE, RED, .16, r=.4)
    two(b2[0] + 1.0, y, h, L['run'], FLOOR, (INK, RED), ('sans', 'bold'))
    s.route([(b1[1], y + h / 2), (b2[0], y + h / 2)], MUTED, THIN, length=.8)
    k.mark(X1 - 1.4, y + h / 2, 'fail', RED, 1.0)

    # Lane 2: MAVRA reads versions, reuses the outcome and runs the SQL in one snapshot.
    y, h = LANE[2], LH[2]
    sx0, sx1 = X0 + 1.0, b2[1] + 1.0
    s.rect(sx0, y, sx1 - sx0, h, EXEC_PALE, EXEC_C, .2, r=.5, dash=(.8, .5))
    text(sx0 + 1.0, baseline(y + 1.6, FLOOR), L['snap'], FLOOR, EXEC_C, 'bold')
    iy, ih = y + 3.0, h - 3.6
    boxes = ((sx0 + 1.0, sx0 + 14.6), (sx0 + 16.6, XC - 1.8), (b2[0], b2[1]))
    (r0, r1), (u0, u1), (q0, q1) = boxes
    k.box(r0, iy, r1 - r0, ih, WHITE, EDGE, .14, r=.4)
    two(r0 + .9, iy, ih, L['read'], FLOOR, INK)
    k.box(u0, iy, u1 - u0, ih, WHITE, ACC, .16, r=.4)
    two(u0 + .9, iy, ih, L['reuse'], FLOOR, (ACC_DK, INK))
    k.box(q0, iy, q1 - q0, ih, WHITE, ACC, .16, r=.4)
    two(q0 + .9, iy, ih, L['run2'], FLOOR, (INK, ACC_DK), ('sans', 'bold'))
    s.route([(r1, iy + ih / 2), (u0, iy + ih / 2)], EXEC_C, THIN, length=.7)
    s.route([(u1, iy + ih / 2), (q0, iy + ih / 2)], EXEC_C, THIN, length=.7)
    # The commit falls inside the snapshot's lifetime but is not visible to it.
    text(XC + .9, baseline(y + 1.6, FLOOR - .2), L['hidden'], FLOOR - .2, MAINT_C, 'bold',
         width=sx1 - XC - 1.6)
    k.mark(X1 - 1.4, iy + ih / 2, 'ok', ACC, 1.0)

    # Lane 3: a later request reads item version 1 and finds no outcome for it.
    y, h = LANE[3], LH[3]
    lx0, lx1 = XC + 2.2, X1
    s.rect(lx0, y, lx1 - lx0, h, WHITE, MAINT_C, .16, r=.4)
    two(lx0 + 1.0, y, h, L['later'], FLOOR, MAINT_C)

    # Time axis.
    ay = H - 1.3
    s.route([(X0 + 2.0, ay), (X1, ay)], MUTED, .18, length=.9)
    text(X0 + 1.4, baseline(ay, FLOOR), L['time'], FLOOR, MUTED, align='right')


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
