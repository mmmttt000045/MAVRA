"""Figure 1: independent agents repeat the same exploration for related questions.

The look of the earlier Figure 1 (LLM-agent glyphs, workbench windows, request
streams into one shared database, violet palette) with the content of three
recorded sessions from the 10-01 workload traces
(exp/2026-10-01-workload-characterization, DeepSeek, direct tools, no memory),
all on the metric electronics revenue (M5) and all asked by name only:

  Agent 1  s094  M5-L1  electronics revenue in January
  Agent 2  s073  M5-T2  the month with the highest electronics revenue
  Agent N  s064  M5-T1  September against the same month a year earlier

Every session lists the tables and reads the schemas of store_sales, item and
date_dim (steps 1-4, inside the dashed box, in all 20 sessions of this
metric); only the date filter of the final SQL (step 5) differs. The script
reads the archived traces and checks that each drawn session made exactly
these calls and that its final SQL contains the drawn filter. The session
count comes from gen/workload-example.tex (tools/workload-stats.py
--example M5), which Example 1 also uses. Questions drop the calendar year.
Four request streams per agent stand for its four lookups.
"""
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import MM, PT, measure  # noqa: E402

NAME = 'metric-record'
W, H = style.COLUMN, 55.2

INK = '#332E40'
MUTED = '#81798D'
EDGE = '#A6A0AE'
RULE = '#DCD5EA'
WHITE = '#FFFFFF'
VIOLET = '#8069B6'
DEEP = '#5C478D'
PALE = '#F4F0FA'
MID = '#D8CBEF'
DB_FACE = '#F6F5F8'
LOAD = '#BD533E'           # warm colour: repeated work only
LOAD_PALE = '#FBE7DF'
LOAD_TINT = '#FDF3EF'

RUN = style.ROOT / 'exp/2026-10-01-workload-characterization/deepseek-v4.1-flash'
AGENTS = (('1', 's094', 'M5-L1'), ('2', 's073', 'M5-T2'), ('N', 's064', 'M5-T1'))
LOOKUPS = (('list_tables', None), ('describe_table', 'store_sales'),
           ('describe_table', 'item'), ('describe_table', 'date_dim'))
# The date filter of each final SQL, as drawn and as it must occur in the
# session's final SQL once table aliases and extra spaces are removed.
FILTERS = (('`... AND d_moy = 1`', ('d_moy = 1',)),
           ('`... GROUP BY d_moy`', ('group by d_moy',)),
           ('`... AND d_moy = 9`', ('d_moy = 9',)))
TABLES = ('store_sales', 'item', 'date_dim')

LABELS = {
    'en': {
        'agent': 'Agent', 'ask': 'ask:',
        # One list of lines per question, broken by hand to fit the box.
        'q': (('Jan. electronics', 'revenue?'), ('best month for', 'electronics revenue?'),
              ('Sep. electronics', 'revenue vs. last year?')),
        'repeated': 'Repeated in all {n} sessions', 'skip': 'avoidable with sharing',
        'steps': ('list tables', '`store_sales` schema', '`item` schema', '`date_dim` schema'),
        'database': 'Database',
    },
    'zh': {
        'agent': '智能体', 'ask': '问：',
        'q': (('1 月电子品类', '营业额是多少？'), ('哪个月电子品类', '营业额最高？'),
              ('9 月电子品类', '营业额同比增加多少？')),
        'repeated': '全部 {n} 个会话都重复', 'skip': '共享后可省去',
        'steps': ('列出所有表', '`store_sales` 表结构', '`item` 表结构', '`date_dim` 表结构'),
        'database': '数据库',
    },
}

# Columns: Agent 1, Agent 2, a gap with the ellipsis, Agent N.
CW, GAP, ELL = 25.6, 1.4, 4.6
X0 = (W - 3 * CW - GAP - ELL) / 2
COLS = (X0, X0 + CW + GAP, X0 + 2 * CW + GAP + ELL)
CENTERS = tuple(x + CW / 2 for x in COLS)
DOTS_X = COLS[1] + CW + ELL / 2

GLYPH_Y, GLYPH_K = .5, .72
ASK_Y, ASK_H = 6.7, 7.5
BOX_Y = 16.5                                   # top edge of the dashed box
WIN_Y = 18.0
ROWS = (22.3, 25.9, 29.5, 33.1)                # steps 1-4
BOX_BOTTOM = 35.25
ROW5 = 37.4
WIN_BOTTOM = 39.4
DB_Y, DB_H, RIM = 44.1, 10.6, 2.0
NAME_PT, ASK_PT, HEAD_PT, STEP_PT, CODE_PT = 7.2, 6.4, 6.5, 6.2, 6.0


def plain(sql):
    """Lower-case SQL without table aliases and repeated spaces."""
    sql = re.sub(r'\b[a-z]{1,2}\.(?=[a-z_]+)', '', sql.lower())
    return re.sub(r'\s+', ' ', sql)


