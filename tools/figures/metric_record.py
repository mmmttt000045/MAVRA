"""Figure 1: agents repeat the same exploration, and what they find goes stale.

Full text width, in the look of the earlier Figure 1 (LLM-agent glyphs,
workbench windows, request streams into one shared database, violet palette).

Top: three recorded sessions from the 10-01 workload traces
(exp/2026-10-01-workload-characterization, DeepSeek, direct tools, no memory),
all on the metric electronics revenue (M5) and all asked by name only:

  Agent 1  s094  M5-L1  electronics revenue in January
  Agent 2  s073  M5-T2  the month with the highest electronics revenue
  Agent N  s091  M5-T1  September against the same month a year earlier

Steps 1-4 (list tables, then the store_sales, item and date_dim profiles) are
the same in all 20 sessions of this metric and sit in one dashed box. Steps
5-6 are each session's own: Agent 1 sums three candidate revenue columns for
January, Agent 2 totals two candidates per month and ranks the months, Agent N
totals two candidates per year and then subtracts; all three answer with
ss_ext_sales_price. The script checks every drawn call and SQL fragment
against the trace; the session count comes from gen/workload-example.tex
(tools/workload-stats.py --example M5), which Example 1 also uses.

Bottom: the database these sessions read. Their SQL joins item on the item
key without a current-row filter, which is right while item holds one row per
key (the profile the agents read: 1,000 rows, 1,000 keys, i_is_current always
'Y'). An ETL job that loads item history (SCD Type 2) adds a second row for an
item, the case Figure 2 continues with (key 17, as there): the same SQL then
matches both rows and counts the item's sales twice, without an error.
Questions drop the calendar year of the dataset.
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
W, H = style.TEXTWIDTH, 77.2

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
# its run_sql calls (lower case, table aliases removed), and the measure its
# final answer uses.
OWN_SQL = ((('sum(ss_ext_sales_price)', 'sum(ss_net_paid)', 'sum(ss_net_paid_inc_tax)', 'd_moy = 1'),),
           (('sum(ss_ext_sales_price)', 'sum(ss_net_paid)', 'group by d_moy'),),
           (('sum(ss_ext_sales_price)', 'sum(ss_net_paid)', 'd_moy = 9', 'group by d_year'),
            ('case when d_year=2002 then ss_ext_sales_price', 'case when d_year=2001 then ss_ext_sales_price')))

LABELS = {
    'en': {
        'agent': 'Agent', 'ask': 'ask:',
        'q': ('Jan. electronics revenue?', 'best month for electronics revenue?',
              'Sep. electronics revenue vs. last year?'),
        'repeated': 'Repeated in all {n} sessions', 'skip': 'avoidable with sharing',
        'own_tag': 'steps 5–6 differ per agent',
        'steps': ('list tables: find the sales, item, date tables',
                  'inspect `store_sales`: revenue and key columns',
                  'inspect `item`: category values, one row per item',
                  'inspect `date_dim`: month column'),
        'own': (('sum 3 candidate revenue columns', 'answer with `ss_ext_sales_price`'),
                ('sum 2 candidate columns per month', 'rank months by `ss_ext_sales_price`'),
                ('sum 2 candidate columns per year', 'subtract last year from this year')),
        'database': 'Database',
        'cols': {'date_dim': ('d_date_sk', 'd_moy'),
                 'store_sales': ('ss_item_sk', 'ss_sold_date_sk', 'ss_net_paid'),
                 'item': ('i_item_sk', 'i_category', 'i_is_current')},
        'cat': "'Electronics'",
        'etl': ('ETL job', 'loads item', 'history'),
        'broken': 'no longer one row per item',
        'stale': 'After the load, one sale of item 17 matches two item rows, so the agents’ query counts it twice, without any error.',
    },
    'zh': {
        'agent': '智能体', 'ask': '问：',
        'q': ('1 月电子品类营业额？', '哪个月电子品类营业额最高？', '9 月电子品类营业额同比增加多少？'),
        'repeated': '全部 {n} 个会话都重复', 'skip': '共享后可省去',
        'own_tag': '第 5–6 步各不相同',
        'steps': ('列出所有表：找到销售、商品、日期表',
                  '查看 `store_sales`：营业额列与键列',
                  '查看 `item`：品类取值，每个商品一行',
                  '查看 `date_dim`：月份列'),
        'own': (('对 3 个候选营业额列求和', '用 `ss_ext_sales_price` 作答'),
                ('按月对 2 个候选列求和', '按 `ss_ext_sales_price` 取最高月'),
                ('按年对 2 个候选列求和', '用今年减去去年')),
        'database': '数据库',
        'cols': {'date_dim': ('d_date_sk', 'd_moy'),
                 'store_sales': ('ss_item_sk', 'ss_sold_date_sk', 'ss_net_paid'),
                 'item': ('i_item_sk', 'i_category', 'i_is_current')},
        'cat': "'电子'",
        'etl': ('ETL 作业', '装载商品', '历史版本'),
        'broken': '不再是每个商品一行',
        'stale': '装载之后，商品 17 的一笔销售匹配两行商品记录，智能体的查询把它算了两次，且不报任何错误。',
    },
}

# Columns: Agent 1, Agent 2, a gap with the ellipsis, Agent N.
CW, GAP, ELL = 54.0, 3.0, 9.0
X0 = (W - 3 * CW - GAP - ELL) / 2
COLS = (X0, X0 + CW + GAP, X0 + 2 * CW + GAP + ELL)
CENTERS = tuple(x + CW / 2 for x in COLS)
DOTS_X = COLS[1] + CW + ELL / 2

GLYPH_Y, GLYPH_K = .6, .85
ASK_Y, ASK_H = 8.3, 5.4
BOX_Y = 15.7                                   # top edge of the dashed box
WIN_Y = 17.4
ROWS = (21.9, 25.9, 29.9, 33.9)                # steps 1-4
BOX_BOTTOM = 36.3
OWN = (38.7, 42.7)                             # steps 5-6
WIN_BOTTOM = 45.1
DB_X, DB_Y, DB_W, DB_H, RIM = 2.0, 50.2, 146.0, 26.4, 2.6
NAME_PT, ASK_PT, HEAD_PT, STEP_PT, NOTE_PT, CELL_PT = 7.6, 7.0, 7.0, 6.9, 6.5, 6.4


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
                assert needle in sql.replace(' = ', '=') or needle in sql, (agent, needle, sql)
        # The SQL the agent states with its answer sums gross sales only.
        final = plain(s['run']['sql'])
        assert 'ss_ext_sales_price' in final and 'ss_net_paid' not in final.split(' from ')[0], agent


def draw(s, lang):
    L = LABELS[lang]
    check_sessions()
    gen = style.macros('workload-example')
    n_sessions = gen['WxSessions']
    style.agree('sessions that repeat the four lookups', gen['WxFourLookups'], n_sessions)

    def label(x, yc, text, size, color=INK, weight='sans', align='left', width=None):
        """Text whose capitals are centred on yc; returns its width."""
        return s.text(x, yc + .34 * size * PT, text, size, color, weight, align, width)

    def dots(x, yc, color=VIOLET):
        for k in (-1, 0, 1):
            s.circle(x + 1.25 * k, yc, .38, color)

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
        s.circle(x, yc, 1.15, WHITE, edge, .22)
        label(x, yc, str(n), 6.2, DEEP, 'bold', 'center')

    def tagged(x, y, text, size, color, weight, align):
        """Text on a white patch, so that it interrupts a dashed border."""
        tw = measure(text, size, weight)
        left = x if align == 'left' else x - tw
        s.rect(left - .7, y - 1.35, tw + 1.4, 2.7, WHITE, None, r=.4)
        label(x, y, text, size, color, weight, align)

    # Agents and their questions -------------------------------------------
    aw = measure(L['ask'], ASK_PT, 'bold') + (.8 if lang == 'en' else 0)
    glyph_w = 7.8 * GLYPH_K
    for (x, cx), (n, _, _), q in zip(zip(COLS, CENTERS), AGENTS, L['q']):
        name = f"{L['agent']} {n}"
        nw = measure(name, NAME_PT, 'bold')
        x0 = cx - (glyph_w + 1.5 + nw) / 2
        agent_glyph(x0 + glyph_w / 2, GLYPH_Y, GLYPH_K)
        label(x0 + glyph_w + 1.5, GLYPH_Y + 3.9 * GLYPH_K, name, NAME_PT, DEEP, 'bold')
        s.rect(x, ASK_Y, CW, ASK_H, WHITE, RULE, .22, r=.8)
        label(x + 1.4, ASK_Y + ASK_H / 2, L['ask'], ASK_PT, DEEP, 'bold')
        label(x + 1.4 + aw, ASK_Y + ASK_H / 2, q, ASK_PT, INK, width=CW - 2.8 - aw)
    dots(DOTS_X, ASK_Y + ASK_H / 2, DEEP)

    # Workbenches: steps 1-4 inside one dashed box, the agent's own steps below
    s.rect(.5, BOX_Y, W - 1.0, BOX_BOTTOM - BOX_Y, LOAD_TINT, None, r=1.0)
    for x, own in zip(COLS, L['own']):
        s.rect(x, WIN_Y, CW, WIN_BOTTOM - WIN_Y, PALE, VIOLET, .26, r=.9)
        for dx in (1.8, 3.0, 4.2):
            s.circle(x + dx, WIN_Y + 1.15, .26, VIOLET)
        s.line(x + CW - 5.0, WIN_Y + 1.15, x + CW - 1.8, WIN_Y + 1.15, VIOLET, .2)
        s.line(x + .5, WIN_Y + 2.3, x + CW - .5, WIN_Y + 2.3, RULE, .2)
        tx = x + 2.6
        s.line(tx, ROWS[0], tx, OWN[-1], RULE, .26)
        marks = ROWS + OWN
        for a, b in zip(marks, marks[1:]):
            s.head(tx, (a + b) / 2 + .45, math.pi / 2, VIOLET, .7)
        for k, (yc, step) in enumerate(zip(ROWS, L['steps'])):
            step_mark(tx, yc, k + 1)
            label(x + 4.8, yc, step, STEP_PT, INK, width=CW - 5.6)
        for k, (yc, step) in enumerate(zip(OWN, own)):
            step_mark(tx, yc, k + 5, DEEP)
            label(x + 4.8, yc, step, STEP_PT, DEEP, width=CW - 5.6)
    dots(DOTS_X, (ROWS[1] + ROWS[2]) / 2)
    dots(DOTS_X, sum(OWN) / 2)
    s.rect(.5, BOX_Y, W - 1.0, BOX_BOTTOM - BOX_Y, None, LOAD, .34, r=1.0, dash=(1.3, .7))
    tagged(2.6, BOX_Y, L['repeated'].format(n=n_sessions), HEAD_PT, LOAD, 'bold', 'left')
    tagged(W - 2.6, BOX_Y, L['skip'], HEAD_PT - .3, LOAD, 'sans', 'right')
    tagged(W - 2.6, BOX_BOTTOM, L['own_tag'], NOTE_PT, DEEP, 'sans', 'right')

    # The database the agents read, before and after an item-history load ---
    x, y, w, h = DB_X, DB_Y, DB_W, DB_H
    s.rect(x, y + RIM / 2, w, h - RIM, DB_FACE)
    ellipse(x, y + h - RIM, w, RIM, DB_FACE, EDGE, .24)
    s.rect(x + .12, y + RIM / 2, w - .24, h - RIM, DB_FACE)
    s.line(x, y + RIM / 2, x, y + h - RIM / 2, EDGE, .24)
    s.line(x + w, y + RIM / 2, x + w, y + h - RIM / 2, EDGE, .24)
    ellipse(x, y, w, RIM, WHITE, EDGE, .24)
    hot = (20.0, 144.0)
    s.rect(hot[0], y + .55, hot[1] - hot[0], 1.5, LOAD_PALE, LOAD, .2, r=.6)
    label(x + w / 2, y + 4.7, L['database'], NAME_PT, INK, 'bold', 'center')

    def table(tx, ty, tw, name, cols, rows, widths):
        """A table card: name band, column names, and data rows (list of cells)."""
        rh, ch = 3.1, 2.9
        th = 3.2 + ch + rh * len(rows) + .4
        s.rect(tx, ty, tw, th, WHITE, VIOLET, .24, r=.4)
        s.rect(tx + .15, ty + .15, tw - .3, 2.9, PALE, None, r=.3)
        label(tx + tw / 2, ty + 1.6, f'`{name}`', 6.9, DEEP, 'sans', 'center', width=tw - 1.6)
        xs = [tx + 1.2]
        for wd in widths[:-1]:
            xs.append(xs[-1] + wd)
        for cx_, col in zip(xs, cols):
            label(cx_, ty + 3.2 + ch / 2, f'`{col}`', 5.9, MUTED)
        s.line(tx + .4, ty + 3.2 + ch, tx + tw - .4, ty + 3.2 + ch, RULE, .18)
        centres = []
        for k, (cells, fill) in enumerate(rows):
            yc = ty + 3.2 + ch + rh * k + rh / 2
            if fill:
                s.rect(tx + .25, yc - rh / 2 + .15, tw - .5, rh - .3, fill, None, r=.3)
            for cx_, cell in zip(xs, cells):
                if cell == '~':
                    s.rect(cx_, yc - .35, 6.0, .7, RULE, None, r=.35)
                elif cell:
                    label(cx_, yc, f'`{cell}`', CELL_PT, INK)
            centres.append(yc)
        return th, centres

    ty = y + 7.2
    dd_x, dd_w = 7.0, 27.0
    th, _ = table(dd_x, ty, dd_w, 'date_dim', L['cols']['date_dim'],
                  [(('~', '~'), None), (('~', '~'), None)], (14.0, 11.0))
    ss_x, ss_w = 43.0, 46.0
    _, ss_rows = table(ss_x, ty, ss_w, 'store_sales', L['cols']['store_sales'],
                       [(('17', '~', '~'), LOAD_PALE), (('~', '~', '~'), None)], (13.5, 18.5, 12.0))
    it_x, it_w = 98.0, 45.0
    _, it_rows = table(it_x, ty, it_w, 'item', L['cols']['item'],
                       [(('17', L['cat'], "'Y'"), None), (('17', L['cat'], "'N'"), AMBER_PALE)],
                       (12.0, 18.5, 12.5))
    # Star joins: store_sales in the middle.
    for x1, x2 in ((dd_x + dd_w, ss_x), (ss_x + ss_w, it_x)):
        yc, mx = ty + 1.6, (x1 + x2) / 2
        s.line(x1, yc, mx - 1.4, yc, VIOLET, .26)
        s.line(mx + 1.4, yc, x2, yc, VIOLET, .26)
        s.poly([(mx - 1.4, yc - 1.0), (mx + 1.4, yc + 1.0), (mx + 1.4, yc - 1.0),
                (mx - 1.4, yc + 1.0)], WHITE, DEEP, .22)
    # The sale of item 17 now matches both item rows.
    sx, sy = ss_x + ss_w, ss_rows[0]
    for yc in it_rows:
        path = [(sx, sy), (it_x, yc)] if abs(yc - sy) < .01 else \
            [(sx, sy), (sx + 3.2, sy), (sx + 3.2, yc), (it_x, yc)]
        s.route(path, LOAD, .3, radius=.6, length=.9)
    label(x + w / 2, ty + th + 2.7, L['stale'], NOTE_PT, LOAD, 'sans', 'center', width=w - 8.0)
    # What step 3 found about item no longer holds.
    label(it_x + it_w / 2, ty - 2.0, L['broken'], NOTE_PT, LOAD, 'bold', 'center', width=it_w + 6)

    # The ETL job that writes the history row.
    ex, ey, ew, eh = 153.0, ty + 1.0, 22.5, 12.6
    s.rect(ex + .9, ey + .9, ew, eh, '#E7E4EC', None, r=.6)
    s.rect(ex, ey, ew, eh, WHITE, EDGE, .24, r=.6)
    label(ex + 1.5, ey + 2.6, L['etl'][0], NAME_PT, INK, 'bold')
    for k, line in enumerate(L['etl'][1:]):
        label(ex + 1.5, ey + 6.2 + 2.9 * k, line, NOTE_PT, AMBER, 'bold' if lang == 'zh' else 'sans')
    s.route([(ex, ey + eh / 2), (it_x + it_w + 3.0, ey + eh / 2), (it_x + it_w + 3.0, it_rows[1]),
             (it_x + it_w, it_rows[1])], AMBER, .34, radius=.8, length=1.0)

    # Request streams: every agent's four lookups land on the same tables.
    def stream(sx_, tx_):
        p0, p1 = (sx_, WIN_BOTTOM), (sx_, WIN_BOTTOM + 2.4)
        p2, p3 = (tx_, DB_Y - 1.8), (tx_, DB_Y + .6)
        s.curve(p0, p1, p2, p3, LOAD, .34)
        s.head(*p3, math.pi / 2, LOAD, 1.0)

    targets = (32.0, 86.0, 138.0)
    for cx, target in zip(CENTERS, targets):
        for k in range(4):
            stream(cx - 3.6 + 2.4 * k, target - 3.0 + 2.0 * k)
    dots(DOTS_X, (WIN_BOTTOM + DB_Y) / 2, LOAD)
    assert DB_Y + DB_H <= H - .3 and ey + eh + .9 <= H


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
