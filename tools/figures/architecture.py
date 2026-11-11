"""Fig. 2: MAVRA's components and the path of one definition through them.

Agents sit on top and the database at the bottom. Between them, the shared
layer is drawn as components around one knowledge base:
  Publish        input (a verified session), extraction of I and p0, derived
                 conditions C, gates G1-G7 with the answer replay, output m^0;
  Knowledge base how state is stored: definitions keyed by kind and name, one
                 entry per revision (B, I, C, E, r) that references shared join
                 entries by key and conditions by signature; the lookup state
                 (aliases, vectors, judges); the check outcomes H keyed by
                 (id(c), V(dep(c))), one row per signature and versions;
  Lookup         alias table, recall, judges, thresholds, four replies;
  Check and run  conditions and the compiled query in one snapshot;
  Maintain       a write, the version filter, the inserted-row filter, repair
                 or retirement.
Steps 1-6 follow the running example of Figure 1 (electronics revenue; an ETL
load adds a history row for item 17). Values come from the TPC-DS fixture that
Figs. 3-5 use: answer 2,754,299.60, dropping the filter gives 13,532,799.00
(4.91x), an item load reruns 2 of 5 checks, and i_is_current = 'Y' is the sole
repair. Lookup settings follow Section IV-C (bge-m3 top 8, three judges,
thresholds 0.1 and 0.9). Thin arrows are calls, thick arrows write shared
state, grey arrows are references by key or reads of the knowledge base, and
dashed arrows read database state. Coordinates are millimetres at print size.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vecfig import PT, measure  # noqa: E402
import style  # noqa: E402
import smallparts as sp  # noqa: E402
from style import (ACC, ACC_DK, ACC_PALE, AMBER_PALE, EDGE, FACE, FIELD, INK, MUTED,  # noqa: E402
                   RED, RULE, SIDE, TOP, WHITE)

NAME = 'architecture'
W, H = style.TEXTWIDTH, 96.6

TITLE, SUB, NOTE, CODE, TAG = 7.4, 6.0, 5.4, 5.2, 4.9
BODY, SMALL = 7.0, 6.4                              # agent cards
LEARN, USE, EXEC_C, MAINT_C = '#7A68B0', ACC, '#C97A1E', '#13897B'   # path colours
LEARN_PALE, EXEC_PALE, MAINT_PALE = '#EFECF7', '#FBEEDD', '#E2F1EE'
REFER = '#B07A00'                                   # lookup: a reference for the agent to confirm
REF = '#6F6B66'                                     # references by key, reads of the knowledge base
OCHRE = '#9A6500'                                   # changed data (item history)
MINI = .95                                          # radius of an inline step reference
THIN, THICK = .22, .5
STEP_C = {1: LEARN, 2: LEARN, 3: USE, 4: EXEC_C, 5: MAINT_C, 6: MAINT_C}
LOSSY = 13532799.00 / 2754299.60                    # draft I without phi vs. the verified answer (Fig. 3)

LABELS = {
    'en': {
        'agent': 'Agent', 'predictive': 'Predictive agent P', 'ask': 'ask:',
        'q': ('Jan. electronics revenue?', 'highest-revenue month?',
              'Sep. revenue vs. last year?', 'will a customer churn?'),
        'p': ('explores, answer verified', 'reuses monthly aggregates', 'reuses it after repair',
              'reuses a customer feature'),
        'when': ('first session', ('before', 5), ('after', 5), ''),
        'middleware': 'MAVRA',
        # Publish
        'publish': 'Publish', 'publish_note': 'session to definition',
        'input': 'input', 'output': 'output', 'session': 'verified session of Agent 1',
        'phi': "`i_category = 'Electronics'`",
        'trace3': ('+ probes; answer', '`2,754,299.60`'),
        'extract': 'Extract', 'extract_note': 'fixed vs. per request',
        'chip_i': r'$I$: $F$, $\mathrm{AGG}_e$, $K$, $\mathcal{J}$, $\varphi$, $\tau$',
        'chip_p': r'$p_0$: Jan. 2001',
        'derive': 'Derive conditions $C$', 'derive_note': 'no LLM',
        'derive_glyphs': ('keys unique', r'coverage $\leq b+\epsilon$'),
        'derive_probe': r'probes: $\mathrm{Dom}(T.a)$, null bounds',
        'gates': 'Gates', 'gates_note': 'basis, fields, grain, read-only',
        'replay': 'replay on learning tables',
        'bars': (r'Compile$(I,p_0)$', r'$I$ without $\varphi$'), 'bar_vals': ('= answer', r'4.9$\times$'),
        'publish_out': 'publish', 'reject': 'else reject',
        # Knowledge base
        'kb': 'Knowledge base', 'kb_note': 'one key–value store shared by all agents',
        'defs': 'Definitions', 'defs_note': r'one entry per revision $m^r=(B,I,C,E,r)$',
        'stubs': (('`join:item|store_sales`', ('rev 0', 2, r'$\rightarrow$ 1', 6)),
                  ('`metric:Store revenue`', 'D01: after coupons'),
                  ('`metric:Store revenue`', 'D02: before coupons'),
                  ('`metric:Return rate`', 'another metric'),
                  ('`feature:customer:spend_90d`', 'a feature')),
        'm_key': '`metric:Electronics revenue`', 'rev01': ('rev 0', 2, r'$\rightarrow$ 1', 6),
        'row_b': 'revenue of electronics items, amount paid',
        'row_e': r'request, SQL trace, answer, gates, deps $V$',
        'filter': "`filter i_category = 'Electronics'`",
        'lstate': 'Lookup state', 'aliases': 'aliases', 'aliases_note': 'wording to keys',
        'alias_row': ('`store turnover`', '`D01 D02`'),
        'vectors': 'vectors, one per entry', 'judges': (r'judges $\times$3,', 'trained on the catalog'),
        'h': r'Check outcomes $\mathcal{H}$', 'h_key': r'key $(\mathrm{id}(c),\,V(\mathrm{dep}(c)))$',
        'h_rows': ('`date_dim`', '`store_sales`$\\rightarrow$`date_dim`', '`item`', '`item`',
                   "`item`, `'Y'`"),
        # Lookup
        'lookup': 'Lookup', 'lookup_note': 'no SQL, no LLM call', 'request': r'request $\rho$',
        'stages': (('Alias table', 'confirmed wording?'), ('Recall', 'bge-m3, 8 nearest'),
                   (r'Judge $\times$3', 'cross-encoder, $p$ each'), ('Decide', '')),
        'refer_zone': 'refer',
        'outs': (('hit', 'one definition'), ('same name', 'all, with differences'),
                 ('refer', 'agent confirms; alias'), ('miss', 'agent explores')),
        # Check and run
        'exec': 'Check and run', 'exec_note': 'one snapshot $D_s$', 'exec_in': r'hit: $m$, $p$, $d$',
        'exec_rows': (r'check $C$: outcome in $\mathcal{H}$ at $V_s$,', r'else run $Q_c$ once',
                      r'compile $d(q_0(D_s,p))$ and run'),
        'cat': 'Electronics', 'feat': r'features: per $(u_i,t_i)$', 'answer': 'answer to the agent',
        # Maintain
        'maint': 'Maintain', 'maint_note': ('after each', 'write'),
        'cells': (
            ('Write', (r'stamp $V(T)$ per table', r'`item`: batch 0$\rightarrow$1',
                       r'insert-only: rows $\Delta T$')),
            ('Stage 1: versions', (r'skip $c$ if $V(\mathrm{dep}(c))$ is unchanged', 'rerun 2 of 5',
                                   'each once, for all definitions')),
            ('Stage 2: inserted rows', (r'check only $\Delta T$, by index', 'key 17 now twice')),
            ('Repair or retire', ('sole single edit, answer kept', r"`i_is_current='Y'`$\rightarrow$rev 1",
                                  'else retire; new value: pending')),
        ),
        'maint_out': 'outcomes at $V$′, rev 1',
        # Database
        'db': 'Database', 'db_note': ('versions $V(T)$', 'change on writes'),
        'batch': (5, r'batch 0 $\rightarrow$ 1'), 'rows_note': ('current', 'new'),
        'snapshot': 'snapshot $D_s$', 'etl': 'ETL job', 'etl_note': 'loads item history',
    },
    'zh': {
        'agent': '智能体', 'predictive': '预测智能体 P', 'ask': '问：',
        'q': ('1 月电子品类营业额？', '电子品类营业额最高月？', '9 月营业额同比去年？', '客户会流失吗？'),
        'p': ('自行探索，答案经核对', '复用月度聚合并排序', '修复后复用该定义', '复用客户特征'),
        'when': ('首次会话', (5, '之前'), (5, '之后'), ''),
        'middleware': 'MAVRA',
        'publish': '发布', 'publish_note': '会话变成定义',
        'input': '输入', 'output': '输出', 'session': '智能体 1 的核验会话',
        'phi': "`i_category = '电子'`",
        'trace3': ('+ 探查；答案', '`2,754,299.60`'),
        'extract': '提取', 'extract_note': '固定部分与请求参数',
        'chip_i': r'$I$: $F$, $\mathrm{AGG}_e$, $K$, $\mathcal{J}$, $\varphi$, $\tau$',
        'chip_p': r'$p_0$：2001 年 1 月',
        'derive': '推导条件 $C$', 'derive_note': '不调用 LLM',
        'derive_glyphs': ('键唯一', r'覆盖 $\leq b+\epsilon$'),
        'derive_probe': r'探查：$\mathrm{Dom}(T.a)$、空值上界',
        'gates': '准入检查', 'gates_note': '字段、粒度、只读等',
        'replay': '在学习表上重放',
        'bars': (r'Compile$(I,p_0)$', r'缺 $\varphi$ 的 $I$'), 'bar_vals': ('= 答案', r'4.9$\times$'),
        'publish_out': '发布', 'reject': '否则拒绝',
        'kb': '知识库', 'kb_note': '所有智能体共享的一个键值存储',
        'defs': '定义', 'defs_note': r'每个修订一条 $m^r=(B,I,C,E,r)$',
        'stubs': (('`join:item|store_sales`', ('修订 0', 2, r'$\rightarrow$ 1', 6)),
                  ('`metric:门店营业额`', 'D01：扣券后'),
                  ('`metric:门店营业额`', 'D02：扣券前'),
                  ('`metric:退货率`', '另一个指标'),
                  ('`feature:customer:spend_90d`', '一个特征')),
        'm_key': '`metric:电子品类营业额`', 'rev01': ('修订 0', 2, r'$\rightarrow$ 1', 6),
        'row_b': '电子品类商品的营业额（实付金额）',
        'row_e': r'请求、SQL 轨迹、答案、检查、依赖 $V$',
        'filter': "`filter i_category = '电子'`",
        'lstate': '查找状态', 'aliases': '别名', 'aliases_note': '说法到键',
        'alias_row': ('`门店营业额`', '`D01 D02`'),
        'vectors': '向量，每条定义一个', 'judges': (r'判别器 $\times$3，', '由目录训练'),
        'h': r'检查结果 $\mathcal{H}$', 'h_key': r'键 $(\mathrm{id}(c),\,V(\mathrm{dep}(c)))$',
        'h_rows': ('`date_dim`', '`store_sales`$\\rightarrow$`date_dim`', '`item`', '`item`',
                   "`item`, `'Y'`"),
        'lookup': '查找', 'lookup_note': '不生成 SQL，不调用 LLM', 'request': r'请求 $\rho$',
        'stages': (('别名表', '确认过的说法？'), ('召回', 'bge-m3，最近 8 条'),
                   (r'判别 $\times$3', '交叉编码器，逐条给 $p$'), ('判定', '')),
        'refer_zone': '参考',
        'outs': (('命中', '一条定义'), ('同名', '全部返回并说明区别'),
                 ('参考', '智能体确认后存为别名'), ('未命中', '智能体自行探索')),
        'exec': '检查并执行', 'exec_note': '同一快照 $D_s$', 'exec_in': r'命中：$m$, $p$, $d$',
        'exec_rows': (r'检查 $C$：取 $\mathcal{H}$ 中 $V_s$ 处的结果，', r'没有则执行一次 $Q_c$',
                      r'编译 $d(q_0(D_s,p))$ 并执行'),
        'cat': '电子', 'feat': r'特征：逐个 $(u_i,t_i)$', 'answer': '答案返回智能体',
        'maint': '维护', 'maint_note': ('每次写入', '之后'),
        'cells': (
            ('写入', (r'每张表的版本戳 $V(T)$', r'`item`：批次 0$\rightarrow$1',
                      r'纯插入：新行 $\Delta T$')),
            ('第一级：版本', (r'$V(\mathrm{dep}(c))$ 未变则跳过', '只重跑 5 项中的 2 项',
                              '每项只跑一次，所有定义共用')),
            ('第二级：插入的行', (r'只经索引检查 $\Delta T$', '键 17 出现两次')),
            ('修复或弃用', ('唯一的单步修改，答案不变', r"`i_is_current='Y'`$\rightarrow$修订 1",
                            '否则弃用；新取值：待验证')),
        ),
        'maint_out': '$V$′ 处的结果、修订 1',
        'db': '数据库', 'db_note': ('版本 $V(T)$', '随写入改变'),
        'batch': (5, r'batch 0 $\rightarrow$ 1'), 'rows_note': ('当前', '新增'),
        'snapshot': '快照 $D_s$', 'etl': 'ETL 作业', 'etl_note': '载入 item 历史',
    },
}

# Boxes (x, y, w, h), millimetres from the top left.
AG_Y, AG_H, AG_W = 2.4, 8.6, 32.0
AG_X = (2.5, 64.0, 104.0, 143.5)
FIELD_BOX = (1.5, 13.4, 176.0, 68.4)
PUB = (2.5, 17.0, 40.2, 44.6)
KB = (45.9, 17.0, 82.1, 44.6)
LOOK = (131.2, 17.0, 44.3, 35.9)
EXEC = (131.2, 55.5, 44.3, 24.9)
MAINT = (2.5, 65.2, 125.5, 15.2)
SLAB = (25.0, 85.4, 150.5, 10.2)
ETL = (2.5, 85.8, 19.5, 9.4)
STAGE_Y = (25.0, 29.6, 34.2)                       # Lookup stages and the state each one reads


def baseline(y_center, size):
    """Baseline that centres capitals and digits on y_center."""
    return y_center + .34 * size * PT


def draw(s, lang):
    L = LABELS[lang]
    text, rect, route = s.text, s.rect, s.route

    def node(b, d=1.4):
        x, y, w, h = b
        s.poly([(x, y), (x + d, y - d), (x + w + d, y - d), (x + w, y)], '#F2F0EC', '#BDB9B2', .12)
        s.poly([(x + w, y), (x + w + d, y - d), (x + w + d, y + h - d), (x + w, y + h)],
               '#E7E4DF', '#BDB9B2', .12)
        rect(x, y, w, h, WHITE, '#BDB9B2', .16, r=.4)

    def person(x, y, c='#8E8B85'):
        s.circle(x, y, .72, c)
        rect(x - 1.1, y + .88, 2.2, 1.25, c, None, r=.62)

    def step(x, y, n):
        s.circle(x, y, 1.5, STEP_C[n])
        text(x, baseline(y, 6.6), str(n), 6.6, WHITE, 'bold', 'center')

    def rich(x, yc, tokens, size, color, style='sans', align='left', width=None):
        """A label whose integer tokens are inline references to steps (small circled numbers in
        the colour of that step's badge). yc is the visual centre. Returns the width drawn."""
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

    def comp(b, title, note, band, note_c, band_h=4.0):
        """A component: a white box with a tinted title band; returns the band's bottom."""
        x, y, w, h = b
        rect(x, y, w, h, WHITE, EDGE, .18, r=.6)
        rect(x + .14, y + .14, w - .28, band_h, band, None, r=.5)
        rect(x + .14, y + .14 + band_h / 2, w - .28, band_h / 2, band, None)
        yc = y + .14 + band_h / 2
        tw = text(x + 1.3, baseline(yc, TITLE), title, TITLE, INK, 'bold')
        if note:
            text(x + w - 1.2, baseline(yc, NOTE), note, NOTE, note_c, align='right', width=w - tw - 3.6)
        return y + .14 + band_h

    def io_tag(x, yc, label, color=INK):
        """A dark input/output tag; returns its width."""
        w = measure(label, TAG, 'bold') + 1.2
        rect(x, yc - 1.0, w, 2.0, color, None, r=.5)
        text(x + .6, baseline(yc, TAG), label, TAG, WHITE, 'bold')
        return w

    def pill(x, yc, label, color, w):
        rect(x, yc - 1.05, w, 2.1, color, None, r=1.05)
        text(x + w / 2, baseline(yc, TAG), label, TAG, WHITE, 'bold', 'center')

    def down(x, y0, y1, color):
        route([(x, y0), (x, y1)], color, THIN, length=.8)

    def heading(x, yc, title, note, x_right, color=ACC_DK):
        tw = text(x, baseline(yc, SUB), title, SUB, color, 'bold')
        if note:
            text(x_right, baseline(yc, NOTE), note, NOTE, MUTED, align='right', width=x_right - x - tw - 1.5)
        return tw

    # Field: the blue band is MAVRA; agents and the database are outside it.
    rect(*FIELD_BOX, FIELD, None, r=1.4)
    rect(3.0, 14.0, .55, 1.9, ACC)
    text(4.3, 15.65, L['middleware'], 6.9, ACC_DK, 'bold')

    # Agents -------------------------------------------------------------------
    for k, (x, letter) in enumerate(zip(AG_X, ('1', '2', 'N', 'P'))):
        node((x, AG_Y, AG_W, AG_H))
        person(x + 2.3, AG_Y + 1.45)
        name = L['predictive'] if letter == 'P' else f"{L['agent']} {letter}"
        text(x + 4.6, AG_Y + 3.0, name, BODY, LEARN if letter == '1' else INK, 'bold')
        if L['when'][k]:
            rich(x + AG_W - 1.0, AG_Y + 3.0 - .34 * (SMALL - .6) * PT, L['when'][k], SMALL - .6,
                 MAINT_C if k == 2 else (USE if k == 1 else MUTED),
                 'bold' if k in (1, 2) else 'sans', align='right')
        aw = text(x + 1.2, AG_Y + 5.7, L['ask'], SMALL, ACC_DK, 'bold')
        text(x + 1.2 + aw + (.8 if lang == 'en' else 0), AG_Y + 5.7, L['q'][k], SMALL, INK,
             width=AG_W - 2.2 - aw)
        text(x + 1.2, AG_Y + 7.95, L['p'][k], SMALL - .4,
             LEARN if letter == '1' else (MAINT_C if letter == 'N' else ACC_DK), width=AG_W - 2.0)
    dots_x = (AG_X[1] + AG_W + AG_X[2]) / 2
    for k in (-1, 0, 1):
        s.circle(dots_x + 1.6 * k, AG_Y + AG_H / 2, .35, EDGE)

    # Step 1: Agent 1's verified session enters Publish.
    px, py, pw, ph = PUB
    a1 = AG_X[0] + AG_W - 5.0
    route([(a1, AG_Y + AG_H), (a1, py)], LEARN, THIN, length=.9)
    step(a1 + 2.7, 14.3, 1)

    # Publish ----------------------------------------------------------------
    pb = comp(PUB, L['publish'], L['publish_note'], LEARN_PALE, LEARN)
    x0, x1 = px + 1.1, px + pw - 1.1
    iw, mid = x1 - x0, px + pw / 2
    # input: the session's SQL with the filter phi and the period p marked, its probes and answer
    y = pb + 2.0
    tw = io_tag(x0, y, L['input'])
    text(x0 + tw + .8, baseline(y, NOTE), L['session'], NOTE, MUTED, width=iw - tw - .8)
    for k, (kw_, part, mark) in enumerate((('`WHERE`', L['phi'], r'$\varphi$'),
                                           ('`AND`', '`d_year = 2001 AND d_moy = 1`', '$p$'))):
        y += 2.6
        ww = text(x0, baseline(y, CODE), kw_, CODE, INK) + .9
        fw = measure(part, CODE)
        rect(x0 + ww - .35, y - 1.05, fw + .7, 2.1, LEARN_PALE if k == 0 else WHITE, LEARN, .16, r=.35,
             dash=None if k == 0 else (.6, .35))
        text(x0 + ww, baseline(y, CODE), part, CODE, INK)
        text(x0 + ww + fw + .8, baseline(y, 6.0), mark, 6.0, LEARN)
        assert x0 + ww + fw + 2.4 < x1, part
    y += 2.6
    ww = text(x0, baseline(y, NOTE), L['trace3'][0], NOTE, MUTED) + .8
    ww += text(x0 + ww, baseline(y, CODE), L['trace3'][1], CODE, INK) + 1.2
    sp.mark(s, x0 + ww, y, True)
    down(mid, y + 1.25, y + 2.55, LEARN)
    # extract: an LLM separates the fixed implementation I from the session's parameter p0
    y += 3.85
    sp.sparkle(s, x0 + 1.0, y, 1.0, LEARN)
    tw = text(x0 + 2.6, baseline(y, SUB), L['extract'], SUB, INK, 'bold')
    text(x1, baseline(y, NOTE), L['extract_note'], NOTE, MUTED, align='right', width=iw - tw - 4)
    y += 2.6
    cw = measure(L['chip_i'], NOTE) + 1.4
    rect(x0, y - 1.15, cw, 2.3, LEARN_PALE, LEARN, .16, r=.5)
    text(x0 + .7, baseline(y, NOTE), L['chip_i'], NOTE, INK)
    pw_ = measure(L['chip_p'], NOTE) + 1.4
    rect(x1 - pw_, y - 1.15, pw_, 2.3, WHITE, LEARN, .16, r=.5, dash=(.6, .35))
    text(x1 - pw_ + .7, baseline(y, NOTE), L['chip_p'], NOTE, INK)
    assert x0 + cw + .8 < x1 - pw_, 'Publish: I and p0 chips overlap'
    down(mid, y + 1.4, y + 2.6, LEARN)
    # derive: conditions from the structure of I and from the session's probes
    y += 3.9
    tw = text(x0, baseline(y, SUB), L['derive'], SUB, INK, 'bold')
    text(x1, baseline(y, NOTE), L['derive_note'], NOTE, MUTED, align='right', width=iw - tw - 2)
    y += 2.45
    xx = x0 + .2 + sp.key_icon(s, x0 + .2, y, ACC_DK) + .9
    xx += text(xx, baseline(y, NOTE), L['derive_glyphs'][0], NOTE, INK) + 1.8
    xx += sp.gauge_icon(s, xx, y) + .9
    text(xx, baseline(y, NOTE), L['derive_glyphs'][1], NOTE, INK, width=x1 - xx)
    y += 2.3
    text(x0 + .2, baseline(y, NOTE), L['derive_probe'], NOTE, INK, width=iw - .2)
    down(mid, y + 1.2, y + 2.4, LEARN)
    # gates: G1-G5 check the source and the structure; G6-G7 replay the answer (lossy extraction fails)
    y += 3.7
    tw = text(x0, baseline(y, SUB), L['gates'], SUB, INK, 'bold') + .9
    tw += text(x0 + tw, baseline(y, SUB), 'G1–G7', SUB, LEARN, 'bold')
    text(x1, baseline(y, NOTE), L['gates_note'], NOTE, MUTED, align='right', width=iw - tw - 1.2)
    y += 2.35
    gw = text(x0 + .2, baseline(y, NOTE), 'G6–G7', NOTE, LEARN, 'bold') + 1.0
    text(x0 + .2 + gw, baseline(y, NOTE), L['replay'], NOTE, INK, width=iw - gw - .2)
    bx0 = x0 + 15.6
    unit = (x1 - 3.0 - bx0) / LOSSY
    for k, (label, val) in enumerate(zip(L['bars'], L['bar_vals'])):
        yb = y + 2.25 + 2.1 * k
        text(bx0 - .8, baseline(yb, NOTE - .2), label, NOTE - .2, INK if k == 0 else RED, align='right')
        bw = unit * (1 if k == 0 else LOSSY)
        rect(bx0, yb - .55, bw, 1.1, ACC if k == 0 else RED, None)
        if k == 0:
            vw = text(bx0 + bw + .7, baseline(yb, NOTE - .2), val, NOTE - .2, ACC_DK)
            sp.mark(s, bx0 + bw + .7 + vw + 1.1, yb, True)
        else:
            sp.mark(s, bx0 + bw + 1.2, yb, False)
            text(bx0 + bw - .6, baseline(yb, NOTE - .6), val, NOTE - .6, WHITE, 'bold', 'right')
    yout = y + 2.25 + 2.1 + 2.7
    tw = io_tag(x0, yout, L['output'], LEARN)
    ww = text(x0 + tw + .8, baseline(yout, NOTE), L['publish_out'], NOTE, LEARN, 'bold') + .6
    text(x0 + tw + .8 + ww, baseline(yout, NOTE + .4), r'$m^0$', NOTE + .4, LEARN)
    text(x1, baseline(yout, NOTE), L['reject'], NOTE, MUTED, align='right')
    assert yout + 1.4 < py + ph, f'Publish overflows: {yout:.1f}'

    # Knowledge base ------------------------------------------------------------
    kx, ky, kw, kh = KB
    rect(kx + 1, ky + 1, kw, kh, SIDE, EDGE, .12, r=.6)
    rect(kx, ky, kw, kh, WHITE, EDGE, .18, r=.6)
    rect(kx, ky, kw, 3.6, ACC, None, r=.6)
    rect(kx, ky + 1.8, kw, 1.8, ACC, None)
    tw = text(kx + 1.4, baseline(ky + 1.8, TITLE), L['kb'], TITLE, WHITE, 'bold')
    text(kx + kw - 1.4, baseline(ky + 1.8, NOTE), L['kb_note'], NOTE, WHITE, align='right',
         width=kw - tw - 4)
    cx0, cx1 = kx + 1.2, kx + 50.0            # definitions
    rx0, rx1 = kx + 51.8, kx + kw - 1.2       # lookup state and H
    cw, rw = cx1 - cx0, rx1 - rx0
    gap_x = (cx1 + rx0) / 2                   # references run in the gap between the two columns
    y_head = ky + 5.3

    # Definitions: entries collapsed to their keys, then one entry field by field. Keys name the
    # kind and the computation; two entries share the name Store revenue (homonyms).
    heading(cx0, y_head, L['defs'], L['defs_note'], cx1)
    op, top0 = 2.55, y_head + 1.6
    stubs = L['stubs'] + (('`...`', ''),)
    rect(cx0, top0, cw, .4 + op * len(stubs) + .2, TOP, EDGE, .16, r=.45)
    stub_y = []
    for k, (key, meta) in enumerate(stubs):
        yc = top0 + .4 + op * k + op / 2
        if k:
            s.line(cx0 + .6, yc - op / 2, cx1 - .6, yc - op / 2, WHITE, .3)
        if isinstance(meta, tuple):
            mw = rich(cx1 - .9, yc, meta, 5.5, MUTED, align='right')
        else:
            mw = text(cx1 - .9, baseline(yc, 5.5), meta, 5.5, MUTED, align='right') if meta else 0
        text(cx0 + .9, baseline(yc, CODE), key, CODE, MUTED if key == '`...`' else INK, width=cw - 2.6 - mw)
        stub_y.append(yc)
    stub_bottom = top0 + .4 + op * len(stubs) + .2

    # The expanded entry: the fields of m^r grouped by B, I, C, E; r is the revision in its header.
    eh, pitch = 2.9, 2.42
    rows = ('B', 'I', None, None, 'C', 'E')
    ent_h = eh + .5 + pitch * len(rows) + .5
    top1 = ky + kh - .9 - ent_h
    assert top1 > stub_bottom + .8, f'definitions overlap: {top1:.1f} vs {stub_bottom:.1f}'
    rect(cx0, top1, cw, ent_h, WHITE, ACC, .2, r=.45)
    rect(cx0 + .15, top1 + .15, cw - .3, eh - .15, ACC_PALE, None, r=.35)
    mw = rich(cx1 - .9, top1 + eh / 2 + .05, L['rev01'], 5.5, ACC_DK, align='right')
    text(cx0 + .9, baseline(top1 + eh / 2 + .05, CODE + .2), L['m_key'], CODE + .2, INK, width=cw - 2.6 - mw)
    gut = cx0 + 3.6
    row_y = [top1 + eh + .5 + pitch * (k + .5) for k in range(len(rows))]
    letters = {'B': INK, 'I': ACC_DK, 'C': '#5E6E82', 'E': LEARN}
    for yc, letter in zip(row_y, rows):
        if letter:
            text(cx0 + 1.75, baseline(yc, 6.2), f'${letter}$', 6.2, letters[letter], align='center')
            if letter != 'B':
                s.line(cx0 + .6, yc - pitch / 2, cx1 - .6, yc - pitch / 2, RULE, .12)
    s.line(cx0 + 3.2, row_y[0] - pitch / 2 + .3, cx0 + 3.2, row_y[-1] + pitch / 2 - .3, RULE, .12)
    avail = cx1 - gut - .6
    text(gut, baseline(row_y[0], NOTE), L['row_b'], NOTE, INK, width=avail)
    text(gut, baseline(row_y[1], CODE),
         r'`store_sales`$\,\cdot\,$`sum(ss_net_paid)`$\,\cdot\,K\,\cdot\,\tau$', CODE, INK, width=avail)
    jw = text(gut, baseline(row_y[2], CODE), '`joins`', CODE, INK) + .9
    jw += text(gut + jw, baseline(row_y[2], CODE), '`join:item|store_sales`', CODE, REF)
    text(gut, baseline(row_y[3], CODE), L['filter'], CODE, INK, width=avail)
    # C: references to condition signatures (KeyUnique, Unmatched, a domain assumption)
    xx = gut
    for _ in range(3):
        xx += sp.key_icon(s, xx, row_y[4], ACC_DK) + .5
    xx += .5
    for _ in range(2):
        xx += sp.gauge_icon(s, xx, row_y[4]) + .5
    xx += .5
    c_end = xx + text(xx, baseline(row_y[4], CODE), '`Dom(i_category)`', CODE, INK)
    text(gut, baseline(row_y[5], NOTE), L['row_e'], NOTE, INK, width=avail)
    ent_bottom = top1 + ent_h
    # joins -> the join entry, by key (through the gap between the columns)
    route([(gut + jw + .8, row_y[2]), (gap_x, row_y[2]), (gap_x, stub_y[0]), (cx1, stub_y[0])],
          REF, .2, length=.7, radius=.4)

    # Lookup state: aliases, vectors, judges, level with the Lookup stage that reads each of them.
    heading(rx0, y_head, L['lstate'], None, rx1)
    ls_top = STAGE_Y[0] - 1.6
    ls_bot = STAGE_Y[2] + 2.6
    rect(rx0, ls_top, rw, ls_bot - ls_top, WHITE, ACC, .18, r=.45)
    ya = STAGE_Y[0]
    tw = text(rx0 + .9, baseline(ya, NOTE), L['aliases'], NOTE, INK, 'bold')
    text(rx1 - .9, baseline(ya, NOTE - .3), L['aliases_note'], NOTE - .3, MUTED, align='right',
         width=rw - tw - 2.6)
    yr = ya + 2.15
    kw_ = text(rx1 - .9, baseline(yr, CODE - .2), L['alias_row'][1], CODE - .2, ACC_DK, align='right')
    text(rx0 + 1.3, baseline(yr, CODE - .2), L['alias_row'][0], CODE - .2, INK, width=rw - kw_ - 3.2)
    yv = STAGE_Y[1]
    for k, (dx, dy) in enumerate(((.3, -.4), (1.1, .3), (1.7, -.5), (2.4, .1), (.8, -1.0))):
        s.circle(rx0 + 1.2 + dx, yv + .2 + dy * .9, .28, ACC if k == 1 else '#9DB8DD')
    text(rx0 + 4.6, baseline(yv, NOTE), L['vectors'], NOTE, INK, width=rw - 5.4)
    yj = STAGE_Y[2]
    for k in (2, 1, 0):
        rect(rx0 + 1.0 + .45 * k, yj - .7 - .45 * k, 2.0, 1.7, WHITE if k else ACC_PALE, ACC, .14, r=.3)
    for k, line in enumerate(L['judges']):
        text(rx0 + 4.6, baseline(yj - 1.05 + 2.1 * k, NOTE), line, NOTE, INK, width=rw - 5.4)

    # Check outcomes H: one row per (signature, versions). A row serves every definition that
    # references the signature; a write to a dependency starts a new row.
    hy = ls_bot + 1.3
    hh = ky + kh - .9 - hy
    rect(rx0, hy, rw, hh, WHITE, EDGE, .18, r=.45)
    rect(rx0 + .15, hy + .15, rw - .3, 2.7, ACC, None, r=.35)
    text(rx0 + .9, baseline(hy + 1.5, SUB - .2), L['h'], SUB - .2, WHITE, 'bold')
    text(rx0 + .9, baseline(hy + 4.35, NOTE - .3), L['h_key'], NOTE - .3, MUTED, width=rw - 1.6)
    hrow = (('key', L['h_rows'][0], '`@0`', True, None), ('gauge', L['h_rows'][1], '`@0`', True, None),
            ('key', L['h_rows'][2], '`@0`', True, None), ('key', L['h_rows'][3], '`@1`', False, 6),
            ('key', L['h_rows'][4], '`@1`', True, 6))
    hp = (hh - 6.0) / len(hrow)
    h_rows = []
    for k, (glyph, label, ver, ok, by) in enumerate(hrow):
        yc = hy + 5.9 + hp * (k + .5)
        if k:
            s.line(rx0 + .6, yc - hp / 2, rx1 - .6, yc - hp / 2, RULE, .1)
        gw = sp.key_icon(s, rx0 + .8, yc, ACC_DK) if glyph == 'key' else sp.gauge_icon(s, rx0 + .8, yc)
        lw = text(rx0 + 1.5 + gw, baseline(yc, CODE - .3), label, CODE - .3, INK)
        vw = text(rx0 + 1.5 + gw + lw + .6, baseline(yc, CODE - .3), ver, CODE - .3,
                  MAINT_C if by else MUTED)
        mx_ = rx0 + 1.5 + gw + lw + .6 + vw + 1.1
        sp.mark(s, mx_, yc, ok, .8)
        if by:
            rich(rx1 - .7, yc, by, 4.9, INK, align='right')
        assert mx_ + 1.0 < rx1 - .7 - (2 * MINI + .3 if by else 0), f'H row {k} too wide'
        h_rows.append(yc)
    # the date_dim row serves three definitions: three dots joined by a line
    d0 = rx1 - 3.6
    s.line(d0, h_rows[0], d0 + 2.4, h_rows[0], ACC_DK, .2)
    for k in range(3):
        s.circle(d0 + 1.2 * k, h_rows[0], .38, ACC_DK)
    # C -> the outcomes its signatures name
    assert hy + 3 < row_y[4] < hy + hh - .5
    route([(c_end + .8, row_y[4]), (rx0, row_y[4])], REF, .2, length=.7)

    # Step 2: Publish writes revision 0 into the definitions.
    assert top1 + 1 < yout < ent_bottom - .6, 'step 2 must reach the expanded entry'
    route([(px + pw, yout), (cx0, yout)], LEARN, THICK, length=1.0)
    step((px + pw + kx) / 2, yout - 2.7, 2)

    # Lookup -------------------------------------------------------------------
    lx, ly, lw, lh = LOOK
    lb = comp(LOOK, L['lookup'], L['lookup_note'], ACC_PALE, ACC_DK)
    # Consumers' requests (step 3).
    c2_x, cn_x = AG_X[1] + AG_W / 2, AG_X[2] + AG_W / 2
    l2_x, ln_x, lp_x = lx + 4.2, lx + lw / 2, lx + lw - 3.6
    route([(c2_x, AG_Y + AG_H), (c2_x, 12.6), (l2_x, 12.6), (l2_x, ly)], USE, THIN, length=.9, radius=.4)
    step(l2_x - 2.8, 14.6, 3)
    route([(cn_x, AG_Y + AG_H), (cn_x, 11.75), (ln_x, 11.75), (ln_x, ly)], MAINT_C, THIN, length=.9,
          radius=.4)
    route([(lp_x, AG_Y + AG_H), (lp_x, ly)], USE, THIN, length=.9)
    text(ln_x + 1.0, 15.9, L['request'], NOTE, ACC_DK)
    sx0, sx1 = lx + 1.0, lx + lw - 1.0
    yd = STAGE_Y[2] + 4.8                   # Decide
    stage_y = STAGE_Y + (yd,)
    assert STAGE_Y[0] - 1.4 > lb + .8
    tops = []
    for k, ((name, note), yc) in enumerate(zip(L['stages'], stage_y)):
        top, hgt = (yc - 1.4, 2.8) if k < 3 else (yc - 1.75, 4.9)
        tops.append(top)
        rect(sx0, top, sx1 - sx0, hgt, FIELD, ACC, .16, r=.45)
        tw = text(sx0 + .8, baseline(yc, NOTE + .2), name, NOTE + .2, INK, 'bold')
        if note:
            text(sx1 - .8, baseline(yc, NOTE), note, NOTE, MUTED, align='right',
                 width=sx1 - sx0 - tw - 2.4)
        if k:
            down(sx0 + 6.0, stage_y[k - 1] + 1.4, top, ACC)
        if k < 3:   # the knowledge base state this stage reads
            route([(rx1 + .2, yc), (lx, yc)], REF, .2, length=.7)
    # Decide: per-candidate thresholds on the judges' mean p; the zones share the replies' colours.
    g0, g1 = sx0 + 12.4, sx1 - 1.2
    gw_ = g1 - g0
    for (a, b, c) in ((0, .1, '#B9B5AE'), (.1, .9, AMBER_PALE), (.9, 1.0, ACC)):
        rect(g0 + a * gw_, yd - .75, (b - a) * gw_, 1.5, c, None)
    rect(g0, yd - .75, gw_, 1.5, None, EDGE, .12)
    text(g0 + .5 * gw_, baseline(yd, TAG - .4), L['refer_zone'], TAG - .4, REFER, 'bold', 'center')
    for t in (.1, .9):
        s.line(g0 + t * gw_, yd - 1.05, g0 + t * gw_, yd + 1.05, INK, .16)
        text(g0 + t * gw_, baseline(yd + 2.0, TAG - .3), f'{t:g}'.lstrip('0'), TAG - .3, INK, align='center')
    text(g0 - .8, baseline(yd, NOTE), '$p$', NOTE, INK, align='right')
    # Replies.
    oy = tops[3] + 4.9 + 1.75
    pw2 = max(measure(o[0], TAG, 'bold') for o in L['outs']) + 1.6
    colours = (ACC, ACC_DK, REFER, '#8E8B85')
    out_y = []
    for k, ((lab, note), col) in enumerate(zip(L['outs'], colours)):
        yc = oy + 2.3 * k
        pill(sx0 + .4, yc, lab, col, pw2)
        text(sx0 + pw2 + 1.3, baseline(yc, NOTE), note, NOTE, INK, width=sx1 - sx0 - pw2 - 1.6)
        out_y.append(yc)
    assert out_y[-1] + 1.2 < ly + lh, f'Lookup overflows: {out_y[-1]:.1f}'
    # A confirmed reference becomes an alias (dashed, back to the alias stage).
    loop_x = sx1 + .5
    note_end = sx0 + pw2 + 1.3 + measure(L['outs'][2][1], NOTE) + .6
    route([(note_end, out_y[2]), (loop_x, out_y[2]), (loop_x, stage_y[0]), (sx1, stage_y[0])],
          REFER, .2, length=.7, radius=.4, dash=(.6, .35))

    # Step 4: a hit goes to Check and run.
    ex, ey, ew, eh_ = EXEC
    hit_x = sx0 + .4 + pw2 / 2
    route([(hit_x, ly + lh), (hit_x, ey)], EXEC_C, THIN, length=.9)
    step(hit_x + 2.6, (ly + lh + ey) / 2, 4)
    text(hit_x + 4.6, baseline((ly + lh + ey) / 2, NOTE), L['exec_in'], NOTE, EXEC_C)
    # Check and run ------------------------------------------------------------------
    eb = comp(EXEC, L['exec'], L['exec_note'], EXEC_PALE, EXEC_C)
    e0, e1 = ex + 1.0, ex + ew - 1.0
    y = eb + 2.0
    for k, label in enumerate(L['exec_rows']):
        yc = y + 2.3 * k + (.4 if k == 2 else 0)
        text(e0 + (2.2 if k == 1 else 0), baseline(yc, NOTE), label, NOTE, INK,
             width=e1 - e0 - (2.2 if k == 1 else 0))
    # H -> the condition check, by key and version
    hx_y = min(y, hy + hh - 1.0)
    route([(rx1 + .2, hx_y), (ex, hx_y)], REF, .2, length=.7)
    cy0 = y + 2.3 * 2 + 1.6
    code = ('SUM(ss_net_paid) ... WHERE', f"i_category = '{L['cat']}'", 'GROUP BY d_moy ORDER BY ...')
    rect(e0, cy0, e1 - e0, .8 + 1.9 * len(code), FACE, None, r=.4)
    for k, line in enumerate(code):
        text(e0 + .5, baseline(cy0 + .4 + 1.9 * (k + .5), CODE - .2), f'`{line}`', CODE - .2, INK,
             width=e1 - e0 - 1.0)
    yf = cy0 + .8 + 1.9 * len(code) + 1.6
    tw = text(e0, baseline(yf, NOTE), L['feat'], NOTE, INK)
    # the feature window: facts inside (t_i - w, t_i] count; later facts are excluded
    a0, a1 = e0 + tw + 1.4, e1 - .3
    cut = a0 + .68 * (a1 - a0)
    rect(a0 + .3 * (a1 - a0), yf - .55, cut - a0 - .3 * (a1 - a0), 1.1, AMBER_PALE, None, r=.3)
    s.line(a0, yf, a1, yf, RULE, .18)
    s.line(cut, yf - 1.0, cut, yf + .9, EXEC_C, .26)
    for t in (.4, .5, .6):
        s.circle(a0 + t * (a1 - a0), yf, .3, EXEC_C)
    for t in (.15, .8, .92):
        dx = a0 + t * (a1 - a0)
        s.line(dx - .28, yf - .28, dx + .28, yf + .28, MUTED, .16)
        s.line(dx - .28, yf + .28, dx + .28, yf - .28, MUTED, .16)
    text(cut + .5, baseline(yf - 1.5, TAG - .3), '$t_i$', TAG - .3, EXEC_C)
    ya = yf + 2.35
    tw = io_tag(e0, ya, L['output'], EXEC_C)
    text(e0 + tw + .8, baseline(ya, NOTE), L['answer'], NOTE, EXEC_C, 'bold', width=e1 - e0 - tw - .8)
    assert ya + 1.1 < ey + eh_, f'Check and run overflows: {ya:.1f}'

    # Maintain ------------------------------------------------------------------
    mx, my, mw_, mh = MAINT
    rect(mx, my, mw_, mh, WHITE, EDGE, .18, r=.6)
    hw = 16.6
    rect(mx + .14, my + .14, hw, mh - .28, MAINT_PALE, None, r=.5)
    rect(mx + .14 + hw / 2, my + .14, hw / 2, mh - .28, MAINT_PALE, None)
    text(mx + 1.3, baseline(my + 4.0, TITLE), L['maint'], TITLE, INK, 'bold')
    for k, line in enumerate(L['maint_note']):
        text(mx + 1.3, baseline(my + 7.2 + 2.4 * k, NOTE), line, NOTE, MAINT_C, width=hw - 1.6)
    widths = (24.4, 29.4, 22.4, 27.0)
    gapc = (mw_ - hw - .3 - sum(widths) - 1.0) / len(widths)
    cx = mx + hw + .3 + gapc
    cell_box = []
    for k, ((title, lines), cwid) in enumerate(zip(L['cells'], widths)):
        top, hgt = my + 1.1, mh - 2.2
        rect(cx, top, cwid, hgt, WHITE, MAINT_C if k == 3 else RULE, .16, r=.45)
        tx = cx + .8
        if k == 0:
            sp.bolt(s, cx + 1.4, top + 2.0, 2.0, MAINT_C)
            tx = cx + 2.6
        text(tx, baseline(top + 2.0, SUB - .3), title, SUB - .3, INK, 'bold', width=cx + cwid - .6 - tx)
        for j, line in enumerate(lines):
            yc = top + 4.6 + 2.3 * j
            lx_ = cx + .8
            col = INK
            if k == 1 and j == 1:   # the item load reruns 2 of 5 checks, once for all definitions
                lx_ += sp.units(s, lx_, yc, 5, 2, MAINT_C) + .8
                sp.rerun(s, lx_ + .6, yc, .55, MAINT_C)
                lx_ += 1.8
            if k == 2 and j == 1:
                col = RED
            if k == 3 and j == 1:
                col = ACC_DK
            text(lx_, baseline(yc, NOTE - .1), line, NOTE - .1, col, width=cx + cwid - .6 - lx_)
            if k == 2 and j == 1:
                sp.mark(s, lx_ + measure(line, NOTE - .1) + 1.2, yc, False, .8)
        cell_box.append((cx, top, cwid, hgt))
        if k:
            pcx, ptop, pcw, phg = cell_box[k - 1]
            route([(pcx + pcw, ptop + phg / 2), (cx, ptop + phg / 2)], MAINT_C, THIN, length=.8)
        cx += cwid + gapc
    # Step 6: rechecked outcomes and the revision go back to the knowledge base.
    dcx, dtop, dcw, _ = cell_box[3]
    up_x = rx0 + 4.0
    assert dcx + 1 < up_x < dcx + dcw - 1
    route([(up_x, dtop), (up_x, ky + kh)], MAINT_C, THICK, length=1.0)
    ymid = (my + ky + kh) / 2 + .1
    step(up_x + 2.6, ymid, 6)
    text(up_x + 4.6, baseline(ymid, NOTE - .2), L['maint_out'], NOTE - .2, MAINT_C, width=lx - up_x - 5.0)

    # Database ------------------------------------------------------------------
    bx, by, bw, bh = SLAB
    d = 1.2
    soft = '#BDB9B2'
    s.poly([(bx, by), (bx + d, by - d), (bx + bw + d, by - d), (bx + bw, by)], '#F2F0EC', soft, .12)
    s.poly([(bx + bw, by), (bx + bw + d, by - d), (bx + bw + d, by + bh - d), (bx + bw, by + bh)],
           '#E7E4DF', soft, .12)
    rect(bx, by, bw, bh, FACE, soft, .16, r=.5)
    top, inner = by + .8, bh - 1.6

    def card(x0_, w_, name, version, hot=False):
        rect(x0_, top, w_, inner, WHITE, OCHRE if hot else EDGE, .16 if hot else .12, r=.35)
        rect(x0_ + .15, top + .15, w_ - .3, 2.3, AMBER_PALE if hot else TOP, None, r=.25)
        text(x0_ + .9, top + 1.9, name, CODE + .2, INK)
        rich(x0_ + w_ - .9, top + 1.9 - .34 * 5.6 * PT, version, 5.6, OCHRE if hot else MUTED,
             'bold' if hot else 'sans', align='right')

    # item: the ETL job added a history row for key 17.
    ix, iw2 = bx + 1.6, 40.6
    card(ix, iw2, '`item`', L['batch'], hot=True)
    cols = (ix + .9, ix + 9.6, ix + 21.6)
    for c, head in zip(cols, ('`i_item_sk`', '`i_category`', '`i_is_current`')):
        text(c, top + 4.3, head, CODE - .5, MUTED)
    cat = 'Electronics' if lang == 'en' else '电子'
    for k, (key, cur) in enumerate((('17', "'Y'"), ('17', "'N'"))):
        yy = top + 6.2 + 1.95 * k
        if k:
            rect(ix + .5, yy - 1.45, iw2 - 1.0, 1.9, AMBER_PALE, None, r=.3)
        for c, value in zip(cols, (key, f"'{cat}'", cur)):
            text(c, yy, f'`{value}`', CODE - .4, INK)
        text(ix + iw2 - .9, yy, L['rows_note'][k], 5.4, OCHRE if k else MUTED, 'bold' if k else 'sans',
             align='right')

    def bars(x0_, w_, n=3):
        for r_ in range(n):
            rect(x0_ + .9, top + 3.3 + 1.65 * r_, w_ - 1.8, .8, '#E4E1DB', None, r=.2)

    for x0_, w_, name in ((ix + iw2 + 1.6, 23.0, '`store_sales`'), (ix + iw2 + 26.2, 19.0, '`date_dim`')):
        card(x0_, w_, name, 'batch 0')
        bars(x0_, w_)
    tx0 = ix + iw2 + 47.0
    text(tx0, by + 3.6, L['db'], TITLE, INK, 'bold')
    for k, line in enumerate(L['db_note']):
        text(tx0, by + 6.1 + 2.3 * k, line, NOTE, MUTED, width=EXEC[0] - 1.0 - tx0)
    # Snapshot: Check and run reads conditions and data in one snapshot.
    nx, nw = EXEC[0], bx + bw - .8 - EXEC[0]
    rect(nx, top, nw, inner, WHITE, EXEC_C, .18, r=.35, dash=(.8, .5))
    text(nx + 1.0, top + 2.6, L['snapshot'], NOTE, EXEC_C, 'bold')
    mini = (nw - 2.0 - 2 * .5) / 3
    for k in range(3):
        mxx = nx + 1.0 + k * (mini + .5)
        rect(mxx, top + 3.5, mini, inner - 4.2, FACE, EDGE, .1, r=.25)
        rect(mxx + .15, top + 3.65, mini - .3, 1.0, TOP, None, r=.2)
    route([(nx + nw / 2, top), (nx + nw / 2, ey + eh_)], EXEC_C, .25, dash=(.7, .45), length=.8)
    # Maintain reads the versions and inserted rows of the changed table.
    wx = cell_box[0][0] + cell_box[0][2] - 4.0
    assert ix + 1 < wx < ix + iw2 - 1
    route([(wx, top), (wx, my + mh)], MAINT_C, .3, dash=(.7, .45), length=.9)

    # ETL (outside the database): step 5 writes a new item history row.
    tx, ty, tw_, th = ETL
    for off in (1.2, .6, 0):
        rect(tx + off, ty - off, tw_ - 1.2, th, WHITE, EDGE, .13, r=.4)
    text(tx + 1.4, ty + 3.5, L['etl'], TITLE, INK, 'bold', width=tw_ - 2.6)
    text(tx + 1.4, ty + 6.5, L['etl_note'], NOTE, OCHRE, width=tw_ - 2.6)
    route([(tx + tw_ - 1.2, ty + th / 2 + 1.2), (bx, ty + th / 2 + 1.2)], MAINT_C, THIN, length=1.0)
    step(tx + tw_ + 1.45, ty + th / 2 - 2.2, 5)


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
