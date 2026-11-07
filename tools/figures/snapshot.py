"""Snapshot-bound execution (Section IV-E), single column: (a) vs. (b) timeline.

The ETL transaction of Fig. 2 adds item history rows and advances item's
version in one commit. (a) A check and a query in separate transactions let
that commit fall between them: the check saw one row per item, the query
counts item 17 twice. (b) MAVRA reads the version, reuses the stored outcome
for it, and runs the query in one read-only snapshot, which does not see the
commit.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import EDGE, FACE, INK, MUTED, RED  # noqa: E402
from smallparts import BLUE, BLUE_TXT, BODY, LABEL, LINE, SMALL, arrow, box, mark  # noqa: E402

NAME = 'snapshot'
W, H = style.COLUMN, 37.0
XC = 46.0                     # the ETL commit

LABELS = {
    'en': {
        'etl': ('ETL: add item history rows,', ('`item`', r'version 0 $\rightarrow$ 1')), 'commit': 'commit',
        'a': '(a) Check, then run, in two transactions', 'b': '(b) MAVRA: one read-only snapshot',
        'check': ('check item key', 'unique'), 'run_a': ('run SQL', 'counts item 17 twice'),
        'read': ('read version', ('`item 0`',)), 'reuse': ('reuse outcome', ('for', '`item 0`')),
        'run_b': ('run SQL', 'counts each item once'), 'hidden': 'not visible', 'time': 'time',
    },
    'zh': {
        'etl': ('ETL：写入 item 历史行，', ('`item`', r'版本 0 $\rightarrow$ 1')), 'commit': '提交',
        'a': '(a) 先检查后执行，分属两个事务', 'b': '(b) MAVRA：同一只读快照',
        'check': ('检查 item', '键唯一'), 'run_a': ('执行 SQL', '商品 17 被算两次'),
        'read': ('读取表版本', ('`item 0`',)), 'reuse': ('复用检查结果', ('版本', '`item 0`')),
        'run_b': ('执行 SQL', '每个商品只算一次'), 'hidden': '看不到', 'time': '时间',
    },
}


def draw(s, lang):
    L = LABELS[lang]
    text = s.text

    def two(x, y, lines, colors, w=None):
        """Two lines in a box whose top is y; a line may be a tuple of parts."""
        for j, line in enumerate(lines):
            xx = x
            for k, part in enumerate(line if isinstance(line, tuple) else (line,)):
                xx += text(xx, y + 2.5 + 2.4 * j, part, SMALL, colors[j]) + .8

    # The ETL transaction and its commit.
    ex0, ey, eh = 12.0, 1.0, 6.0
    box(s, ex0, ey, XC - ex0, eh, EDGE, FACE)
    two(ex0 + 1.2, ey, L['etl'], (INK, INK))
    s.line(XC, ey + eh / 2, XC, H - 3.2, MUTED, LINE, dash=(.7, .45))
    s.circle(XC, ey + eh / 2, .7, INK)
    text(XC + 1.4, ey + eh / 2 + .8, L['commit'], BODY, INK, 'bold')

    # (a) Check and query in separate transactions.
    ay = 10.6
    text(1.2, ay, L['a'], LABEL, INK, 'bold')
    by, bh = ay + 1.4, 6.0
    c0, c1 = 3.0, 21.0
    q0, q1 = XC + 6.4, XC + 28.4
    box(s, c0, by, c1 - c0, bh)
    two(c0 + 1.2, by, L['check'], (INK, INK))
    mark(s, c1 - 1.6, by + bh - 1.5, True)
    box(s, q0, by, q1 - q0, bh, RED)
    two(q0 + 1.2, by, L['run_a'], (INK, RED))
    arrow(s, [(c1, by + bh / 2), (q0, by + bh / 2)])
    mark(s, q1 + 3.2, by + bh / 2, False)

    # (b) MAVRA: version read, outcome reuse and query in one snapshot.
    yb = by + bh + 4.2
    text(1.2, yb, L['b'], LABEL, INK, 'bold')
    sy, sh = yb + 1.4, 8.2
    s.rect(2.0, sy, q1 + 1.0 - 2.0, sh, '#F4F8FD', BLUE, LINE + .02, r=.6, dash=(.8, .5))
    s.line(XC, sy, XC, sy + sh, MUTED, LINE, dash=(.7, .45))
    iy, ih = sy + 1.1, sh - 2.2

    hw = measure(L['hidden'], SMALL, 'bold')
    s.rect(XC - hw / 2 - .3, iy - .1, hw + .6, 2.6, '#F4F8FD', None)
    text(XC, iy + 1.9, L['hidden'], SMALL, BLUE_TXT, 'bold', 'center')
    r0, r1 = 3.0, 16.6
    u0, u1 = 19.4, 36.0
    box(s, r0, iy, r1 - r0, ih)
    two(r0 + 1.2, iy, L['read'], (INK, INK))
    box(s, u0, iy, u1 - u0, ih)
    two(u0 + 1.2, iy, L['reuse'], (INK, INK))
    mark(s, u1 - 1.6, iy + ih - 1.5, True)
    box(s, q0, iy, q1 - q0, ih, BLUE)
    two(q0 + 1.2, iy, L['run_b'], (INK, BLUE_TXT))
    arrow(s, [(r1, iy + ih / 2), (u0, iy + ih / 2)])
    arrow(s, [(u1, iy + ih / 2 + .8), (q0, iy + ih / 2 + .8)])
    mark(s, q1 + 3.2, iy + ih / 2, True)
    assert u1 < XC - hw / 2 - .4 and XC + hw / 2 + .4 < q0, hw

    # Time axis.
    ty = H - 1.6
    arrow(s, [(2.0, ty), (83.4, ty)])
    text(83.4, ty - .9, L['time'], SMALL, MUTED, align='right')
    assert sy + sh < ty - 1.2


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
