"""Figure 1: independent agents repeat the same exploration for related questions.

Three recorded sessions from the 10-01 workload traces
(exp/2026-10-01-workload-characterization, DeepSeek, direct tools, no memory),
all on the metric electronics revenue (M5) and all asked by name only:

  Agent 1  s094  M5-L1  electronics revenue in January
  Agent 2  s073  M5-T2  the month with the highest electronics revenue
  Agent N  s064  M5-T1  September against the same month a year earlier

Every session lists the tables and reads the schemas of store_sales, item and
date_dim (steps 1-4, the boxed part, in all 20 sessions of this metric); only
the date filter of the final SQL (step 5) differs. The script reads the
archived traces and checks that each drawn session made exactly these calls
and that its final SQL contains the drawn filter. The session count comes
from gen/workload-example.tex (tools/workload-stats.py --example M5), which
Example 1 also uses. Questions drop the calendar year of the dataset.

Plain style on purpose: flat boxes, one accent colour for the repeated steps,
no icons; the text and the caption carry the numbers.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vecfig import PT, measure  # noqa: E402
import style  # noqa: E402
from style import ACC_DK, EDGE, INK, WHITE  # noqa: E402

NAME = 'metric-record'
W, H = style.COLUMN, 43.8

RUN = style.ROOT / 'exp/2026-10-01-workload-characterization/deepseek-v4.1-flash'
AGENTS = (('1', 's094', 'M5-L1'), ('2', 's073', 'M5-T2'), ('N', 's064', 'M5-T1'))
LOOKUPS = (('list_tables', None), ('describe_table', 'store_sales'),
           ('describe_table', 'item'), ('describe_table', 'date_dim'))
# The date filter of each final SQL, as drawn and as it must occur in the
# session's final SQL once table aliases and extra spaces are removed.
FILTERS = ((('`... AND d_moy = 1`',), ('d_moy = 1',)),
           (('`... GROUP BY d_moy`', '`ORDER BY revenue DESC`'),
            ('group by d_moy order by revenue desc',)),
           (('`... AND d_moy = 9`', '`GROUP BY d_year, d_moy`'),
            ('d_moy = 9', 'group by d_year, d_moy')))

REPEAT, REPEAT_FILL = '#B03A2E', '#FBF4F2'     # the one accent: repeated steps
BORDER = '#A9A59E'

LABELS = {
    'en': {
        'agent': 'Agent', 'ask': 'ask:',
        # One list of lines per question, broken by hand to fit the box.
        'q': (('electronics', 'revenue in January?'),
              ('which month had', 'the highest', 'electronics revenue?'),
              ('September', 'electronics revenue', 'vs. a year earlier?')),
        'repeated': 'Repeated in all {n} sessions', 'skip': 'avoidable with sharing',
        'steps': ('list tables', '`store_sales` schema', '`item` schema', '`date_dim` schema'),
        'final': 'final SQL',
    },
    'zh': {
        'agent': '智能体', 'ask': '问：',
        'q': (('1 月电子品类', '营业额是多少？'), ('哪个月电子品类', '营业额最高？'),
              ('9 月电子品类', '营业额比上年同月', '高多少？')),
        'repeated': '全部 {n} 个会话都重复', 'skip': '共享后可省去',
        'steps': ('列出所有表', '`store_sales` 表结构', '`item` 表结构', '`date_dim` 表结构'),
        'final': '最终 SQL',
    },
}

# Columns: Agent 1, Agent 2, a gap with the ellipsis, Agent N.
CW, GAP, ELL = 25.87, 1.2, 4.8
X0 = (W - 3 * CW - GAP - ELL) / 2
COLS = (X0, X0 + CW + GAP, X0 + 2 * CW + GAP + ELL)
DOTS_X = COLS[1] + CW + ELL / 2
NAME_PT, ASK_PT, HEAD_PT, STEP_PT, CODE_PT = 7.0, 6.3, 6.6, 6.3, 6.0
ASK_PITCH, STEP_PITCH = 2.55, 3.55


def baseline(y_center, size):
    """Baseline that centres capitals and digits on y_center."""
    return y_center + .34 * size * PT


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
    text, rect, route = s.text, s.rect, s.route

    def dots(yc):
        for k in (-1, 0, 1):
            s.circle(DOTS_X + 1.5 * k, yc, .36, EDGE)

    def arrows(y0, y1):
        for x in COLS:
            route([(x + CW / 2, y0), (x + CW / 2, y1)], EDGE, .2, length=.85)

    # Agents and their questions -------------------------------------------
    aw = measure(L['ask'], ASK_PT, 'bold') + (.75 if lang == 'en' else 0)
    card_y = .6
    card_h = 4.75 + ASK_PITCH * max(len(q) for q in L['q'])
    for x, (label, _, _), lines in zip(COLS, AGENTS, L['q']):
        rect(x, card_y, CW, card_h, WHITE, BORDER, .18, r=.5)
        text(x + 1.2, card_y + 3.0, f"{L['agent']} {label}", NAME_PT, INK, 'bold', width=CW - 2.4)
        y = card_y + 5.75
        text(x + 1.2, y, L['ask'], ASK_PT, ACC_DK, 'bold')
        for k, line in enumerate(lines):
            text(x + 1.2 + (aw if k == 0 else 0), y + ASK_PITCH * k, line, ASK_PT, INK,
                 width=CW - 2.4 - (aw if k == 0 else 0))
    dots(card_y + card_h / 2)

    # Steps 1-4, the same for every agent, in one box ------------------------
    box_y = card_y + card_h + 1.7
    arrows(card_y + card_h, box_y)
    rows = [box_y + 5.4 + STEP_PITCH * k for k in range(4)]
    box_h = rows[-1] + 2.1 - box_y
    bx0, bx1 = .25, W - .25
    rect(bx0, box_y, bx1 - bx0, box_h, REPEAT_FILL, REPEAT, .28, r=.8, dash=(1.1, .6))
    text(bx0 + 1.2, baseline(box_y + 2.2, HEAD_PT), L['repeated'].format(n=n_sessions),
         HEAD_PT, REPEAT, 'bold')
    text(bx1 - 1.2, baseline(box_y + 2.2, HEAD_PT - .4), L['skip'], HEAD_PT - .4, REPEAT,
         'sans', 'right')
    for x in COLS:
        for k, (yc, step) in enumerate(zip(rows, L['steps'])):
            text(x + 1.2, baseline(yc, STEP_PT), str(k + 1), STEP_PT, REPEAT, 'bold')
            text(x + 3.2, baseline(yc, STEP_PT), step, STEP_PT, INK, width=CW - 4.0)
    dots((rows[1] + rows[2]) / 2)

    # Step 5, the only part that differs: the date filter of the final SQL --
    ans_y = box_y + box_h + 1.7
    ans_h = 8.9
    arrows(box_y + box_h, ans_y)
    for x, (lines, _) in zip(COLS, FILTERS):
        rect(x, ans_y, CW, ans_h, WHITE, BORDER, .18, r=.5)
        text(x + 1.2, baseline(ans_y + 2.0, STEP_PT), '5', STEP_PT, INK, 'bold')
        text(x + 3.2, baseline(ans_y + 2.0, STEP_PT), L['final'], STEP_PT, INK, 'bold')
        for k, line in enumerate(lines):
            text(x + 1.2, ans_y + 5.15 + 2.4 * k, line, CODE_PT, INK, width=CW - 2.0)
    dots(ans_y + ans_h / 2)
    assert ans_y + ans_h <= H - .3, ans_y + ans_h


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
