"""MAVRA architecture told with one worked example (redesign of 2026-11-02).

Agents sit on top, MAVRA in the middle, the database at the bottom. One
definition, Electronics revenue on TPC-DS, runs through every step:

  1-2  Agent A asks for January electronics revenue; the verified session is
       extracted and passes the publication checks (revision 0).
  3    Agent B asks for Q3; lookup matches the stored name and returns the
       same entry, used with months 7-9.
  4    B's guards and SQL run on one snapshot.
  5    An ETL job loads item history (SCD Type 2): key 17 gets a second row
       and item's ETL batch moves from 0 to 1.
  6    Agent C asks for October; the item version no longer matches, so the
       entry is pending. Maintain reruns the item guard, which fails; repair
       finds i_is_current = 'Y', republishes join:item|store_sales and the
       metric as revision 1 after the regression test.
  7    Agent N reuses a feature on the same tables with per-seed cutoffs.

Agents B, C, ..., N stand for the many agents that reuse the store; the
ellipsis between C and N marks the agents that are not drawn.

Shared knowledge shows what the store holds: one JSON entry per key
(src/knowledge.rs Entry, Metric, JoinRef; src/checks.rs Check, Outcome).
The large card is the metric entry with its real field names; the cards on
its right are entries it references by key: the join entry, and check
results keyed by the serialized check. Values come from the 10-03 TPC-DS
fixture run (exp/2026-10-03-shared-memory, entry metric:电子品类门店营业额):
learning task January, value 273265.4, date_dim key check over 1096 keys.
English labels translate the fixture's Chinese names. The database label is
exactly Database in both languages.

Coordinates are millimetres at paper size. Thin arrows are calls, thick
arrows write shared state, dashed arrows read database state; grey arrows
inside the store are references by key.
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
OCHRE = '#9A6500'
THIN, THICK = .22, .5
ROW = 2.42                                          # JSON line pitch

LABELS = {
    'en': {
        'agent': 'Agent',
        'ask': 'ask:',
        'q': ('Jan. electronics revenue?', 'Q3 electronics revenue?',
              'Oct. electronics revenue?', 'will a customer churn?'),
        'p': ('explores, answer verified', 'reuses it for months 7–9', 'reuses it after repair',
              'reuses a customer feature'),
        'when': ('first session', 'before the update', 'after the update', ''),
        'middleware': 'MAVRA',
        'publish': 'Publish', 'learner': 'Learning', 'learner2': 'agent', 'extracts': 'drafts JSON',
        'checks': 'Checks', 'check_rows': ('fields, joins', 'grain key', 'read-only SQL', 'same answer'),
        'shared': 'Shared knowledge', 'shared_note': 'one JSON entry per key',
        'm_key': '`metric:Electronics revenue`', 'rev1': r'revision 0 $\rightarrow$ 1 · Valid',
        'groups': ('what it computes', 'learned from Agent A', 'reuse conditions and dependencies'),
        'filter': ('`{"item": "`', '''`i_category = 'Electronics'`''', '`"}`'),
        'stub1': '`metric:Store revenue`', 'stub2': '`feature:customer:spend_90d`',
        'meta1': 'another metric', 'meta2': 'a feature', 'more': 'more entries', 'more_agents': 'more agents', 'shared3': 'one result, used by 3 definitions', 'rev1j': r'revision 0 $\rightarrow$ 1',
        'lookup': 'Lookup', 'lookup_note': 'by name, versions', 'l_rows': ('valid', 'item changed', 'feature valid'),
        'maint': 'Maintain', 'maint_note': 'rerun its checks', 'item_key': 'item key unique?',
        'repeats': 'key 17 repeats', 'repair': 'Repair',
        'regression': 'regression test', 'to_rev1': 'publish revision 1', 'else': 'else invalidate',
        'pending': 'pending',
        'exec': 'Check and', 'exec2': 'run', 'exec_note': 'one snapshot', 'sketch': 'SQL sketch',
        'exec_rows': ('checks pass', 'run SQL'), 'feature': '`spend_90d`', 'cutoff': 'cutoff',
        'window': '90-day window', 'cat': 'Electronics',
        'db': 'Database', 'db_note': 'table versions', 'db_note2': 'change on writes',
        'rows_note': ('current row', 'new history row'),
        'snapshot': 'snapshot', 'etl': 'ETL job', 'etl_note': 'loads item history',
    },
    'zh': {
        'agent': '智能体',
        'ask': '问：',
        'q': ('1 月电子品类营业额？', 'Q3 电子品类营业额？', '10 月电子品类营业额？', '客户会流失吗？'),
        'p': ('自行探索，答案经核对', '复用该条目，取 7–9 月', '修复后复用该条目', '复用客户特征'),
        'when': ('首次会话', '更新之前', '更新之后', ''),
        'middleware': 'MAVRA',
        'publish': '发布', 'learner': '学习', 'learner2': '智能体', 'extracts': '起草 JSON',
        'checks': '发布前检查', 'check_rows': ('字段与连接', '粒度键', '只读 SQL', '答案一致'),
        'shared': '共享知识', 'shared_note': '每个键一条 JSON 条目',
        'm_key': '`metric:电子品类营业额`', 'rev1': r'修订 0 $\rightarrow$ 1 · 有效',
        'groups': ('计算什么', '从智能体 A 学来', '复用条件与依赖'),
        'filter': ('`{"item": "`', '''`i_category = '电子'`''', '`"}`'),
        'stub1': '`metric:门店营业额`', 'stub2': '`feature:customer:spend_90d`',
        'meta1': '另一个指标', 'meta2': '一个特征', 'more': '更多条目', 'more_agents': '更多智能体', 'shared3': '一个结果，三个定义共用', 'rev1j': r'修订 0 $\rightarrow$ 1',
        'lookup': '查找', 'lookup_note': '按名称，比较版本', 'l_rows': ('有效', 'item 已变化', '特征有效'),
        'maint': '维护', 'maint_note': '重跑它的检查', 'item_key': 'item 键唯一？',
        'repeats': '键 17 重复', 'repair': '自动修复',
        'regression': '回归测试', 'to_rev1': '发布修订 1', 'else': '否则置为失效',
        'pending': '待校验',
        'exec': '校验并', 'exec2': '执行', 'exec_note': '同一快照', 'sketch': 'SQL 示意',
        'exec_rows': ('检查通过', '执行 SQL'), 'feature': '`spend_90d`', 'cutoff': '截止时间',
        'window': '90 天窗口', 'cat': '电子',
        'db': 'Database', 'db_note': '表版本随', 'db_note2': '写入改变',
        'rows_note': ('当前行', '新增历史行'),
        'snapshot': '快照', 'etl': 'ETL 作业', 'etl_note': 'item 历史版本',
    },
}

# Boxes (x, y, w, h).
AG_Y, AG_H = 2.4, 8.6
AG_X = (2.5, 62.0, 96.4, 143.8)
AG_W = 32.0
FIELD_BOX = (1.5, 13.3, 175.8, 50.3)
PUB = (2.5, 16.9, 19.6, 45.9)
STORE = (25.0, 14.8, 105.6, 47.8)
LOOK = (133.2, 16.0, 21.6, 15.4)
MAINT = (133.2, 34.2, 21.6, 28.4)
EXEC = (157.4, 16.0, 19.6, 46.6)
SLAB = (25.0, 66.0, 151.8, 10.2)
ETL = (2.5, 66.4, 19.6, 9.4)


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
    for k, (x, letter) in enumerate(zip(AG_X, 'ABCN')):
        node((x, AG_Y, AG_W, AG_H))
        person(x + 2.3, AG_Y + 1.45)
        text(x + 4.6, AG_Y + 3.0, f"{L['agent']} {letter}", BODY, LEARN if letter == 'A' else INK,
             'bold')
        if L['when'][k]:
            text(x + AG_W - 1.0, AG_Y + 3.0, L['when'][k], SMALL - .6,
                 OCHRE if k == 2 else MUTED, 'bold' if k == 2 else 'sans', align='right')
        aw_ = text(x + 1.2, AG_Y + 5.7, L['ask'], SMALL, ACC_DK, 'bold')
        text(x + 1.2 + aw_ + (.8 if lang == 'en' else 0), AG_Y + 5.7, L['q'][k], SMALL, INK,
             width=AG_W - 2.2 - aw_)
        text(x + 1.2, AG_Y + 7.95, L['p'][k], SMALL - .4, LEARN if letter == 'A' else ACC_DK,
             width=AG_W - 2.0)

    # More agents than can be drawn: B, C, ..., N.
    dots_x = (AG_X[2] + AG_W + 1.4 + AG_X[3]) / 2
    for k in (-1, 0, 1):
        s.circle(dots_x + 2.0 * k, AG_Y + AG_H / 2 - .6, .45, EDGE)
    text(dots_x, AG_Y + AG_H / 2 + 2.6, L['more_agents'], SMALL - .6, MUTED, align='center',
         width=AG_X[3] - AG_X[2] - AG_W - 2.2)

    # Step 1: A's verified session enters Publish.
    a1 = PUB[0] + PUB[2] - 4.0
    route([(a1, AG_Y + AG_H), (a1, PUB[1])], LEARN, THIN)
    step(a1 - 3.0, 14.4, 1, LEARN)

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
        ('filters', [(L['filter'][0], INK, 0), (L['filter'][1], '#2F7A70', .3),
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
    mc, mbottom = entry(mx0, my0, mw0, L['m_key'], L['rev1'], mrows, 10.8,
                        head=ACC_PALE, edge=ACC, meta_c=ACC_DK, fs=6.2, row=2.75)
    y_time, y_joins = mc[3], mc[4]

    # Entries the metric references by key.
    rx = mx0 + mw0 + 4.0
    rw = sx + sw_ - 1.3 - rx
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
    k2c, k2b = entry(rx, b2 + 1.0, rw, '`check:KeyUnique(date_dim.d_date_sk)`', None, [
        ('#', L['shared3'], ACC_DK),
        ('outcome', '`{"pass": true, "n_keys": 1096}`', INK),
    ], 10.5, row=2.3)
    jc, jb = entry(rx, k2b + 1.0, rw, '`join:item|store_sales`', L['rev1j'], [
        ('on', '`[["ss_item_sk", "i_item_sk"]]`', INK),
        ('filters', [('`{"item": "`', INK, 0), ("`i_is_current = 'Y'`", ACC_DK, .3),
                     ('`"}`', INK, 0)], ACC_DK),
        ('*', [('`"guards"`', KEYC, 0), ('`: [{"type": "KeyUnique"}], ...`', INK, 0)], INK),
    ], 10.5, row=2.3)
    k1c, k1b = entry(rx, jb + 1.0, rw, '`check:KeyUnique(item.i_item_sk)`', None, [
        ('filter', [('`"`', INK, 0), ("`i_is_current = 'Y'`", ACC_DK, .3), ('`"`', INK, 0)],
         ACC_DK),
        ('outcome', '`{"pass": true, "n_keys": ...}`', INK),
        ('*', [('`"deps"`', KEYC, 0), ('`: {"item": {"batch": 1}}, ...`', INK, 0)], INK),
    ], 10.5, row=2.3)

    # References by key: the metric -> join entry -> check result; the two
    # other definitions reach the same date_dim check result.
    gap = mx0 + mw0 + 1.6
    route([(mx0 + mw0, y_time), (gap, y_time), (gap, k2c[0]), (rx, k2c[0])], REF, .2,
          length=.8, radius=.5)
    route([(mx0 + mw0, y_joins), (gap + 1.0, y_joins), (gap + 1.0, jc[0] - 3.0), (rx, jc[0] - 3.0)],
          REF, .2, length=.8, radius=.5)
    for yy in other_y[:2]:
        route([(rx + rw, yy), (rx + rw + .7, yy), (rx + rw + .7, k2c[0]), (rx + rw, k2c[0])],
              REF, .2, length=.7, radius=.3)
    gx = rx + rw - 5.0
    route([(gx, jb - .2), (gx, jb + 1.0)], REF, .2, length=.7)

    # Step 2: Publish writes the entry.
    route([(px + pw, my0 + 1.6), (sx, my0 + 1.6)], LEARN, THICK, length=1.0)
    step((px + pw + sx) / 2, my0 + 5.0, 2, LEARN)

    # Later agents reach Lookup and Check and run through one bus ------------
    bus_y = 12.3
    centres = [x + AG_W / 2 for x in AG_X[1:]]
    look_c, exec_c = mid(LOOK)[0], mid(EXEC)[0]
    s.line(centres[0], bus_y, centres[-1], bus_y, USE, .3)
    for xc in centres:
        s.line(xc, AG_Y + AG_H, xc, bus_y, USE, .3)
    route([(look_c, bus_y), (look_c, LOOK[1])], USE, THIN, length=1.0)
    step(look_c - 3.0, 14.2, 3, USE)
    run_y = LOOK[1] + 3.0
    route([(LOOK[0] + LOOK[2], run_y), (EXEC[0], run_y)], EXEC_C, THIN, length=1.0)
    step((LOOK[0] + LOOK[2] + EXEC[0]) / 2, 14.4, 4, EXEC_C)

    # Lookup ----------------------------------------------------------------
    lx, ly, lw, lh = LOOK
    box(LOOK)
    text(lx + 1.3, ly + 3.4, L['lookup'], TITLE, INK, 'bold')
    text(lx + 1.3, ly + 6.0, L['lookup_note'], SMALL - .5, MUTED, width=lw - 2.4)
    for k, (letter, state) in enumerate((('B', 'ok'), ('C', 'wait'), ('N', 'ok'))):
        yc = ly + 7.9 + 2.75 * k
        pill(lx + 1.0, yc, letter, USE)
        text(lx + 4.6, baseline(yc, SMALL - .3), L['l_rows'][k], SMALL - .3,
             INK if state == 'ok' else OCHRE, width=lw - 5.6)
        if state == 'ok':
            mark(lx + lw - 1.8, yc, 'ok')
    route([(sx + sw_, ly + 8.0), (lx, ly + 8.0)], USE, THIN, length=1.0)

    # Maintain and repair ----------------------------------------------------
    qx, qy, qw, qh = MAINT
    route([(lx + lw / 2, ly + lh), (lx + lw / 2, qy)], USE, THIN, length=1.0)
    text(lx + lw / 2 + 1.0, baseline((ly + lh + qy) / 2, SMALL - .5), L['pending'], SMALL - .5,
         OCHRE, 'bold')
    box(MAINT)
    text(qx + 1.3, qy + 3.5, L['maint'], TITLE, INK, 'bold')
    step(qx + qw - 2.2, qy + 2.7, 6, USE)
    text(qx + 1.3, qy + 6.4, L['maint_note'], SMALL - .3, MUTED, width=qw - 2.4)
    text(qx + 1.3, qy + 9.3, L['item_key'], SMALL - .3, INK, width=qw - 4.4)
    mark(qx + qw - 1.8, qy + 8.6, 'fail')
    text(qx + 1.3, qy + 11.8, L['repeats'], SMALL - .3, RED, width=qw - 2.4)
    s.line(qx + 1.0, qy + 13.3, qx + qw - 1.0, qy + 13.3, RULE, .16)
    text(qx + 1.3, qy + 16.1, L['repair'], NOTE, INK, 'bold', width=qw - 2.4)
    text(qx + 1.3, qy + 18.8, "`i_is_current='Y'`", JS, ACC_DK, width=qw - 2.4)
    mark(qx + 2.0, qy + 20.8, 'ok')
    text(qx + 3.4, qy + 21.5, L['regression'], SMALL - .5, ACC_DK, width=qw - 4.0)
    text(qx + 1.3, qy + 24.2, L['to_rev1'], SMALL - .3, ACC_DK, 'bold', width=qw - 2.4)
    text(qx + 1.3, qy + 26.7, L['else'], SMALL - .5, MUTED, width=qw - 2.4)
    # Repair writes the join entry and the metric back at revision 1.
    route([(qx, jc[1]), (sx + sw_, jc[1])], USE, THICK, length=1.0)

    # Check and run ------------------------------------------------------------
    ex, ey, ew, eh = EXEC
    box(EXEC)
    text(ex + 1.3, ey + 3.4, L['exec'], TITLE, INK, 'bold', width=ew - 2.4)
    text(ex + 1.3, ey + 6.4, L['exec2'], TITLE, INK, 'bold', width=ew - 2.4)
    text(ex + 1.3, ey + 9.2, L['exec_note'], SMALL - .3, EXEC_C, 'bold', width=ew - 2.4)
    pill(ex + 1.0, ey + 11.9, 'B', USE)
    text(ex + 4.6, baseline(ey + 11.9, SMALL - .5), L['sketch'], SMALL - .5, MUTED, width=ew - 5.6)
    cx_, cy_, cw_ = ex + 1.0, ey + 13.6, ew - 2.0
    code = ('SUM(ss_net_paid)', 'WHERE i_category', f"= '{L['cat']}'", 'AND d_moy IN', '(7, 8, 9) ...')
    rect(cx_, cy_, cw_, 1.4 + 2.35 * len(code), FACE, None, r=.4)
    for k, line in enumerate(code):
        text(cx_ + .6, cy_ + 2.4 + 2.35 * k, f'`{line}`', JS - .2, INK, width=cw_ - 1.0)
    ry = cy_ + 1.4 + 2.35 * len(code) + 2.8
    for k, label in enumerate(L['exec_rows']):
        yy = ry + 2.7 * k
        mark(ex + 2.0, yy - .7, 'ok', EXEC_C)
        text(ex + 3.3, yy, label, SMALL - .3, INK, width=ew - 4.0)
    fy = ry + 2.7 + 3.6
    s.line(ex + 1.0, fy - 2.0, ex + ew - 1.0, fy - 2.0, RULE, .16)
    pill(ex + 1.0, fy, 'N', USE)
    text(ex + 4.6, baseline(fy, JS), L['feature'], JS, INK, width=ew - 8.5)
    step(ex + ew - 2.2, fy, 7, EXEC_C)
    axis_y, cut = fy + 5.4, ex + 12.4
    rect(ex + 1.6, axis_y - .9, cut - ex - 1.6, 1.8, AMBER_PALE, None, r=.3)
    s.line(ex + 1.6, axis_y, ex + ew - 1.4, axis_y, RULE, .18)
    s.line(cut, axis_y - 1.6, cut, axis_y + 1.1, EXEC_C, .26)
    for dx in (3.6, 6.8, 10.0):
        s.circle(ex + dx, axis_y, .42, EXEC_C)
    for dx in (15.0, 17.6):
        s.line(ex + dx - .35, axis_y - .35, ex + dx + .35, axis_y + .35, MUTED, .18)
        s.line(ex + dx - .35, axis_y + .35, ex + dx + .35, axis_y - .35, MUTED, .18)
    text(cut, axis_y - 2.0, L['cutoff'], SMALL - .8, EXEC_C, align='center')
    text((ex + 1.6 + cut) / 2, axis_y + 3.0, L['window'], SMALL - .8, EXEC_C, align='center')

    # Database -------------------------------------------------------------
    bx, by, bw, bh = SLAB
    d = 1.4
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
        text(x0 + w_ - .9, top + 1.9, version, 5.6, OCHRE if hot else MUTED,
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
    card(ix, iw, '`item`', r'batch 0 $\rightarrow$ 1', hot=True)
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
    nx, nw = EXEC[0], EXEC[2]
    rect(nx, top, nw, inner, WHITE, EXEC_C, .18, r=.35, dash=(.8, .5))
    text(nx + 1.0, top + 2.6, L['snapshot'], SMALL - .3, EXEC_C, 'bold')
    mini = (nw - 2.0 - 2 * .5) / 3
    for k in range(3):
        mx = nx + 1.0 + k * (mini + .5)
        rect(mx, top + 3.5, mini, inner - 4.2, FACE, EDGE, .1, r=.25)
        rect(mx + .15, top + 3.65, mini - .3, 1.0, TOP, None, r=.2)

    # Database reads: the item guard and the snapshot.
    rd = qx + qw / 2 - 2.0
    route([(rd, top), (rd, qy + qh)], SLATE, .3, dash=(.7, .45), length=1.0)
    route([(exec_c, top), (exec_c, ey + eh)], EXEC_C, .3, dash=(.7, .45), length=1.0)

    # ETL ------------------------------------------------------------------
    tx, ty, tw_, th = ETL
    for off in (1.2, .6, 0):
        rect(tx + off, ty - off, tw_ - 1.2, th, WHITE, EDGE, .13, r=.4)
    text(tx + 1.4, ty + 3.5, L['etl'], TITLE, INK, 'bold', width=tw_ - 2.6)
    text(tx + 1.4, ty + 6.5, L['etl_note'], SMALL - .3, OCHRE, width=tw_ - 2.6)
    route([(tx + tw_ - 1.2, ty + th / 2 + 1.2), (bx, ty + th / 2 + 1.2)], INK, THIN, length=1.0)
    step(tx + tw_ + 1.45, ty + th / 2 - 2.2, 5, SLATE)


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
