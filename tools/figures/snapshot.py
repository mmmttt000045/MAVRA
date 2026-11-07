"""Snapshot-bound execution (Section IV-E), single column: (a) vs. (b) timeline.

The ETL transaction of Fig. 2 adds a history row for item 17 and advances
item's version in one commit. (a) A check and a query in separate transactions
let that commit fall between them: the check saw one row per item, the query
sees the new row and counts item 17 twice. (b) MAVRA reads the version, reuses
the stored outcome for it, and runs the query in one read-only snapshot, which
does not see the commit.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import EDGE, FACE, INK, MUTED, RED  # noqa: E402
from smallparts import (BLUE, BLUE_FIELD, BLUE_PALE, BLUE_TXT, BODY, LABEL, LINE, RED_PALE, SMALL,  # noqa: E402
                        arrow, baseline, box, mark, parts, step, verdict)

NAME = 'snapshot'
W, H = style.COLUMN, 38.4
XC = 46.0                     # the ETL commit
FAINT = '#A9C3E3'             # the commit, as seen from inside the snapshot

LABELS = {
    'en': {
        'etl': ((('ETL: ', 'bold'), ('add a history row for item 17', 'sans')),
                (('`item`', 'sans'), (r' version 0 $\rightarrow$ 1', 'sans'))),
        'commit': 'commit',
        'a': '(a) Check, then run, in two transactions', 'b': '(b) MAVRA: one read-only snapshot',
        'check': ('check item key unique', 'one row per item'), 'run_a': ('run SQL, sees new row', 'counts item 17 twice'),
        'read': ('read version', '`item 0`'), 'reuse': ('reuse outcome', 'for `item 0`'),
        'run_b': ('run SQL at `item 0`', 'counts each item once'), 'hidden': 'not visible', 'time': 'time',
    },
    'zh': {
        'etl': ((('ETL：', 'bold'), ('为商品 17 写入一条历史行', 'sans')),
                (('`item`', 'sans'), (r' 版本 0 $\rightarrow$ 1', 'sans'))),
        'commit': '提交',
        'a': '(a) 先检查后执行，分属两个事务', 'b': '(b) MAVRA：同一只读快照',
        'check': ('检查 item 键唯一', '每个商品一行'), 'run_a': ('执行 SQL，看到新行', '商品 17 被算两次'),
        'read': ('读取表版本', '`item 0`'), 'reuse': ('复用检查结果', '版本 `item 0`'),
        'run_b': ('在 `item 0` 上执行 SQL', '每个商品只算一次'), 'hidden': '看不到', 'time': '时间',
    },
}


def draw(s, lang):
    L = LABELS[lang]
    text = s.text

    def two(x, y, w, lines, colors, right=0.0):
        """Two lines in a box whose top is y, leaving room for a mark at the right."""
        for j, line in enumerate(lines):
            text(x + 1.2, y + 2.55 + 2.45 * j, line, SMALL, colors[j], width=w - 2.4 - right)

    # Step 5: the ETL transaction and its commit.
    ex0, ey, eh = 7.0, 1.0, 6.0
    eyc = ey + eh / 2
    step(s, 3.6, eyc, 5)
    box(s, ex0, ey, XC - 1.8 - ex0, eh, EDGE, FACE)
    for j, line in enumerate(L['etl']):
        end = parts(s, ex0 + 1.2, ey + 2.55 + 2.45 * j, [(t, INK, st) for t, st in line], SMALL)
        assert end < XC - 2.6, end
    s.line(XC - 1.8, eyc, XC, eyc, INK, LINE)
    s.circle(XC, eyc, .75, INK)
    text(XC + 1.5, baseline(eyc, BODY), L['commit'], BODY, INK, 'bold')

    # (a) Check and query in separate transactions; the commit falls in between.
    ay = 11.6
    aw = text(1.2, ay, L['a'], LABEL, INK, 'bold')
    assert 1.2 + aw < XC - 1.0, aw
    by, bh = ay + 1.5, 6.2
    c0, c1 = 3.0, 27.0
    q0, q1 = XC + 6.0, 78.4
    box(s, c0, by, c1 - c0, bh)
    two(c0, by, c1 - c0, L['check'], (INK, MUTED), right=2.2)
    mark(s, c1 - 1.6, by + bh - 1.7, True)
    box(s, q0, by, q1 - q0, bh, RED, RED_PALE)
    two(q0, by, q1 - q0, L['run_a'], (INK, RED))
    arrow(s, [(c1, by + bh / 2), (q0, by + bh / 2)])
    verdict(s, q1 + 2.6, by + bh / 2, False)

    # (b) MAVRA: version read, outcome reuse and query in one snapshot.
    yb = by + bh + 4.4
    bw = text(1.2, yb, L['b'], LABEL, INK, 'bold')
    step(s, 1.2 + bw + 2.0, yb - .8, 4)
    sy, sh = yb + 1.5, 9.0
    s.line(XC, eyc + .75, XC, sy, MUTED, LINE, dash=(.7, .45))
    s.rect(2.0, sy, q1 + 1.0 - 2.0, sh, BLUE_FIELD, BLUE, LINE + .04, r=.7)
    s.line(XC, sy + .3, XC, sy + sh - .3, FAINT, LINE, dash=(.7, .45))
    iy, ih = sy + 1.4, sh - 2.8
    r0, r1 = 3.0, 17.4
    u0, u1 = 20.0, 37.0
    box(s, r0, iy, r1 - r0, ih)
    two(r0, iy, r1 - r0, L['read'], (INK, INK))
    box(s, u0, iy, u1 - u0, ih)
    two(u0, iy, u1 - u0, L['reuse'], (INK, INK), right=2.2)
    mark(s, u1 - 1.6, iy + ih - 1.7, True)
    box(s, q0, iy, q1 - q0, ih, BLUE, BLUE_PALE)
    two(q0, iy, q1 - q0, L['run_b'], (INK, BLUE_TXT))
    arrow(s, [(r1, iy + ih / 2), (u0, iy + ih / 2)])
    arrow(s, [(u1, iy + ih - 1.6), (q0, iy + ih - 1.6)])
    verdict(s, q1 + 2.6, iy + ih / 2, True)

    hw = measure(L['hidden'], SMALL, 'bold')
    hy = iy + 2.0
    s.rect(XC - hw / 2 - .4, hy - 1.6, hw + .8, 2.2, BLUE_FIELD, None)
    text(XC, hy, L['hidden'], SMALL, BLUE_TXT, 'bold', 'center')
    assert u1 + .6 < XC - hw / 2 - .4 and XC + hw / 2 + .4 < q0 - .6, hw

    # Time axis; the commit is marked on it.
    ty = H - 1.6
    s.line(XC, sy + sh, XC, ty, MUTED, LINE, dash=(.7, .45))
    arrow(s, [(2.0, ty), (83.4, ty)])
    text(83.4, ty - 1.0, L['time'], SMALL, MUTED, align='right')
    assert sy + sh < ty - 1.2
