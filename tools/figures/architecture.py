"""MAVRA system overview (Figure 2): four core components around a shared knowledge cache.

Double column (178.0 mm wide, 90.0 mm high).
Balances visual abstraction with concrete technical mechanisms across four noun components:
  - Top row: Concurrent data agents (Agent 1 learning session, Agent 2 before write,
    ..., Agent N after write, and Predictive agent P at cutoff t_i).
  - Top-left (Knowledge Extractor, steps 1-2): Agent 1 Trace UI card -> Extract Query & C
    (separating fixed relational core (B, I) from bindings beta_0 + AST/probe condition
    derivation) -> Candidate Validation (3 admission gates including SQL recompilation)
    -> Definition m^0 written into Knowledge Cache.
  - Top-center+right (Knowledge Cache, step 3 lookup): Unified storage and local semantic
    lookup component housing:
      (1) Graph catalog M: composable join, homonymous D01/D02, metrics, predictive
          feature + 4-band tuple anatomy m^r = (B, I, C, E, r) with C -> H refs.
      (2) Condition nodes H: keyed by (id(c), V(dep(c))), showing multi-definition
          sharing dots, @v0 passes, @v1 grain break, @v1 repaired pass, and coalesced cache Gamma.
      (3) Semantic lookup index: Alias & bge-m3 Recall + 3-seed XLM-R Cross-Encoder
          Scorer + calibrated (.1, .9) spectrum routing Hit (m^r, beta) to Query Executor
          (step 4) or returning Diffs/Refer/Miss to agents.
  - Bottom-left (Maintenance Manager, steps 5-6): 3-stage incremental update pipeline
    (1. Prune by Table Versions -> 2. Coalesced Node Check Q_c via Gamma ->
     3. Certified Repair), bidirectional (<->) DB version/check
    arrow, and write-back (step 6) to Knowledge Cache.
  - Bottom-right (Query Executor, step 4): Single Read-Only Snapshot D_s (versions V_s)
    combining (1) Validate C and C_req via Gamma[k(c, V_s)] and (2) Bind & Compile SQL
    (analytical metric + leak-free point-in-time feature window), bidirectional (<->)
    execution on snapshot D_s, and guarded return path to agents.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vecfig import PT, measure  # noqa: E402
import style  # noqa: E402
from style import WHITE  # noqa: E402

NAME = 'architecture'
W, H = style.TEXTWIDTH, 90.0

TITLE, BODY, SMALL, TINY, STEP = 7.2, 6.2, 5.75, 5.35, 6.6
INK, MUTED = '#1F2328', '#596068'
CARD_EDGE, SUB_EDGE, RULE = '#737B84', '#B6BEC7', '#CFD5DC'
EDGE = CARD_EDGE
HEAD_BAND, FACE, TOP = '#ECEFF3', '#F4F5F7', '#EAECEF'
CONTAINER_BG, CONTAINER_EDGE = '#F7F8FA', '#8492A6'
FIELD = CONTAINER_BG
ACC, ACC_DK, ACC_PALE = '#24416B', '#1B3254', '#EDF1F7'
NAVY_SOFT, NAVY_EDGE = '#F6F8FB', '#9EB1CC'
LEARN, LEARN_DK, LEARN_PALE, LEARN_EDGE = '#46506E', '#323A52', '#EFF1F6', '#B0B7CA'
EXEC_C, EXEC_DK, EXEC_PALE, EXEC_EDGE = '#7D5C38', '#5E4427', '#F4EFE8', '#C2B19C'
AMBER, AMBER_PALE = '#8A683B', '#F3EDE2'
MAINT_C, MAINT_DK, MAINT_PALE, MAINT_EDGE = '#2E5B58', '#214442', '#EBF1F0', '#9DB8B5'
RED, RED_PALE, RED_EDGE = '#942B2B', '#F6EDED', '#CCA6A6'
SLATE, REF = '#4E5D6C', '#6E747C'
THIN, THICK = .22, .48


def baseline(yc, size):
    return yc + .34 * size * PT


def draw(s, lang):
    en = (lang == 'en')
    text, rect, route = s.text, s.rect, s.route

    def label(x, yc, txt, size=SMALL, color=INK, wt='sans', align='left', width=None):
        return text(x, baseline(yc, size), txt, size, color, wt, align, width)

    def box(b, fill=WHITE, edge=EDGE, sw=.18, r=.65, dash=None):
        rect(*b, fill, edge, sw, r=r, dash=dash)

    def card_head(b, title_txt, sub_txt, band_fill, edge_c=EDGE, title_c=INK, sub_c=MUTED, bh=3.2):
        x, y, w, h = b
        rect(x, y, w, h, WHITE, edge_c, .2, r=.65)
        rect(x + .12, y + .12, w - .24, bh, band_fill, None, r=.55)
        rect(x + .12, y + .12 + bh / 2, w - .24, bh / 2, band_fill, None)
        yc = y + .12 + bh / 2
        tw = label(x + 1.15, yc, title_txt, TITLE, title_c, 'bold')
        if sub_txt:
            label(x + w - 1.05, yc, sub_txt, 4.95, sub_c, 'sans', 'right', width=w - tw - 2.3)
        return tw

    def node3d(b, d=1.0, edge_c='#A6AEB8'):
        x, y, w, h = b
        s.poly([(x, y), (x + d, y - d), (x + w + d, y - d), (x + w, y)], '#F3F4F6', edge_c, .12)
        s.poly([(x + w, y), (x + w + d, y - d), (x + w + d, y + h - d), (x + w, y + h)],
               '#E5E8EC', edge_c, .12)
        rect(x, y, w, h, WHITE, edge_c, .18, r=.55)

    def step_badge(x, yc, n, color, r=1.35):
        s.circle(x, yc, r, color)
        label(x, yc, str(n), STEP if r >= 1.25 else 5.8, WHITE, 'bold', 'center')

    def mini_step(x, yc, n, color, r=.84):
        s.circle(x, yc, r, color)
        label(x, yc, str(n), 4.85, WHITE, 'bold', 'center')

    def check_mark(x, yc, ok, c=None, k=.86):
        if ok:
            s.poly([(x - .58 * k, yc + .02 * k), (x - .14 * k, yc + .46 * k), (x + .62 * k, yc - .52 * k)],
                   None, c or ACC, .24, closed=False)
        else:
            s.line(x - .46 * k, yc - .46 * k, x + .46 * k, yc + .46 * k, c or RED, .24)
            s.line(x - .46 * k, yc + .46 * k, x + .46 * k, yc - .46 * k, c or RED, .24)

    def pill(x, yc, txt, fill_c, text_c=WHITE, edge_c=None, size=4.4, pad=.65, h=1.72, wt='bold', dash=None):
        w = measure(txt, size, wt) + 2 * pad
        rect(x, yc - h / 2, w, h, fill_c, edge_c, .14 if edge_c else 0, r=.35, dash=dash)
        label(x + w / 2, yc, txt, size, text_c, wt, 'center')
        return w

    def person_icon(x, yc, c='#68707A'):
        s.circle(x, yc - .58, .60, c)
        rect(x - .95, yc + .14, 1.9, 1.06, c, None, r=.52)

    def key_icon(x, yc, c=ACC_DK):
        s.circle(x + .46, yc, .41, None, c, .18)
        s.line(x + .87, yc, x + 1.85, yc, c, .18)
        s.line(x + 1.42, yc, x + 1.42, yc + .36, c, .18)
        s.line(x + 1.76, yc, x + 1.76, yc + .36, c, .18)

    def join_icon(x, yc, c=ACC_DK):
        rect(x, yc - .44, .82, .88, ACC_PALE, c, .14, r=.13)
        rect(x + 1.06, yc - .44, .82, .88, WHITE, c, .14, r=.13)
        s.line(x + .82, yc, x + 1.06, yc, c, .18)

    def dom_icon(x, yc, c=MAINT_C):
        rect(x, yc - .44, 1.82, .88, MAINT_PALE, c, .14, r=.16)
        for dx_i in (.42, .91, 1.40):
            s.circle(x + dx_i, yc, .15, c)

    def share_dots(x, yc, n, col=ACC):
        span = (n - 1) * 1.12
        if n > 1:
            s.line(x, yc, x + span, yc, col, .17)
        for idx_d in range(n):
            s.circle(x + idx_d * 1.12, yc, .29, col)

    # =========================================================================
    # 1. Top Row: Concurrent Data Agents (1, 2, ..., N and Predictive P)
    # =========================================================================
    ag_y, ag_h = 1.4, 8.4
    ag_specs = (
        (1.6, 38.0, 'Agent 1' if en else '智能体 1',
         'first session' if en else '首次探索', None,
         'ask:' if en else '问：', 'Jan. electronics revenue?' if en else '1 月电子品类营业额？',
         'explores DB, submits answer' if en else '探查数据库并提交答案', LEARN),
        (45.2, 38.0, 'Agent 2' if en else '智能体 2',
         'before' if en else '写入前', 5,
         'ask:' if en else '问：', 'highest-revenue month?' if en else '电子营业额最高月份？',
         'ranks months by revenue' if en else '按营收对月份排序', ACC_DK),
        (88.8, 38.4, 'Agent N' if en else '智能体 N',
         'after' if en else '写入后', 5,
         'ask:' if en else '问：', 'Sep. revenue vs. last year?' if en else '9 月电子营业额同比？',
         'compares periods after repair' if en else '修复后比较两个期间', MAINT_DK),
        (132.4, 41.2, 'Predictive agent P' if en else '预测智能体 P',
         'cutoff date' if en else '预测截点', None,
         'ask:' if en else '问：', 'will this customer churn?' if en else '该客户是否会流失？',
         'reuses pre-cutoff features' if en else '复用截点前特征', EXEC_DK),
    )
    for ax, aw, aname, awhen, astep, aask, aq, anote, acol in ag_specs:
        node3d((ax, ag_y, aw, ag_h))
        person_icon(ax + 2.05, ag_y + 1.95, '#68707A')
        label(ax + 3.75, ag_y + 1.95, aname, BODY, INK, 'bold')
        if awhen:
            rx_end = ax + aw - 1.05
            if astep is not None:
                mini_step(rx_end - .85, ag_y + 1.95, astep, MAINT_C, r=.82)
                rx_end -= 2.0
            is_hi = ('after' in awhen or '后' in awhen)
            label(rx_end, ag_y + 1.95, awhen, 4.65, MAINT_DK if is_hi else MUTED,
                  'bold' if is_hi else 'sans', 'right')
        w_ask = label(ax + 1.2, ag_y + 4.75, aask, 5.15, ACC_DK, 'bold')
        label(ax + 1.2 + w_ask + (.6 if en else 0), ag_y + 4.75, aq, 5.15, INK,
              width=aw - 2.1 - w_ask)
        label(ax + 1.2, ag_y + 7.0, anote, 4.65, acol, width=aw - 2.0)

    dots_cx = (45.2 + 38.0 + 88.8) / 2
    for k in (-1, 0, 1):
        s.circle(dots_cx + 1.25 * k, ag_y + ag_h / 2, .32, '#8A919A')

    # =========================================================================
    # 2. Middle Band: MAVRA Shared Layer Container (4 Core Components)
    # =========================================================================
    my, mh = 12.8, 59.8
    rect(1.2, my, W - 2.4, mh, CONTAINER_BG, CONTAINER_EDGE, .22, r=1.15)
    rect(2.5, my + .75, .62, 1.85, ACC_DK)
    label(3.75, my + 1.68, 'MAVRA', TITLE + .15, ACC_DK, 'bold')

    # -------------------------------------------------------------------------
    # (A) Component 1 (Top-Left): KNOWLEDGE EXTRACTOR (Steps 1-2)
    # -------------------------------------------------------------------------
    EXT = (2.4, 15.8, 39.8, 37.2)
    px, py, pw, ph = EXT
    card_head(EXT, 'Knowledge Extractor' if en else '知识抽取器',
              'off-path' if en else '非关键路径',
              HEAD_BAND, CARD_EDGE, INK, LEARN_DK, bh=3.2)

    # Step 1 arrow: Agent 1 -> Knowledge Extractor
    a1_x = px + 20.4
    route([(a1_x, ag_y + ag_h), (a1_x, py)], LEARN, THIN, length=.9)
    step_badge(a1_x + 2.6, 14.15, 1, LEARN, r=1.32)

    lx, lw = px + 1.05, pw - 2.1
    mid_px = px + pw / 2

    # Card P1: Agent 1 Exploration Trace
    ly, lh = py + 3.75, 10.1
    rect(lx, ly, lw, lh, '#F9FAFB', SUB_EDGE, .15, r=.45)
    rect(lx + .1, ly + .1, lw - .2, 2.15, TOP, None, r=.35)
    rect(lx + .1, ly + 1.1, lw - .2, 1.15, TOP, None)
    label(lx + .85, ly + 1.15, 'Agent 1 exploration trace' if en else '智能体 1 探索轨迹', 4.65, INK, 'bold')
    w_ds0 = measure('source', 4.15, 'bold') + 2 * .6
    pill(lx + lw - .75 - w_ds0, ly + 1.15,
         'source', LEARN, WHITE, size=4.15, pad=.6, h=1.44)

    p1_rows = (
        ('Q', LEARN_PALE, LEARN_DK,
         '"Jan. 2026 electronics rev.?"' if en else '"2026年1月电子品类营业额？"'),
        ('SQL', TOP, INK,
         "`SUM(net_paid) ... 2026-01`"),
        ('Log', ACC_PALE, ACC_DK,
         'probes + answer `2,754,299.60`' if en else '探查与原答案 `2,754,299.60`'),
    )
    for idx_r, (rtag, rbg, rfg, rtxt) in enumerate(p1_rows):
        ry = ly + 3.45 + idx_r * 2.48
        tw_p = pill(lx + .75, ry, rtag, rbg, rfg, edge_c=rfg, size=4.1, pad=.54, h=1.5)
        label(lx + 1.2 + tw_p, ry, rtxt, 4.5, INK,
              width=lw - tw_p - (3.5 if idx_r == 2 else 1.6))
        if idx_r == 2:
            check_mark(lx + lw - 1.25, ry, True, ACC, k=.72)

    route([(mid_px, ly + lh), (mid_px, ly + lh + .75)], LEARN, .19, length=.55)

    # Card P2: Query Extraction + Condition Derivation
    ex_y, ex_h = ly + lh + .75, 8.75
    rect(lx, ex_y, lw, ex_h, WHITE, SUB_EDGE, .15, r=.45)
    label(lx + .85, ex_y + 1.45,
          '1. Extract query & checks' if en else '1. 抽取查询与检查', 4.8, INK, 'bold')
    label(lx + lw - .8, ex_y + 1.45,
          'AST + probes + catalog' if en else '语法树、探针与目录',
          4.2, MUTED, 'sans', 'right')

    # Row A: Fixed Core (B, I) chip vs Parameterized bindings beta_0
    r2a_y = ex_y + 4.1
    c_core_w = 25.4
    rect(lx + .75, r2a_y - 1.05, c_core_w, 2.1, LEARN_PALE, LEARN, .14, r=.32)
    label(lx + .75 + c_core_w / 2, r2a_y,
          'Scope, joins, and aggregate' if en
          else '范围、连接与聚合',
          4.1, LEARN_DK, 'bold', 'center')
    rx_slot = lx + 1.15 + c_core_w
    sw_slot = lw - (rx_slot - lx) - .75
    rect(rx_slot, r2a_y - 1.05, sw_slot, 2.1, WHITE, LEARN, .14, r=.32, dash=(.52, .30))
    label(rx_slot + sw_slot / 2, r2a_y,
          'period' if en else '期间', 4.1, LEARN_DK, 'bold', 'center')

    # Row B: Derived executable conditions C(m^0)
    r2b_y = ex_y + 7.1
    s.line(lx + .75, ex_y + 5.7, lx + lw - .75, ex_y + 5.7, RULE, .12)
    key_icon(lx + .8, r2b_y, ACC_DK)
    label(lx + 2.9, r2b_y, 'unique key' if en else '键唯一', 4.2, INK)
    join_icon(lx + 11.4, r2b_y, ACC_DK)
    label(lx + 13.55, r2b_y, 'join loss bound' if en else '连接损失上界', 4.15, INK)
    dom_icon(lx + 26.6, r2b_y, MAINT_C)
    label(lx + 28.65, r2b_y, 'null / scale' if en else '空值/量纲', 4.2, INK)

    route([(mid_px, ex_y + ex_h), (mid_px, ex_y + ex_h + .75)], LEARN, .19, length=.55)

    # Card P3: Candidate Validation & SQL Recompilation Check
    vy, vh = ex_y + ex_h + .75, 8.15
    rect(lx, vy, lw, vh, WHITE, SUB_EDGE, .15, r=.45)
    label(lx + .85, vy + 1.45,
          '2. Candidate Validation' if en else '2. 候选验证与重编译', 4.8, INK, 'bold')
    label(lx + lw - .8, vy + 1.45,
          '3 admission gates' if en else '3 道准入门控', 4.25, ACC_DK, 'bold', 'right')

    g1_y = vy + 4.05
    w_g15 = pill(lx + .75, g1_y, '1–2', TOP, INK, edge_c=SUB_EDGE, size=4.05, pad=.46, h=1.48)
    label(lx + 1.2 + w_g15, g1_y,
          'Source and structure-parameter checks' if en else '来源检查、结构与参数检查',
          4.35, INK, width=lw - w_g15 - 3.6)
    check_mark(lx + lw - 1.25, g1_y, True, ACC, k=.70)

    g2_y = vy + 6.5
    w_g67 = pill(lx + .75, g2_y, '3', ACC_PALE, ACC_DK, edge_c=ACC, size=4.05, pad=.46, h=1.48)
    label(lx + 1.15 + w_g67, g2_y, 'Recompilation check' if en else '重编译检查', 4.15, ACC_DK, 'bold')
    check_mark(lx + 22.8, g2_y, True, ACC, k=.64)
    drop_txt = 'no filter: $4.9\\times$' if en else '漏过滤：$4.9\\times$'
    drop_w = measure(drop_txt, 3.85, 'bold') + 2.85
    drop_x = lx + lw - .75 - drop_w
    rect(drop_x, g2_y - .74, drop_w, 1.48, RED_PALE, RED_EDGE, .13, r=.32)
    label(drop_x + .55, g2_y, drop_txt, 3.85, RED, 'bold')
    check_mark(drop_x + drop_w - .9, g2_y, False, RED, k=.52)

    route([(mid_px, vy + vh), (mid_px, vy + vh + .7)], LEARN, .19, length=.52)

    # Card P4: Output Executable Definition m^0
    oy, oh = vy + vh + .7, 3.55
    rect(lx, oy, lw, oh, LEARN_PALE, LEARN_EDGE, .17, r=.42)
    w_out = pill(lx + .65, oy + oh / 2, 'out' if en else '输出', LEARN_DK, WHITE, size=4.05, pad=.45, h=1.55)
    w_m0 = label(lx + .65 + w_out + .48, oy + oh / 2, 'rev 0', 4.65, LEARN_DK, 'bold')
    bx_cur = lx + .65 + w_out + .48 + w_m0 + .42
    for f_txt, f_col in (('scope' if en else '范围', LEARN_DK),
                         ('core' if en else '查询', ACC_DK),
                         ('checks' if en else '检查', MAINT_DK),
                         ('evidence' if en else '证据', SLATE)):
        bx_cur += pill(bx_cur, oy + oh / 2, f_txt, WHITE, f_col, edge_c=f_col, size=3.85, pad=.34, h=1.55) + .26
    assert bx_cur - .26 <= lx + lw - .4, (bx_cur - .26, lx + lw)

    # -------------------------------------------------------------------------
    # (B) Component 2 (Top-Center + Top-Right): KNOWLEDGE CACHE (Graph + Lookup)
    # -------------------------------------------------------------------------
    KC = (45.4, 15.8, 128.8, 37.2)
    kx, ky, kw, kh = KC
    box(KC, WHITE, ACC, .22, r=.65)
    rect(kx, ky, kw, 3.2, ACC_DK, None, r=.65)
    rect(kx, ky + 1.6, kw, 1.6, ACC_DK, None)
    tw_kb = label(kx + 1.35, ky + 1.6, 'Knowledge Cache' if en else '共享知识缓存', TITLE, WHITE, 'bold')
    label(kx + kw - 1.25, ky + 1.6,
          'dependency graph · versioned check results · semantic lookup index' if en
          else '依赖图 · 按版本缓存的检查结果 · 语义查找索引',
          4.7, '#DCE4F0', 'sans', 'right', width=kw - tw_kb - 2.8)

    # Step 2 thick arrow: Knowledge Extractor -> Knowledge Cache (publish m^0)
    step2_y = oy + oh / 2
    route([(px + pw, step2_y), (kx, step2_y)], LEARN, THICK, length=.85)
    step_badge((px + pw + kx) / 2, step2_y - 2.35, 2, LEARN, r=1.22)

    # Request bus from Agents 2, N, P -> Knowledge Cache (Step 3: lookup(rho))
    bus_y = 11.35
    c_a2 = 45.2 + 38.0 / 2
    c_an = 88.8 + 38.4 / 2
    c_ap = 132.4 + 18.0
    req_x = 150.4
    s.line(c_a2, bus_y, c_ap, bus_y, ACC, .24)
    for cx_ag in (c_a2, c_an, c_ap):
        s.line(cx_ag, ag_y + ag_h, cx_ag, bus_y, ACC, .22)
    route([(req_x, bus_y), (req_x, ky)], ACC, THIN, length=.9)
    step_badge(req_x - 2.6, 14.15, 3, ACC, r=1.32)
    label(req_x + 1.15, 14.25, 'lookup' if en else '查找', 5.15, ACC_DK, 'bold')

    # --- Sub-panel 1 (Left inside KC): Graph Catalog M ---
    dx, dy, dw, dh = kx + 1.1, ky + 3.75, 42.6, kh - 4.45
    label(dx + .12, dy + .88, 'Definition catalog' if en else '定义目录', BODY - .2, ACC_DK, 'bold')
    label(dx + dw - .12, dy + .88, 'versioned entries', 4.65, MUTED, 'sans', 'right')

    cat_y, cat_h = dy + 1.95, 11.45
    rect(dx, cat_y, dw, cat_h, FACE, SUB_EDGE, .15, r=.42)
    cat_entries = (
        ('`join:item|sales`', 'r0 $\\rightarrow$ r1', 'join'),
        ('`metric:Store revenue`', 'D01: after coupons' if en else 'D01: 扣券实付', 'hom'),
        ('`metric:Store revenue`', 'D02: before coupons' if en else 'D02: 券前总额', 'hom'),
        ('`metric:Return rate`', 'returns / sales' if en else '退货率指标', 'met'),
        ('`feature:cust:spend_90d`', 'customer, last 90 days' if en else '客户及过去 90 天', 'feat'),
    )
    cat_ys = []
    for idx_c, (ckey, cmeta, ckind) in enumerate(cat_entries):
        ry = cat_y + 1.25 + idx_c * 2.24
        if idx_c % 2 == 1:
            rect(dx + .24, ry - 1.04, dw - .48, 2.08, WHITE, None, r=.18)
        label(dx + .8, ry, ckey, 4.55, INK, width=dw - 17.0)
        if ckind == 'join':
            mini_step(dx + dw - 1.25, ry, 6, MAINT_C, r=.70)
            label(dx + dw - 2.15, ry, '$\\rightarrow$r1', 4.25, MAINT_DK, 'bold', 'right')
            mini_step(dx + dw - 6.05, ry, 2, LEARN, r=.70)
            label(dx + dw - 6.95, ry, 'r0', 4.25, LEARN_DK, 'bold', 'right')
        else:
            col_m = ACC_DK if ckind == 'hom' else (EXEC_DK if ckind == 'feat' else MUTED)
            label(dx + dw - .8, ry, cmeta, 4.25, col_m,
                  'bold' if ckind in ('hom', 'feat') else 'sans', 'right')
        cat_ys.append(ry)

    # Expanded Definition Tuple Anatomy: metric:Electronics revenue
    mx, my_card = dx, cat_y + cat_h + .78
    mw_card, mh_card = dw, dy + dh - my_card
    rect(mx, my_card, mw_card, mh_card, WHITE, NAVY_EDGE, .18, r=.44)
    rect(mx + .12, my_card + .12, mw_card - .24, 2.45, ACC_PALE, None, r=.34)
    label(mx + .8, my_card + 1.32, '`metric:Electronics revenue`', 4.75, INK, 'bold')
    mini_step(mx + mw_card - 1.2, my_card + 1.32, 6, MAINT_C, r=.74)
    label(mx + mw_card - 2.2, my_card + 1.32, '$\\rightarrow$1', 4.4, MAINT_DK, 'bold', 'right')
    mini_step(mx + mw_card - 6.45, my_card + 1.32, 2, LEARN, r=.74)
    label(mx + mw_card - 7.45, my_card + 1.32, 'rev 0', 4.4, LEARN_DK, 'bold', 'right')

    # Band B
    b_yc = my_card + 3.9
    pill(mx + .75, b_yc, 'Scope', LEARN_PALE, LEARN_DK, edge_c=LEARN, size=4.15, pad=.52, h=1.55)
    label(mx + 7.4, b_yc,
          'revenue · store · Electronics · net paid · sale date' if en
          else '营收 · 门店 · 电子品类 · 实付净额 · 销售日期',
          4.45, INK, width=mw_card - 8.1)
    s.line(mx + .65, my_card + 5.15, mx + mw_card - .65, my_card + 5.15, RULE, .12)

    # Band I
    i_y1 = my_card + 6.45
    i_y2 = my_card + 8.55
    i_y3 = my_card + 10.65
    pill(mx + .75, i_y1, 'Core', ACC_PALE, ACC_DK, edge_c=ACC, size=4.15, pad=.60, h=1.55)
    label(mx + 7.4, i_y1,
          '`sales` · `SUM(net_paid)` · sale date' if en
          else '`sales` · `SUM(net_paid)` · 销售日期',
          4.45, INK, width=mw_card - 8.1)
    label(mx + 7.4, i_y2,
          'joins `join:item|sales` + `date`' if en
          else '引用 `join:item|sales` + `date`',
          4.4, ACC_DK, width=mw_card - 8.1)
    label(mx + 7.4, i_y3,
          "fixed `category='Electronics'`" if en
          else "固定 `category='Electronics'`",
          4.4, INK, width=mw_card - 8.1)
    s.line(mx + .65, my_card + 11.9, mx + mw_card - .65, my_card + 11.9, RULE, .12)

    # Band C
    c_yc = my_card + 13.35
    pill(mx + .75, c_yc, 'Checks', MAINT_PALE, MAINT_DK, edge_c=MAINT_C, size=4.15, pad=.52, h=1.55)
    key_icon(mx + 8.0, c_yc, ACC_DK)
    label(mx + 10.2, c_yc, '$\\times 3$', 4.25, INK)
    join_icon(mx + 13.1, c_yc, ACC_DK)
    label(mx + 15.3, c_yc, '$\\times 2$', 4.25, INK)
    dom_icon(mx + 18.2, c_yc, MAINT_C)
    label(mx + 20.4, c_yc, '$\\times 1$', 4.25, INK)
    label(mx + 24.0, c_yc,
          'shared' if en else '共享',
          4.35, MAINT_DK, 'bold', width=mw_card - 24.7)
    s.line(mx + .65, my_card + 14.75, mx + mw_card - .65, my_card + 14.75, RULE, .12)

    # Band E
    e_yc = my_card + 16.4
    pill(mx + .75, e_yc, 'Source', TOP, SLATE, edge_c=SLATE, size=4.15, pad=.54, h=1.55)
    label(mx + 7.4, e_yc,
          '2.75M, bucket digests, versions' if en
          else '2.75M、摘要、版本',
          4.35, SLATE, width=mw_card - 8.1)

    # --- Sub-panel 2 (Middle inside KC): Condition Nodes H & Check Cache Gamma ---
    hx = dx + dw + 2.5
    hy, hw, hh = dy, 38.6, dh
    label(hx + .12, hy + .88, 'Shared checks' if en else '共享检查', BODY - .2, ACC_DK, 'bold')
    label(hx + hw - .12, hy + .88, 'by table version', 4.5, MUTED, 'sans', 'right')

    hc_y, hc_h = hy + 1.95, hh - 1.95
    rect(hx, hc_y, hw, hc_h, NAVY_SOFT, NAVY_EDGE, .17, r=.44)
    rect(hx + .12, hc_y + .12, hw - .24, 2.2, '#E9EEF5', None, r=.34)
    label(hx + .85, hc_y + 1.2, 'Condition' if en else '检查条件', 4.25, ACC_DK, 'bold')
    label(hx + 23.0, hc_y + 1.2, 'Shared' if en else '共享', 4.25, ACC_DK, 'bold', 'center')
    label(hx + hw - .85, hc_y + 1.2, 'Cached result' if en else '缓存结果', 4.25, ACC_DK, 'bold', 'right')

    h_rows = (
        ('key', 'sales grain', 4, '@v0', True, None),
        ('key', '`date.date_id`', 4, '@v0', True, None),
        ('join', '`sales` $\\rightarrow$ `date`', 3, '@v0', True, None),
        ('join', '`sales` $\\rightarrow$ `item`', 2, '@v0,1', True, None),
        ('dom', '`Null(category)`', 1, '@v0,1', True, None),
        ('key', '`item.item_id`', 2, '@v0', True, None),
        ('key', '`item.item_id` (dup `17`)', 0, '@v1', False, 6),
        ('key', "`item.item_id` (`'Y'`)", 0, '@v1', True, 6),
    )
    h_ys = []
    for idx_h, (hkind, htxt, nshare, hver, hok, hstep) in enumerate(h_rows):
        ry = hc_y + 3.6 + idx_h * 3.12
        if hstep == 6 and not hok:
            rect(hx + .5, ry - 1.34, hw - 1.0, 2.68, RED_PALE, RED_EDGE, .13, r=.28)
        elif hstep == 6 and hok:
            rect(hx + .5, ry - 1.34, hw - 1.0, 2.68, MAINT_PALE, MAINT_EDGE, .13, r=.28)
        elif idx_h % 2 == 1:
            rect(hx + .5, ry - 1.34, hw - 1.0, 2.68, WHITE, None, r=.22)

        ic_x = hx + .9
        if hkind == 'key':
            key_icon(ic_x, ry, (MAINT_DK if hstep == 6 else ACC_DK) if hok else RED)
        elif hkind == 'join':
            join_icon(ic_x, ry, ACC_DK)
        else:
            dom_icon(ic_x, ry, MAINT_C)

        label(hx + 3.05, ry, htxt, 4.15, INK if hok else RED,
              'bold' if hstep == 6 else 'sans', width=18.2 if nshare > 0 else 22.0)
        if nshare > 0:
            share_dots(hx + 21.85, ry, min(nshare, 3), ACC)
        if hstep == 6:
            label(hx + hw - 5.1, ry, hver, 4.25, MAINT_DK if hok else RED, 'bold', 'right')
            check_mark(hx + hw - 3.65, ry, hok, MAINT_DK if hok else RED, k=.64)
            mini_step(hx + hw - 1.55, ry, hstep, MAINT_C, r=.72)
        else:
            label(hx + hw - 3.15, ry, hver, 4.25, MUTED, 'sans', 'right')
            check_mark(hx + hw - 1.55, ry, True, ACC, k=.64)
        h_ys.append(ry)

    sf_y = hc_y + hc_h - 1.4
    s.line(hx + .75, sf_y - 1.2, hx + hw - .75, sf_y - 1.2, RULE, .12)
    label(hx + hw / 2, sf_y,
          'coalesced graph eval · shared across defs' if en
          else '合并图校验 · 一次重算跨定义复用',
          4.2, ACC_DK, 'bold', 'center')

    # Orthogonal reference wires inside Knowledge Cache (M <-> H and KB -> Extractor)
    ch_x1 = dx + dw + .78
    ch_x2 = dx + dw + 1.65
    # 0) join:item|sales -> Extractor P2 grounding reuse (via gutter x=43.8)
    route([(dx, cat_ys[0]), (43.8, cat_ys[0]), (43.8, ex_y + 1.45), (px + pw, ex_y + 1.45)],
          ACC, .20, dash=(.55, .32), length=.64, radius=.30)
    # 1) Band I joins -> catalog join:item|sales
    route([(mx + mw_card, i_y2), (ch_x1, i_y2), (ch_x1, cat_ys[0]), (dx + dw, cat_ys[0])],
          REF, .17, length=.54, radius=.30)
    # 2) Store revenue -> date.date_id @v0
    route([(dx + dw, cat_ys[1]), (ch_x2, cat_ys[1]), (ch_x2, h_ys[1]), (hx + .5, h_ys[1])],
          REF, .17, length=.54, radius=.30)
    # 3) Band C -> item.item_id @v0
    route([(mx + mw_card, c_yc), (ch_x2, c_yc), (ch_x2, h_ys[5]), (hx + .5, h_ys[5])],
          REF, .17, length=.54, radius=.30)

    # --- Sub-panel 3 (Right inside KC): Semantic Lookup Index ---
    sx = hx + hw + 2.2
    sy_l, sw_l, sh_l = dy, kx + kw - 1.1 - sx, dh
    label(sx + .12, sy_l + .88, 'Semantic lookup index' if en else '语义查找索引', BODY - .2, ACC_DK, 'bold')
    label(sx + sw_l - .12, sy_l + .88, 'no SQL · no LLM scan' if en else '不生 SQL · 免扫目录',
          4.35, MUTED, 'sans', 'right')

    sc_y_l, sc_h_l = sy_l + 1.95, sh_l - 1.95
    rect(sx, sc_y_l, sw_l, sc_h_l, NAVY_SOFT, NAVY_EDGE, .17, r=.44)

    # Top row inside Semantic Lookup: (1) Alias & Dense Recall -> (2) Scorer x3
    t_y, t_h = sc_y_l + 1.0, 12.1
    t1_x, t1_w = sx + .95, 18.6
    t2_x, t2_w = t1_x + t1_w + 1.5, sw_l - 1.9 - t1_w - 1.5

    # Module 1: Alias Hash + bge-m3 Vector Neighborhood + Top-K Grid
    rect(t1_x, t_y, t1_w, t_h, WHITE, SUB_EDGE, .15, r=.42)
    label(t1_x + t1_w / 2, t_y + 1.45, '1. Alias & Recall' if en else '1. 别名与召回',
          4.9, ACC_DK, 'bold', 'center')
    vcx, vcy = t1_x + 4.1, t_y + 6.3
    s.circle(vcx, vcy, 2.65, WHITE, NAVY_EDGE, .15)
    s.circle(vcx, vcy, 1.72, ACC_PALE, NAVY_EDGE, .12)
    s.circle(vcx - .15, vcy, .40, EXEC_C)
    for dx_v, dy_v, col_v in ((-.82, -.66, ACC), (.80, -.56, ACC), (.56, .74, ACC),
                              (-1.75, 1.18, '#B0BAC6'), (1.82, .25, '#B0BAC6')):
        s.circle(vcx + dx_v, vcy + dy_v, .26, col_v)
    label(vcx, t_y + 10.65, '`bge-m3`', 4.15, MUTED, 'sans', 'center')

    gx = t1_x + 7.75
    pill(gx, t_y + 3.9, 'alias $O(1)$' if en else '别名直达', WHITE, ACC_DK, edge_c=ACC, size=4.25, pad=.40, h=1.62)
    cand_tags = (('D01', True), ('D02', True), ('ER', True), ('top8', False))
    for idx_g, (ctag, chi) in enumerate(cand_tags):
        col_i, row_i = idx_g % 2, idx_g // 2
        cx_g = gx + col_i * 5.05
        cy_g = t_y + 5.75 + row_i * 2.25
        rect(cx_g, cy_g, 4.72, 1.88, ACC_PALE if chi else WHITE, ACC if chi else SUB_EDGE, .13, r=.24)
        label(cx_g + 2.36, cy_g + .94, ctag, 4.3, ACC_DK if chi else MUTED, 'bold' if chi else 'sans', 'center')

    route([(t1_x + t1_w, t_y + t_h / 2), (t2_x, t_y + t_h / 2)], ACC, .21, length=.62)

    # Module 2: Cross-Encoder Scorer x3
    rect(t2_x, t_y, t2_w, t_h, WHITE, SUB_EDGE, .15, r=.42)
    label(t2_x + t2_w / 2, t_y + 1.45, '2. Scorer $\\times 3$' if en else '2. 打分器 $\\times 3$',
          4.9, ACC_DK, 'bold', 'center')
    tok_y = t_y + 4.05
    tok_raw = (('request', ACC, WHITE), ('attrs', LEARN_PALE, LEARN_DK), ('diffs', AMBER_PALE, EXEC_DK))
    tok_specs = [(lbl, bg, fg, max(3.4, measure(lbl, 4.35, 'bold') + .82)) for lbl, bg, fg in tok_raw]
    tot_tok_w = sum(tw_i for _, _, _, tw_i in tok_specs) + .36 * (len(tok_specs) - 1)
    tx_cur = t2_x + (t2_w - tot_tok_w) / 2
    tok_centers = []
    for t_lbl, t_bg, t_fg, t_w in tok_specs:
        rect(tx_cur, tok_y - .85, t_w, 1.7, t_bg, t_fg if t_bg != ACC else ACC_DK, .12, r=.24)
        label(tx_cur + t_w / 2, tok_y, t_lbl, 4.35, t_fg, 'bold', 'center')
        tok_centers.append(tx_cur + t_w / 2)
        tx_cur += t_w + .36
    att_y = t_y + 7.25
    for st_off in (.48, .24, 0.0):
        rect(t2_x + 1.0 + st_off, att_y - 1.05 - st_off * .38, t2_w - 2.45, 2.05, WHITE, ACC, .13, r=.26)
    for tc_x in tok_centers:
        s.line(tc_x, tok_y + .85, tc_x, att_y - 1.38, NAVY_EDGE, .13)
    label(t2_x + t2_w / 2, att_y, 'XLM-R $\\times 3$ score' if en else '交叉编码 $\\times 3$ 打分',
          4.45, INK, 'bold', 'center')
    label(t2_x + t2_w / 2, t_y + 10.65,
          'rule-labeled synthetic data' if en else '规则打标合成数据',
          3.95, LEARN_DK, 'bold', 'center', width=t2_w - .8)

    # Middle row inside Semantic Lookup: Calibrated Decision Spectrum (.1, .9)
    sp_y = t_y + t_h + 2.35
    label(sx + 1.0, sp_y, 'score:' if en else '得分:', 4.35, INK, 'bold')
    bar_lx, bar_lw, bar_lh = sx + 5.45, sw_l - 6.45, 2.2
    w_miss = bar_lw * .17
    w_ref = bar_lw * .45
    w_hit = bar_lw - w_miss - w_ref
    rect(bar_lx, sp_y - bar_lh / 2, w_miss, bar_lh, '#DFE3E8', None, r=.25)
    rect(bar_lx + w_miss, sp_y - bar_lh / 2, w_ref, bar_lh, AMBER_PALE, None)
    rect(bar_lx + w_miss + w_ref, sp_y - bar_lh / 2, w_hit, bar_lh, ACC, None, r=.25)
    rect(bar_lx, sp_y - bar_lh / 2, bar_lw, bar_lh, None, SUB_EDGE, .14, r=.25)
    s.line(bar_lx + w_miss, sp_y - bar_lh / 2 - .22, bar_lx + w_miss, sp_y + bar_lh / 2 + .22, INK, .18)
    s.line(bar_lx + w_miss + w_ref, sp_y - bar_lh / 2 - .22, bar_lx + w_miss + w_ref, sp_y + bar_lh / 2 + .22, INK, .18)
    label(bar_lx + w_miss / 2, sp_y, '<.1', 4.3, MUTED, 'bold', 'center')
    label(bar_lx + w_miss + w_ref / 2, sp_y,
          '.1   Refer   .9' if en else '.1   候选消歧   .9', 4.3, EXEC_DK, 'bold', 'center')
    x_ge = bar_lx + w_miss + w_ref
    label(x_ge + w_hit * .5, sp_y, '$\\geq$.9 (1 | >1)', 4.05, WHITE, 'bold', 'center')

    # Bottom row inside Semantic Lookup: 2-Way Dispatch (Hit vs Diffs/Refer/Miss)
    dec_y, dec_h = sp_y + 3.45, 5.2
    b1_x, b1_w = sx + .95, 18.6
    b2_x, b2_w = b1_x + b1_w + 1.35, sw_l - 1.9 - b1_w - 1.35
    hit1_x = x_ge + w_hit * .28
    hitn_x = x_ge + w_hit * .76
    miss_drop_x = b2_x + 1.8
    ref_x = x_ge - 1.25
    route([(hit1_x, sp_y + bar_lh / 2),
           (hit1_x, dec_y - 1.05),
           (b1_x + b1_w / 2, dec_y - 1.05),
           (b1_x + b1_w / 2, dec_y)], ACC, .19, length=.52, radius=.24)
    route([(bar_lx + w_miss / 2, sp_y + bar_lh / 2),
           (bar_lx + w_miss / 2, sp_y + bar_lh / 2 + .65),
           (miss_drop_x, sp_y + bar_lh / 2 + .65),
           (miss_drop_x, dec_y)], SLATE, .16, dash=(.38, .28), length=.48, radius=.18)
    route([(ref_x, sp_y + bar_lh / 2),
           (ref_x, dec_y)], AMBER, .19, length=.52)
    route([(hitn_x, sp_y + bar_lh / 2),
           (hitn_x, dec_y)], AMBER, .19, length=.52)

    rect(b1_x, dec_y, b1_w, dec_h, ACC_PALE, ACC, .18, r=.42)
    label(b1_x + b1_w / 2, dec_y + 1.85, 'Hit (one definition)' if en else '命中一个定义',
          5.0, ACC_DK, 'bold', 'center')
    label(b1_x + b1_w / 2, dec_y + 3.9, 'to Query Executor' if en else '交查询执行器',
          4.55, ACC_DK, 'sans', 'center')

    rect(b2_x, dec_y, b2_w, dec_h, AMBER_PALE, AMBER, .16, r=.42)
    label(b2_x + b2_w / 2, dec_y + 1.85, 'Diffs / Refer / Miss' if en else '差异 / 参考 / 未中',
          4.85, EXEC_DK, 'bold', 'center')
    label(b2_x + b2_w / 2, dec_y + 3.9, 'resolve$\\rightarrow$alias | explore' if en else '消歧写别名 / 探索',
          4.4, MUTED, 'sans', 'center')

    # Ambiguous/Miss dashed return lane (lane 1: x = 175.15 up to agent request bus)
    ret_amb_x = 175.15
    route([(b2_x + b2_w, dec_y + dec_h / 2), (ret_amb_x, dec_y + dec_h / 2),
           (ret_amb_x, bus_y), (c_ap, bus_y)],
          AMBER, .2, heads='end', dash=(.55, .35), length=.72, radius=.35)

    # -------------------------------------------------------------------------
    # (C) Component 3 (Bottom-Left): MAINTENANCE MANAGER (Steps 5-6)
    # -------------------------------------------------------------------------
    MAINT = (2.4, 55.8, 100.4, 16.0)
    qx, qy, qw, qh = MAINT
    tw_mm = card_head(MAINT, 'Maintenance Manager' if en else '维护管理器',
                      'write or failed check · follow dependencies' if en
                      else '写入或检查失败 · 按依赖关系维护',
                      HEAD_BAND, CARD_EDGE, INK, MAINT_DK, bh=3.15)
    mini_step(qx + 1.15 + tw_mm + 1.35, qy + .12 + 3.15 / 2, 5, MAINT_C, r=.74)

    sc_y, sc_h = qy + 3.85, qh - 4.65
    s1_x, s1_w = qx + 1.0, 31.6
    s2_x, s2_w = s1_x + s1_w + 1.4, 30.8
    s3_x, s3_w = s2_x + s2_w + 1.4, qw - (1.0 + 31.6 + 1.4 + 30.8 + 1.4) - 1.0

    def maint_card_head(cx, cw, num, title_s, border_c=SUB_EDGE, bg_c=WHITE, head_c=TOP):
        rect(cx, sc_y, cw, sc_h, bg_c, border_c, .16, r=.42)
        rect(cx + .1, sc_y + .1, cw - .2, 2.35, head_c, None, r=.32)
        pill(cx + .65, sc_y + 1.25, str(num), MAINT_C, WHITE, size=4.25, pad=.44, h=1.44)
        label(cx + 2.95, sc_y + 1.25, title_s, 4.7, INK, 'bold', width=cw - 3.45)

    r1_y = sc_y + 5.15
    r2_y = sc_y + 8.85

    # Stage 1: Prune by Table Versions
    maint_card_head(s1_x, s1_w, 1,
                    'Prune by Table Versions' if en else '按表版本剪枝定位')
    s1_t1, s1_t2, s1_t3 = '`sales` v0', '`date` v0', '`item` v0$\\rightarrow$v1'
    s1_w1 = measure(s1_t1, 3.8, 'sans') + .72
    s1_w2 = measure(s1_t2, 3.8, 'sans') + .72
    s1_w3 = measure(s1_t3, 3.8, 'bold') + .78
    s1_start = s1_x + (s1_w - (s1_w1 + s1_w2 + s1_w3 + 1.0)) / 2
    x_cur1 = s1_start
    x_cur1 += pill(x_cur1, r1_y, s1_t1, FACE, MUTED, edge_c=SUB_EDGE, size=3.8, pad=.36, h=1.72, wt='sans') + .5
    x_cur1 += pill(x_cur1, r1_y, s1_t2, FACE, MUTED, edge_c=SUB_EDGE, size=3.8, pad=.36, h=1.72, wt='sans') + .5
    pill(x_cur1, r1_y, s1_t3, AMBER_PALE, EXEC_DK, edge_c=AMBER, size=3.8, pad=.39, h=1.72)
    label(s1_x + s1_w / 2, r2_y,
          'only `item` changed · recheck dependents' if en else '仅 `item` 变更 · 核验依赖项',
          4.25, MAINT_DK, 'bold', 'center', width=s1_w - 1.2)

    route([(s1_x + s1_w, sc_y + sc_h / 2), (s2_x, sc_y + sc_h / 2)], MAINT_C, .23, length=.62)

    # Stage 2: Coalesced Node Check Q_c
    maint_card_head(s2_x, s2_w, 2,
                    'Shared check' if en else '共享检查')
    w_dt = pill(s2_x + .65, r1_y, "`KeyUnique(item)`", AMBER_PALE, EXEC_DK, edge_c=AMBER, size=3.8, pad=.34, h=1.72)
    dup_lbl = 'dup `item_id=17`' if en else '键 `17` 重复'
    dup_w = measure(dup_lbl, 3.85, 'bold') + 2.35
    dup_x = s2_x + s2_w - .65 - dup_w
    rect(dup_x, r1_y - .86, dup_w, 1.72, RED_PALE, RED, .14, r=.32)
    label(dup_x + .45, r1_y, dup_lbl, 3.85, RED, 'bold')
    check_mark(dup_x + dup_w - .85, r1_y, False, RED, k=.52)
    route([(s2_x + .65 + w_dt + .14, r1_y), (dup_x - .14, r1_y)], RED, .19, length=.46)
    label(s2_x + s2_w / 2, r2_y,
          'one shared hash-aggregate check' if en else '一次共享哈希聚合检查',
          4.25, MUTED, 'sans', 'center', width=s2_w - 1.2)

    route([(s2_x + s2_w, sc_y + sc_h / 2), (s3_x, sc_y + sc_h / 2)], MAINT_C, .23, length=.62)

    # Stage 3: Certified Repair
    maint_card_head(s3_x, s3_w, 3,
                    'Certified Repair' if en else '可证修复',
                    border_c=MAINT_EDGE, bg_c='#F7FAFA', head_c=MAINT_PALE)
    w_patch = pill(s3_x + .65, r1_y, "`+ is_current='Y'`", WHITE, MAINT_DK, edge_c=MAINT_C, size=3.95, pad=.36, h=1.72)
    rev_lbl = '$\\rightarrow$ `rev 1`'
    ans_lbl = 'Ans' if en else '重放'
    w_ans = measure(ans_lbl, 4.0, 'bold')
    w_rev = measure(rev_lbl, 4.0, 'bold')
    out_w = w_ans + w_rev + 3.0
    out_x = s3_x + s3_w - .65 - out_w
    rect(out_x, r1_y - .86, out_w, 1.72, MAINT_PALE, MAINT_C, .14, r=.32)
    label(out_x + .45, r1_y, ans_lbl, 4.0, MAINT_DK, 'bold')
    check_mark(out_x + .45 + w_ans + .74, r1_y, True, MAINT_C, k=.48)
    label(out_x + out_w - .45, r1_y, rev_lbl, 4.0, MAINT_DK, 'bold', 'right')
    route([(s3_x + .65 + w_patch + .14, r1_y), (out_x - .14, r1_y)], MAINT_C, .19, length=.46)
    label(s3_x + s3_w / 2, r2_y,
          'unique edit · else pending | retire' if en else '唯一局部修复 · 否则挂起／停用',
          4.25, MUTED, 'sans', 'center', width=s3_w - 1.2)

    # Step 6 thick upward arrow: Maintenance Manager Stage 3 -> Knowledge Cache (rev 1)
    s6_x = s3_x + s3_w / 2
    route([(s6_x, qy), (s6_x, ky + kh)], MAINT_C, THICK, length=.82)
    step_badge(s6_x + 2.35, (qy + ky + kh) / 2, 6, MAINT_C, r=1.12)
    label(s6_x - 1.25, (qy + ky + kh) / 2, 'rev 1' if en else '写入 rev 1', 4.45, MAINT_DK, 'bold', 'right')

    # -------------------------------------------------------------------------
    # (D) Component 4 (Bottom-Right): QUERY EXECUTOR (Step 4)
    # -------------------------------------------------------------------------
    EXEC = (105.4, 55.8, 68.8, 16.0)
    ex, ey, ew, eh = EXEC
    card_head(EXEC, 'Query Executor' if en else '查询执行器',
              'snapshot-bound validation' if en else '快照绑定验证',
              HEAD_BAND, CARD_EDGE, INK, EXEC_DK, bh=3.15)

    # Dashed check-cache read arrow: Condition nodes H -> Query Executor (Validate C)
    h_read_x = 119.8
    route([(h_read_x, ky + kh), (h_read_x, ey)], REF, .22, dash=(.56, .34), length=.74)
    label(h_read_x - 1.15, (ey + ky + kh) / 2, 'read cache' if en else '读缓存',
          4.35, REF, 'bold', 'right')

    # Step 4 solid arrow: Knowledge Cache (Hit) -> Query Executor
    hit_cx = b1_x + b1_w / 2
    route([(hit_cx, dec_y + dec_h), (hit_cx, ey)], EXEC_C, THIN, length=.82)
    step_badge(hit_cx + 2.45, (ey + ky + kh) / 2, 4, EXEC_C, r=1.12)

    # Inner dashed container: One Read-Only Snapshot D_s (versions V_s)
    sx_in, sy_in, sw_in, sh_in = ex + .95, ey + 3.7, ew - 1.9, 8.95
    rect(sx_in, sy_in, sw_in, sh_in, '#FAF9F7', EXEC_C, .17, r=.44, dash=(.70, .38))
    label(sx_in + sw_in / 2, sy_in + 1.05,
          'One read-only snapshot with table versions' if en else '同一只读快照与表版本',
          4.65, EXEC_DK, 'bold', 'center')

    # Two horizontal sub-cards inside snapshot D_s
    q_cy, q_ch = sy_in + 2.05, sh_in - 2.65
    q1_x, q1_w = sx_in + .75, 25.4
    q2_x, q2_w = q1_x + q1_w + 1.5, sw_in - 1.5 - q1_w - 1.5

    # Sub-card 1: Validate C and C_req at V_s
    rect(q1_x, q_cy, q1_w, q_ch, WHITE, SUB_EDGE, .14, r=.36)
    label(q1_x + .8, q_cy + 1.15,
          '1. Validate checks' if en else '1. 核验条件', 4.65, INK, 'bold')
    check_mark(q1_x + q1_w - 1.15, q_cy + 1.15, True, ACC, k=.62)
    pill(q1_x + .8, q_cy + 3.05,
         'cached pass: reuse result' if en else '命中：复用结果',
         ACC_PALE, ACC_DK, edge_c=ACC, size=3.95, pad=.38, h=1.52)
    pill(q1_x + .8, q_cy + 5.08,
         'miss: run check query' if en else '未中：执行检查',
         FACE, INK, edge_c=SUB_EDGE, size=3.95, pad=.38, h=1.48, wt='sans')

    route([(q1_x + q1_w, q_cy + q_ch / 2), (q2_x, q_cy + q_ch / 2)], EXEC_C, .21, length=.58)

    # Sub-card 2: Bind & Compile SQL on D_s
    rect(q2_x, q_cy, q2_w, q_ch, WHITE, SUB_EDGE, .14, r=.36)
    label(q2_x + .8, q_cy + 1.15,
          '2. Bind & compile SQL' if en else '2. 绑定参数并编译 SQL', 4.65, INK, 'bold')

    tm_y = q_cy + 2.98
    w_pm = pill(q2_x + .8, tm_y, 'Metric' if en else '指标', ACC_PALE, ACC_DK, edge_c=ACC, size=3.95, pad=.38, h=1.46)
    label(q2_x + 1.2 + w_pm, tm_y,
          'group, aggregate, rank',
          4.15, INK, width=q2_w - w_pm - 2.2)

    tf_y = q_cy + 5.18
    w_pf = pill(q2_x + .8, tf_y, 'Feature' if en else '特征', EXEC_PALE, EXEC_DK, edge_c=EXEC_C, size=3.95, pad=.36, h=1.46)
    label(q2_x + 1.2 + w_pf, tf_y, 'lookback', 4.15, INK, 'bold')
    tl_x1 = q2_x + 19.6
    tl_x2 = q2_x + q2_w - 1.0
    tl_cut = tl_x1 + (tl_x2 - tl_x1) * .68
    s.line(tl_x1, tf_y, tl_x2, tf_y, SUB_EDGE, .16)
    rect(tl_x1 + .75, tf_y - .62, tl_cut - (tl_x1 + .75), 1.24, MAINT_PALE, MAINT_C, .13, r=.2)
    for px_dot in (.28, .58, .84):
        s.circle(tl_x1 + .75 + (tl_cut - tl_x1 - .75) * px_dot, tf_y, .21, MAINT_DK)
    s.line(tl_cut, tf_y - .90, tl_cut, tf_y + .90, EXEC_DK, .25)
    label(tl_cut, tf_y - 1.32, 'cutoff', 3.75, MAINT_DK, 'bold', 'center')
    check_mark(tl_cut + (tl_x2 - tl_cut) * .54, tf_y, False, RED, k=.46)

    # Guarded Answer / Feature Output Bar + Upward Return Arrow (lane 2: x = 176.25)
    ans_y, ans_h = sy_in + sh_in + .5, 2.25
    rect(sx_in, ans_y, sw_in, ans_h, EXEC_PALE, EXEC_C, .17, r=.38)
    check_mark(sx_in + 1.6, ans_y + ans_h / 2, True, EXEC_DK, k=.66)
    label(sx_in + 3.0, ans_y + ans_h / 2,
          'Guarded answer / leak-free features' if en else '返回受保护答案 ／ 防穿越特征表',
          4.65, EXEC_DK, 'bold')

    ret_ans_x = 176.25
    ag_p_right = 132.4 + 41.2
    route([(sx_in + sw_in, ans_y + ans_h / 2), (ret_ans_x, ans_y + ans_h / 2),
           (ret_ans_x, ag_y + ag_h / 2), (ag_p_right, ag_y + ag_h / 2)],
          EXEC_C, .24, heads='end', length=.82, radius=.45)

    # =========================================================================
    # 3. Bottom Band: ETL Job (Step 5) and PostgreSQL Database with Snapshot D_s
    # =========================================================================
    db_y, db_h = 76.6, 12.0
    ETL = (1.6, db_y + .3, 22.0, db_h - .6)
    tx, ty, tw_e, th_e = ETL
    for off in (.85, .42, 0.0):
        rect(tx + off, ty - off, tw_e - .85, th_e, WHITE, '#A6AEB8', .14, r=.45)
    label(tx + 1.15, ty + 2.7, 'ETL job' if en else 'ETL 作业', TITLE, INK, 'bold')
    label(tx + 1.15, ty + 5.85, 'loads `item`' if en else '追加 `item`', 4.75, MAINT_DK, 'bold')
    label(tx + 1.15, ty + 8.7, "history (`17,'N'`)" if en else "历史行 (`17,'N'`)", 4.4, MUTED)

    DB = (28.4, db_y, 146.4, db_h)
    bx, by, bw, bh_d = DB
    d_slab = 1.0
    s.poly([(bx, by), (bx + d_slab, by - d_slab), (bx + bw + d_slab, by - d_slab), (bx + bw, by)],
           '#F3F4F6', '#A6AEB8', .12)
    s.poly([(bx + bw, by), (bx + bw + d_slab, by - d_slab), (bx + bw + d_slab, by + bh_d - d_slab), (bx + bw, by + bh_d)],
           '#E5E8EC', '#A6AEB8', .12)
    rect(bx, by, bw, bh_d, FACE, '#A6AEB8', .18, r=.55)

    # Step 5 arrow: ETL -> Database
    etl_ay = ty + th_e / 2
    route([(tx + tw_e - .85, etl_ay), (bx, etl_ay)], MAINT_C, THICK, length=.9)
    step_badge((tx + tw_e - .85 + bx) / 2, etl_ay - 2.5, 5, MAINT_C, r=1.24)

    # Left DB Header + Transactional Trigger Metadata Chips
    label(bx + 1.3, by + 2.6, 'Database', TITLE, INK, 'bold')
    pill(bx + 1.3, by + 6.0, '`mavra_versions`', WHITE, MAINT_DK, edge_c=MAINT_C, size=4.15, pad=.44, h=1.66, wt='sans')
    pill(bx + 1.3, by + 8.9, '16-shard trigger' if en else '16 分片触发器', WHITE, MAINT_DK, edge_c=MAINT_C, size=4.25, pad=.46, h=1.66, wt='sans')

    ctop, ch_in = by + .85, bh_d - 1.7

    # 1) item table
    ix, iw = bx + 23.2, 44.2
    rect(ix, ctop, iw, ch_in, WHITE, EXEC_EDGE, .18, r=.4)
    rect(ix + .12, ctop + .12, iw - .24, 2.2, AMBER_PALE, None, r=.3)
    label(ix + .85, ctop + 1.2, '`item`', 5.1, INK, 'bold')
    mini_step(ix + iw - 12.7, ctop + 1.2, 5, MAINT_C, r=.74)
    label(ix + iw - .85, ctop + 1.2, 'v0 $\\rightarrow$ v1', 4.75, EXEC_DK, 'bold', 'right')
    label(ix + .85, ctop + 3.55, '`item_id    category      is_current`', 4.15, MUTED)
    s.line(ix + .65, ctop + 4.65, ix + iw - .65, ctop + 4.65, RULE, .12)
    label(ix + .85, ctop + 6.0, "`17         'Electronics' 'Y'`", 4.35, INK)
    label(ix + iw - .85, ctop + 6.0, 'current' if en else '当前行', 4.35, MUTED, 'sans', 'right')
    rect(ix + .45, ctop + 7.3, iw - .9, 2.55, AMBER_PALE, None, r=.24)
    label(ix + .85, ctop + 8.6, "`17         'Electronics' 'N'`", 4.35, INK)
    label(ix + iw - .85, ctop + 8.6, 'new row' if en else '新增历史行', 4.35, EXEC_DK, 'bold', 'right')

    # 2) sales & date tables
    for tx_c, tw_c, tname_c, keys_c, fields_c in (
        (ix + iw + 1.1, 17.5, '`sales`', '`item_id, date_id`', '`net_paid`'),
        (ix + iw + 19.7, 15.2, '`date`', '`date_id`', '`month, year`'),
    ):
        rect(tx_c, ctop, tw_c, ch_in, WHITE, SUB_EDGE, .14, r=.4)
        rect(tx_c + .12, ctop + .12, tw_c - .24, 2.2, TOP, None, r=.3)
        label(tx_c + .7, ctop + 1.2, tname_c, 4.7, INK, 'bold')
        label(tx_c + tw_c - .65, ctop + 1.2, 'v0', 4.3, MUTED, 'sans', 'right')
        label(tx_c + .7, ctop + 3.55, keys_c, 4.05, MUTED, width=tw_c - 1.4)
        label(tx_c + .7, ctop + 5.3, fields_c, 4.05, MUTED, width=tw_c - 1.4)
        for r_i in range(2):
            rect(tx_c + .75, ctop + 6.75 + r_i * 1.7, tw_c - 1.5, .82, '#E1E4E8', None, r=.18)

    # 3) Snapshot D_s aligned directly beneath Query Executor
    sn_x, sn_w = 132.0, 41.8
    rect(sn_x, ctop, sn_w, ch_in, WHITE, None, r=.42)
    rect(sn_x + .12, ctop + .12, sn_w - .24, 2.2, EXEC_PALE, None, r=.32)
    rect(sn_x, ctop, sn_w, ch_in, None, EXEC_C, .2, r=.42, dash=(.78, .42))
    label(sn_x + .9, ctop + 1.2, 'snapshot' if en else '一致性快照', 4.95, EXEC_DK, 'bold')
    label(sn_x + sn_w - .85, ctop + 1.2, 'versioned · read-only' if en else '记录版本 · 只读', 4.3, EXEC_DK, 'sans', 'right')
    slice_names = ('`item`', '`sales`', '`date`')
    mini_w = (sn_w - 2.0 - 1.4) / 3
    for k_m, sl_lbl in enumerate(slice_names):
        mx_s = sn_x + 1.0 + k_m * (mini_w + .7)
        rect(mx_s, ctop + 3.0, mini_w, ch_in - 3.8, FACE, SUB_EDGE, .12, r=.25)
        rect(mx_s + .1, ctop + 3.1, mini_w - .2, 1.8, '#EFEAE2', None, r=.18)
        label(mx_s + mini_w / 2, ctop + 4.0, sl_lbl, 3.9, EXEC_DK, 'bold', 'center')
        for r_j in range(2):
            rect(mx_s + .65, ctop + 5.65 + r_j * 1.6, mini_w - 1.3, .68, '#DCD8D0', None, r=.15)

    # =========================================================================
    # 4. Prominent Bidirectional Database Interaction Arrows (<->)
    # =========================================================================
    maint_db_x = ix + iw / 2
    route([(maint_db_x, qy + qh), (maint_db_x, ctop)],
          MAINT_C, .32, heads='both', dash=(.72, .4), length=.95)
    label(maint_db_x + 1.4, 74.15,
          'table versions and check results' if en else '表版本与检查结果',
          4.7, MAINT_DK, 'bold')

    snap_cx = sn_x + sn_w / 2
    route([(snap_cx, ey + eh), (snap_cx, ctop)],
          EXEC_C, .34, heads='both', dash=(.72, .4), length=1.0)
    label(snap_cx + 1.4, 74.15,
          'compiled SQL $\\leftrightarrow$ rows' if en else '编译 SQL $\\leftrightarrow$ 结果',
          4.7, EXEC_DK, 'bold')


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
