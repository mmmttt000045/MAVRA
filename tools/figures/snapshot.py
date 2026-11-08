"""Admission and snapshot-bound execution with transactional versions (Section IV-E), single column.

Top: what Admissible(q, R) checks before a query runs (Algorithm 2, line 2):
a request declaring the current revision passes; one declaring a retired
revision is told why it was retired and which revision is current; a query
that drops the filter the store now requires on item is rejected.
Middle, on one time axis: the ETL transaction bumps one of item's 16 counter
rows inside the same transaction (statement trigger); Agent 2's snapshot s
read v_s(item) = 0 before the commit, so it reuses the verdict at item = 0 and
counts item 17 once; the maintenance and repair checks of step 6 run outside
any snapshot and record a verdict only if v(item) is the same before and after
the check; Agent N's snapshot s′ reads item = 1 and reuses the repaired verdict.
Bottom: the counter table and the verdict store H_tx, keyed by
id(c) @ v_s(dep(c)), with who wrote each verdict and which snapshot reused it.

Values follow the running example (counters are 0 when the triggers are
installed after loading; one ETL statement bumps one shard; key counts from the
fixture with one history row for item 17). Rejection reasons paraphrase
check_metric_refs and review_sql; the recording rule is exec_check's
before/after read of the counters (src/middle.rs).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import EDGE, FACE, INK, MUTED, RED, RULE, WHITE  # noqa: E402
from smallparts import (BAND, BLUE, BLUE_FIELD, BLUE_PALE, BLUE_TXT, CODE_T, EXEC_C, HEAD_T, LINE,  # noqa: E402
                        MAINT_C, MAINT_PALE, RED_PALE, SMALL, arrow, baseline, box, mark, parts, step,
                        structure, tag)

NAME = 'snapshot'
W, H = style.COLUMN, 54.6
XC = 46.0                     # the ETL commit
FAINT = '#A9C3E3'             # the commit, as seen from inside a snapshot

LABELS = {
    'en': {
        'adm': (('Admission before execution', 'bold'),), 'adm_note': 'Algorithm 2, line 2',
        'adm_cols': ('request', 'declares', 'check'),
        'adm_rows': (('`run_metric`', '`ER@r1`', 'current; required `item` filter present', 'runs in $s$′'),
                     ('`run_sql`', '`ER@r0`', "r0 retired: join now needs `i_is_current='Y'`; use r1", ''),
                     ('`run_sql`', 'none', "no `i_is_current='Y'`: item 17 counted twice", '')),
        'etl': ((('ETL: ', 'bold'), ('`INSERT`', 'sans'), (" history row `(17,...,'N')`", 'sans')),
                (('same transaction: trigger `v+1` on (`item`, `5`)', 'sans'),)),
        'commit': 'COMMIT', 'hidden': 'not visible', 'time': 'time',
        's': r'$s$: Agent 2', 'maint': 'step 6, outside snapshots', 's2': r'$s$′: Agent N, after repair',
        'boxes_s': (('L5', '`item=0`'), ('L7', 'hit'), ('L11', '17 once')),
        'maint_box': r'$v($`item`$)=1$ before and after: record',
        'boxes_s2': (('L5', '`item=1`'), ('L7', 'hit'), ('L11', 'runs')),
        'versions': (('`mavra_versions`', 'sans'),),
        'cols_v': ('`table`', '`shard`', '`v`'),
        'sum': r'$v_s(T)=\sum v$, 16 rows',
        'verdicts': ((r'Verdicts $\mathcal{H}_\mathrm{tx}$', 'bold'),),
        'key': r'key $\mathrm{id}(c)$ @ $v_s(\mathrm{dep}(c))$',
        'cols_h': (r'$\mathrm{id}(c)$ @ $v_s$', '`rows/keys`', r'written $\rightarrow$ reused'),
        'rows_h': ((('`KeyUnique(item.i_item_sk)@item=0`',), '`1000/1000`', True, 'publication', '$s$'),
                   (('`KeyUnique(item.i_item_sk)@item=1`',), '`1001/1000`', False, 'maintenance', ''),
                   (('`KeyUnique(item.i_item_sk,`', "`  i_is_current='Y')@item=1`"), '`1000/1000`', True, 'repair',
                    '$s$′')),
    },
    'zh': {
        'adm': (('执行前的准入', 'bold'),), 'adm_note': '算法 2 第 2 行',
        'adm_cols': ('请求', '声明', '检查'),
        'adm_rows': (('`run_metric`', '`ER@r1`', '当前修订；含必需的 `item` 过滤', '在 $s$′ 中执行'),
                     ('`run_sql`', '`ER@r0`', "r0 已失效：连接现须 `i_is_current='Y'`；改用 r1", ''),
                     ('`run_sql`', '未声明', "缺 `i_is_current='Y'`：商品 17 算两次", '')),
        'etl': ((('ETL：', 'bold'), ('`INSERT`', 'sans'), (" 历史行 `(17,...,'N')`", 'sans')),
                (('同一事务：触发器给 (`item`, `5`) 行 `v+1`', 'sans'),)),
        'commit': '提交', 'hidden': '看不到', 'time': '时间',
        's': r'$s$：智能体 2', 'maint': '步骤 6，在快照之外', 's2': r'$s$′：智能体 N，修复之后',
        'boxes_s': (('L5', '`item=0`'), ('L7', '命中'), ('L11', '算一次')),
        'maint_box': r'前后读到 $v($`item`$)=1$：记录',
        'boxes_s2': (('L5', '`item=1`'), ('L7', '命中'), ('L11', '执行')),
        'versions': (('`mavra_versions`', 'sans'),),
        'cols_v': ('`table`', '`shard`', '`v`'),
        'sum': r'$v_s(T)=\sum v$，16 行',
        'verdicts': ((r'结论 $\mathcal{H}_\mathrm{tx}$', 'bold'),),
        'key': r'键 $\mathrm{id}(c)$ @ $v_s(\mathrm{dep}(c))$',
        'cols_h': (r'$\mathrm{id}(c)$ @ $v_s$', '`rows/keys`', r'写入 $\rightarrow$ 复用'),
        'rows_h': ((('`KeyUnique(item.i_item_sk)@item=0`',), '`1000/1000`', True, '发布', '$s$'),
                   (('`KeyUnique(item.i_item_sk)@item=1`',), '`1001/1000`', False, '维护', ''),
                   (('`KeyUnique(item.i_item_sk,`', "`  i_is_current='Y')@item=1`"), '`1000/1000`', True, '修复',
                    '$s$′')),
    },
}

COUNTERS = (('`date_dim`', '`0`', '`0`'), ('`item`', '`0`', '`0`'), ('`item`', '`5`', r'`0`$\rightarrow$`1`'))


def size_of(label):
    return CODE_T if label.startswith('`') else SMALL


def lane_boxes(s, yc, h, items, spans, last=None):
    """One lane's steps: an L<n> tag and a label per box, joined by arrows."""
    for k, ((t, label), (a, b)) in enumerate(zip(items, spans)):
        done = last is not None and k == len(spans) - 1
        box(s, a, yc - h / 2, b - a, h, BLUE if done else EDGE, BLUE_PALE if done else WHITE)
        w = tag(s, a + .5, yc, t, EXEC_C)
        room = b - a - w - 1.4 - (2.0 if done and last else 0)
        s.text(a + .5 + w + .5, baseline(yc, size_of(label)), label, size_of(label), BLUE_TXT if done else INK,
               width=room)
        if done and last:
            mark(s, b - 1.3, yc, True, k=.72)
        if k + 1 < len(spans):
            arrow(s, [(b, yc), (spans[k + 1][0], yc)])


