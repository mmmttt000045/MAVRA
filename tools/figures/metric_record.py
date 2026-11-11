"""Figure 1: Three challenges of sharing computations across data agents on a retail database.

Single column (84.6 mm wide). Organizes the running e-commerce example into
three compact panels that directly motivate C1, C2, and C3:
  (a) C1 — Sharing opportunity: Agents 1, 2, ..., N ask different period, ranking,
      and comparison questions over electronics revenue, repeating Steps 1-4
      (schema/join/filter/measure exploration) while differing only in Step 5.
  (b) C2 — Request ambiguity & near-miss trap: "electronics turnover" denotes
      the same calculation, whereas "electronics revenue net of returns" is close
      in wording/embedding but requires subtracting returns; similarity lookup
      causes a silent false hit.
  (c) C3 — Silent condition break under updates: appending sales rows updates
      answers without breaking the SQL, whereas loading item history duplicates
      item_id=17 under an unchanged schema, causing silent double-counting.
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
W, H = style.COLUMN, 60.0

INK = '#2B2A28'
MUTED = '#6B6A66'
EDGE = '#9A968E'
RULE = '#DEDAD2'
WHITE = '#FFFFFF'
VIOLET = '#6B56A6'
DEEP = '#4A387B'
PALE = '#F4F1FA'
BLUE = '#2A78D6'
BLUE_DK = '#1D5BA6'
BLUE_PALE = '#E6F0FC'
RED = '#C2412E'
RED_PALE = '#FBE9E5'
RED_TINT = '#FDF5F3'
TEAL = '#13897B'
TEAL_PALE = '#E4F5F2'
AMBER = '#B87700'
AMBER_PALE = '#FDF2DA'
FACE = '#F7F6F3'

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
        'p1': '(a) C1: Redundant exploration across sharing opportunities',
        'p1_tag': '93% probes repeat',
        'agent': 'Agent',
        'q': ('"Jan. electronics rev.?"', '"Best month for elec. rev.?"', '"Sep. rev. vs. last yr?"'),
        'shared_head': 'Steps 1-4: repeated discovery of fixed core $I$',
        'shared_steps': (
            ('1-2', 'desc & join', '`sales` $\\bowtie$ `item` $\\bowtie$ `date`'),
            ('3-4', 'filter & probe', "`category='Elec.'`, `SUM(net_paid)`"),
        ),
        'step5_head': 'Step 5: request-specific parameter $p$ or derivation $d$',
        'own': ('param `month=1`', 'rank by `month`', 'diff across `year`'),
        'p2': '(b) C2: Wording similarity vs. computation equivalence',
        'r_same': '"electronics turnover in Jan."',
        'r_same_res': 'different words, same core $I$  (true hit)',
        'r_diff': '"elec. revenue net of returns"',
        'r_diff_res': 'high cosine sim., misses `- returns` (false hit)',
        'p3': '(c) C3: Benign writes vs. silent condition violations on shared DB',
        'w_ok': 'Write 1: append `sales`',
        'w_ok_sub': 'result changes; conditions hold',
        'w_bad': 'Write 2: load `item` history',
        'w_bad_sub': 'dup `item_id=17` double-counts sales',
    },
    'zh': {
        'p1': '(a) C1：共享机会下的重复探索',
        'p1_tag': '93% 探查重复',
        'agent': '智能体',
        'q': ('"1月电子营业额？"', '"电子营业额最高月？"', '"9月营业额同比？"'),
        'shared_head': '步骤 1-4：重复发现核心计算（固定语义 $I$）',
        'shared_steps': (
            ('1-2', '查表与连接', '`sales` $\\bowtie$ `item` $\\bowtie$ `date`'),
            ('3-4', '过滤与探查', "`category='Elec.'`, `SUM(net_paid)`"),
        ),
        'step5_head': '步骤 5：请求特定的参数 $p$ 或派生操作 $d$',
        'own': ('参数 `month=1`', '按 `month` 排名', '跨 `year` 差值'),
        'p2': '(b) C2：措辞相似不等于计算等价',
        'r_same': '"1月电子品类流水"',
        'r_same_res': '措辞不同，同一计算 $I$（命中）',
        'r_diff': '"扣除退货后的电子营业额"',
        'r_diff_res': '向量高度相似，漏减退货（误命中）',
        'p3': '(c) C3：共享数据库上的常规写入与静默条件破坏',
        'w_ok': '写入 1：追加 `sales`',
        'w_ok_sub': '结果更新；粒度与连接仍成立',
        'w_bad': '写入 2：装载 `item` 历史',
        'w_bad_sub': '模式未变；重复 `item_id=17` 致销售翻倍',
    },
}


def plain(sql):
    sql = re.sub(r'\b[a-z]{1,2}\.(?=[a-z_]+)', '', sql.lower())
    return re.sub(r'\s+', ' ', sql)


def check_sessions():
    rows = {json.loads(l)['agent']: json.loads(l) for l in open(RUN / 'sessions.jsonl', encoding='utf-8')}
    calls = {}
    for line in open(RUN / 'trace.jsonl', encoding='utf-8'):
        c = json.loads(line)
        calls.setdefault(c['agent'], []).append(c)
    for (_, agent, task), own in zip(AGENTS, OWN_SQL):
        s = rows[agent]
        assert (s['task'], s['phrasing'], s['metric']) == (task, 'named', 'M5'), agent
        cs = sorted(calls[agent], key=lambda c: (c['step'], c['seq']))
        sqls = [plain(c['args']['sql']) for c in cs if c['tool'] == 'run_sql']
        for sql, needles in zip(sqls, own):
            for needle in needles:
                assert needle in sql, (agent, needle, sql)


def draw(s, lang):
    L = LABELS[lang]
    check_sessions()
    gen = style.macros('workload-example')
    style.agree('sessions that repeat the four lookups', gen['WxFourLookups'], gen['WxSessions'])

    def label(x, yc, text, size, color=INK, weight='sans', align='left', width=None):
        return s.text(x, yc + .34 * size * PT, text, size, color, weight, align, width)

    def mark(x, yc, ok, r=1.05):
        s.circle(x, yc, r, BLUE if ok else RED)
        k = .5 * r
        if ok:
            s.poly([(x - 1.0 * k, yc + .05 * k), (x - .2 * k, yc + .8 * k), (x + 1.05 * k, yc - .8 * k)],
                   None, WHITE, .28, closed=False)
        else:
            s.line(x - .75 * k, yc - .75 * k, x + .75 * k, yc + .75 * k, WHITE, .28)
            s.line(x - .75 * k, yc + .75 * k, x + .75 * k, yc - .75 * k, WHITE, .28)

    # =========================================================================
    # Panel (a): C1 — Redundant exploration vs. reusable core
    # =========================================================================
    y0, h1 = 0.6, 22.8
    s.rect(0.6, y0, W - 1.2, h1, FACE, EDGE, .18, r=.6)
    s.rect(0.7, y0 + 0.1, W - 1.4, 3.0, PALE, None, r=.5)
    label(1.6, y0 + 1.6, L['p1'], 6.0, DEEP, 'bold')
    tw = measure(L['p1_tag'], 5.2, 'bold') + 1.6
    s.rect(W - 1.4 - tw, y0 + 0.45, tw, 2.2, RED_PALE, RED, .14, r=.4)
    label(W - 1.4 - tw / 2, y0 + 1.55, L['p1_tag'], 5.2, RED, 'bold', 'center')

    # Three agent columns
    cw, gap, ell = 25.0, 1.2, 4.0
    x_start = 1.6
    cols = (x_start, x_start + cw + gap, x_start + 2 * cw + gap + ell)
    dots_x = cols[1] + cw + ell / 2
    ay = y0 + 3.6
    for x, (num, _, _), q in zip(cols, AGENTS, L['q']):
        s.rect(x, ay, cw, 4.6, WHITE, VIOLET, .18, r=.45)
        s.circle(x + 2.0, ay + 1.5, 1.0, VIOLET)
        label(x + 2.0, ay + 1.5, num, 5.2, WHITE, 'bold', 'center')
        label(x + 3.5, ay + 1.5, f"{L['agent']} {num}", 5.6, DEEP, 'bold')
        label(x + 1.0, ay + 3.5, q, 5.2, INK, width=cw - 1.6)
    for k in (-1, 0, 1):
        s.circle(dots_x + 0.95 * k, ay + 2.3, .28, VIOLET)

    # Dashed box for Steps 1-4 repeated across all agents
    by = ay + 5.2
    bh = 8.4
    s.rect(1.4, by, W - 2.8, bh, RED_TINT, RED, .24, r=.55, dash=(1.0, 0.55))
    label(2.4, by + 1.5, L['shared_head'], 5.3, RED, 'bold')
    for idx, (st_no, act, detail) in enumerate(L['shared_steps']):
        ry = by + 3.8 + idx * 3.1
        s.rect(2.4, ry - 1.15, 4.2, 2.2, WHITE, RED, .16, r=.35)
        label(4.5, ry, st_no, 5.0, RED, 'bold', 'center')
        label(7.4, ry, act, 5.4, INK, 'bold')
        pw = measure(detail, 5.2) + 1.8
        px = W - 2.4 - pw
        s.rect(px, ry - 1.15, pw, 2.2, WHITE, VIOLET, .15, r=.35)
        label(px + pw / 2, ry, detail, 5.2, DEEP, 'sans', 'center')
        ax0 = 7.4 + measure(act, 5.4, 'bold') + 0.8
        s.line(ax0, ry, px - 0.3, ry, RED, .18)
        s.head(px - 0.2, ry, 0, RED, .55)

    # Step 5 row: each agent's own parameter or derivation
    s5y = by + bh + 2.2
    for x, own in zip(cols, L['own']):
        s.rect(x, s5y - 1.35, cw, 2.7, BLUE_PALE, BLUE, .18, r=.4)
        s.circle(x + 1.8, s5y, 0.9, BLUE)
        label(x + 1.8, s5y, '5', 5.0, WHITE, 'bold', 'center')
        label(x + 3.2, s5y, own, 5.2, BLUE_DK, 'bold', width=cw - 3.6)
    for k in (-1, 0, 1):
        s.circle(dots_x + 0.95 * k, s5y, .28, BLUE)

    # =========================================================================
    # Panel (b): C2 — Request ambiguity & near-miss trap
    # =========================================================================
    y2, h2 = y0 + h1 + 1.2, 14.2
    s.rect(0.6, y2, W - 1.2, h2, FACE, EDGE, .18, r=.6)
    s.rect(0.7, y2 + 0.1, W - 1.4, 3.0, AMBER_PALE, None, r=.5)
    label(1.6, y2 + 1.6, L['p2'], 6.0, AMBER, 'bold')

    # Row 1: Synonym -> True hit
    r1y = y2 + 5.2
    s.rect(1.6, r1y - 1.5, 34.8, 3.0, WHITE, BLUE, .18, r=.4)
    label(2.4, r1y, L['r_same'], 5.3, INK, width=33.2)
    s.line(36.8, r1y, 40.0, r1y, BLUE, .22)
    s.head(40.1, r1y, 0, BLUE, .6)
    s.rect(40.6, r1y - 1.5, W - 42.2, 3.0, BLUE_PALE, BLUE, .16, r=.4)
    mark(42.3, r1y, True, .85)
    label(43.8, r1y, L['r_same_res'], 5.2, BLUE_DK, 'bold', width=W - 45.8)

    # Row 2: Near-miss filter -> False hit under similarity
    r2y = y2 + 9.2
    s.rect(1.6, r2y - 1.5, 34.8, 3.0, WHITE, RED, .18, r=.4)
    label(2.4, r2y, L['r_diff'], 5.3, INK, width=33.2)
    s.line(36.8, r2y, 40.0, r2y, RED, .22)
    s.head(40.1, r2y, 0, RED, .6)
    s.rect(40.6, r2y - 1.5, W - 42.2, 3.0, RED_PALE, RED, .16, r=.4)
    mark(42.3, r2y, False, .85)
    label(43.8, r2y, L['r_diff_res'], 5.1, RED, 'bold', width=W - 45.8)

    # Bottom note in Panel (b)
    note_b = 'Needs constraint-level grounding without synthesizing new SQL first' if lang == 'en' else '需在不预先生成完整 SQL 的前提下逐项核验请求约束'
    label(W / 2, y2 + 12.5, note_b, 5.1, MUTED, 'sans', 'center')

    # =========================================================================
    # Panel (c): C3 — Shared database & silent condition violations under writes
    # =========================================================================
    y3, h3 = y2 + h2 + 1.2, 19.4
    s.rect(0.6, y3, W - 1.2, h3, FACE, EDGE, .18, r=.6)
    s.rect(0.7, y3 + 0.1, W - 1.4, 3.0, TEAL_PALE, None, r=.5)
    label(1.6, y3 + 1.6, L['p3'], 6.0, TEAL, 'bold')

    # Mini schema bar: date <-> sales <-> item
    sy = y3 + 4.0
    sh = 4.6
    tables = (
        (1.6, 22.8, 'date', '`date_id` (PK), `month`'),
        (28.0, 26.8, 'sales', '`date_id, item_id`, `net_paid`'),
        (58.4, 24.6, 'item', '`item_id` (1:1?), `category`'),
    )
    for tx, tw_, tname, cols_txt in tables:
        is_item = tname == 'item'
        s.rect(tx, sy, tw_, sh, WHITE, RED if is_item else VIOLET, .2, r=.35)
        s.rect(tx + .12, sy + .12, tw_ - .24, 1.8, RED_PALE if is_item else PALE, None, r=.25)
        label(tx + tw_ / 2, sy + 1.0, f'`{tname}`', 5.4, RED if is_item else DEEP, 'bold', 'center')
        label(tx + 1.0, sy + 3.2, cols_txt, 4.9, INK, width=tw_ - 1.6)
    for (x1, w1, _, _), (x2, _, _, _) in zip(tables, tables[1:]):
        mx = (x1 + w1 + x2) / 2
        yc = sy + sh / 2
        s.line(x1 + w1, yc, x2, yc, VIOLET, .22)
        s.poly([(mx - .9, yc - .65), (mx + .9, yc + .65),
                (mx + .9, yc - .65), (mx - .9, yc + .65)], WHITE, DEEP, .18)

    # Two write cards at bottom of Panel (c)
    wy = sy + sh + 1.2
    wh = 8.4
    w1x, w1w = 1.6, 36.2
    w2x, w2w = 39.2, 43.8

    s.rect(w1x, wy, w1w, wh, BLUE_PALE, BLUE, .18, r=.45)
    mark(w1x + 2.0, wy + 2.1, True, .85)
    label(w1x + 3.6, wy + 2.1, L['w_ok'], 5.4, BLUE_DK, 'bold', width=w1w - 4.4)
    label(w1x + 1.2, wy + 4.8, L['w_ok_sub'], 5.0, INK, width=w1w - 2.0)
    label(w1x + 1.2, wy + 7.0, r'$\rightarrow$ keep definition valid' if lang == 'en' else r'$\rightarrow$ 保持定义有效', 5.0, BLUE_DK, 'bold')

    s.rect(w2x, wy, w2w, wh, RED_PALE, RED, .18, r=.45)
    mark(w2x + 2.0, wy + 2.1, False, .85)
    label(w2x + 3.6, wy + 2.1, L['w_bad'], 5.4, RED, 'bold', width=w2w - 4.4)
    label(w2x + 1.2, wy + 4.8, L['w_bad_sub'], 5.0, INK, width=w2w - 2.0)
    label(w2x + 1.2, wy + 7.0, r"$\rightarrow$ isolate & repair (`is_current='Y'`)" if lang == 'en' else r"$\rightarrow$ 隔离并修复 (`is_current='Y'`)", 5.0, RED, 'bold')

    assert y3 + h3 <= H - 0.2, y3 + h3


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
