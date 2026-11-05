"""Figure 1: memoryless agents repeat the same exploration for related questions.

Three recorded sessions from the 10-01 workload traces
(exp/2026-10-01-workload-characterization, DeepSeek, direct tools, no memory),
all on the metric electronics revenue (M5) and all asked by name only:

  Agent 1  s094  M5-L1  electronics revenue in January
  Agent 2  s073  M5-T2  the month with the highest electronics revenue
  Agent N  s064  M5-T1  September against the same month a year earlier

Every session lists the tables and reads the schemas of store_sales, item and
date_dim (steps 1-4, the boxed part, in all 20 sessions of this metric); only
the date predicate of the answer SQL (step 5) differs. The script reads the
archived traces, checks that each drawn session made exactly these calls and
that its answer SQL contains the drawn predicate, and takes the per-session
tokens and seconds from the trace. The session count in the box comes from
gen/workload-example.tex (tools/workload-stats.py --example M5), which the
text of Example 1 also uses. Questions drop the calendar year of the dataset.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vecfig import PT, measure  # noqa: E402
import style  # noqa: E402
from style import ACC, ACC_DK, EDGE, INK, MUTED, RED, WHITE  # noqa: E402

NAME = 'metric-record'
W, H = style.COLUMN, 53.3

RUN = style.ROOT / 'exp/2026-10-01-workload-characterization/deepseek-v4.1-flash'
AGENTS = (('1', 's094', 'M5-L1'), ('2', 's073', 'M5-T2'), ('N', 's064', 'M5-T1'))
LOOKUPS = (('list_tables', None), ('describe_table', 'store_sales'),
           ('describe_table', 'item'), ('describe_table', 'date_dim'))
# The date predicate of each answer SQL, as drawn and as it must occur in the
# session's final SQL once table aliases and extra spaces are removed.
PREDICATES = ((('`... AND d_moy = 1`',), ('d_moy = 1',)),
              (('`... GROUP BY d_moy`', '`ORDER BY revenue DESC`'),
               ('group by d_moy order by revenue desc',)),
              (('`... AND d_moy = 9`', '`GROUP BY d_year, d_moy`'),
               ('d_moy = 9', 'group by d_year, d_moy')))

BOX_FILL, BOX_EDGE, CHIP_EDGE = '#FDF1EC', RED, '#E8B9AC'
FOUND = '#8F3626'
CARD_EDGE, CARD_TOP, CARD_SIDE = '#BDB9B2', '#F2F0EC', '#E7E4DF'

LABELS = {
    'en': {
        'agent': 'Agent', 'ask': 'ask:',
        # One list of lines per question, broken by hand to fit the card.
        'q': (('electronics', 'revenue in January?'),
              ('which month had', 'the highest', 'electronics revenue?'),
              ('September', 'electronics revenue', 'vs. a year earlier?')),
        'repeated': 'Steps 1–4 repeat in all {n} sessions', 'skip': 'skippable with sharing',
        'steps': ('list tables', '`store_sales` schema', '`item` schema', '`date_dim` schema'),
        'found': 'found again each time: join keys, `i_category`, `d_moy`, candidate revenue columns',
        'answer': 'answer SQL', 'cost': '{tok}k tokens · {sec} s',
    },
    'zh': {
        'agent': '智能体', 'ask': '问：',
        'q': (('1 月电子品类', '营业额是多少？'), ('哪个月电子品类', '营业额最高？'),
              ('9 月电子品类', '营业额比上年同月', '高多少？')),
        'repeated': '第 1–4 步在全部 {n} 个会话中重复', 'skip': '共享后可省去',
        'steps': ('列出所有表', '`store_sales` 表结构', '`item` 表结构', '`date_dim` 表结构'),
        'found': '每次重新找到：连接键、`i_category`、`d_moy`、营业额候选列',
        'answer': '答案 SQL', 'cost': '{tok}k token · {sec} 秒',
    },
}

# Columns: Agent 1, Agent 2, a gap with the ellipsis, Agent N.
CW, GAP, ELL = 25.87, 1.2, 4.8
X0 = (W - 3 * CW - GAP - ELL) / 2
COLS = (X0, X0 + CW + GAP, X0 + 2 * CW + GAP + ELL)
DOTS_X = COLS[1] + CW + ELL / 2
DEPTH = 1.4                                     # 3D edge of the agent cards
CARD_Y = 1.75
NAME_PT, ASK_PT, HEAD_PT, STEP_PT, FOUND_PT, CODE_PT, COST_PT = 7.0, 6.3, 6.6, 6.1, 6.0, 5.8, 5.8
ASK_PITCH = 2.55


def baseline(y_center, size):
    """Baseline that centres capitals and digits on y_center."""
    return y_center + .34 * size * PT


def plain(sql):
    """Lower-case SQL without table aliases and repeated spaces."""
    sql = re.sub(r'\b[a-z]{1,2}\.(?=[a-z_]+)', '', sql.lower())
    return re.sub(r'\s+', ' ', sql)


def sessions():
    """The drawn sessions with their calls checked against the traces."""
    rows = {json.loads(l)['agent']: json.loads(l) for l in open(RUN / 'sessions.jsonl', encoding='utf-8')}
    calls = {}
    for line in open(RUN / 'trace.jsonl', encoding='utf-8'):
        c = json.loads(line)
        calls.setdefault(c['agent'], []).append(c)
    out = []
    for (_, agent, task), (_, needles) in zip(AGENTS, PREDICATES):
        s = rows[agent]
        assert (s['task'], s['phrasing'], s['metric']) == (task, 'named', 'M5'), agent
        cs = sorted(calls[agent], key=lambda c: (c['step'], c['seq']))
        tools = [(c['tool'], (c.get('args') or {}).get('table')) for c in cs]
        assert tools == list(LOOKUPS) + [('run_sql', None), ('final_answer', None)], (agent, tools)
        final = plain(' '.join(s['final_sql']))
        for needle in needles:
            assert needle in final, (agent, needle, final)
        run = s['run']
        out.append({'tok': f"{(run['input_tokens'] + run['output_tokens']) / 1000:.1f}",
                    'sec': f"{run['seconds']:.0f}"})
    return out


def check_lines(lines, size, first_room, room):
    """Hand-broken question lines; the first leaves first_room for the ask label."""
    for k, line in enumerate(lines):
        w = measure(line, size)
        assert w <= (first_room if k == 0 else room), (line, round(w, 2))
    return lines


def draw(s, lang):
    L = LABELS[lang]
    gen = style.macros('workload-example')
    shown = sessions()
    n_sessions = gen['WxSessions']
    style.agree('sessions that repeat the four lookups', gen['WxFourLookups'], n_sessions)
    text, rect, route = s.text, s.rect, s.route

    def card(x, y, w, h):
        s.poly([(x, y), (x + DEPTH, y - DEPTH), (x + w + DEPTH, y - DEPTH), (x + w, y)],
               CARD_TOP, CARD_EDGE, .12)
        s.poly([(x + w, y), (x + w + DEPTH, y - DEPTH), (x + w + DEPTH, y + h - DEPTH),
                (x + w, y + h)], CARD_SIDE, CARD_EDGE, .12)
        rect(x, y, w, h, WHITE, CARD_EDGE, .16, r=.4)

    def person(x, y, c='#8E8B85'):
        s.circle(x, y, .72, c)
        rect(x - 1.1, y + .88, 2.2, 1.25, c, None, r=.62)

    def badge(x, yc, label, color):
        s.circle(x, yc, 1.12, color)
        text(x, baseline(yc, 5.8), label, 5.8, WHITE, 'bold', 'center')

    def dots(yc):
        for k in (-1, 0, 1):
            s.circle(DOTS_X + 1.5 * k, yc, .38, EDGE)

    # Agents and their questions -------------------------------------------
    cw = CW - DEPTH
    aw = measure(L['ask'], ASK_PT, 'bold') + (.75 if lang == 'en' else 0)
    asks = [check_lines(q, ASK_PT, cw - 2.2 - aw, cw - 2.2) for q in L['q']]
    card_h = 4.9 + ASK_PITCH * max(len(a) for a in asks)
    for x, (label, _, _), lines in zip(COLS, AGENTS, asks):
        card(x, CARD_Y, cw, card_h)
        person(x + 2.3, CARD_Y + 1.45)
        text(x + 4.6, CARD_Y + 3.0, f"{L['agent']} {label}", NAME_PT, INK, 'bold', width=cw - 5)
        y = CARD_Y + 5.75
        text(x + 1.2, y, L['ask'], ASK_PT, ACC_DK, 'bold')
        for k, line in enumerate(lines):
            text(x + 1.2 + (aw if k == 0 else 0), y + ASK_PITCH * k, line, ASK_PT, INK)
    dots(CARD_Y + card_h / 2 - .4)

    # The repeated exploration: one box over every agent's steps 1-4 ---------
    box_y = CARD_Y + card_h + 1.7
    for x in COLS:
        route([(x + cw / 2, CARD_Y + card_h), (x + cw / 2, box_y)], EDGE, .22, length=.9)
    chip_y0, chip_h, chip_pitch = box_y + 4.3, 3.45, 4.05
    found_y = chip_y0 + 3 * chip_pitch + chip_h + 2.35
    box_h = found_y + 1.55 - box_y
    bx0, bx1 = .2, W - .2
    rect(bx0, box_y, bx1 - bx0, box_h, BOX_FILL, BOX_EDGE, .3, r=.9, dash=(1.1, .6))
    text(bx0 + 1.3, baseline(box_y + 2.15, HEAD_PT),
         L['repeated'].format(n=n_sessions), HEAD_PT, RED, 'bold')
    text(bx1 - 1.3, baseline(box_y + 2.15, FOUND_PT), L['skip'], FOUND_PT, RED, 'sans', 'right')
    for x in COLS:
        for k, step in enumerate(L['steps']):
            y = chip_y0 + chip_pitch * k
            rect(x + .3, y, CW - .6, chip_h, WHITE, CHIP_EDGE, .16, r=.5)
            badge(x + 1.85, y + chip_h / 2, str(k + 1), RED)
            text(x + 3.45, baseline(y + chip_h / 2, STEP_PT), step, STEP_PT, INK,
                 width=CW - .6 - 3.45)
    dots(chip_y0 + 1.5 * chip_pitch + chip_h / 2)
    text(W / 2, baseline(found_y, FOUND_PT), L['found'], FOUND_PT, FOUND, 'sans', 'center',
         width=bx1 - bx0 - 2.0)

    # Step 5, the only part that differs: the answer SQL's date predicate ---
    ans_y = box_y + box_h + 1.7
    ans_h = 11.4
    for x, (lines, _), cost in zip(COLS, PREDICATES, shown):
        route([(x + CW / 2, box_y + box_h), (x + CW / 2, ans_y)], EDGE, .22, length=.9)
        rect(x, ans_y, CW, ans_h, WHITE, ACC, .2, r=.6)
        badge(x + 1.85, ans_y + 2.05, '5', ACC)
        text(x + 3.45, baseline(ans_y + 2.05, STEP_PT), L['answer'], STEP_PT, ACC_DK, 'bold')
        for k, line in enumerate(lines):
            text(x + 1.0, ans_y + 5.35 + 2.4 * k, line, CODE_PT, ACC_DK, width=CW - 1.6)
        text(x + 1.0, ans_y + ans_h - 1.15, L['cost'].format(**cost), COST_PT, MUTED,
             width=CW - 1.6)
    dots(ans_y + ans_h / 2)
    assert ans_y + ans_h <= H - .3, ans_y + ans_h


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