def draw(s, lang):
    L = LABELS[lang]
    text = s.text
    x0, x1 = 1.0, 83.6
    band, head, pitch = 2.9, 2.35, 2.55
    gx, lx = 2.3, 5.0                                # badge gutter; lanes start at lx

    # Admission: declared revisions and required filters are checked before any snapshot opens.
    ay0 = 1.0
    top = ay0 + band + head + .3
    ah = top - ay0 + 3 * pitch + .25
    yb = structure(s, x0, ay0, x1 - x0, ah, band, L['adm'], L['adm_note'], BLUE_PALE, INK)
    ca = (x0 + 1.0, x0 + 12.8, x0 + 23.4)
    for c, label in zip(ca, L['adm_cols']):
        text(c, yb + 1.95, label, HEAD_T, MUTED)
    s.line(x0, top, x1, top, RULE, .14)
    for i, (req, decl, check, res) in enumerate(L['adm_rows']):
        yc = top + pitch * (i + .5)
        ok = i == 0
        text(ca[0], baseline(yc, CODE_T), req, CODE_T, INK)
        text(ca[1], baseline(yc, size_of(decl)), decl, size_of(decl), INK if ok else RED)
        right = (measure(res, SMALL, 'bold') + 3.4) if res else 2.6
        text(ca[2], baseline(yc, SMALL), check, SMALL, INK if ok else RED, width=x1 - ca[2] - right - .6)
        mark(s, x1 - right + .9, yc, ok, k=.72)
        if res:
            text(x1 - 1.0, baseline(yc, SMALL), res, SMALL, BLUE_TXT, 'bold', align='right')

    # One time axis: the ETL commit, Agent 2's snapshot across it, maintenance, Agent N's snapshot.
    ey, eh = ay0 + ah + 1.6, 5.0
    step(s, gx, ey + eh / 2, 5, r=1.0)
    box(s, lx, ey, XC - 1.6 - lx, eh, EDGE, FACE)
    for j, line in enumerate(L['etl']):
        end = parts(s, lx + .8, ey + 2.05 + 2.3 * j, [(t, MAINT_C if j else INK, st) for t, st in line], SMALL)
        assert end < XC - 2.2, end
    eyc = ey + eh / 2
    s.line(XC - 1.6, eyc, XC, eyc, INK, LINE)
    s.circle(XC, eyc, .7, INK)
    text(XC + 1.3, baseline(eyc, SMALL), L['commit'], SMALL, INK, 'bold')

    lane, bh = 4.1, 3.2
    # Agent 2's snapshot s: opened before the commit, so the commit is not visible inside it.
    sy = ey + eh + .6
    syc = sy + lane / 2
    step(s, gx, syc, 4, r=1.0)
    s_end = 67.4
    s.rect(lx - .3, sy, s_end - lx + .3, lane, BLUE_FIELD, BLUE, LINE, r=.6)
    lane_boxes(s, syc, bh, L['boxes_s'], ((lx + .5, 18.6), (20.2, 33.4), (XC + 6.2, s_end - .5)), last=True)
    s.line(XC, sy + .2, XC, sy + lane - .2, FAINT, LINE, dash=(.7, .45))
    hw = measure(L['hidden'], SMALL, 'bold')
    s.rect(XC - hw / 2 - .5, syc - 1.2, hw + 1.0, 2.4, BLUE_FIELD, None)
    text(XC, baseline(syc, SMALL), L['hidden'], SMALL, BLUE_TXT, 'bold', 'center')
    assert XC - hw / 2 - .5 > 33.4 + 1.0 and XC + hw / 2 + .5 < XC + 6.2 - .4, hw
    text(s_end + .8, baseline(syc, SMALL), L['s'], SMALL, BLUE_TXT, 'bold', width=x1 - s_end - .9)
    # Maintenance and repair (step 6), outside any snapshot: a verdict is recorded only at a stable version.
    my = sy + lane + .5
    myc = my + lane / 2
    step(s, gx, myc, 6, r=1.0)
    text(lx + .4, baseline(myc, SMALL), L['maint'], SMALL, MUTED, width=XC - lx - 2.0)
    box(s, XC + 2.6, myc - bh / 2, x1 - XC - 2.6, bh, MAINT_C, MAINT_PALE)
    text(XC + 3.3, baseline(myc, SMALL), L['maint_box'], SMALL, INK, width=x1 - XC - 4.0)
    # Agent N's snapshot s' after the repair.
    ny = my + lane + .5
    nyc = ny + lane / 2
    step(s, gx, nyc, 4, r=1.0)
    n0 = XC + 2.0
    s.rect(n0, ny, x1 - n0, lane, BLUE_FIELD, BLUE, LINE, r=.6)
    text(lx + .4, baseline(nyc, SMALL), L['s2'], SMALL, BLUE_TXT, 'bold', width=XC - lx - 2.0)
    lane_boxes(s, nyc, bh, L['boxes_s2'], ((n0 + .6, 59.8), (61.4, 71.2), (72.8, x1 - .6)), last=False)
    # Time axis; the commit line crosses the lanes.
    ty = ny + lane + 1.3
    s.line(XC, eyc + .7, XC, sy, MUTED, LINE, dash=(.7, .45))
    s.line(XC, sy + lane, XC, ty, MUTED, LINE, dash=(.7, .45))
    arrow(s, [(lx, ty), (x1, ty)])
    text(lx + .4, ty - .75, L['time'], SMALL, MUTED)

    # The counter table in the database and the verdict store keyed by transactional versions.
    t0 = ty + 1.6
    hh = (2.55, 2.55, 4.45)
    top_t = t0 + band + head + .3
    th = top_t - t0 + sum(hh) + .3
    vx1 = 22.6
    yb = structure(s, x0, t0, vx1 - x0, th, band, L['versions'], None, BAND, INK)
    cv = (x0 + 1.0, x0 + 10.2, x0 + 16.2)
    for c, label in zip(cv, L['cols_v']):
        text(c, yb + 1.95, label, HEAD_T, MUTED)
    s.line(x0, top_t, vx1, top_t, RULE, .14)
    for i, row in enumerate(COUNTERS):
        yc = top_t + 2.5 * (i + .5)
        if i == 2:
            s.rect(x0 + .3, yc - 1.1, vx1 - x0 - .6, 2.2, MAINT_PALE, None, r=.35)
        for j, (c, v) in enumerate(zip(cv, row)):
            text(c, baseline(yc, CODE_T), v, CODE_T, MAINT_C if (i == 2 and j == 2) else INK)
    text(cv[0], baseline(top_t + 3 * 2.5 + 1.1, HEAD_T), L['sum'], HEAD_T, MUTED, width=vx1 - x0 - 1.4)

    hx0 = vx1 + 1.4
    yb = structure(s, hx0, t0, x1 - hx0, th, band, L['verdicts'], L['key'])
    chh = (hx0 + 1.0, hx0 + 32.4, hx0 + 43.6)
    for c, label in zip(chh, L['cols_h']):
        text(c, yb + 1.95, label, HEAD_T, MUTED, width=(x1 - c - .8) if c == chh[2] else None)
    s.line(hx0, top_t, x1, top_t, RULE, .14)
    y0 = top_t
    for (ids, stats, ok, writer, reuser), h in zip(L['rows_h'], hh):
        if reuser:
            s.rect(hx0 + .3, y0 + .15, x1 - hx0 - .6, h - .3, BLUE_PALE, None, r=.35)
        elif not ok:
            s.rect(hx0 + .3, y0 + .15, x1 - hx0 - .6, h - .3, RED_PALE, RED, LINE, r=.35, dash=(.7, .45))
        yc = y0 + (h / 2 if len(ids) == 1 else 1.3)
        for j, label in enumerate(ids):
            text(chh[0], baseline(yc + 2.05 * j, CODE_T), label, CODE_T, INK, width=chh[1] - chh[0] - .3)
        text(chh[1], baseline(yc, CODE_T), stats, CODE_T, INK if ok else RED)
        mark(s, chh[2] - 1.15, yc, ok, k=.68)
        end = chh[2] + text(chh[2], baseline(yc, SMALL), writer, SMALL, INK if writer in ('publication', '发布')
                            else MAINT_C)
        if reuser:
            end += text(end, baseline(yc, SMALL), r' $\rightarrow$ ' + reuser, SMALL, BLUE_TXT, 'bold')
        assert end < x1 - .6, (writer, end)
        y0 += h
    assert t0 + th < H - .3, t0 + th
