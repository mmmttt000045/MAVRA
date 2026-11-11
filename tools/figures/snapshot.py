"""Admission and snapshot-bound execution with transactional versions (Section IV-E), single column.

Top: what Admissible(q, R) checks before a query runs (Algorithm 2, line 2):
a request declaring the current revision passes; one declaring a retired
revision is told which revision is current; a query that drops the filter the
store now requires on item is rejected (it would count item 17 twice).
Middle, on one time axis: the ETL transaction inserts the history row and, in
the same transaction, its statement trigger bumps one of item's 16 counter
rows in mavra_versions (drawn as 16 cells; v_s(item) is their sum). Agent 2's
snapshot s read v_s(item) = 0 before the commit, so it reuses the verdict at
item = 0 and counts item 17 once; the maintenance and repair checks of step 6
run outside any snapshot and record a verdict only if they read the same
v(item) before and after the check; Agent N's snapshot s' reads item = 1 and
reuses the repaired verdict.
Bottom: the verdict store H_tx, keyed by id(c) @ v_s(dep(c)), with who wrote
each verdict and which snapshot reused it.

Values follow the running example (counters are 0 when the triggers are
installed after loading; one ETL statement bumps one shard, pid mod 16; key
counts from the fixture with one history row for item 17). Rejection reasons
paraphrase check_metric_refs and review_sql; the recording rule is
exec_check's before/after read of the counters (src/middle.rs).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import EDGE, FACE, INK, MUTED, RED, WHITE  # noqa: E402
from smallparts import (BLUE, BLUE_FIELD, BLUE_PALE, BLUE_TXT, CODE_T, EXEC_C, LINE, MAINT_C,  # noqa: E402
                        MAINT_PALE, RED_PALE, SMALL, arrow, baseline, box, mark, parts, step, structure, tag)

NAME = 'snapshot'
W, H = style.COLUMN, 47.0
XC = 46.0                     # the ETL commit
FAINT = '#A9C3E3'             # the commit, as seen from inside a snapshot
SHARD = 5                     # the shard the ETL backend bumps (pid mod 16)

LABELS = {
    'en': {
        'adm': (('Admission ', 'bold'), (r'$\mathrm{Admissible}(q,\mathcal{R})$', 'bold')),
        'adm_rows': (('`run_metric`', '`ER@r1`', 'current, required filter kept', r'runs in $s$′'),
                     ('`run_sql`', '`ER@r0`', 'r0 retired; current is r1', ''),
                     ('`run_sql`', 'none', "drops `i_is_current='Y'`: item 17 twice", '')),
        'etl': (('ETL: ', 'bold'), ('`INSERT`', 'sans'), (" history row `(17,...,'N')`", 'sans')),
        'shards': '`mavra_versions`, `item`:',
        'commit': 'COMMIT', 'hidden': 'not visible', 'time': 'time',
        's': r'$s$: Agent 2', 'maint': 'outside snapshots', 's2': r'$s$′: Agent N',
        'boxes_s': (('L5', '`item=0`'), ('L7', 'hit'), ('L11', '17 once')),
        'check': 'check', 'record': 'record',
        'boxes_s2': (('L5', '`item=1`'), ('L7', 'hit'), ('L11', 'runs')),
        'verdicts': ((r'Verdicts $\mathcal{H}_\mathrm{tx}$', 'bold'),),
        'key': r'key $\mathrm{id}(c)$ @ $v_s(\mathrm{dep}(c))$',
        'writers': ('publication', 'maintenance', 'repair'),
    },
    'zh': {
        'adm': (('准入 ', 'bold'), (r'$\mathrm{Admissible}(q,\mathcal{R})$', 'bold')),
        'adm_rows': (('`run_metric`', '`ER@r1`', '当前修订，保留必需过滤', r'在 $s$′ 中执行'),
                     ('`run_sql`', '`ER@r0`', 'r0 已失效；当前为 r1', ''),
                     ('`run_sql`', '未声明', "缺 `i_is_current='Y'`：商品 17 算两次", '')),
        'etl': (('ETL：', 'bold'), ('`INSERT`', 'sans'), (" 历史行 `(17,...,'N')`", 'sans')),
        'shards': '`mavra_versions`，`item`：',
        'commit': '提交', 'hidden': '看不到', 'time': '时间',
        's': r'$s$：智能体 2', 'maint': '在快照之外', 's2': r'$s$′：智能体 N',
        'boxes_s': (('L5', '`item=0`'), ('L7', '命中'), ('L11', '算一次')),
        'check': '检查', 'record': '记录',
        'boxes_s2': (('L5', '`item=1`'), ('L7', '命中'), ('L11', '执行')),
        'verdicts': ((r'结论 $\mathcal{H}_\mathrm{tx}$', 'bold'),),
        'key': r'键 $\mathrm{id}(c)$ @ $v_s(\mathrm{dep}(c))$',
        'writers': ('发布', '维护', '修复'),
    },
}

# H_tx entries: key (id(c), version part), rows/keys, verdict, index of the writer label, the snapshot reusing it.
VERDICTS = ((('`KeyUnique(item.i_item_sk)`', '`@item=0`'), '`1000/1000`', True, 0, '$s$'),
            (('`KeyUnique(item.i_item_sk)`', '`@item=1`'), '`1001/1000`', False, 1, ''),
            (("`KeyUnique(item.i_item_sk,i_is_current='Y')`", '`@item=1`'), '`1000/1000`', True, 2, '$s$′'))


def size_of(label):
    return CODE_T if label.startswith('`') else SMALL


def lane_boxes(s, yc, h, items, spans, last=None):
    """One lane's steps: an L<n> tag and a label per box, joined by arrows."""
    for k, ((t, label), (a, b)) in enumerate(zip(items, spans)):
        done = last is not None and k == len(spans) - 1
        box(s, a, yc - h / 2, b - a, h, BLUE if done else EDGE, BLUE_PALE if done else WHITE)
        w = tag(s, a + .5, yc, t, EXEC_C)
        room = b - a - w - 1.4 - (2.0 if done and last else 0)
        color = BLUE_TXT if done else (MAINT_C if label.startswith('`item=') else INK)
        s.text(a + .5 + w + .5, baseline(yc, size_of(label)), label, size_of(label), color, width=room)
        if done and last:
            mark(s, b - 1.3, yc, True, k=.72)
        if k + 1 < len(spans):
            arrow(s, [(b, yc), (spans[k + 1][0], yc)])