def check_sessions():
    """Assert that the drawn sessions made exactly the drawn calls."""
    rows = {json.loads(l)['agent']: json.loads(l) for l in open(RUN / 'sessions.jsonl', encoding='utf-8')}
    calls = {}
    for line in open(RUN / 'trace.jsonl', encoding='utf-8'):
        c = json.loads(line)
        calls.setdefault(c['agent'], []).append(c)
    for (_, agent, task), (_, needles) in zip(AGENTS, FILTERS):
        s = rows[agent]
        assert (s['task'], s['phrasing'], s['metric']) == (task, 'named', 'M5'), agent
        cs = sorted(calls[agent], key=lambda c: (c['step'], c['seq']))
        tools = [(c['tool'], (c.get('args') or {}).get('table')) for c in cs]
        assert tools == list(LOOKUPS) + [('run_sql', None), ('final_answer', None)], (agent, tools)
        final = plain(' '.join(s['final_sql']))
        for needle in needles:
            assert needle in final, (agent, needle, final)


def draw(s, lang):
    L = LABELS[lang]
    check_sessions()
    gen = style.macros('workload-example')
    n_sessions = gen['WxSessions']
    style.agree('sessions that repeat the four lookups', gen['WxFourLookups'], n_sessions)

    def label(x, yc, text, size, color=INK, weight='sans', align='left', width=None):
        """Text whose capitals are centred on yc; returns its width."""
        return s.text(x, yc + .34 * size * PT, text, size, color, weight, align, width)

    def dots(yc, color=VIOLET):
        for k in (-1, 0, 1):
            s.circle(DOTS_X + 1.15 * k, yc, .34, color)

    def ellipse(x, y, w, h, fill=None, stroke=None, sw=.2):
        c = s.c
        c.saveState()
        s._style(fill, stroke, sw)
        c.ellipse(x * MM, (H - y - h) * MM, (x + w) * MM, (H - y) * MM,
                  stroke=stroke is not None, fill=fill is not None)
        c.restoreState()

    def agent_glyph(hx, y, k):
        """Neural head and console torso of the earlier figure's LLM agent."""
        s.poly([(hx - 3.9 * k, y + 7.6 * k), (hx - 3.5 * k, y + 5.9 * k),
                (hx - 1.9 * k, y + 5.0 * k), (hx + 1.9 * k, y + 5.0 * k),
                (hx + 3.5 * k, y + 5.9 * k), (hx + 3.9 * k, y + 7.6 * k)],
               VIOLET, DEEP, .21 * k)
        s.circle(hx, y + 2.7 * k, 2.25 * k, PALE, DEEP, .24 * k)
        nodes = ((hx - 1.1 * k, y + 2.4 * k), (hx, y + 1.6 * k),
                 (hx + 1.1 * k, y + 2.5 * k), (hx, y + 3.6 * k))
        for a, b in ((0, 1), (1, 2), (0, 3), (2, 3), (1, 3)):
            s.line(*nodes[a], *nodes[b], VIOLET, .17 * k)
        for nx, ny in nodes:
            s.circle(nx, ny, .29 * k, DEEP)
        s.rect(hx - 1.9 * k, y + 5.55 * k, 3.8 * k, 1.65 * k, DEEP, None, r=.3 * k)
        s.poly([(hx - 1.1 * k, y + 5.95 * k), (hx - .65 * k, y + 6.3 * k),
                (hx - 1.1 * k, y + 6.65 * k)], None, WHITE, .18 * k, closed=False)
        s.line(hx - .2 * k, y + 6.65 * k, hx + 1.05 * k, y + 6.65 * k, WHITE, .17 * k)

    def step_mark(x, yc, n):
        s.circle(x, yc, .98, WHITE, VIOLET, .2)
        label(x, yc, str(n), 5.8, DEEP, 'bold', 'center')

    # Agents and their questions -------------------------------------------
    aw = measure(L['ask'], ASK_PT, 'bold') + (.75 if lang == 'en' else 0)
    glyph_w = 7.8 * GLYPH_K
    for (x, cx), (n, _, _), lines in zip(zip(COLS, CENTERS), AGENTS, L['q']):
        name = f"{L['agent']} {n}"
        nw = measure(name, NAME_PT, 'bold')
        x0 = cx - (glyph_w + 1.3 + nw) / 2
        agent_glyph(x0 + glyph_w / 2, GLYPH_Y, GLYPH_K)
        label(x0 + glyph_w + 1.3, GLYPH_Y + 3.9 * GLYPH_K, name, NAME_PT, DEEP, 'bold')
        s.rect(x, ASK_Y, CW, ASK_H, WHITE, RULE, .2, r=.7)
        y = ASK_Y + 2.85
        s.text(x + 1.1, y, L['ask'], ASK_PT, DEEP, 'bold')
        for k, line in enumerate(lines):
            room = CW - 2.2 - (aw if k == 0 else 0)
            s.text(x + 1.1 + (aw if k == 0 else 0), y + 2.6 * k, line, ASK_PT, INK, width=room)
    dots(ASK_Y + ASK_H / 2, DEEP)

    # Workbenches: steps 1-4 inside one dashed box, step 5 below it ----------
    s.rect(.35, BOX_Y, W - .7, BOX_BOTTOM - BOX_Y, LOAD_TINT, None, r=.9)
    for x, (code, _) in zip(COLS, FILTERS):
        s.rect(x, WIN_Y, CW, WIN_BOTTOM - WIN_Y, PALE, VIOLET, .24, r=.8)
        for dx in (1.5, 2.5, 3.5):
            s.circle(x + dx, WIN_Y + 1.05, .22, VIOLET)
        s.line(x + CW - 4.0, WIN_Y + 1.05, x + CW - 1.5, WIN_Y + 1.05, VIOLET, .17)
        s.line(x + .4, WIN_Y + 2.1, x + CW - .4, WIN_Y + 2.1, RULE, .17)
        tx = x + 2.2
        s.line(tx, ROWS[0], tx, ROW5, RULE, .24)
        for a, b in zip(ROWS, ROWS[1:] + (ROW5,)):
            s.head(tx, (a + b) / 2 + .35, math.pi / 2, VIOLET, .6)
        for k, (yc, step) in enumerate(zip(ROWS, L['steps'])):
            step_mark(tx, yc, k + 1)
            label(x + 4.0, yc, step, STEP_PT, INK, width=CW - 4.6)
        step_mark(tx, ROW5, 5)
        label(x + 4.0, ROW5, code, CODE_PT, INK, width=CW - 4.6)
    dots((ROWS[1] + ROWS[2]) / 2)
    dots(ROW5)
    s.rect(.35, BOX_Y, W - .7, BOX_BOTTOM - BOX_Y, None, LOAD, .3, r=.9, dash=(1.1, .6))
    for text, size, weight, align, x in ((L['repeated'].format(n=n_sessions), HEAD_PT, 'bold',
                                          'left', 2.3),
                                         (L['skip'], HEAD_PT - .4, 'sans', 'right', W - 2.3)):
        tw = measure(text, size, weight)
        left = x if align == 'left' else x - tw
        s.rect(left - .6, BOX_Y - 1.15, tw + 1.2, 2.3, WHITE, None)
        label(x, BOX_Y, text, size, LOAD, weight, align)

    # One shared database; every agent's four lookups land on it ------------
    x, w = 1.6, W - 3.2
    s.rect(x, DB_Y + RIM / 2, w, DB_H - RIM, DB_FACE)
    ellipse(x, DB_Y + DB_H - RIM, w, RIM, DB_FACE, EDGE, .22)
    s.rect(x + .12, DB_Y + RIM / 2, w - .24, DB_H - RIM, DB_FACE)
    s.line(x, DB_Y + RIM / 2, x, DB_Y + DB_H - RIM / 2, EDGE, .22)
    s.line(x + w, DB_Y + RIM / 2, x + w, DB_Y + DB_H - RIM / 2, EDGE, .22)
    ellipse(x, DB_Y, w, RIM, WHITE, EDGE, .22)
    hot = (19.0, 66.0)
    s.rect(hot[0], DB_Y + .4, hot[1] - hot[0], 1.2, LOAD_PALE, LOAD, .19, r=.5)
    label(W / 2, DB_Y + 3.5, L['database'], NAME_PT, INK, 'bold', 'center')
    tw_, ty, th = 20.0, DB_Y + 4.9, 3.2
    lefts = (7.0, (W - tw_) / 2, W - 7.0 - tw_)
    for tx, name in zip(lefts, TABLES):
        s.rect(tx, ty, tw_, th, WHITE, VIOLET, .21, r=.35)
        s.rect(tx + .13, ty + .13, tw_ - .26, th - .26, PALE, None, r=.25)
        label(tx + tw_ / 2, ty + th / 2, f'`{name}`', 6.3, DEEP, 'sans', 'center',
              width=tw_ - 1.2)
    for a, b in zip(lefts, lefts[1:]):
        x1, x2, yc = a + tw_, b, ty + th / 2
        mx = (x1 + x2) / 2
        s.line(x1, yc, mx - 1.3, yc, VIOLET, .24)
        s.line(mx + 1.3, yc, x2, yc, VIOLET, .24)
        s.poly([(mx - 1.3, yc - .9), (mx + 1.3, yc + .9), (mx + 1.3, yc - .9),
                (mx - 1.3, yc + .9)], WHITE, DEEP, .2)

    def stream(sx, tx):
        p0, p1 = (sx, WIN_BOTTOM), (sx, WIN_BOTTOM + 2.0)
        p2, p3 = (tx, DB_Y - 1.6), (tx, DB_Y + .45)
        s.curve(p0, p1, p2, p3, LOAD, .3)
        s.head(*p3, math.pi / 2, LOAD, .85)

    targets = (27.0, W / 2, W - 27.0)
    for cx, target in zip(CENTERS, targets):
        for k in range(4):
            stream(cx - 2.4 + 1.6 * k, target - 2.1 + 1.4 * k)
    dots((WIN_BOTTOM + DB_Y) / 2, LOAD)
    assert DB_Y + DB_H <= H - .3


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
