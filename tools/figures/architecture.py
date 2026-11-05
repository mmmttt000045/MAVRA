"""Shared-layer architecture, with one analytical lifecycle and a predictive branch.

Agents 1, 2, and N continue the electronics-revenue questions in Figure 1.
The numbered steps 1-6 cover publication, reuse, item-history loading, and
shared maintenance. A separately labeled predictive agent P retrieves the
spend_90d definition and uses its entity/cutoff compiler. The catalog shares
definitions, joins, and versioned check outcomes across both workloads.

Values and repair follow the 10-03 TPC-DS fixture (item 17, revision 0 to 1,
date_dim key check over 1096 keys). The analytical question bindings and
predictive branch are schematic. Coordinates are millimetres at paper size.
Thin arrows are calls, thick arrows publish shared state, dashed arrows
read database state, and grey arrows denote shared object references.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vecfig import PT, measure  # noqa: E402
import style  # noqa: E402
from style import (ACC, ACC_DK, ACC_PALE, AMBER_PALE, EDGE, FACE, FIELD, INK, MUTED,  # noqa: E402
                   RED, RULE, SIDE, SLATE, TOP, WHITE)

NAME = 'architecture'
W, H = style.TEXTWIDTH, 76.4

# The committed PDF is 178 mm wide and scaled to the 181.9 mm IEEEtran text
# width (x1.022). JSON text sits at 5.9 pt, about 6 pt on paper.
TITLE, BODY, NOTE, SMALL, JS, STEP = 7.4, 7.0, 6.9, 6.4, 5.9, 6.6
LEARN, USE, EXEC_C = '#7A68B0', ACC, '#C97A1E'      # path colours: learning, reuse, execution
LEARN_PALE = '#EFECF7'
KEYC = '#8A5A00'                                    # JSON field names
REF = '#6F6B66'                                     # references by key inside the store
OCHRE = '#9A6500'                                   # changed data (item history)
MAINT_C = '#13897B'                                 # path colour: data change and maintenance (5-6)
MINI = .95                                          # radius of an inline step reference
THIN, THICK = .22, .5
ROW = 2.42                                          # JSON line pitch

LABELS = {
    'en': {
        'agent': 'Agent', 'predictive': 'Predictive agent P', 'compile_feature': 'Feature compile', 'window_short': '90 days',
        'ask': 'ask:',
        'q': ('Jan. electronics revenue?', 'highest-revenue month?',
              'Sep. revenue vs. last year?', 'will a customer churn?'),
        'p': ('explores, answer verified', 'reuses monthly aggregates', 'reuses it after repair',
              'reuses a customer feature'),
        'when': ('first session', ('before', 5), ('after', 5), ''),
        'middleware': 'MAVRA',
        'publish': 'Publish', 'learner': 'Learning', 'learner2': 'agent', 'extracts': 'drafts JSON',
        'checks': 'Checks', 'check_rows': ('fields, joins', 'grain key', 'read-only SQL', 'same answer'),
        'shared': 'Shared knowledge', 'shared_note': 'definitions, joins, check outcomes',
        'm_key': '`metric:Electronics revenue`', 'rev01': ('rev 0', 2, r'$\rightarrow$ 1', 6),
        'groups': ('Computation $I$', 'Learning provenance $E$', 'Conditions $C$ and dependencies'),
        'filter': ('`{"item": "`', '''`i_category = 'Electronics'`''', '`"}`'),
        'stub1': '`metric:Store revenue`', 'stub2': '`feature:customer:spend_90d`',
        'meta1': 'another metric', 'meta2': 'a feature', 'more': 'more entries', 'more_agents': 'more agents', 'shared3': 'one result, used by 3 definitions',
        'lookup': 'Lookup', 'lookup_note': 'by name, versions', 'l_rows': ('valid', ('item changed', 5), 'feature valid'),
        'maint': 'Maintain', 'maint_note': 'rerun its checks', 'item_key': 'item key unique?',
        'repeats': 'key 17 repeats', 'repair': 'Repair',
        'regression': 'regression test', 'to_rev1': 'publish rev 1', 'back': 'rev 1', 'else': 'else invalidate',
        'pending': 'pending',
        'exec': 'Check and', 'exec2': 'run', 'exec_note': 'one snapshot', 'sketch': 'SQL sketch',
        'after6': ('after', 6), 'batch': (5, r'batch 0 $\rightarrow$ 1'),
        'exec_rows': ('checks pass', 'run SQL'), 'feature': '`spend_90d`', 'cutoff': 'cutoff',
        'window': '90-day window', 'cat': 'Electronics',
        'db': 'Database', 'db_note': 'table versions', 'db_note2': 'change on writes',
        'rows_note': ('current row', 'new history row'),
        'snapshot': 'snapshot', 'etl': 'ETL job', 'etl_note': 'loads item history',
    },
    'zh': {
        'agent': '智能体', 'predictive': '预测智能体 P', 'compile_feature': '特征编译', 'window_short': '90 天',
        'ask': '问：',
        'q': ('1 月电子品类营业额？', '电子品类营业额最高月？', '9 月营业额同比去年？', '客户会流失吗？'),
        'p': ('自行探索，答案经核对', '复用月度聚合并排序', '修复后复用该条目', '复用客户特征'),
        'when': ('首次会话', (5, '之前'), (5, '之后'), ''),
        'middleware': 'MAVRA',
        'publish': '发布', 'learner': '学习', 'learner2': '智能体', 'extracts': '起草 JSON',
        'checks': '发布前检查', 'check_rows': ('字段与连接', '粒度键', '只读 SQL', '答案一致'),
        'shared': '共享知识', 'shared_note': '共享定义、连接与检查结果',
        'm_key': '`metric:电子品类营业额`', 'rev01': ('修订 0', 2, r'$\rightarrow$ 1', 6),
        'groups': ('计算 $I$', '学习来源 $E$', '条件 $C$ 与依赖版本'),
        'filter': ('`{"item": "`', '''`i_category = '电子'`''', '`"}`'),
        'stub1': '`metric:门店营业额`', 'stub2': '`feature:customer:spend_90d`',
        'meta1': '另一个指标', 'meta2': '一个特征', 'more': '更多条目', 'more_agents': '更多智能体', 'shared3': '一个结果，三个定义共用',
        'lookup': '查找', 'lookup_note': '按名称，比较版本', 'l_rows': ('有效', ('item 已变', 5), '特征有效'),
        'maint': '维护', 'maint_note': '重跑它的检查', 'item_key': 'item 键唯一？',
        'repeats': '键 17 重复', 'repair': '自动修复',
        'regression': '回归测试', 'to_rev1': '发布修订 1', 'back': '修订 1', 'else': '否则置为失效',
        'pending': '待校验',
        'exec': '校验并', 'exec2': '执行', 'exec_note': '同一快照', 'sketch': 'SQL 示意',
        'after6': (6, '之后'), 'batch': (5, r'batch 0 $\rightarrow$ 1'),
        'exec_rows': ('检查通过', '执行 SQL'), 'feature': '`spend_90d`', 'cutoff': '截止时间',
        'window': '90 天窗口', 'cat': '电子',
        'db': '数据库', 'db_note': '表版本随', 'db_note2': '写入改变',
        'rows_note': ('当前行', '新增历史行'),
        'snapshot': '快照', 'etl': 'ETL 作业', 'etl_note': '载入 item 历史',
    },
}

# Boxes (x, y, w, h).
AG_Y, AG_H = 2.4, 8.6
AG_X = (2.5, 54.0, 96.4, 143.8)
AG_W = 32.0
FIELD_BOX = (1.5, 13.3, 176.0, 50.3)
PUB = (2.5, 16.9, 19.6, 45.9)
STORE = (25.0, 14.8, 105.2, 47.8)
LOOK = (132.4, 16.0, 20.8, 14.8)
MAINT = (132.4, 34.2, 20.8, 28.4)
EXEC = (156.0, 16.0, 19.0, 34.5)
FEAT = (156.0, 51.8, 19.0, 10.8)
SLAB = (25.0, 66.0, 150.0, 10.2)
ETL = (2.5, 66.4, 19.6, 9.4)
# Step colours; an inline reference to step n uses the same colour as its badge.
STEP_C = {1: LEARN, 2: LEARN, 3: USE, 4: EXEC_C, 5: MAINT_C, 6: MAINT_C}


def mid(box):
    x, y, w, h = box
    return x + w / 2, y + h / 2


def baseline(y_center, size):
    """Baseline that centres capitals and digits on y_center."""
    return y_center + .34 * size * PT


def draw(s, lang):
    L = LABELS[lang]
    text, rect, route = s.text, s.rect, s.route

    def box(b, fill=WHITE, edge=EDGE, sw=.16):
        rect(*b, fill, edge, sw, r=.6)

    def node(b, d=1.4):
        x, y, w, h = b
        s.poly([(x, y), (x + d, y - d), (x + w + d, y - d), (x + w, y)], '#F2F0EC', '#BDB9B2', .12)
        s.poly([(x + w, y), (x + w + d, y - d), (x + w + d, y + h - d), (x + w, y + h)],
               '#E7E4DF', '#BDB9B2', .12)
        rect(x, y, w, h, WHITE, '#BDB9B2', .16, r=.4)

    def person(x, y, c='#8E8B85'):
        s.circle(x, y, .72, c)
        rect(x - 1.1, y + .88, 2.2, 1.25, c, None, r=.62)

    def mark(x, y, kind, c=None):
        if kind == 'ok':
            s.poly([(x - .62, y), (x - .15, y + .5), (x + .65, y - .55)], None, c or ACC, .26,
                   closed=False)
        else:
            s.line(x - .5, y - .5, x + .5, y + .5, c or RED, .26)
            s.line(x - .5, y + .5, x + .5, y - .5, c or RED, .26)

    def pill(x, yc, label, color, w=3.0):
        rect(x, yc - 1.15, w, 2.3, color, None, r=.6)
        text(x + w / 2, baseline(yc, 5.8), label, 5.8, WHITE, 'bold', 'center')

    def step(x, y, n, color):
        s.circle(x, y, 1.5, color)
        text(x, baseline(y, STEP), str(n), STEP, WHITE, 'bold', 'center')

    def rich(x, yc, tokens, size, color, style='sans', align='left', width=None):
        """A label whose integer tokens are inline references to steps: small
        circled numbers in the colour of that step's badge. yc is the visual
        centre of the line. Returns the width drawn."""
        tokens = tokens if isinstance(tokens, tuple) else (tokens,)
        gap = .4

        def size_of(t):
            return 2 * MINI if isinstance(t, int) else measure(t, size, style)
        total = sum(size_of(t) for t in tokens) + gap * (len(tokens) - 1)
        if width is not None:
            assert total <= width, f'{tokens!r} is {total:.1f} mm wide; {width:.1f} mm available'
        xx = x - total if align == 'right' else x
        for t in tokens:
            if isinstance(t, int):
                s.circle(xx + MINI, yc, MINI, STEP_C[t])
                text(xx + MINI, baseline(yc, 4.9), str(t), 4.9, WHITE, 'bold', 'center')
            else:
                text(xx, baseline(yc, size), t, size, color, style)
            xx += size_of(t) + gap
        return total

    def sparkle(x, y, r, c):
        k = .28 * r
        s.poly([(x, y - r), (x + k, y - k), (x + r, y), (x + k, y + k), (x, y + r),
                (x - k, y + k), (x - r, y), (x - k, y - k)], c, None)

    # JSON entries -----------------------------------------------------------
    def entry(x, y, w, key, meta, rows, keyw, fill=WHITE, edge=EDGE, head=TOP, meta_c=MUTED,
              fs=JS, row=ROW):
        """A store entry: its key on a header band, then "field": value rows.

        rows: (field, value, colour). field is a JSON key, None for a
        continuation line, '#' for a plain-language heading over the fields
        below it, '*' for a line that spans the key column. A value given as
        a list of (text, colour, gap after) parts is drawn part by part.
        Returns the y centre of each row and the bottom of the card."""
        group_h, hs = row + .1, fs - .1
        h = 3.3 + sum(group_h if f == '#' else row for f, _, _ in rows) + (.9 if rows else 0)
        rect(x, y, w, h, fill, edge, .16, r=.45)
        rect(x + .15, y + .15, w - .3, 3.0, head, None, r=.35)
        if isinstance(meta, tuple):
            mw = rich(x + w - .9, y + 2.3 - .34 * 5.7 * PT, meta, 5.7, meta_c, align='right')
        else:
            mw = text(x + w - .9, y + 2.3, meta, 5.7, meta_c, 'sans', 'right') if meta else 0
        text(x + .9, y + 2.3, key, fs, INK, width=w - 2.4 - mw)
        centres, yy = [], y + 3.5
        for field, value, color in rows:
            if field == '#':
                text(x + .9, baseline(yy + group_h / 2 + .15, hs), value, hs, color, 'bold',
                     width=w - 1.8)
                lx0 = x + .9 + measure(value, hs, 'bold') + .8
                s.line(lx0, yy + group_h / 2, x + w - .9, yy + group_h / 2, RULE, .14)
                centres.append(yy + group_h / 2)
                yy += group_h
                continue
            yc = yy + row / 2
            if field and field != '*':
                text(x + .9, baseline(yc, fs), f'`"{field}"`', fs, KEYC)
            vx = x + .9 + (0 if field == '*' else keyw) + (0 if field else .8)
            if isinstance(value, list):
                for part, pc, gap_after in value:
                    vx += text(vx, baseline(yc, fs), part, fs, pc) + gap_after
                assert vx <= x + w - .9, value
            else:
                text(vx, baseline(yc, fs), value, fs, color, width=x + w - .9 - vx)
            centres.append(yc)
            yy += row
        return centres, y + h

    # Field: the blue band is MAVRA; agents and the database are outside it.
    rect(*FIELD_BOX, FIELD, None, r=1.4)
    rect(3.0, 14.0, .55, 1.9, ACC)
    text(4.3, 15.65, L['middleware'], NOTE, ACC_DK, 'bold')

    # Agents and their questions -----------------------------------------
    for k, (x, letter) in enumerate(zip(AG_X, ('1', '2', 'N', 'P'))):
        node((x, AG_Y, AG_W, AG_H))
        person(x + 2.3, AG_Y + 1.45)
        text(x + 4.6, AG_Y + 3.0, (L['predictive'] if letter == 'P' else f"{L['agent']} {letter}"), BODY, LEARN if letter == '1' else INK,
             'bold')
        if L['when'][k]:
            rich(x + AG_W - 1.0, AG_Y + 3.0 - .34 * (SMALL - .6) * PT, L['when'][k], SMALL - .6,
                 MAINT_C if k == 2 else (USE if k == 1 else MUTED),
                 'bold' if k in (1, 2) else 'sans', align='right')
        aw_ = text(x + 1.2, AG_Y + 5.7, L['ask'], SMALL, ACC_DK, 'bold')
        text(x + 1.2 + aw_ + (.8 if lang == 'en' else 0), AG_Y + 5.7, L['q'][k], SMALL, INK,
             width=AG_W - 2.2 - aw_)
        text(x + 1.2, AG_Y + 7.95, L['p'][k], SMALL - .4,
             LEARN if letter == '1' else (MAINT_C if letter == 'N' else ACC_DK),
             width=AG_W - 2.0)

    # The ellipsis belongs to the analytical consumers, before Agent N.
    dots_x = (AG_X[1] + AG_W + AG_X[2]) / 2
    for k in (-1, 0, 1):
        s.circle(dots_x + 1.6 * k, AG_Y + AG_H / 2, .35, EDGE)

    # Step 1: A's verified session enters Publish.
    a1 = PUB[0] + PUB[2] - 4.4
    route([(a1, AG_Y + AG_H), (a1, PUB[1])], LEARN, THIN)
    step(a1 + 2.6, 14.4, 1, LEARN)

    # Publish -------------------------------------------------------------
    px, py, pw, ph = PUB
    box(PUB)
    text(px + 1.4, py + 3.5, L['publish'], TITLE, INK, 'bold')
    lx, ly, lw, lh = px + 1.0, py + 5.0, pw - 2.0, 11.2
    rect(lx, ly, lw, lh, LEARN_PALE, None, r=.5)
    text(lx + .9, ly + 3.0, L['learner'], NOTE, INK, 'bold', width=lw - 1.6)
    text(lx + .9, ly + 5.8, L['learner2'], NOTE, INK, 'bold', width=lw - 1.6)
    sparkle(lx + 1.9, ly + 8.6, 1.15, LEARN)
    text(lx + 3.6, ly + 9.5, L['extracts'], SMALL - .4, LEARN, width=lw - 4.2)
    route([(px + pw / 2, ly + lh), (px + pw / 2, ly + lh + 2.6)], LEARN, THIN, length=.9)
    cy0 = ly + lh + 2.6
    rect(lx, cy0, lw, 16.4, WHITE, LEARN, .16, r=.5)
    text(lx + .9, cy0 + 3.2, L['checks'], NOTE, INK, 'bold', width=lw - 1.6)
    for k, label in enumerate(L['check_rows']):
        yy = cy0 + 6.3 + 2.9 * k
        mark(lx + 1.5, yy - .7, 'ok', LEARN)
        text(lx + 2.7, yy, label, SMALL - .3, INK, width=lw - 3.1)

    # Shared knowledge ------------------------------------------------------
    sx, sy, sw_, sh = STORE
    rect(sx + 1, sy + 1, sw_, sh, SIDE, EDGE, .12, r=.6)
    box(STORE)
    rect(sx, sy, sw_, 3.0, ACC, None, r=.6)
    rect(sx, sy + 1.5, sw_, 1.5, ACC, None)
    tw = text(sx + 1.4, baseline(sy + 1.5, TITLE), L['shared'], TITLE, WHITE, 'bold')
    text(sx + sw_ - 1.4, baseline(sy + 1.5, SMALL), L['shared_note'], SMALL, WHITE, align='right',
         width=sw_ - tw - 4)

    # The metric entry, field by field (after step 6).
    mx0, my0, mw0 = sx + 1.3, sy + 3.8, 54.8
    g = L['groups']
    mrows = [
        ('#', g[0], ACC_DK),
        ('fact', '`"store_sales"`', INK),
        ('measure', '`"sum(ss_net_paid)"`', INK),
        ('time', '`{"dim": "date_dim", ...}`', INK),
        ('joins', '`[{"key": "join:item|store_sales",`', INK),
        (None, '`"revision": 1}]`', ACC_DK),
        ('filters', [(L['filter'][0], INK, 0), (L['filter'][1], INK, .3),
                     (L['filter'][2], INK, 0)], INK),
        ('*', '`...`', MUTED),
        ('#', g[1], LEARN),
        ('*', [('`"examples"`', KEYC, 0), ('`: [...], `', MUTED, 0), ('`"evidence"`', KEYC, 0),
               ('`: {...}, ...`', MUTED, 0)], MUTED),
        ('#', g[2], SLATE),
        ('guards', '`[{"type": "KeyUnique", ...}]`', INK),
        ('deps', '`{"item": {"batch": 1, ...}, ...}`', ACC_DK),
        ('*', '`...`', MUTED),
    ]
    mc, mbottom = entry(mx0, my0, mw0, L['m_key'], L['rev01'], mrows, 10.8,
                        head=ACC_PALE, edge=ACC, meta_c=ACC_DK, fs=6.2, row=2.75)
    y_time, y_joins = mc[3], mc[4]

    # Entries the metric references by key.
    rx = mx0 + mw0 + 3.5
    rw = sx + sw_ - 1.8 - rx
    # Other entries (collapsed to their keys), with an ellipsis for the rest.
    other = ((L['stub1'], L['meta1']), (L['stub2'], L['meta2']), ('`...`', L['more']))
    op = 2.55
    rect(rx, my0, rw, .5 + op * len(other) + .3, TOP, EDGE, .16, r=.45)
    other_y = []
    for k, (key, meta) in enumerate(other):
        yc = my0 + .5 + op * k + op / 2
        if k:
            s.line(rx + .6, yc - op / 2, rx + rw - .6, yc - op / 2, WHITE, .3)
        mw_ = text(rx + rw - .9, baseline(yc, 5.7), meta, 5.7, MUTED, align='right')
        text(rx + .9, baseline(yc, JS), key, JS, MUTED if k == 2 else INK, width=rw - 2.6 - mw_)
        other_y.append(yc)
    b2 = my0 + .5 + op * len(other) + .3
    k2c, k2b = entry(rx, b2 + .9, rw, '`check:KeyUnique(date_dim.d_date_sk)`', None, [
        ('#', L['shared3'], ACC_DK),
        ('outcome', '`{"pass": true, "n_keys": 1096}`', INK),
    ], 10.0, row=2.3)
    # The item key check sits above the join entry, so the join entry (which
    # repair rewrites) lines up with Maintain's "publish rev 1" row.
    k1c, k1b = entry(rx, k2b + .9, rw, '`check:KeyUnique(item.i_item_sk)`', None, [
        ('filter', [('`"`', INK, 0), ("`i_is_current = 'Y'`", ACC_DK, .3), ('`"`', INK, 0)],
         ACC_DK),
        ('outcome', '`{"pass": true, "n_keys": ...}`', INK),
        ('*', [('`"deps"`', KEYC, 0), ('`: {"item": {"batch": 1}}, ...`', INK, 0)], INK),
    ], 10.0, row=2.3)
    jtop = k1b + 1.4
    jc, jb = entry(rx, jtop, rw, '`join:item|store_sales`', L['rev01'], [
        ('on', '`[["ss_item_sk", "i_item_sk"]]`', INK),
        ('filters', [('`{"item": "`', INK, 0), ("`i_is_current = 'Y'`", ACC_DK, .3),
                     ('`"}`', INK, 0)], ACC_DK),
        ('*', [('`"guards"`', KEYC, 0), ('`: [{"type": "KeyUnique"}], ...`', INK, 0)], INK),
    ], 10.0, row=2.3)
    assert jb <= sy + sh - .8, jb

    # References by key: the metric -> join entry -> check result; the two
    # other definitions reach the same date_dim check result.
    gap = mx0 + mw0 + 1.5
    route([(mx0 + mw0, y_time), (gap, y_time), (gap, k2c[0]), (rx, k2c[0])], REF, .2,
          length=.75, radius=.45)
    route([(mx0 + mw0, y_joins), (gap + .9, y_joins), (gap + .9, jtop + 1.65), (rx, jtop + 1.65)],
          REF, .2, length=.75, radius=.45)
    for yy in other_y[:2]:
        route([(rx + rw, yy), (rx + rw + 1.15, yy), (rx + rw + 1.15, k2c[0]), (rx + rw, k2c[0])],
              REF, .2, length=.65, radius=.35)
    gx = rx + rw - 5.0
    route([(gx, jtop), (gx, k1b)], REF, .2, length=.65)

    # Step 2: Publish writes the entry.
    route([(px + pw, my0 + 1.6), (sx, my0 + 1.6)], LEARN, THICK, length=1.0)
    step((px + pw + sx) / 2, my0 + 4.4, 2, LEARN)

    # Consumer paths into Lookup. Agent 2 (step 3, before step 5) and Agent N
    # (after step 5, in the maintenance colour) do not share a bus.
    c2_x = AG_X[1] + AG_W / 2
    cn_x = AG_X[2] + AG_W / 2
    l2_x, ln_x, lp_x = LOOK[0] + 4.2, LOOK[0] + LOOK[2] / 2, LOOK[0] + LOOK[2] - 3.2
    route([(c2_x, AG_Y + AG_H), (c2_x, 12.6), (l2_x, 12.6), (l2_x, LOOK[1])],
          USE, THIN, length=.9, radius=.4)
    step(l2_x - 2.8, 14.3, 3, USE)
    route([(cn_x, AG_Y + AG_H), (cn_x, 11.75), (ln_x, 11.75), (ln_x, LOOK[1])],
          MAINT_C, THIN, length=.9, radius=.4)
    route([(lp_x, AG_Y + AG_H), (lp_x, LOOK[1])], USE, THIN, length=.9)
    run_y = LOOK[1] + 2.4
    route([(LOOK[0] + LOOK[2], run_y), (EXEC[0], run_y)], EXEC_C, THIN, length=1.0)
    step((LOOK[0] + LOOK[2] + EXEC[0]) / 2, 14.4, 4, EXEC_C)

    # Lookup ----------------------------------------------------------------
    # Rows: 2 and P are valid; N, the bottom row, goes down to Maintain and
    # comes back up once revision 1 exists.
    lx, ly, lw, lh = LOOK
    box(LOOK)
    text(lx + 1.3, ly + 3.3, L['lookup'], TITLE, INK, 'bold')
    text(lx + 1.3, ly + 5.8, L['lookup_note'], SMALL - .5, MUTED, width=lw - 2.4)
    row_y = {}
    for k, letter in enumerate(('2', 'P', 'N')):
        yc = ly + 7.6 + 2.65 * k
        row_y[letter] = yc
        label = L['l_rows'][{'2': 0, 'N': 1, 'P': 2}[letter]]
        pill(lx + 1.0, yc, letter, MAINT_C if letter == 'N' else USE)
        rich(lx + 4.6, yc, label, SMALL - .3, MAINT_C if letter == 'N' else INK,
             width=lw - 5.6)
        if letter != 'N':
            mark(lx + lw - 1.8, yc, 'ok')
    assert row_y['N'] + 1.15 < ly + lh
    route([(sx + sw_, row_y['2']), (lx, row_y['2'])], USE, THIN, length=1.0)

    # Maintain and repair (step 6) -------------------------------------------
    qx, qy, qw, qh = MAINT
    gap_y = (ly + lh + qy) / 2
    down_x, up_x = lx + 2.5, lx + lw - 1.8
    route([(down_x, ly + lh), (down_x, qy)], MAINT_C, THIN, length=.9)
    text(down_x + .9, baseline(gap_y, SMALL - .6), L['pending'], SMALL - .6, MAINT_C, 'bold')
    route([(up_x, qy), (up_x, ly + lh)], MAINT_C, THIN, length=.9)
    text(up_x - .9, baseline(gap_y, SMALL - .6), L['back'], SMALL - .6, MAINT_C, 'bold',
         align='right')
    box(MAINT)
    text(qx + 1.3, qy + 3.5, L['maint'], TITLE, INK, 'bold')
    step(qx + qw - 2.2, qy + 2.7, 6, MAINT_C)
    text(qx + 1.3, qy + 6.2, L['maint_note'], SMALL - .3, MUTED, width=qw - 2.4)
    text(qx + 1.3, qy + 9.0, L['item_key'], SMALL - .3, INK, width=qw - 4.4)
    mark(qx + qw - 1.8, qy + 8.3, 'fail')
    text(qx + 1.3, qy + 11.4, L['repeats'], SMALL - .3, RED, width=qw - 2.4)
    # The repair block is placed so "publish rev 1" sits on the join entry's
    # filters row, which the thick write-back arrow reaches in a straight line.
    y_jf = jc[1]
    pb = baseline(y_jf, SMALL - .3)
    rule_y = pb - 10.9
    assert rule_y > qy + 12.4, rule_y
    s.line(qx + 1.0, rule_y, qx + qw - 1.0, rule_y, RULE, .16)
    text(qx + 1.3, pb - 8.1, L['repair'], NOTE, INK, 'bold', width=qw - 2.4)
    text(qx + 1.3, pb - 5.4, "`i_is_current='Y'`", JS, ACC_DK, width=qw - 2.4)
    mark(qx + 2.0, pb - 3.4, 'ok')
    text(qx + 3.4, pb - 2.7, L['regression'], SMALL - .5, ACC_DK, width=qw - 4.0)
    text(qx + 1.3, pb, L['to_rev1'], SMALL - .3, ACC_DK, 'bold', width=qw - 2.4)
    text(qx + 1.3, pb + 2.5, L['else'], SMALL - .5, MUTED, width=qw - 2.4)
    assert pb + 2.5 < qy + qh - .6
    # Repair publishes revision 1: the join entry (and the metric that references it).
    route([(qx, y_jf), (sx + sw_, y_jf)], MAINT_C, THICK, length=1.0)

    # Check and run ------------------------------------------------------------
    ex, ey, ew, eh = EXEC
    box(EXEC)
    text(ex + 1.2, ey + 3.1, L['exec'], TITLE, INK, 'bold', width=ew - 2.2)
    text(ex + 1.2, ey + 5.7, L['exec2'], TITLE, INK, 'bold', width=ew - 2.2)
    text(ex + 1.2, ey + 8.1, L['exec_note'], SMALL - .3, EXEC_C, 'bold', width=ew - 2.2)
    pill(ex + 1.0, ey + 10.6, '2', USE)
    text(ex + 4.5, baseline(ey + 10.6, SMALL - .5), L['sketch'], SMALL - .5, MUTED, width=ew - 5.3)
    cx_, cy_, cw_ = ex + 1.0, ey + 12.1, ew - 2.0
    code = ('SUM(ss_net_paid)', 'WHERE i_category', f"= '{L['cat']}'", 'GROUP BY d_moy', '... ORDER BY ...')
    rect(cx_, cy_, cw_, 1.1 + 2.15 * len(code), FACE, None, r=.4)
    for k, line in enumerate(code):
        text(cx_ + .45, cy_ + 2.1 + 2.15 * k, f'`{line}`', JS - .2, INK, width=cw_ - .7)
    yc_ag = ey + 26.2
    pill(ex + 1.0, yc_ag, '2', USE)
    text(ex + 4.3, baseline(yc_ag, SMALL - .6), '·', SMALL - .6, MUTED)
    pill(ex + 5.1, yc_ag, 'N', MAINT_C)
    rich(ex + 8.5, yc_ag, L['after6'], SMALL - .6, MAINT_C, width=ew - 9.0)
    for k, label in enumerate(L['exec_rows']):
        yy = ey + 29.7 + 2.55 * k
        mark(ex + 1.9, yy - .7, 'ok', EXEC_C)
        text(ex + 3.2, yy, label, SMALL - .3, INK, width=ew - 4.0)
    # A separate predictive branch shares lookup, not metric snapshot execution.
    fx, fy, fw, fh = FEAT
    box(FEAT)
    text(fx + 1.0, fy + 2.1, L['compile_feature'], SMALL, INK, 'bold', width=fw - 2.0)
    pill(fx + 1.0, fy + 4.3, 'P', USE)
    text(fx + 4.5, baseline(fy + 4.3, JS), L['feature'], JS, INK, width=fw - 5.3)
    p_row_y = row_y['P']
    ch_x = (lx + lw + fx) / 2
    route([(lx + lw, p_row_y), (ch_x, p_row_y), (ch_x, fy + 4.3), (fx, fy + 4.3)],
          USE, THIN, length=.75, radius=.4)
    axis_y, cut = fy + 6.8, fx + 12.0
    rect(fx + 1.5, axis_y - .6, cut - fx - 1.5, 1.2, AMBER_PALE, None, r=.3)
    s.line(fx + 1.5, axis_y, fx + fw - 1.3, axis_y, RULE, .18)
    s.line(cut, axis_y - 1.0, cut, axis_y + .85, EXEC_C, .26)
    for dx in (3.5, 6.6, 9.7):
        s.circle(fx + dx, axis_y, .35, EXEC_C)
    for dx in (14.4, 16.8):
        s.line(fx + dx - .3, axis_y - .3, fx + dx + .3, axis_y + .3, MUTED, .18)
        s.line(fx + dx - .3, axis_y + .3, fx + dx + .3, axis_y - .3, MUTED, .18)
    text(fx + 1.9, fy + 9.7, L['window_short'], SMALL - .8, EXEC_C)
    text(cut, fy + 9.7, '$t_i$', SMALL - .8, EXEC_C, align='center')

    # Database -------------------------------------------------------------
    bx, by, bw, bh = SLAB
    d = 1.2
    soft = '#BDB9B2'
    s.poly([(bx, by), (bx + d, by - d), (bx + bw + d, by - d), (bx + bw, by)], '#F2F0EC', soft, .12)
    s.poly([(bx + bw, by), (bx + bw + d, by - d), (bx + bw + d, by + bh - d), (bx + bw, by + bh)],
           '#E7E4DF', soft, .12)
    rect(bx, by, bw, bh, FACE, soft, .16, r=.5)
    text(bx + 2.0, by + 3.8, L['db'], TITLE, INK, 'bold')
    text(bx + 2.0, by + 6.4, L['db_note'], SMALL - .3, MUTED)
    text(bx + 2.0, by + 8.9, L['db_note2'], SMALL - .3, MUTED)
    top, inner = by + .8, bh - 1.6

    def card(x0, w_, name, version, hot=False):
        rect(x0, top, w_, inner, WHITE, OCHRE if hot else EDGE, .16 if hot else .12, r=.35)
        rect(x0 + .15, top + .15, w_ - .3, 2.3, AMBER_PALE if hot else TOP, None, r=.25)
        text(x0 + .9, top + 1.9, name, JS, INK)
        rich(x0 + w_ - .9, top + 1.9 - .34 * 5.6 * PT, version, 5.6, OCHRE if hot else MUTED,
             'bold' if hot else 'sans', align='right')

    def bars(x0, w_, n=3):
        for r_ in range(n):
            rect(x0 + .9, top + 3.3 + 1.65 * r_, w_ - 1.8, .8, '#E4E1DB', None, r=.2)

    for x0, w_, name, version in ((50.0, 27.0, '`store_sales`', 'batch 0'),
                                  (79.0, 23.0, '`date_dim`', 'batch 0')):
        card(x0, w_, name, version)
        bars(x0, w_)
    # item: the ETL job added a history row for key 17.
    ix, iw = 104.0, 48.2
    card(ix, iw, '`item`', L['batch'], hot=True)
    cols = (ix + .9, ix + 10.0, ix + 23.4)
    for c, head in zip(cols, ('`i_item_sk`', '`i_category`', '`i_is_current`')):
        text(c, top + 4.4, head, JS - .5, MUTED)
    cat = 'Electronics' if lang == 'en' else '电子'
    for k, (key, cur) in enumerate((('17', "'Y'"), ('17', "'N'"))):
        yy = top + 6.3 + 1.95 * k
        if k:
            rect(ix + .5, yy - 1.45, iw - 1.0, 1.9, AMBER_PALE, None, r=.3)
        for c, value in zip(cols, (key, f"'{cat}'", cur)):
            text(c, yy, f'`{value}`', JS - .4, INK)
        text(ix + iw - 1.0, yy, L['rows_note'][k], 5.6, OCHRE if k else MUTED,
             'bold' if k else 'sans', align='right')
    # Snapshot: step 4's guards and SQL read the same state.
    nx, nw = EXEC[0], bx + bw - .8 - EXEC[0]
    rect(nx, top, nw, inner, WHITE, EXEC_C, .18, r=.35, dash=(.8, .5))
    text(nx + 1.0, top + 2.6, L['snapshot'], SMALL - .3, EXEC_C, 'bold')
    mini = (nw - 2.0 - 2 * .5) / 3
    for k in range(3):
        mx = nx + 1.0 + k * (mini + .5)
        rect(mx, top + 3.5, mini, inner - 4.2, FACE, EDGE, .1, r=.25)
        rect(mx + .15, top + 3.65, mini - .3, 1.0, TOP, None, r=.2)

    # Database reads: the item guard and the snapshot.
    rd = qx + qw / 2 - 2.0
    route([(rd, top), (rd, qy + qh)], MAINT_C, .3, dash=(.7, .45), length=1.0)
    snap_y = top + inner / 2
    chk_y = ey + 30.3
    route([(nx + nw, snap_y), (176.6, snap_y), (176.6, chk_y), (ex + ew, chk_y)],
          EXEC_C, .25, dash=(.7, .45), length=.7, radius=.4)

    # ETL (outside the database): step 5 writes a new item history row.
    tx, ty, tw_, th = ETL
    for off in (1.2, .6, 0):
        rect(tx + off, ty - off, tw_ - 1.2, th, WHITE, EDGE, .13, r=.4)
    text(tx + 1.4, ty + 3.5, L['etl'], TITLE, INK, 'bold', width=tw_ - 2.6)
    text(tx + 1.4, ty + 6.5, L['etl_note'], SMALL - .3, OCHRE, width=tw_ - 2.6)
    route([(tx + tw_ - 1.2, ty + th / 2 + 1.2), (bx, ty + th / 2 + 1.2)], MAINT_C, THIN, length=1.0)
    step(tx + tw_ + 1.45, ty + th / 2 - 2.2, 5, MAINT_C)


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
