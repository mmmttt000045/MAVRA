"""Figure 1: agents repeat the same multi-turn exploration on one shared database.

Single column, in the look of the earlier Figure 1 (LLM-agent glyphs,
workbench windows, request/response streams into one shared database, violet palette).

Top: three recorded sessions from the 10-01 workload traces
(exp/2026-10-01-workload-characterization, DeepSeek, direct tools, no memory),
all on the metric electronics revenue (M5) and all asked by name only:

  Agent 1  s094  M5-L1  electronics revenue in January
  Agent 2  s073  M5-T2  the month with the highest electronics revenue
  Agent N  s091  M5-T1  September against the same month a year earlier

Steps 1-4 in the dashed box show the multi-turn interactive exploration that
all 20 sessions of this metric repeat—probing the three table schemas, testing
joins across store_sales, item and date_dim, sampling/filtering the electronics
category, and probing candidate revenue columns—each drawn as (agent probe ->
database observation) along the session's own path.
Step 5 is each session's question-specific period query: Agent 1 filters
January, Agent 2 ranks the 12 months, and Agent N compares the two years.

Bottom: the shared database holding store_sales, item and date_dim that all
sessions repeatedly probe.
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
W, H = style.COLUMN, 66.2

INK = '#332E40'
MUTED = '#81798D'
EDGE = '#A6A0AE'
RULE = '#DCD5EA'
WHITE = '#FFFFFF'
VIOLET = '#8069B6'
DEEP = '#5C478D'
PALE = '#F4F0FA'
DB_FACE = '#F6F5F8'
LOAD = '#BD533E'           # warm colour: repeated work
LOAD_PALE = '#FBE7DF'
LOAD_TINT = '#FDF3EF'
AMBER = '#C68E35'
AMBER_PALE = '#FBEDCE'

RUN = style.ROOT / 'exp/2026-10-01-workload-characterization/deepseek-v4.1-flash'
AGENTS = (('1', 's094', 'M5-L1'), ('2', 's073', 'M5-T2'), ('N', 's091', 'M5-T1'))
LOOKUPS = (('list_tables', None), ('describe_table', 'store_sales'),
           ('describe_table', 'item'), ('describe_table', 'date_dim'))
OWN_SQL = ((('ss_sold_date_sk = d_date_sk', 'ss_item_sk = i_item_sk',
             'i_category =', 'sum(ss_ext_sales_price)', 'sum(ss_net_paid)',
             'sum(ss_net_paid_inc_tax)', 'd_moy = 1'),),
           (('i_item_sk = ss_item_sk', 'd_date_sk = ss_sold_date_sk',
             'where i_category =', 'sum(ss_ext_sales_price)', 'sum(ss_net_paid)',
             'group by d_moy', 'order by revenue desc'),),
           (('ss_sold_date_sk = d_date_sk', 'ss_item_sk = i_item_sk',
             'where i_category =', 'sum(ss_ext_sales_price)', 'sum(ss_net_paid)',
             'd_moy = 9', 'group by d_year'),
            ('case when d_year=2002 then', 'case when d_year=2001 then')))

LABELS = {
    'en': {
        'agent': 'Agent', 'ask': 'user ask:',
        'q': (('Jan. electronics', 'revenue?'), ('best month for', 'electronics revenue?'),
              ('Sep. electronics', 'revenue vs. last year?')),
        'win_title': 'Multi-turn exploration',
        'repeated': 'Repeated in all {n} sessions', 'skip': 'avoidable with sharing',
        # Each step in 1-4 is (agent probe, DB observation pill).
        'steps': ((('desc tables', '3 schemas'),
                   ('test join', 'sales,date,item'),
                   ('probe item', "'Electronics'"),
                   ('probe cols', '3 rev. cols')),
                  (('list & desc', '3 schemas'),
                   ('check cat.', "'Electronics'"),
                   ('test join', 'sales,item,date'),
                   ('test sums', 'gross, net')),
                  (('read schemas', '3 tables'),
                   ('check cols', 'rev. cols'),
                   ('test join', 'item, date keys'),
                   ('test filter', "'Electronics'"))),
        'own': ('query Jan. (`d_moy=1`)', 'rank the 12 months', 'compare two years'),
        'database': 'Database',
        'db_note': 'same tables, join keys & columns probed every session',
    },
    'zh': {
        'agent': '智能体', 'ask': '用户问：',
        'q': (('1 月电子品类', '营业额是多少？'), ('哪个月电子品类', '营业额最高？'),
              ('9 月电子品类', '营业额同比增加多少？')),
        'win_title': '多轮交互探索',
        'repeated': '全部 {n} 个会话都重复', 'skip': '共享后可省去',
        'steps': ((('查表结构', '3 张表'),
                   ('测表连接', '销/日/商'),
                   ('采样商品', '电子品类'),
                   ('探查度量', '3 个营收列')),
                  (('列并读表', '3 张表'),
                   ('查品类值', '电子品类'),
                   ('测试连接', '销/商/日'),
                   ('比对汇总', '毛额/净额')),
                  (('读表结构', '3 张表'),
                   ('探查列值', '候选营收列'),
                   ('验证连接', '商品/日期键'),
                   ('测试过滤', '电子品类'))),
        'own': ('查 1 月 (`d_moy=1`)', '给 12 个月排序', '比较两年 9 月'),
        'database': '数据库',
        'db_note': '每个会话都在重复探查同一组表、连接键与目标列',
    },
}

# Columns: Agent 1, Agent 2, a gap with the ellipsis, Agent N.
CW, GAP, ELL = 25.2, 1.4, 4.2
X0 = (W - 3 * CW - GAP - ELL) / 2
COLS = (X0, X0 + CW + GAP, X0 + 2 * CW + GAP + ELL)
CENTERS = tuple(x + CW / 2 for x in COLS)
DOTS_X = COLS[1] + CW + ELL / 2

GLYPH_Y, GLYPH_K = .5, .72
ASK_Y, ASK_H = 6.7, 7.5
BOX_Y = 16.5                                   # top edge of the dashed box
WIN_Y = 18.0
ROWS = (22.6, 26.3, 30.0, 33.7)                # steps 1-4
BOX_BOTTOM = 35.8
ROW5 = 38.7
WIN_BOTTOM = 40.7
DB_Y, DB_H, RIM = 48.2, 17.5, 2.0
NAME_PT, ASK_PT, HEAD_PT, STEP_PT, PILL_PT = 7.2, 6.0, 6.5, 5.5, 5.0


def plain(sql):
    """Lower-case SQL without table aliases and repeated spaces."""
    sql = re.sub(r'\b[a-z]{1,2}\.(?=[a-z_]+)', '', sql.lower())
    return re.sub(r'\s+', ' ', sql)


def check_sessions():
    """Assert that the drawn sessions and all M5 sessions match the drawn steps."""
    rows = {json.loads(l)['agent']: json.loads(l) for l in open(RUN / 'sessions.jsonl', encoding='utf-8')}
    calls = {}
    for line in open(RUN / 'trace.jsonl', encoding='utf-8'):
        c = json.loads(line)
        calls.setdefault(c['agent'], []).append(c)
    for agent, s in rows.items():
        if s['metric'] == 'M5':
            cs = calls[agent]
            sqls = ' '.join(plain(c['args']['sql']) for c in cs if c['tool'] == 'run_sql')
            assert 'join item' in sqls and 'join date_dim' in sqls, agent
            assert 'i_category' in sqls and 'sum(' in sqls, agent
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
        s.circle(x, yc, .95, WHITE, edge, .2)
        label(x, yc, str(n), 5.6, DEEP, 'bold', 'center')

    def tagged(x, y, text, size, color, weight, align):
        """Text on a white patch, so that it interrupts a dashed border."""
        tw = measure(text, size, weight)
        left = x if align == 'left' else x - tw
        s.rect(left - .6, y - 1.15, tw + 1.2, 2.3, WHITE, None)
        label(x, y, text, size, color, weight, align)

    # Agents and their user-ask boxes --------------------------------------
    aw = measure(L['ask'], ASK_PT, 'bold') + (.55 if lang == 'en' else 0)
    glyph_w = 7.8 * GLYPH_K
    for (x, cx), (n, _, _), lines in zip(zip(COLS, CENTERS), AGENTS, L['q']):
        name = f"{L['agent']} {n}"
        nw = measure(name, NAME_PT, 'bold')
        x0 = cx - (glyph_w + 1.3 + nw) / 2
        agent_glyph(x0 + glyph_w / 2, GLYPH_Y, GLYPH_K)
        label(x0 + glyph_w + 1.3, GLYPH_Y + 3.9 * GLYPH_K, name, NAME_PT, DEEP, 'bold')
        s.rect(x, ASK_Y, CW, ASK_H, WHITE, RULE, .2, r=.7)
        y = ASK_Y + 2.85
        s.text(x + 1.0, y, L['ask'], ASK_PT, DEEP, 'bold')
        for k, line in enumerate(lines):
            room = CW - 1.8 - (aw if k == 0 else 0)
            s.text(x + 1.0 + (aw if k == 0 else 0), y + 2.6 * k, line, ASK_PT, INK, width=room)
    dots(ASK_Y + ASK_H / 2, DEEP)

    # Workbenches: multi-turn exploration (steps 1-4) inside one dashed box,
    # and step 5 (each agent's period query) below.
    s.rect(.55, BOX_Y, W - 1.1, BOX_BOTTOM - BOX_Y, LOAD_TINT, None, r=.9)
    for x, steps, own in zip(COLS, L['steps'], L['own']):
        s.rect(x, WIN_Y, CW, WIN_BOTTOM - WIN_Y, PALE, VIOLET, .24, r=.8)
        for dx in (1.25, 2.05, 2.85):
            s.circle(x + dx, WIN_Y + 1.15, .19, VIOLET)
        label(x + 3.7, WIN_Y + 1.15, L['win_title'], 5.2, DEEP, 'bold', width=CW - 4.2)
        s.line(x + .4, WIN_Y + 2.25, x + CW - .4, WIN_Y + 2.25, RULE, .17)
        tx = x + 2.0
        s.line(tx, ROWS[0], tx, ROW5, RULE, .24)
        for a, b in zip(ROWS, ROWS[1:]):
            s.head(tx, (a + b) / 2 + .35, math.pi / 2, VIOLET, .58)
        s.head(tx, BOX_BOTTOM + 1.35, math.pi / 2, VIOLET, .58)
        for k, (yc, (act, obs)) in enumerate(zip(ROWS, steps)):
            step_mark(tx, yc, k + 1)
            w_act = label(x + 3.45, yc, act, STEP_PT, INK)
            # Small DB-observation pill on the right, connected by a turn arrow.
            pw = measure(obs, PILL_PT, 'sans') + .95
            px = x + CW - .5 - pw
            ax0 = x + 3.45 + w_act + .3
            ax1 = px - .2
            assert ax1 > ax0 + .45, (act, obs, ax0, ax1)
            s.line(ax0, yc, ax1, yc, VIOLET, .17)
            s.head(ax1, yc, 0, VIOLET, .48)
            s.rect(px, yc - 1.08, pw, 2.16, WHITE, VIOLET, .15, r=.35)
            label(px + pw / 2, yc, obs, PILL_PT, DEEP, 'sans', 'center')
        step_mark(tx, ROW5, 5, DEEP)
        label(x + 3.45, ROW5, own, 5.8, DEEP, 'sans', width=CW - 3.95)
    dots((ROWS[1] + ROWS[2]) / 2)
    dots(ROW5)
    s.rect(.55, BOX_Y, W - 1.1, BOX_BOTTOM - BOX_Y, None, LOAD, .3, r=.9, dash=(1.1, .6))
    tagged(2.5, BOX_Y, L['repeated'].format(n=n_sessions), HEAD_PT, LOAD, 'bold', 'left')
    tagged(W - 2.5, BOX_Y, L['skip'], HEAD_PT - .4, LOAD, 'sans', 'right')

    # One shared database: same tables, join keys, and target columns
    # repeatedly probed by every session.
    x, w = 1.6, W - 3.2
    s.rect(x, DB_Y + RIM / 2, w, DB_H - RIM, DB_FACE)
    ellipse(x, DB_Y + DB_H - RIM, w, RIM, DB_FACE, EDGE, .22)
    s.rect(x + .12, DB_Y + RIM / 2, w - .24, DB_H - RIM, DB_FACE)
    s.line(x, DB_Y + RIM / 2, x, DB_Y + DB_H - RIM / 2, EDGE, .22)
    s.line(x + w, DB_Y + RIM / 2, x + w, DB_Y + DB_H - RIM / 2, EDGE, .22)
    ellipse(x, DB_Y, w, RIM, WHITE, EDGE, .22)
    hot = (11.5, 73.5)
    s.rect(hot[0], DB_Y + .4, hot[1] - hot[0], 1.2, LOAD_PALE, LOAD, .19, r=.5)

    # Header: "Database" + explanatory subtitle on one line
    db_w = measure(L['database'], 6.8, 'bold')
    note_w = measure(L['db_note'], 5.5, 'bold')
    tot_w = db_w + 1.8 + note_w
    hx0 = (W - tot_w) / 2
    hy = DB_Y + 3.4
    label(hx0, hy, L['database'], 6.8, INK, 'bold')
    s.circle(hx0 + db_w + .9, hy, .22, LOAD)
    label(hx0 + db_w + 1.8, hy, L['db_note'], 5.5, LOAD, 'bold')

    ty, th, hh = DB_Y + 5.2, 8.2, 2.5
    rh = (th - hh) / 2
    tables = (
        (3.8, 20.8, 'date_dim', ('d_date_sk', 'd_moy, d_year')),
        (30.2, 24.6, 'store_sales', ('ss_date_sk, ss_item_sk', 'ss_net_paid, ...')),
        (60.4, 20.8, 'item', ('i_item_sk', 'i_category')),
    )
    for tx, tw, name, fields in tables:
        s.rect(tx, ty, tw, th, WHITE, VIOLET, .21, r=.35)
        s.rect(tx + .13, ty + .13, tw - .26, hh - .13, PALE, None, r=.25)
        label(tx + tw / 2, ty + hh / 2, f'`{name}`', 6.1, DEEP, 'sans', 'center', width=tw - 1.0)
        # Highlight the repeatedly probed filter/measure row
        s.rect(tx + .13, ty + hh + rh + .06, tw - .26, rh - .19, AMBER_PALE)
        for yy in (ty + hh, ty + hh + rh):
            s.line(tx, yy, tx + tw, yy, RULE, .15)
        s.line(tx + 2.8, ty + hh, tx + 2.8, ty + th, RULE, .13)
        for row, field in enumerate(fields):
            yc = ty + hh + (row + .5) * rh
            f_pt = 5.0 if len(field) > 18 else 5.5
            label(tx + 3.3, yc, f'`{field}`', f_pt, INK, 'sans', 'left', width=tw - 3.6)
            if row == 0:
                # Key icon for join-key row
                s.circle(tx + 1.05, yc - .1, .36, WHITE, DEEP, .15)
                s.line(tx + 1.4, yc - .1, tx + 2.15, yc - .1, DEEP, .16)
                s.line(tx + 1.85, yc - .1, tx + 1.85, yc + .25, DEEP, .15)
            else:
                # Mini column/distribution icon
                for col, bh in enumerate((.6, .95, .78)):
                    s.rect(tx + .68 + col * .55, yc + .48 - bh, .32, bh, AMBER)

    # Join bowties connecting the join-key rows across the three tables
    yc_key = ty + hh + .5 * rh
    for (x1, w1, _, _), (x2, _, _, _) in zip(tables, tables[1:]):
        mx = (x1 + w1 + x2) / 2
        s.line(x1 + w1, yc_key, mx - 1.15, yc_key, VIOLET, .24)
        s.line(mx + 1.15, yc_key, x2, yc_key, VIOLET, .24)
        s.poly([(mx - 1.15, yc_key - .82), (mx + 1.15, yc_key + .82),
                (mx + 1.15, yc_key - .82), (mx - 1.15, yc_key + .82)],
               WHITE, DEEP, .2)

    # Widely spaced, non-overlapping request/response streams
    def stream(sx_, tx_, returning=False):
        y_top = WIN_BOTTOM + (.65 if returning else 0)
        y_bot = DB_Y + (.55 if not returning else .25)
        dy = y_bot - y_top
        p0, p1 = (sx_, y_top), (sx_, y_top + .42 * dy)
        p2, p3 = (tx_, y_bot - .42 * dy), (tx_, y_bot)
        color = VIOLET if returning else LOAD
        s.curve(p0, p1, p2, p3, color, .26 if returning else .32,
                (.65, .45) if returning else None)
        if returning:
            s.head(sx_, WIN_BOTTOM + .12, -math.pi / 2, VIOLET, .85)
        else:
            s.head(*p3, math.pi / 2, LOAD, .9)

    targets = (20.0, W / 2, W - 20.0)
    for cx, target in zip(CENTERS, targets):
        for dx_s, dx_t, ret in ((-3.0, -2.6, False), (0.0, 0.0, False), (3.0, 2.6, True)):
            stream(cx + dx_s, target + dx_t, returning=ret)
    dots((WIN_BOTTOM + DB_Y) / 2, LOAD)
    assert DB_Y + DB_H <= H - .3, DB_Y + DB_H


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
