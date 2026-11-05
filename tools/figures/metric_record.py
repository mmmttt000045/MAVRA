"""Figure 1: agents repeat the same exploration, and what they find goes stale.

Single column, in the look of the earlier Figure 1 (LLM-agent glyphs,
workbench windows, request streams into one shared database, violet palette).

Top: three recorded sessions from the 10-01 workload traces
(exp/2026-10-01-workload-characterization, DeepSeek, direct tools, no memory),
all on the metric electronics revenue (M5) and all asked by name only:

  Agent 1  s094  M5-L1  electronics revenue in January
  Agent 2  s073  M5-T2  the month with the highest electronics revenue
  Agent N  s091  M5-T1  September against the same month a year earlier

Steps 1-4 (list tables, then read store_sales, item and date_dim) are the
same in all 20 sessions of this metric and sit in one dashed box. Step 5 is
each session's own SQL in a short phrase: Agent 1 sums three candidate
revenue columns, Agent 2 ranks the months, Agent N compares the two years.
The script checks every drawn call and SQL fragment against the trace; the
session count comes from gen/workload-example.tex (tools/workload-stats.py
--example M5), which Example 1 also uses. Questions drop the calendar year.

Bottom: the database these sessions read. Their SQL joins item on the item
key without a current-row filter, right while item holds one row per key.
An ETL job that loads item history (SCD Type 2) adds a second row for an
item, the case Figure 2 continues with (item 17, as there), and the same SQL
then counts the item's sales twice.
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
W, H = style.COLUMN, 65.1

INK = '#332E40'
MUTED = '#81798D'
EDGE = '#A6A0AE'
RULE = '#DCD5EA'
WHITE = '#FFFFFF'
VIOLET = '#8069B6'
DEEP = '#5C478D'
PALE = '#F4F0FA'
DB_FACE = '#F6F5F8'
LOAD = '#BD533E'           # warm colour: repeated work and its failure
LOAD_PALE = '#FBE7DF'
LOAD_TINT = '#FDF3EF'
AMBER = '#B7791F'
AMBER_PALE = '#FBEDCE'

RUN = style.ROOT / 'exp/2026-10-01-workload-characterization/deepseek-v4.1-flash'
AGENTS = (('1', 's094', 'M5-L1'), ('2', 's073', 'M5-T2'), ('N', 's091', 'M5-T1'))
LOOKUPS = (('list_tables', None), ('describe_table', 'store_sales'),
           ('describe_table', 'item'), ('describe_table', 'date_dim'))
# Each session's own SQL after the lookups, as fragments that must occur in
# its run_sql calls (lower case, table aliases removed).
OWN_SQL = ((('sum(ss_ext_sales_price)', 'sum(ss_net_paid)', 'sum(ss_net_paid_inc_tax)', 'd_moy = 1'),),
           (('group by d_moy', 'order by revenue desc'),),
           (('d_moy = 9', 'group by d_year'),
            ('case when d_year=2002 then', 'case when d_year=2001 then')))

LABELS = {
    'en': {
        'agent': 'Agent', 'ask': 'ask:',
        # One list of lines per question, broken by hand to fit the box.
        'q': (('Jan. electronics', 'revenue?'), ('best month for', 'electronics revenue?'),
              ('Sep. electronics', 'revenue vs. last year?')),
        'repeated': 'Repeated in all {n} sessions', 'skip': 'avoidable with sharing',
        'steps': ('list tables', 'read sales table', 'read item table', 'read date table'),
        'own': ('try 3 revenue columns', 'rank the 12 months', 'compare two years'),
        'database': 'Database',
        'rows': ('current', 'history'),
        'etl': 'ETL: item history',
        'stale': 'same SQL now counts item 17 twice',
    },
    'zh': {
        'agent': '智能体', 'ask': '问：',
        'q': (('1 月电子品类', '营业额是多少？'), ('哪个月电子品类', '营业额最高？'),
              ('9 月电子品类', '营业额同比增加多少？')),
        'repeated': '全部 {n} 个会话都重复', 'skip': '共享后可省去',
        'steps': ('列出所有表', '读销售表', '读商品表', '读日期表'),
        'own': ('试 3 个营业额列', '给 12 个月排序', '比较两年'),
        'database': '数据库',
        'rows': ('当前', '历史'),
        'etl': 'ETL：商品历史版本',
        'stale': '同一 SQL 现在把商品 17 算了两次',
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
DB_Y, DB_H, RIM = 44.1, 20.6, 2.0
NAME_PT, ASK_PT, HEAD_PT, STEP_PT, NOTE_PT, CELL_PT = 7.2, 6.4, 6.5, 6.3, 6.1, 6.2


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
    for (_, agent, task), own in zip(AGENTS, OWN_SQL):
        s = rows[agent]
        assert (s['task'], s['phrasing'], s['metric']) == (task, 'named', 'M5'), agent
        cs = sorted(calls[agent], key=lambda c: (c['step'], c['seq']))
        tools = [(c['tool'], (c.get('args') or {}).get('table')) for c in cs]
        want = list(LOOKUPS) + [('run_sql', None)] * len(own) + [('final_answer', None)]
        assert tools == want, (agent, tools)
        sqls = [plain(c['args']['sql']) for c in cs if c['tool'] == 'run_sql']
        for sql, needles in zip(sqls, own):
            for needle in needles:
                assert needle in sql, (agent, needle, sql)
        # The joins read item on the item key with no current-row filter.
        for sql in sqls:
            assert 'join item' in sql and 'i_is_current' not in sql, (agent, sql)


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

    def step_mark(x, yc, n, edge=VIOLET):
        s.circle(x, yc, .98, WHITE, edge, .2)
        label(x, yc, str(n), 5.8, DEEP, 'bold', 'center')

    def tagged(x, y, text, size, color, weight, align):
        """Text on a white patch, so that it interrupts a dashed border."""
        tw = measure(text, size, weight)
        left = x if align == 'left' else x - tw
        s.rect(left - .6, y - 1.15, tw + 1.2, 2.3, WHITE, None)
        label(x, y, text, size, color, weight, align)

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

    # Workbenches: steps 1-4 inside one dashed box, the agent's own step below
    s.rect(.35, BOX_Y, W - .7, BOX_BOTTOM - BOX_Y, LOAD_TINT, None, r=.9)
    for x, own in zip(COLS, L['own']):
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
        step_mark(tx, ROW5, 5, DEEP)
        label(x + 4.0, ROW5, own, STEP_PT, DEEP, width=CW - 4.6)
    dots((ROWS[1] + ROWS[2]) / 2)
    dots(ROW5)
    s.rect(.35, BOX_Y, W - .7, BOX_BOTTOM - BOX_Y, None, LOAD, .3, r=.9, dash=(1.1, .6))
    tagged(2.3, BOX_Y, L['repeated'].format(n=n_sessions), HEAD_PT, LOAD, 'bold', 'left')
    tagged(W - 2.3, BOX_Y, L['skip'], HEAD_PT - .4, LOAD, 'sans', 'right')

    # One shared database; an item-history load breaks the agents' join ----
    x, w = 1.6, W - 3.2
    s.rect(x, DB_Y + RIM / 2, w, DB_H - RIM, DB_FACE)
    ellipse(x, DB_Y + DB_H - RIM, w, RIM, DB_FACE, EDGE, .22)
    s.rect(x + .12, DB_Y + RIM / 2, w - .24, DB_H - RIM, DB_FACE)
    s.line(x, DB_Y + RIM / 2, x, DB_Y + DB_H - RIM / 2, EDGE, .22)
    s.line(x + w, DB_Y + RIM / 2, x + w, DB_Y + DB_H - RIM / 2, EDGE, .22)
    ellipse(x, DB_Y, w, RIM, WHITE, EDGE, .22)
    hot = (19.0, 66.0)
    s.rect(hot[0], DB_Y + .4, hot[1] - hot[0], 1.2, LOAD_PALE, LOAD, .19, r=.5)
    label(W / 2, DB_Y + 3.6, L['database'], NAME_PT, INK, 'bold', 'center')

    def chip(tx, ty, tw, name):
        s.rect(tx, ty, tw, 3.2, WHITE, VIOLET, .21, r=.35)
        s.rect(tx + .13, ty + .13, tw - .26, 2.94, PALE, None, r=.25)
        label(tx + tw / 2, ty + 1.6, f'`{name}`', 6.3, DEEP, 'sans', 'center', width=tw - 1.2)

    ty = DB_Y + 5.4
    dd = (4.4, 16.5)                           # x, width
    ss = (26.6, 22.0)
    it = (57.6, 23.4)
    chip(dd[0], ty, dd[1], 'date_dim')
    chip(ss[0], ty, ss[1], 'store_sales')
    # The item card shows its rows for item 17: the current one and the row an
    # ETL job added when it loaded item history.
    rh = 3.0
    ih = 3.2 + 2 * rh + .35
    s.rect(it[0], ty, it[1], ih, WHITE, VIOLET, .21, r=.35)
    s.rect(it[0] + .13, ty + .13, it[1] - .26, 2.94, PALE, None, r=.25)
    label(it[0] + it[1] / 2, ty + 1.6, '`item`', 6.3, DEEP, 'sans', 'center')
    rows = []
    for k, (flag, note) in enumerate(zip(("'Y'", "'N'"), L['rows'])):
        yc = ty + 3.2 + rh * k + rh / 2
        if k:
            s.rect(it[0] + .25, yc - rh / 2 + .15, it[1] - .5, rh - .3, AMBER_PALE, None, r=.3)
        label(it[0] + 1.3, yc, '`17`', CELL_PT, INK)
        label(it[0] + 5.2, yc, f'`{flag}`', CELL_PT, INK)
        label(it[0] + it[1] - 1.2, yc, note, 5.9, AMBER if k else MUTED,
              'bold' if k else 'sans', 'right')
        rows.append(yc)
    # date_dim joins store_sales; store_sales now matches both rows of item 17.
    yc = ty + 1.6
    x1, x2 = dd[0] + dd[1], ss[0]
    mx = (x1 + x2) / 2
    s.line(x1, yc, mx - 1.2, yc, VIOLET, .24)
    s.line(mx + 1.2, yc, x2, yc, VIOLET, .24)
    s.poly([(mx - 1.2, yc - .9), (mx + 1.2, yc + .9), (mx + 1.2, yc - .9),
            (mx - 1.2, yc + .9)], WHITE, DEEP, .2)
    sx = ss[0] + ss[1]
    bend = sx + 3.6
    for r_ in rows:
        s.route([(sx, yc), (bend, yc), (bend, r_), (it[0], r_)], LOAD, .3, radius=.6, length=.85)
    # The ETL load and its consequence.
    base = ty + ih + 2.5
    ex = it[0] + it[1] / 2
    s.route([(ex, base - 1.2), (ex, ty + ih)], AMBER, .3, length=.85)
    label(ex, base + .2, L['etl'], NOTE_PT, AMBER, 'bold', 'center', width=it[1] + 3)
    label(dd[0], base + .2, L['stale'], NOTE_PT, LOAD, 'bold', 'left', width=it[0] - dd[0] - 2)

    # Request streams: every agent's four lookups land on the same tables.
    def stream(sx_, tx_):
        p0, p1 = (sx_, WIN_BOTTOM), (sx_, WIN_BOTTOM + 2.0)
        p2, p3 = (tx_, DB_Y - 1.5), (tx_, DB_Y + .5)
        s.curve(p0, p1, p2, p3, LOAD, .3)
        s.head(*p3, math.pi / 2, LOAD, .85)

    targets = (27.0, W / 2, W - 27.0)
    for cx, target in zip(CENTERS, targets):
        for k in range(4):
            stream(cx - 2.4 + 1.6 * k, target - 2.1 + 1.4 * k)
    dots((WIN_BOTTOM + DB_Y) / 2, LOAD)
    assert DB_Y + DB_H <= H - .3, DB_Y + DB_H
    assert base + 1.5 <= DB_Y + DB_H - RIM / 2, base


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
