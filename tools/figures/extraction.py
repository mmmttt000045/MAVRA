"""Extraction and checked publication (Section IV-B), single column.

Agent 1's verified session (January electronics revenue, the M5-L1 learning
task) becomes a parameterized definition: the learning agent drafts the JSON
fields of Fig. 2, the month literal becomes the period input, and the server
derives the data conditions. Publication needs every gate; the last one runs
the SQL compiled from the draft for January and must return the verified
answer.

Values are from the recorded runs on the TPC-DS fixture: the verified answer
2,754,299.60 (sessions s094 etc. of exp/2026-10-01-workload-characterization),
and a rejected draft (exp/2026-10-31-diverse-scenarios/case-evidence.json,
M5-L1, failed gate G7) whose compiled SQL returned 13,532,799.00, January
revenue over all categories, because it lacked the electronics filter.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import ACC, ACC_DK, ACC_PALE, EDGE, FACE, INK, RED, RULE, SLATE, WHITE  # noqa: E402
from smallparts import (BODY, CODE, KEYC, LEARN, LEARN_PALE, NOTE, SMALL, THICK, THIN,  # noqa: E402
                        Kit, baseline)

NAME = 'extraction'
W, H = style.COLUMN, 51.0
VERIFIED, WRONG_VALUE = '2,754,299.60', '13,532,799.00'

LABELS = {
    'en': {
        'agent': 'Agent 1', 'verified': ('answer verified:', VERIFIED),
        'ask': 'ask:', 'q': 'Jan. electronics revenue?',
        'cat': 'Electronics', 'literal_note': "this question's month",
        'draft': 'Learning agent drafts JSON', 'period': r'month $\rightarrow$ period',
        'conds': 'Derived conditions',
        'cond_rows': ('item key unique', 'date key unique', 'sales grain unique', 'joins stay complete'),
        'checks': 'Checks before publishing',
        'gates': ('business basis', 'fields, joins', 'grain key', 'read-only SQL'),
        'same': 'same answer?', 'session_sql': 'session SQL', 'compiled_sql': 'compiled SQL, period = Jan.',
        'wrong': ('rejected:', 'draft missing the filter'),
        'shared': 'Shared knowledge', 'entry': 'Electronics revenue', 'rev0': 'rev 0', 'publish': 'publish',
    },
    'zh': {
        'agent': '智能体 1', 'verified': ('答案经核对：', VERIFIED),
        'ask': '问：', 'q': '1 月电子品类营业额？',
        'cat': '电子', 'literal_note': '本题的月份',
        'draft': '学习智能体起草 JSON', 'period': r'月份 $\rightarrow$ 期间参数',
        'conds': '推导出的条件',
        'cond_rows': ('item 键唯一', '日期键唯一', '销售粒度唯一', '连接保持完整'),
        'checks': '发布前检查',
        'gates': ('口径依据', '字段与连接', '粒度键', '只读 SQL'),
        'same': '答案一致？', 'session_sql': '会话 SQL', 'compiled_sql': '编译 SQL，期间 = 1 月',
        'wrong': ('不予发布：', '漏掉品类过滤的草稿'),
        'shared': '共享知识', 'entry': '电子品类营业额', 'rev0': '修订 0', 'publish': '发布',
    },
}

ROW = 2.35                       # JSON line pitch


def draw(s, lang):
    L = LABELS[lang]
    k = Kit(s)
    text = s.text

    # Agent 1's verified session ------------------------------------------------
    nx, ny, nw, nh = 1.0, 2.0, 81.4, 12.6
    k.node(nx, ny, nw, nh)
    k.person(nx + 2.3, ny + 1.45)
    text(nx + 4.6, ny + 3.0, L['agent'], BODY, LEARN, 'bold')
    k.rich(nx + nw - 1.2, ny + 2.2, (L['verified'][0], f'`{L["verified"][1]}`'), SMALL - .2, LEARN,
           align='right')
    aw = text(nx + 1.2, ny + 5.7, L['ask'], SMALL, ACC_DK, 'bold')
    text(nx + 1.2 + aw + (.8 if lang == 'en' else 0), ny + 5.7, L['q'], SMALL, INK)
    cx, cy, cw = nx + 1.0, ny + 6.9, nw - 2.0
    s.rect(cx, cy, cw, 1.0 + 2 * 2.3, FACE, None, r=.4)
    text(cx + .5, cy + 2.2, '`SELECT SUM(ss_net_paid) FROM store_sales JOIN item ... JOIN date_dim ...`',
         CODE, INK, width=cw - .9)
    y2 = cy + 4.5
    head = f"`WHERE i_category = '{L['cat']}' AND `"
    hw = text(cx + .5, y2, head, CODE, INK)
    lit = '`d_moy = 1`'
    litw = measure(lit, CODE)
    s.rect(cx + .5 + hw - .3, y2 - 1.75, litw + .6, 2.3, LEARN_PALE, None, r=.3)
    text(cx + .5 + hw, y2, lit, CODE, LEARN)
    text(cx + .5 + hw + litw, y2, '` AND ...`', CODE, INK)
    text(cx + cw - .6, y2, L['literal_note'], NOTE - .3, LEARN, align='right')

    # Step 1: the session enters the learning agent ----------------------------------
    dx0, dy0 = 1.0, 19.0
    a1 = 12.0
    s.route([(a1, ny + nh), (a1, dy0)], LEARN, THIN, length=.9)
    k.step(a1 + 2.6, (ny + nh + dy0) / 2, 1)

    # The draft definition (JSON fields as stored, cf. Fig. 2) --------------------
    dw = 53.2
    rows = (('fact', '`"store_sales"`'), ('measure', '`"sum(ss_net_paid)"`'),
            ('filters', f"`{{\"item\": \"i_category = '{L['cat']}'\"}}`"),
            ('time', '`{"dim": "date_dim", ...}`'))
    dh = 3.0 + .5 + ROW * len(rows) + .5
    k.box(dx0, dy0, dw, dh, WHITE, LEARN, .16, r=.5)
    s.rect(dx0 + .15, dy0 + .15, dw - .3, 2.85, LEARN_PALE, None, r=.4)
    k.sparkle(dx0 + 1.9, dy0 + 1.6, 1.0, LEARN)
    text(dx0 + 3.6, baseline(dy0 + 1.6, SMALL), L['draft'], SMALL, INK, 'bold')
    keyw = 10.2
    for i, (field, value) in enumerate(rows):
        yc = dy0 + 3.5 + ROW * i + ROW / 2
        text(dx0 + .9, baseline(yc, CODE), f'`"{field}"`', CODE, KEYC)
        vw = text(dx0 + .9 + keyw, baseline(yc, CODE), value, CODE, INK, width=dw - 1.8 - keyw)
        if field == 'time':
            text(dx0 + dw - .9, baseline(yc, NOTE - .3), L['period'], NOTE - .3, LEARN, 'bold', 'right',
                 width=dw - 2.6 - keyw - vw)

    # Derived conditions (server side) -----------------------------------------------
    gx, gw = dx0 + dw + 3.2, 83.6 - (dx0 + dw + 3.2)
    k.box(gx, dy0, gw, dh, WHITE, EDGE, .16, r=.5)
    s.rect(gx + .15, dy0 + .15, gw - .3, 2.85, '#E6E9EE', None, r=.4)
    text(gx + 1.0, baseline(dy0 + 1.6, SMALL), L['conds'], SMALL, SLATE, 'bold', width=gw - 1.6)
    for i, label in enumerate(L['cond_rows']):
        yc = dy0 + 3.5 + ROW * i + ROW / 2
        s.rect(gx + 1.1, yc - .45, .9, .9, SLATE, None, r=.15)
        text(gx + 2.7, baseline(yc, SMALL - .4), label, SMALL - .4, INK, width=gw - 3.4)
    s.route([(dx0 + dw, dy0 + dh / 2 + 1.5), (gx, dy0 + dh / 2 + 1.5)], SLATE, THIN, length=.8)

    # Checks before publishing (G1-G7) -------------------------------------------------
    by0 = dy0 + dh + 3.0
    s.route([(a1, dy0 + dh), (a1, by0)], LEARN, THIN, length=.9)
    bx0, bw = 1.0, 57.0
    bh = H - .8 - by0
    k.box(bx0, by0, bw, bh, WHITE, LEARN, .16, r=.5)
    text(bx0 + 1.2, by0 + 2.9, L['checks'], SMALL + .2, INK, 'bold')
    xx = bx0 + 1.2
    gy = by0 + 5.4
    for label in L['gates']:
        k.mark(xx + .6, gy - .7, 'ok', LEARN, .9)
        xx += 1.8 + text(xx + 1.6, gy, label, SMALL - .5, INK) + 1.6
    assert xx < bx0 + bw, xx
    s.line(bx0 + 1.0, gy + 1.1, bx0 + bw - 1.0, gy + 1.1, RULE, .14)
    text(bx0 + 1.2, gy + 3.5, L['same'], SMALL - .3, LEARN, 'bold')
    vx = bx0 + bw - 3.6                                   # right edge of the values
    for i, label in enumerate((L['session_sql'], L['compiled_sql'])):
        yy = gy + 3.5 + 2.3 * i
        text(bx0 + 15.0, yy, label, SMALL - .5, INK)
        text(vx, yy, f'`{VERIFIED}`', CODE, INK, align='right')
        k.mark(vx + 1.6, yy - .7, 'ok', LEARN, .9)
    yy = gy + 3.5 + 2.3 * 2
    text(bx0 + 1.2, yy, L['wrong'][0], SMALL - .3, RED, 'bold')
    text(bx0 + 15.0, yy, L['wrong'][1], SMALL - .5, RED, width=vx - 14.0 - bx0 - 15.0)
    text(vx, yy, f'`{WRONG_VALUE}`', CODE, RED, align='right')
    k.mark(vx + 1.6, yy - .7, 'fail', RED, .8)
    assert yy + .8 < by0 + bh, (yy, by0 + bh)

    # Step 2: publish revision 0 into the shared knowledge ------------------------------
    sx, sw = bx0 + bw + 3.6, 83.6 - (bx0 + bw + 3.6)
    sy, sh = by0 + 1.2, bh - 2.4
    s.rect(sx + .8, sy + .8, sw - .8, sh, '#DCD9D3', EDGE, .12, r=.6)
    k.box(sx, sy, sw - .8, sh, WHITE, EDGE, .16)
    k.header(sx, sy, sw - .8, L['shared'], ACC, size=SMALL - .4)
    ey = sy + 4.0
    s.rect(sx + .8, ey, sw - 2.4, sh - 4.8, ACC_PALE, ACC, .14, r=.4)
    text(sx + 1.5, ey + 2.6, L['entry'], SMALL - .6, INK, 'bold', width=sw - 3.6)
    k.pill(sx + 1.5, ey + 4.9, L['rev0'], LEARN, size=5.2, h=2.0)
    ay = by0 + bh / 2 + 1.0
    s.route([(bx0 + bw, ay), (sx, ay)], LEARN, THICK, length=1.0)
    k.step(bx0 + bw + 1.8, ay - 3.0, 2, r=1.3)


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
