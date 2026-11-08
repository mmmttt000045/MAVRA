"""Lookup and shared maintenance over versioned check outcomes (Section IV-D), single column.

Algorithm 1 run on the store after the item-history load of Fig. 2 (step 5).
Top: the definition's recorded stamps V_x next to the version tracker's
current stamps, V(T) = <schema fingerprint, DML counter, ETL batch>. Only
item's stamp differs, so lookup marks the definition pending (line 7) and
selects the conditions that read item (line 8). Bottom: the outcome store H,
keyed by k(c, V) = (id(c), V(dep(c))). The date_dim outcome keeps its key and
still serves three definitions; the item key check has no outcome at item's
new stamp, so it runs once (line 2) and fails with 1001 rows over 1000 keys
(key 17 repeats); Repair's filter passes at the same stamp and becomes
revision 1 (step 6). The outcome at item's old stamp stays behind, unused.

Values: the stamps recorded for M5-L1 on the 1M-row retail fixture
(exp/2026-10-08-lifecycle/cell-mavra.json, evidence.versions: schema md5
prefixes 1d5b, 9662, 5a15; DML counters 1096, 1000, 1000000; batch 0). The
running example's load adds the one history row of Fig. 2, so item moves to
DML 1001 and batch 1, and the key check counts 1001 rows over 1000 keys.
Which definitions share the date_dim outcome is schematic, as in Fig. 2.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from style import INK, MUTED, RED, RULE  # noqa: E402
from smallparts import (BLUE_PALE, BLUE_TXT, CODE_T, HEAD_T, LINE, MAINT_C, MAINT_PALE,  # noqa: E402
                        RED_PALE, SMALL, baseline, mark, step, stamp, structure, tag)

NAME = 'maintenance'
W, H = style.COLUMN, 41.2

OLD, NEW = stamp('9662', '1000', '0'), stamp('9662', '1001', '1')
TRACKED = (('`date_dim`', stamp('1d5b', '1096', '0'), None),
           ('`item`', OLD, NEW),
           ('`store_sales`', stamp('5a15', '$10^6$', '0'), None))
# Outcome rows: stamp, n_rows, n_keys, verdict.
OUTCOMES = ((TRACKED[0][1], '1096', '1096', True), (OLD, '1000', '1000', True),
            (NEW, '1001', '1000', False), (NEW, '1000', '1000', True))
GREY = '#9C9A95'

LABELS = {
    'en': {
        'def': (('Definition $x$: ', 'bold'), ('`metric:Electronics revenue`', 'sans'), (', rev 0', 'sans')),
        'def_note': r'$V(T)=\langle$schema, DML, ETL batch$\rangle$',
        'cols_a': ('table', r'$V_x(T)$, recorded', r'$V(T)$, version tracker'),
        'pending': 'pending: `item` changed',
        'delta': r"$\Delta C(x)$: conditions with `item` $\in\mathrm{dep}(c)$, such as `KeyUnique(item.i_item_sk)`",
        'store': (('Outcome store $H$', 'bold'),),
        'key': r'key $k(c,V)=(\mathrm{id}(c),\,V(\mathrm{dep}(c)))$',
        'cols_h': (r'$\mathrm{id}(c)$', r'$V(\mathrm{dep}(c))$', '`n_rows`', '`n_keys`'),
        'ids': (('`KeyUnique(date_dim.d_date_sk)`',), ('`KeyUnique(item.i_item_sk)`',),
                ('`KeyUnique(item.i_item_sk)`',),
                ('`KeyUnique(item.i_item_sk,`', "`          i_is_current = 'Y')`")),
        'first': (None, None, r'miss: $Q_c$ runs once', 'Repair candidate'),
        'res': ('pass, used by 3', 'pass, old version', 'fail: key 17 repeats', 'pass: join, metric rev 1'),
    },
    'zh': {
        'def': (('定义 $x$：', 'bold'), ('`metric:Electronics revenue`', 'sans'), ('，修订版 0', 'sans')),
        'def_note': r'$V(T)=\langle$结构指纹, DML, 批次$\rangle$',
        'cols_a': ('表', r'$V_x(T)$（记录值）', r'$V(T)$（版本跟踪器）'),
        'pending': '待验证：`item` 已变化',
        'delta': r"$\Delta C(x)$：$\mathrm{dep}(c)$ 含 `item` 的条件，如 `KeyUnique(item.i_item_sk)`",
        'store': (('检查结果存储 $H$', 'bold'),),
        'key': r'键 $k(c,V)=(\mathrm{id}(c),\,V(\mathrm{dep}(c)))$',
        'cols_h': (r'$\mathrm{id}(c)$', r'$V(\mathrm{dep}(c))$', '`n_rows`', '`n_keys`'),
        'ids': (('`KeyUnique(date_dim.d_date_sk)`',), ('`KeyUnique(item.i_item_sk)`',),
                ('`KeyUnique(item.i_item_sk)`',),
                ('`KeyUnique(item.i_item_sk,`', "`          i_is_current = 'Y')`")),
        'first': (None, None, r'未命中：$Q_c$ 只执行一次', '修复候选'),
        'res': ('通过，三个定义共用', '通过（旧版本）', '失败：键 17 重复', '通过：发布修订版 1'),
    },
}


def draw(s, lang):
    L = LABELS[lang]
    text = s.text
    gx = 2.15                    # the access path runs down this gutter, left of the structures
    x0, x1 = 4.4, 83.6
    band, head = 2.9, 2.85       # title band; column heads down to the rule

    # The definition's recorded stamps next to the current ones (line 7 compares them).
    ay, pitch_a = 1.0, 2.7
    top_a = ay + band + head
    ah = top_a - ay + 3 * pitch_a + .3
    yb = structure(s, x0, ay, x1 - x0, ah, band, L['def'], L['def_note'], BLUE_PALE, INK)
    ca = (x0 + 1.0, x0 + 15.0, x0 + 31.0, x0 + 48.0)
    for c, label in zip(ca, L['cols_a']):
        text(c, yb + 2.1, label, HEAD_T, MUTED)
    s.line(x0, top_a, x1, top_a, RULE, .14)
    rows_a = [top_a + pitch_a * (i + .5) for i in range(3)]
    for (name, old, new), yc in zip(TRACKED, rows_a):
        bc = baseline(yc, CODE_T)
        if new:
            s.rect(x0 + .3, yc - pitch_a / 2 + .15, x1 - x0 - .6, pitch_a - .3, MAINT_PALE, None, r=.4)
            step(s, ca[2] + .95, yc, 5, r=.95)
            text(ca[2] + 2.4, bc, new, CODE_T, MAINT_C)
            text(ca[3], baseline(yc, SMALL), r'$\neq$', SMALL, MAINT_C)
            text(ca[3] + 2.6, baseline(yc, SMALL), L['pending'], SMALL, MAINT_C, 'bold', width=x1 - ca[3] - 3.6)
        else:
            text(ca[2], bc, old, CODE_T, MUTED)
            text(ca[3], baseline(yc, SMALL), '=', SMALL, MUTED)
        text(ca[0], bc, name, CODE_T, INK)
        text(ca[1], bc, old, CODE_T, INK)

    # Line 8: the affected conditions.
    y_delta = ay + ah + 2.1
    text(x0 + 1.0, baseline(y_delta, SMALL), L['delta'], SMALL, INK, width=x1 - x0 - 1.4)

    # The outcome store H; the two rows at item's new stamp take two lines.
    hy = y_delta + 2.1
    heights = (2.95, 2.95, 4.75, 4.75)
    top = hy + band + head
    tops = [top + sum(heights[:i]) for i in range(4)]
    bottom = top + sum(heights) + .3
    yb = structure(s, x0, hy, x1 - x0, bottom - hy, band, L['store'], L['key'])
    ch = (x0 + 1.0, x0 + 29.4, x0 + 42.2, x0 + 48.9, x0 + 55.4)
    for c, label in zip(ch, L['cols_h']):
        text(c, yb + 2.1, label, HEAD_T, MUTED)
    s.line(x0, top, x1, top, RULE, .14)
    fills = (BLUE_PALE, None, RED_PALE, MAINT_PALE)
    colors = (BLUE_TXT, GREY, RED, MAINT_C)
    firsts = []
    for i, (y0, h) in enumerate(zip(tops, heights)):
        if fills[i]:
            s.rect(x0 + .3, y0 + .2, x1 - x0 - .6, h - .4, fills[i], RED if i == 2 else None, LINE, r=.4,
                   dash=(.7, .45) if i == 2 else None)
        two = len(L['ids'][i]) > 1 or L['first'][i]
        first = y0 + 1.3 if two else y0 + h / 2
        firsts.append(first)
        ink = GREY if i == 1 else INK
        for j, label in enumerate(L['ids'][i]):
            text(ch[0], baseline(first + 2.15 * j, CODE_T), label, CODE_T, ink, width=ch[1] - ch[0] - .4)
        bc = baseline(first, CODE_T)
        st, n_rows, n_keys, ok = OUTCOMES[i]
        text(ch[1], bc, st, CODE_T, MAINT_C if i >= 2 else ink, width=ch[2] - ch[1] - .4)
        text(ch[2], bc, f'`{n_rows}`', CODE_T, RED if not ok else ink)
        text(ch[3], bc, f'`{n_keys}`', CODE_T, ink)
        tx = ch[4] + 2.2                       # verdict text, right of its mark
        room = x1 - .8 - tx
        if L['first'][i]:
            text(tx, baseline(first, SMALL), L['first'][i], SMALL, colors[i], width=room)
        vy = first + 2.15 if two else first
        if i == 1:
            s.poly([(ch[4] + .3, vy), (ch[4] + .68, vy + .4), (ch[4] + 1.32, vy - .44)], None, GREY, .26,
                   closed=False)
        else:
            mark(s, ch[4] + .8, vy, ok, k=.8)
        text(tx, baseline(vy, SMALL), L['res'][i], SMALL, colors[i], 'sans' if i == 1 else 'bold', width=room)

    # The access path down the gutter: line 7 at item's stamp, line 8, line 2 at the new key, step 6 at Repair.
    y_item, y_l2, y_rep = rows_a[1], firsts[2], firsts[3]
    s.line(gx, y_item, gx, y_rep, MAINT_C, LINE + .06)
    for y, label in ((y_item, 'L7'), (y_delta, 'L8'), (y_l2, 'L2')):
        w = tag(s, gx, y, label, MAINT_C, align='center')
        assert gx + w / 2 < x0 - .25, w
    step(s, gx, y_rep, 6, r=1.15)
    assert bottom < H - .3, bottom
