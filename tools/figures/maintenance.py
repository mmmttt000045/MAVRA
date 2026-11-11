"""Shared, selective maintenance and restricted repair (Section IV-D), single column.

Top: the outcome store seen from the definitions that use it. The four seeded
definitions of the maintenance experiments (store revenue, returned amount,
return rate, Electronics revenue) reference 7 distinct conditions 15 times:
the date_dim key check serves all four, and one key check on store_returns is
the grain of one definition and the join cardinality of another. Markers 1-5
are Fig. 3's (Electronics revenue's conditions); a key marks KeyUnique, a
gauge Unmatched. A write (bolt) selects the conditions whose dep(c) contains
the written table, and each reruns once for all definitions and agents. The
squares count checks: solid ones run, outlined ones would also run in a full
recheck per definition (2 of 5 after the item load, 3 of 12 after a
store_sales append).

Bottom: the restricted repair after the item key check fails at item's new
stamp (1001 rows over 1000 keys; repair is tried only for 1 < rows/keys < 1.5).
Candidate columns are item's non-key columns with at most 20 distinct values
(i_current_price, with 50, is not tried). Each bar is the row count of one
value; a value qualifies only if its bar reaches the distinct key count, and
then only if the filtered rows have one row per key. Exactly one filter
passes, so it is adopted (stored as grain:item for other definitions on item),
giving join and metric revision 1 after regression on the learning snapshot.

Values: the fixture of src/metricbench.rs (1000 items in 5 categories of 200,
i_current_price with 50 values) plus the running example's one history row
for item 17 ('Electronics', 'N'), so 1001 rows, Electronics 201. Conditions
follow bound_conditions() for the seeded metrics of src/integration_tests.rs
(M1, M2, M3, M5); recheck counts follow from their dep sets; the search
follows repair_grain() in src/middle.rs.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import INK, MUTED, RULE  # noqa: E402
from smallparts import (BLUE, BLUE_TXT, CODE_T, HEAD_T, MAINT_C, MAINT_PALE,  # noqa: E402
                        SMALL, baseline, bolt, gauge_icon, key_icon, mark, rerun, stamp, step, structure, units)
from extraction import marker  # noqa: E402

NAME = 'maintenance'
W, H = style.COLUMN, 50.2

DEFS = ('SR', 'RA', 'RR', 'ER')
R = r'$\rightarrow$'
# (marker, family, table or join, definitions that reference it, rerun after the item load, after a sales append)
ROWS = (
    (1, 'key', '`store_sales.`$K$', 'SR RR ER', False, True),
    (2, 'key', '`item.i_item_sk`', 'ER', True, False),
    (3, 'loss', f'`store_sales`{R}`item`', 'ER', True, True),
    (4, 'key', '`date_dim.d_date_sk`', 'SR RA RR ER', False, False),
    (5, 'loss', f'`store_sales`{R}`date_dim`', 'SR RR ER', False, True),
    (6, 'key', '`store_returns.`$K_r$', 'RA RR', False, False),
    (7, 'loss', f'`store_returns`{R}`date_dim`', 'RA', False, False),
)
# Conditions per definition (for the full-recheck count).
PER_DEF = {d: sum(d in r[3].split() for r in ROWS) for d in DEFS}
KEYS = 1000                       # distinct item keys
# Candidate columns of item (distinct values) and the row count of each value at stamp <9662,1001,1>.
CANDS = (('`i_is_current`', 2, (("`'Y'`", 1000), ("`'N'`", 1))),
         ('`i_category`', 5, ((None, (200, 200, 200, 200, 201)),)))

LABELS = {
    'en': {
        'store': (('Shared outcomes in $\\mathcal{H}$', 'bold'),),
        'store_note': '7 outcomes, 15 references',
        'families': ('KeyUnique', 'Unmatched'),
        'writes': ('`item` load', 'sales append'),
        'legend': ('rerun once for all agents', 'full recheck per definition'),
        'repair': (('Repair: a filter on ', 'bold'), ('`item`', 'sans'), (' that restores one row per key', 'bold')),
        'trigger': ((' at ', INK), (stamp('9662', '1001', '1'), MAINT_C),
                    (': `1001` rows, `1000` keys; ratio in (1, 1.5), so search', INK)),
        'col': 'column (distinct values)', 'bars': 'rows carrying each value', 'keys': 'keys `1000`',
        'each': 'each', 'pass': 'sole pass',
        'skip': ('`i_current_price` (50)', 'over 20 values: not tried'),
        'adopt': (('kept as ', INK), ('`grain:item`', MAINT_C), ('; join and metric rev 1 after regression', INK)),
    },
    'zh': {
        'store': (('$\\mathcal{H}$ 中的共享检查结果', 'bold'),),
        'store_note': '7 条结果，15 处引用',
        'families': ('KeyUnique', 'Unmatched'),
        'writes': ('`item` 载入', '销售追加'),
        'legend': ('对全部智能体只重跑一次', '整定义重查'),
        'repair': (('修复：在 ', 'bold'), ('`item`', 'sans'), (' 上找恢复每键一行的过滤', 'bold')),
        'trigger': ((' 在 ', INK), (stamp('9662', '1001', '1'), MAINT_C),
                    ('：`1001` 行、`1000` 个键；比值在 (1, 1.5) 内，于是搜索', INK)),
        'col': '列（不同取值数）', 'bars': '各取值的行数', 'keys': '键数 `1000`',
        'each': '每个', 'pass': '唯一通过',
        'skip': ('`i_current_price` (50)', '超过 20 个取值，不尝试'),
        'adopt': (('存为 ', INK), ('`grain:item`', MAINT_C), ('；回归后发布连接与指标修订版 1', INK)),
    },
}


def family_icon(s, x, yc, family):
    return key_icon(s, x, yc, INK) if family == 'key' else gauge_icon(s, x, yc)


def draw(s, lang):
    L = LABELS[lang]
    text = s.text
    x0, x1 = 1.0, 83.6
    band = 2.9

    # The outcome store as a condition-by-definition table, with the conditions each write selects.
    ay, pitch, head = 1.0, 2.45, 2.6
    top = ay + band + head + .2
    n = len(ROWS)
    total_y = top + n * pitch
    ah = total_y + 3.0 - ay
    yb = structure(s, x0, ay, x1 - x0, ah, band, L['store'], L['store_note'])
    cx = {d: 35.4 + 4.9 * i for i, d in enumerate(DEFS)}           # definition columns (centres)
    wx = (61.8, 75.6)                                                # write columns (centres)
    hy = yb + head / 2 + .1
    hx = x0 + 1.0
    for fam, label in zip(('key', 'loss'), L['families']):
        hx += family_icon(s, hx, hy, fam) + .6
        hx += text(hx, baseline(hy, HEAD_T), label, HEAD_T, MUTED) + 1.6
    assert hx < cx['SR'] - 2.0, hx
    for d in DEFS:
        text(cx[d], baseline(hy, HEAD_T), d, HEAD_T, INK, 'bold', 'center')
    for x, label in zip(wx, L['writes']):
        w = measure(label, HEAD_T, 'bold') + 1.5
        bolt(s, x - w / 2 + .45, hy, 1.9, MAINT_C)
        text(x - w / 2 + 1.5, baseline(hy, HEAD_T), label, HEAD_T, MAINT_C, 'bold')
        assert w < 13.0, w
    s.line(x0, top, x1, top, RULE, .14)
    for i, (num, fam, where, users, item_load, append) in enumerate(ROWS):
        yc = top + pitch * (i + .5)
        if item_load:
            s.rect(x0 + .3, yc - pitch / 2 + .12, x1 - x0 - .6, pitch - .24, MAINT_PALE, None, r=.35)
        marker(s, x0 + 1.7, yc, num, r=.8)
        family_icon(s, x0 + 3.0, yc, fam)
        text(x0 + 6.3, baseline(yc, CODE_T), where, CODE_T, INK, width=cx['SR'] - 1.4 - x0 - 6.3)
        us = users.split()
        if len(us) > 1:                              # one outcome, several definitions
            s.line(cx[us[0]], yc, cx[us[-1]], yc, BLUE, .22)
        for d in us:
            s.circle(cx[d], yc, .58, BLUE)
        for x, hit in zip(wx, (item_load, append)):
            if hit:
                rerun(s, x, yc, .62, MAINT_C)
        if num == 2:                                 # the item key check fails at the new stamp
            mark(s, wx[0] + 2.0, yc, False, k=.75)
    s.line(x0, total_y, x1, total_y, RULE, .14)
    # Checks run per write: solid run once for all agents, outlined only in a full recheck per definition.
    ty = total_y + 1.5
    counts = ((2, PER_DEF['ER']), (3, PER_DEF['SR'] + PER_DEF['RR'] + PER_DEF['ER']))
    assert counts == ((2, 5), (3, 12)), counts
    lx = x0 + 1.0
    for k, label in enumerate(L['legend']):
        lx += units(s, lx, ty, 2 if k else 1, 1, MAINT_C) + .6
        lx += text(lx, baseline(ty, SMALL), label, SMALL, MUTED) + 1.8
    assert lx < wx[0] - 5.0, lx
    for x, (ours, whole) in zip(wx, counts):
        label = f'{ours}/{whole}'
        lw = measure(label, SMALL, 'bold')
        uw = min(whole, 6) * 1.02 - .22
        xs = x - (uw + .8 + lw) / 2
        units(s, xs, ty, whole, ours, MAINT_C, per_row=6)
        text(xs + uw + .8, baseline(ty, SMALL), label, SMALL, MAINT_C, 'bold')

    # Restricted repair of the failing key check (step 6).
    by = ay + ah + 1.6
    rp, cat_h = 2.3, 3.1
    btop = by + band + 2.55 + 2.95
    bh = btop + 2 * rp + cat_h + rp + 2.55 - by
    yb = structure(s, x0, by, x1 - x0, bh, band, L['repair'], None, MAINT_PALE, INK)
    step(s, x1 - 2.2, by + band / 2 + .05, 6, r=1.05)
    y_tr = yb + 1.4
    marker(s, x0 + 1.7, y_tr, 2, r=.8)
    end = x0 + 3.0 + key_icon(s, x0 + 3.0, y_tr, INK) + .8
    end += text(end, baseline(y_tr, CODE_T), '`item.i_item_sk`', CODE_T, INK)
    for label, color in L['trigger']:
        size = CODE_T if label.startswith(r'$\langle') else SMALL
        end += text(end, baseline(y_tr, size), label, size, color)
    assert end < x1 - .8, end
    # Bars: rows carrying each value of each candidate column, against the distinct key count.
    bx, bw = x0 + 25.4, 33.0
    kx = bx + bw                                     # the key line
    sc = bw / KEYS
    hy = y_tr + 2.85
    text(x0 + 1.0, hy, L['col'], HEAD_T, MUTED, width=bx - x0 - 7.0)
    text(bx, hy, L['bars'], HEAD_T, MUTED)
    text(kx, hy, L['keys'], HEAD_T, MAINT_C, 'bold', 'center')
    s.line(x0, btop, x1, btop, RULE, .14)
    y = btop
    vx = bx - 1.0
    for col, nd, values in CANDS:
        first = True
        for value, rows in values:
            h = cat_h if isinstance(rows, tuple) else rp
            yc = y + h / 2
            if first:
                text(x0 + 1.0, baseline(yc, CODE_T), col, CODE_T, INK)
                text(x0 + 1.0 + measure(col, CODE_T) + .6, baseline(yc, SMALL), f'({nd})', SMALL, MUTED)
                first = False
            text(vx, baseline(yc, CODE_T if value else SMALL), value or L['each'], CODE_T if value else SMALL,
                 INK, align='right')
            if isinstance(rows, tuple):              # the five categories, each far short of the key count
                bh_ = .42
                for k, r in enumerate(rows):
                    s.rect(bx, yc - 2.5 * bh_ - .4 + k * (bh_ + .2), r * sc, bh_, '#B8B5AE', None)
                text(bx + max(rows) * sc + .8, baseline(yc, CODE_T), f'`{min(rows)}`–`{max(rows)}`', CODE_T, MUTED)
                mark(s, kx + 2.0, yc, False, k=.7)
            elif rows == KEYS:                       # reaches the key line, and one row per key after the filter
                s.rect(bx, yc - .62, rows * sc, 1.24, BLUE, None)
                ex = kx + 1.0
                ex += text(ex, baseline(yc, CODE_T), '`1000/1000`', CODE_T, BLUE_TXT)
                mark(s, ex + 1.1, yc, True, k=.72)
                text(ex + 2.4, baseline(yc, SMALL), L['pass'], SMALL, BLUE_TXT, 'bold', width=x1 - ex - 3.0)
            else:
                s.rect(bx, yc - .62, max(rows * sc, .3), 1.24, '#B8B5AE', None)
                text(bx + 1.1, baseline(yc, CODE_T), f'`{rows}`', CODE_T, MUTED)
                mark(s, kx + 2.0, yc, False, k=.7)
            y += h
        s.line(x0 + .6, y, x1 - .6, y, RULE, .1)
    s.line(kx, btop - .3, kx, y, MAINT_C, .2, dash=(.6, .4))
    # The column over the limit, never tried.
    yc = y + rp / 2
    w = text(x0 + 1.0, baseline(yc, CODE_T), L['skip'][0], CODE_T, MUTED)
    s.line(x0 + .8, yc - .1, x0 + 1.2 + w, yc - .1, MUTED, .14)
    text(bx, baseline(yc, SMALL), L['skip'][1], SMALL, MUTED)
    y += rp
    end = x0 + 1.0
    for label, color in L['adopt']:
        size = CODE_T if label.startswith('`') else SMALL
        end += text(end, baseline(y + 1.25, size), label, size, color)
    assert end < x1 - .8, end
    assert by + bh < H - .25, by + bh
