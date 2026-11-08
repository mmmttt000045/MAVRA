"""Shared, selective maintenance and restricted repair (Section IV-D), single column.

Top: the outcome store seen from the definitions that use it. The four seeded
definitions of the maintenance experiments (store revenue, returned amount,
return rate, Electronics revenue) reference 7 distinct conditions 15 times:
the date_dim key check serves all four, and one key check on store_returns is
the grain of one definition and the join cardinality of another. A write
selects the conditions whose dep(c) contains the written table, and each runs
once for all definitions and agents: 2 rechecks after the item load (5 if each
affected definition were rechecked whole), 3 after a store_sales append (12).

Bottom: the restricted repair after the item key check fails at item's new
stamp (1001 rows over 1000 keys; repair is tried only for 1 < rows/keys < 1.5).
Candidate columns are item's columns with at most 20 distinct values; a value
qualifies only if exactly as many rows carry it as there are keys, and then
only if the filtered rows have one row per key. Exactly one filter passes, so
it is adopted (stored as grain:item for other definitions on item), giving
join and metric revision 1 after regression on the learning snapshot.

Values: the fixture of src/metricbench.rs (1000 items in 5 categories of 200,
i_current_price with 50 values) plus the running example's one history row
for item 17 ('Electronics', 'N'), so 1001 rows, Electronics 201. Conditions
follow bound_conditions() for the seeded metrics of src/integration_tests.rs
(M1, M2, M3, M5); recheck counts follow from their dep sets.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import INK, MUTED, RULE  # noqa: E402
from smallparts import (BLUE, BLUE_PALE, BLUE_TXT, CODE_T, HEAD_T, MAINT_C, MAINT_PALE,  # noqa: E402
                        SMALL, baseline, mark, stamp, step, structure)

NAME = 'maintenance'
W, H = style.COLUMN, 53.2

DEFS = ('SR', 'RA', 'RR', 'ER')
R = r'$\rightarrow$'
# (condition, definitions that reference it, rerun after the item load, rerun after a sales append)
ROWS = (
    ('`KeyUnique(store_sales.`$K$`)`', 'SR RR ER', False, True),
    ('`KeyUnique(store_returns.`$K_r$`)`', 'RA RR', False, False),
    ('`KeyUnique(item.i_item_sk)`', 'ER', True, False),
    ('`KeyUnique(date_dim.d_date_sk)`', 'SR RA RR ER', False, False),
    (f'`Unmatched(store_sales`{R}`item)`', 'ER', True, True),
    (f'`Unmatched(store_sales`{R}`date_dim)`', 'SR RR ER', False, True),
    (f'`Unmatched(store_returns`{R}`date_dim)`', 'RA', False, False),
)
# Conditions per definition (for the whole-definition recheck count).
PER_DEF = {d: sum(d in r[1].split() for r in ROWS) for d in DEFS}

LABELS = {
    'en': {
        'store': (('Outcomes in $\\mathcal{H}$ and the definitions using them', 'bold'),),
        'store_note': '15 references, 7 outcomes',
        'cond': r'condition $c$ (one outcome per $V(\mathrm{dep}(c))$)', 'used': 'used by', 'rerun': 'rerun after',
        'writes': ('`item` load', 'sales append'),
        'total': 'checks, each once for all agents (whole-definition recheck)',
        'repair': (('Repair: a filter on ', 'bold'), ('`item`', 'sans'), (' that restores one row per key', 'bold')),
        'trigger': (('`KeyUnique(item.i_item_sk)` at ', INK), (stamp('9662', '1001', '1'), MAINT_C),
                    (': `1001` rows, `1000` keys; ratio $<1.5$, so search', INK)),
        'cols': ('column (distinct values)', 'value', 'rows', 'rows/keys under it', ''),
        'cands': ((r'`i_is_current` (2)', "`'Y'`", '`1000`', '`1000/1000`', 'the only pass'),
                  ('', "`'N'`", '`1`', '', r'pruned: rows $\neq$ keys'),
                  (r'`i_category` (5)', 'each value', '`200`–`201`', '', r'pruned: rows $\neq$ keys')),
        'skip': '`i_current_price` has 50 values: not a candidate (limit 20)',
        'adopt': (('exactly one filter passes: kept as ', INK), ('`grain:item`', INK),
                  ('; join, metric rev 1 after regression', INK)),
    },
    'zh': {
        'store': (('$\\mathcal{H}$ 中的检查结果及引用它们的定义', 'bold'),),
        'store_note': '15 处引用，7 条结果',
        'cond': r'条件 $c$（每个 $V(\mathrm{dep}(c))$ 一条结果）', 'used': '引用者', 'rerun': '写入后重跑',
        'writes': ('`item` 载入', '销售追加'),
        'total': '次检查，各对全部智能体只跑一次（整定义重查）',
        'repair': (('修复：在 ', 'bold'), ('`item`', 'sans'), (' 上找恢复每键一行的过滤', 'bold')),
        'trigger': (('`KeyUnique(item.i_item_sk)` 在 ', INK), (stamp('9662', '1001', '1'), MAINT_C),
                    ('：`1001` 行、`1000` 个键；比值 $<1.5$，于是搜索', INK)),
        'cols': ('列（不同取值数）', '取值', '行数', '过滤后 行/键', ''),
        'cands': ((r'`i_is_current` (2)', "`'Y'`", '`1000`', '`1000/1000`', '唯一通过'),
                  ('', "`'N'`", '`1`', '', r'剪枝：行数 $\neq$ 键数'),
                  (r'`i_category` (5)', '每个取值', '`200`–`201`', '', r'剪枝：行数 $\neq$ 键数')),
        'skip': '`i_current_price` 有 50 个取值，不作候选（上限 20）',
        'adopt': (('恰好一个过滤通过：存为 ', INK), ('`grain:item`', INK), ('；回归后发布连接与指标修订版 1', INK)),
    },
}


def is_code(label):
    return label.startswith('`') or label.startswith(r'$\langle')


def draw(s, lang):
    L = LABELS[lang]
    text = s.text
    x0, x1 = 1.0, 83.6
    band = 2.9

    # The outcome store as a condition-by-definition table, with the conditions each write selects.
    ay, pitch = 1.0, 2.5
    head1, head2 = 2.25, 2.35
    top = ay + band + head1 + head2 + .35
    n = len(ROWS)
    total_y = top + n * pitch
    ah = total_y + 2.7 - ay
    yb = structure(s, x0, ay, x1 - x0, ah, band, L['store'], L['store_note'])
    cx = {d: 38.6 + 4.9 * i for i, d in enumerate(DEFS)}           # definition columns (centres)
    wx = (63.4, 76.6)                                                # write columns (centres)
    h1, h2 = yb + 1.9, yb + head1 + 1.95
    text(x0 + 1.0, h2, L['cond'], HEAD_T, MUTED, width=cx['SR'] - 2.2 - x0 - 1.0)
    text((cx['SR'] + cx['ER']) / 2, h1, L['used'], HEAD_T, MUTED, align='center')
    text((wx[0] + wx[1]) / 2, h1, L['rerun'], HEAD_T, MUTED, align='center')
    for d in DEFS:
        text(cx[d], h2, d, HEAD_T, INK, 'bold', 'center')
    for x, label in zip(wx, L['writes']):
        w = text(x, h2, label, HEAD_T, MAINT_C, 'bold', 'center')
        assert w < 12.4, w
    s.line(x0, top, x1, top, RULE, .14)
    for i, (cid, users, item_load, append) in enumerate(ROWS):
        yc = top + pitch * (i + .5)
        if item_load:
            s.rect(x0 + .3, yc - pitch / 2 + .15, x1 - x0 - .6, pitch - .3, MAINT_PALE, None, r=.35)
        text(x0 + 1.0, baseline(yc, CODE_T), cid, CODE_T, INK, width=cx['SR'] - 2.2 - x0 - 1.0)
        for d in users.split():
            s.circle(cx[d], yc, .55, BLUE)
        for x, hit in zip(wx, (item_load, append)):
            if hit:
                s.circle(x, yc, .62, MAINT_C)
            else:
                s.line(x - .6, yc, x + .6, yc, RULE, .2)
        if i == 2:                                  # the item key check fails at the new stamp
            mark(s, wx[0] + 2.1, yc, False, k=.75)
    s.line(x0, total_y, x1, total_y, RULE, .14)
    ty = total_y + 1.35
    counts = ((2, PER_DEF['ER']), (3, PER_DEF['SR'] + PER_DEF['RR'] + PER_DEF['ER']))
    assert counts == ((2, 5), (3, 12)), counts
    text(x0 + 1.0, baseline(ty, SMALL), L['total'], SMALL, MUTED, width=wx[0] - 5.5 - x0 - 1.0)
    for x, (ours, whole) in zip(wx, counts):
        parts_w = measure(f'{ours}', SMALL, 'bold') + measure(f' ({whole})', SMALL)
        xs = x - parts_w / 2
        xs += text(xs, baseline(ty, SMALL), f'{ours}', SMALL, MAINT_C, 'bold')
        text(xs, baseline(ty, SMALL), f' ({whole})', SMALL, MUTED)

    # Restricted repair of the failing key check (step 6).
    by = ay + ah + 2.0
    rows_c = L['cands']
    cpitch = 2.45
    btop = by + band + 2.95 + 2.55 + .4
    bh = btop + len(rows_c) * cpitch + 2.5 * 2 + .3 - by
    yb = structure(s, x0, by, x1 - x0, bh, band, L['repair'], None, MAINT_PALE, INK)
    step(s, x1 - 2.2, by + band / 2 + .05, 6, r=1.05)
    y_tr = yb + 1.45
    end = x0 + 1.0
    for label, color in L['trigger']:
        size = CODE_T if is_code(label) else SMALL
        end += text(end, baseline(y_tr, size), label, size, color)
    assert end < x1 - .8, end
    cc = (x0 + 1.0, x0 + 24.6, x0 + 37.0, x0 + 46.6, x0 + 62.0)
    hy = y_tr + 2.85
    for c, label in zip(cc, L['cols']):
        if label:
            text(c, hy, label, HEAD_T, MUTED)
    s.line(x0, btop, x1, btop, RULE, .14)
    for i, row in enumerate(rows_c):
        yc = btop + cpitch * (i + .5)
        ok = i == 0
        if ok:
            s.rect(x0 + .3, yc - cpitch / 2 + .15, x1 - x0 - .6, cpitch - .3, BLUE_PALE, None, r=.35)
        for j, (c, v) in enumerate(zip(cc, row)):
            if not v:
                continue
            size = CODE_T if v.startswith('`') else SMALL
            color = BLUE_TXT if (ok and j == 4) else (MUTED if j == 4 else INK)
            nxt = cc[j + 1] if j < 4 else x1 - .8
            pad = 2.0 if j == 4 else 0
            text(c + pad, baseline(yc, size), v, size, color, 'bold' if (ok and j == 4) else 'sans',
                 width=nxt - c - .4 - pad)
        if ok:
            mark(s, cc[4] + .8, yc, True, k=.75)
        else:
            s.line(cc[4] + .2, yc, cc[4] + 1.4, yc, RULE, .2)
    ny = btop + len(rows_c) * cpitch + 1.35
    text(x0 + 1.0, baseline(ny, SMALL), L['skip'], SMALL, MUTED, width=x1 - x0 - 2.0)
    end = x0 + 1.0
    for label, color in L['adopt']:
        size = CODE_T if label.startswith('`') else SMALL
        end += text(end, baseline(ny + 2.5, size), label, size, MAINT_C if label.startswith('`') else color)
    assert end < x1 - .8, end
    assert by + bh < H - .3, by + bh
