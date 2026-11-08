"""Snapshot-bound execution with transactional versions (Section IV-E), single column.

Algorithm 2 run while the item-history load of Fig. 2 commits. Top: the ETL
transaction inserts item 17's history row; the statement trigger mavra_bump
adds one to item's counter row (shard pid % 16, here 5) in the same
transaction, so the row and the bump commit together. Middle: run_metric's
read-only REPEATABLE READ transaction s. Its first statement reads the
counters (PostgreSQL takes the snapshot there), so v_s(item) = 0 matches the
item rows s can see. The verdict store H_tx, keyed by id(c) @ v_s(dep(c)),
already holds the item key check at item = 0, so s reuses it and runs the
query in the same snapshot: the commit is invisible and item 17 counts once.
A later snapshot reads item = 1, finds no verdict, runs the check inside
itself, fails (1001 rows over 1000 keys), aborts, and invalidates V(item).

Values follow the running example: counters start at 0 when the triggers are
installed after loading; one ETL statement bumps one shard. Key counts as in
Fig. 4 (1000 items, 1096 dates, one history row for item 17).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import EDGE, FACE, INK, MUTED, RED, RULE, WHITE  # noqa: E402
from smallparts import (BAND, BLUE, BLUE_FIELD, BLUE_PALE, BLUE_TXT, CODE_T, EXEC_C, HEAD_T, LINE,  # noqa: E402
                        MAINT_C, MAINT_PALE, RED_PALE, SMALL, arrow, baseline, box, mark, parts, step,
                        structure, tag, verdict)

NAME = 'snapshot'
W, H = style.COLUMN, 42.8
XC = 48.6                     # the ETL commit
FAINT = '#A9C3E3'             # the commit, as seen from inside the snapshot

LABELS = {
    'en': {
        'etl': ((('ETL: ', 'bold'), ('`INSERT`', 'sans'), (" history row `(17, ..., 'N')`", 'sans')),
                (('trigger `mavra_bump`: `v+1` on (`item`, `pid%16=5`)', 'sans'),)),
        'commit': 'COMMIT',
        'snap': r'snapshot $s$: repeatable read, read only', 'hidden': 'not visible',
        'boxes': ((('`BEGIN`',), ('read only',)), ((r'read $v_s$',), ('`item=0`',)),
                  ((r'probe $H_\mathrm{tx}$',), ('hit: pass',)), ((r'run $q$ in $s$, `COMMIT`',), ('item 17 counted once',))),
        'time': 'time',
        'versions': (('`mavra_versions`', 'sans'),),
        'cols_v': ('`table_name`', '`shard`', '`v`'),
        'sum': r'in $s$: $v_s($`item`$)=\sum v=0$',
        'verdicts': ((r'Verdicts $H_\mathrm{tx}$', 'bold'),),
        'key': r'key $\mathrm{id}(c)$ @ $v_s(\mathrm{dep}(c))$',
        'cols_h': (r'$\mathrm{id}(c)$', r'$v_s(\mathrm{dep}(c))$', '`n_rows/n_keys`'),
        'later': r'from a later snapshot: abort it, invalidate $V($`item`$)$',
    },
    'zh': {
        'etl': ((('ETL：', 'bold'), ('`INSERT`', 'sans'), (" 历史行 `(17, ..., 'N')`", 'sans')),
                (('触发器 `mavra_bump`：(`item`, `pid%16=5`) 行 `v+1`', 'sans'),)),
        'commit': '提交',
        'snap': r'快照 $s$：可重复读、只读', 'hidden': '看不到',
        'boxes': ((('`BEGIN`',), ('只读',)), ((r'读 $v_s$',), ('`item=0`',)),
                  ((r'查 $H_\mathrm{tx}$',), ('命中',)), ((r'在 $s$ 中执行 $q$ 并 `COMMIT`',), ('商品 17 只算一次',))),
        'time': '时间',
        'versions': (('`mavra_versions`', 'sans'),),
        'cols_v': ('`table_name`', '`shard`', '`v`'),
        'sum': r'$s$ 中：$v_s($`item`$)=\sum v=0$',
        'verdicts': ((r'结论存储 $H_\mathrm{tx}$', 'bold'),),
        'key': r'键 $\mathrm{id}(c)$ @ $v_s(\mathrm{dep}(c))$',
        'cols_h': (r'$\mathrm{id}(c)$', r'$v_s(\mathrm{dep}(c))$', '`n_rows/n_keys`'),
        'later': r'由之后的快照写入：该快照中止，作废 $V($`item`$)$',
    },
}

COUNTERS = (('`date_dim`', '`0`', '`0`'), ('`item`', '`0`', '`0`'), ('`item`', '`5`', r'`0`$\rightarrow$`1`'),
            ('`store_sales`', '`0`', '`0`'))
VERDICTS = (('`KeyUnique(item.i_item_sk)`', '`item=0`', '`1000/1000`', True),
            ('`KeyUnique(date_dim.d_date_sk)`', '`date_dim=0`', '`1096/1096`', True),
            ('`KeyUnique(item.i_item_sk)`', '`item=1`', '`1001/1000`', False))


def draw(s, lang):
    L = LABELS[lang]
    text = s.text
    gx, x0, x1 = 2.15, 4.4, 83.6

    # Step 5: the ETL transaction; the trigger bumps item's counter row in the same transaction.
    ey, eh = 1.0, 6.0
    eyc = ey + eh / 2
    step(s, gx, eyc, 5, r=1.15)
    box(s, x0, ey, XC - 1.7 - x0, eh, EDGE, FACE)
    for j, line in enumerate(L['etl']):
        end = parts(s, x0 + 1.0, ey + 2.5 + 2.4 * j, [(t, MAINT_C if j else INK, st) for t, st in line], SMALL)
        assert end < XC - 2.4, end
    s.line(XC - 1.7, eyc, XC, eyc, INK, LINE)
    s.circle(XC, eyc, .75, INK)
    text(XC + 1.5, baseline(eyc, SMALL), L['commit'], SMALL, INK, 'bold')

    # Step 4: run_metric in one read-only snapshot; the commit falls inside it but is not visible.
    sy, sh = ey + eh + 2.0, 10.4
    syc = sy + sh / 2
    step(s, gx, syc, 4, r=1.15)
    s.line(XC, eyc + .75, XC, sy, MUTED, LINE, dash=(.7, .45))
    s.rect(x0, sy, x1 - x0, sh, BLUE_FIELD, BLUE, LINE + .04, r=.7)
    s.line(XC, sy + .3, XC, sy + sh - .3, FAINT, LINE, dash=(.7, .45))
    ty = sy + 2.25
    tw = text(x0 + 1.0, ty, L['snap'], SMALL, BLUE_TXT, 'bold')
    hw = measure(L['hidden'], SMALL, 'bold')
    s.rect(XC - hw / 2 - .4, ty - 1.6, hw + .8, 2.2, BLUE_FIELD, None)
    text(XC, ty, L['hidden'], SMALL, BLUE_TXT, 'bold', 'center')
    assert x0 + 1.0 + tw < XC - hw / 2 - .6, tw
    by, bh = sy + 3.4, 5.9
    spans = ((x0 + 1.0, 16.4), (18.0, 31.4), (33.0, XC - 3.0), (XC + 3.4, x1 - 1.0))
    tags = ('L4', 'L5', 'L7', 'L11')
    for k, ((a, b), lines, label) in enumerate(zip(spans, L['boxes'], tags)):
        last = k == 3
        box(s, a, by, b - a, bh, BLUE if last else EDGE, BLUE_PALE if last else WHITE)
        y1, y2 = by + 2.35, by + 4.75
        tw = tag(s, a + .6, y1 - .8, label, EXEC_C)
        text(a + .6 + tw + .6, y1, lines[0][0], SMALL, INK, width=b - a - tw - 1.8)
        right = 2.6 if k in (2, 3) else 0
        text(a + .9, y2, lines[1][0], SMALL if not lines[1][0].startswith('`') else CODE_T,
             BLUE_TXT if last else INK, width=b - a - 1.6 - right)
        if k == 2:
            mark(s, b - 1.3, y2 - .8, True, k=.8)
        if k < 3:
            nxt = spans[k + 1][0]
            arrow(s, [(b, by + bh / 2), (nxt, by + bh / 2)])
    verdict(s, x1 - 2.3, by + 4.75 - .8, True, r=.95)

    # Time axis.
    ay = sy + sh + 2.5
    s.line(XC, sy + sh, XC, ay, MUTED, LINE, dash=(.7, .45))
    arrow(s, [(x0, ay), (x1, ay)])
    text(x1 - 1.2, ay - .8, L['time'], SMALL, MUTED, align='right')

    # The counter table in the database and MAVRA's verdict store, keyed by transactional versions.
    band, head, pitch = 2.9, 2.75, 2.45
    ty0 = ay + 1.4
    vx0, vx1 = x0, 29.6
    top_v = ty0 + band + head
    hgt = band + head + 4 * pitch + 2.7 + .3
    yb = structure(s, vx0, ty0, vx1 - vx0, hgt, band, L['versions'], None, BAND, INK)
    cv = (vx0 + 1.0, vx0 + 12.4, vx0 + 18.6)
    for c, label in zip(cv, L['cols_v']):
        text(c, yb + 2.0, label, HEAD_T, MUTED)
    s.line(vx0, top_v, vx1, top_v, RULE, .14)
    for i, row in enumerate(COUNTERS):
        yc = top_v + pitch * (i + .5)
        if i == 2:
            s.rect(vx0 + .3, yc - pitch / 2 + .15, vx1 - vx0 - .6, pitch - .3, MAINT_PALE, None, r=.4)
        for j, (c, v) in enumerate(zip(cv, row)):
            text(c, baseline(yc, CODE_T), v, CODE_T, MAINT_C if (i == 2 and j == 2) else INK,
                 width=(cv[j + 1] if j < 2 else vx1 - .4) - c - .3)
    s.line(vx0, top_v + 4 * pitch, vx1, top_v + 4 * pitch, RULE, .14)
    text(cv[0], baseline(top_v + 4 * pitch + 1.45, SMALL), L['sum'], SMALL, INK, width=vx1 - vx0 - 1.4)

    hx0, hx1 = vx1 + 1.6, x1
    yb = structure(s, hx0, ty0, hx1 - hx0, hgt, band, L['verdicts'], L['key'])
    chh = (hx0 + 1.0, hx0 + 29.4, hx0 + 39.6, hx1 - 1.6)
    for c, label in zip(chh, L['cols_h']):
        text(c, yb + 2.0, label, HEAD_T, MUTED)
    s.line(hx0, top_v, hx1, top_v, RULE, .14)
    heights = (3.15, 3.15, 5.3)
    y0 = top_v
    for i, ((cid, vs, stats, ok), h) in enumerate(zip(VERDICTS, heights)):
        if i == 0:
            s.rect(hx0 + .3, y0 + .2, hx1 - hx0 - .6, h - .4, BLUE_PALE, None, r=.4)
        elif i == 2:
            s.rect(hx0 + .3, y0 + .2, hx1 - hx0 - .6, h - .4, RED_PALE, RED, LINE, r=.4, dash=(.7, .45))
        yc = y0 + (h / 2 if i < 2 else 1.4)
        bc = baseline(yc, CODE_T)
        ink = RED if not ok else INK
        text(chh[0], bc, cid, CODE_T, INK, width=chh[1] - chh[0] - .3)
        text(chh[1], bc, vs, CODE_T, MAINT_C if i == 2 else INK, width=chh[2] - chh[1] - .3)
        text(chh[2], bc, stats, CODE_T, ink, width=chh[3] - chh[2] - 1.3)
        mark(s, chh[3] + .3, yc, ok, k=.8)
        if i == 2:
            text(chh[0], baseline(yc + 2.3, SMALL), L['later'], SMALL, RED, width=hx1 - hx0 - 2.0)
        y0 += h
    assert ty0 + hgt < H - .3, ty0 + hgt
    # The reads of step 4: line 5 sums the counters, line 7 probes the verdicts.
    for xa, xb in ((24.0, 24.0), (39.0, 39.0)):
        s.route([(xa, by + bh), (xb, ty0)], EXEC_C, LINE + .04, dash=(.6, .4), length=.8)