def shards(s, x, yc, bumped, cell=.66, gap=.13, n=16):
    """The 16 counter rows of one table as cells: all 0, the bumped one filled; returns the width."""
    for i in range(n):
        cx = x + i * (cell + gap)
        if i == bumped:
            s.rect(cx, yc - cell * .75, cell, cell * 1.5, MAINT_C, None, r=.1)
        else:
            s.rect(cx, yc - cell * .75, cell, cell * 1.5, WHITE, EDGE, .1, r=.1)
    return n * (cell + gap) - gap


def flag(s, x, yc, label):
    """A counter read, v = n, as a small teal pill; returns its width."""
    w = measure(label, CODE_T) + 1.0
    s.rect(x, yc - .95, w, 1.9, WHITE, MAINT_C, .16, r=.95)
    s.text(x + .5, baseline(yc, CODE_T), label, CODE_T, MAINT_C)
    return w


def draw(s, lang):
    L = LABELS[lang]
    text = s.text
    x0, x1 = 1.0, 83.6
    band, pitch = 2.9, 2.45
    gx, lx = 2.3, 5.0                                # badge gutter; lanes start at lx

    # Admission (Algorithm 2, line 2): declared revisions and required filters, before any snapshot opens.
    ay0 = 1.0
    top = ay0 + band + .25
    ah = top - ay0 + 3 * pitch + .25
    structure(s, x0, ay0, x1 - x0, ah, band, L['adm'], None, BLUE_PALE, INK)
    tag(s, x1 - 1.0, ay0 + .15 + band / 2, 'L2', EXEC_C, align='right')
    cw = max(measure(f'{r} {d}', CODE_T) for r, d, _, _ in L['adm_rows']) + 1.4
    cx = x0 + 1.0 + cw + 1.6                         # verdict marks
    for i, (req, decl, check, res) in enumerate(L['adm_rows']):
        yc = top + pitch * (i + .5)
        ok = i == 0
        s.rect(x0 + 1.0, yc - .98, cw, 1.96, WHITE, EDGE, .14, r=.98)    # the call, as an API request
        x = x0 + 1.7 + text(x0 + 1.7, baseline(yc, CODE_T), req + ' ', CODE_T, INK)
        text(x, baseline(yc, size_of(decl)), decl, size_of(decl), INK if ok else RED)
        mark(s, cx, yc, ok, k=.72)
        end = cx + 1.6 + text(cx + 1.6, baseline(yc, SMALL), check, SMALL, INK if ok else RED)
        if res:
            end += text(end, baseline(yc, SMALL), r' $\rightarrow$ ' + res, SMALL, BLUE_TXT, 'bold')
        assert end < x1 - .8, end

    # One time axis: the ETL transaction and its commit, Agent 2's snapshot across it, maintenance, Agent N's snapshot.
    ey, eh = ay0 + ah + 1.5, 5.1
    step(s, gx, ey + eh / 2, 5, r=1.0)
    box(s, lx, ey, XC - 1.6 - lx, eh, EDGE, FACE)
    end = parts(s, lx + .8, ey + 2.05, [(t, INK, st) for t, st in L['etl']], SMALL)
    assert end < XC - 2.2, end
    y2 = ey + 3.85
    end = lx + .8 + text(lx + .8, baseline(y2, CODE_T), L['shards'], CODE_T, MAINT_C) + .8
    end += shards(s, end, y2, SHARD) + .6
    end += text(end, baseline(y2, CODE_T), '`+1`', CODE_T, MAINT_C, 'bold')
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
    # Maintenance and repair (step 6), outside any snapshot: a check is recorded only if v(item) did not move.
    my = sy + lane + .5
    myc = my + lane / 2
    step(s, gx, myc, 6, r=1.0)
    text(lx + .4, baseline(myc, SMALL), L['maint'], SMALL, MUTED, width=XC - lx - 2.0)
    mx = XC + 2.6
    box(s, mx, myc - bh / 2, x1 - mx, bh, MAINT_C, MAINT_PALE)
    x = mx + .7
    x += flag(s, x, myc, '`v=1`')
    cw = measure(L['check'], SMALL) + 1.4
    arrow(s, [(x, myc), (x + 1.6, myc)], MAINT_C)
    x += 1.6
    s.rect(x, myc - .95, cw, 1.9, WHITE, EDGE, .14, r=.3)
    text(x + cw / 2, baseline(myc, SMALL), L['check'], SMALL, INK, align='center')
    x += cw
    arrow(s, [(x, myc), (x + 1.6, myc)], MAINT_C)
    x += 1.6
    x += flag(s, x, myc, '`v=1`') + .8
    x += text(x, baseline(myc, SMALL), r'$=$ ', SMALL, MAINT_C, 'bold')
    x += text(x, baseline(myc, SMALL), L['record'], SMALL, MAINT_C, 'bold')
    assert x < x1 - .6, x
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
    tw = text(x0 + .3, baseline(ty, SMALL), L['time'], SMALL, MUTED)
    arrow(s, [(max(lx, x0 + .3 + tw + .7), ty), (x1, ty)])

    # The verdict store keyed by transactional versions: who wrote each verdict, which snapshot reused it.
    t0 = ty + 1.6
    top_t = t0 + band + .25
    th = top_t - t0 + 3 * pitch + .25
    structure(s, x0, t0, x1 - x0, th, band, L['verdicts'], L['key'])
    chh = (x0 + 1.0, x0 + 48.6, x0 + 60.4)
    for i, (key, stats, ok, writer, reuser) in enumerate(VERDICTS):
        yc = top_t + pitch * (i + .5)
        if reuser:
            s.rect(x0 + .3, yc - pitch / 2 + .12, x1 - x0 - .6, pitch - .24, BLUE_PALE, None, r=.35)
        else:
            s.rect(x0 + .3, yc - pitch / 2 + .12, x1 - x0 - .6, pitch - .24, RED_PALE, RED, LINE, r=.35,
                   dash=(.7, .45))
        kw = text(chh[0], baseline(yc, CODE_T), key[0], CODE_T, INK)
        kw += text(chh[0] + kw, baseline(yc, CODE_T), key[1], CODE_T, MAINT_C)
        assert chh[0] + kw < chh[1] - .4, kw
        text(chh[1], baseline(yc, CODE_T), stats, CODE_T, INK if ok else RED)
        mark(s, chh[2] - 1.1, yc, ok, k=.68)
        name = L['writers'][writer]
        end = chh[2] + text(chh[2], baseline(yc, SMALL), name, SMALL, INK if writer == 0 else MAINT_C)
        if reuser:
            end += text(end, baseline(yc, SMALL), r' $\rightarrow$ ' + reuser, SMALL, BLUE_TXT, 'bold')
        assert end < x1 - .6, (name, end)
    assert t0 + th < H - .25, t0 + th
