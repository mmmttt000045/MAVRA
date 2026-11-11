"""MAVRA system overview (Figure 2): shared knowledge base and four runtime components.

Double column (178.0 mm wide, 95.0 mm high).
Balances visual abstraction with concrete technical mechanisms across all modules:
  - Top row: Concurrent data agents (Agent 1 learning session, Agent 2 before write,
    ..., Agent N after write, and Predictive agent P at cutoff t_i).
  - Left (Publish, steps 1-2): Agent 1 Session Log UI card -> Extract & Derive C
    (separating fixed relational core (B, I) from lifted slot p_0 + AST/probe
    condition synthesis) -> Verify Gates G1-G7 (structural/grain gates G1-G5 +
    answer-reproduction oracle G6-G7 catching omitted filters) -> Definition m^0.
  - Center (Knowledge base): Strictly domain definitions & shared check outcomes
    (no lookup state!):
      (1) Definitions M: catalog entries (composable join, homonymous D01/D02,
          metrics, predictive feature) + 4-band tuple anatomy m^r = (B, I, C, E, r)
          with orthogonal compositional link to join:item|store_sales and C -> H refs.
      (2) Check outcomes H: keyed by (id(c), V(dep(c))), showing multi-definition
          sharing dots, @v0 passes, @v1 grain break, @v1 repaired pass, and
          single-flight coalescing.
  - Top-right (Lookup, step 3): Internal Alias & bge-m3 Recall neighborhood +
    Catalog-trained Cross-Encoder x3 token-attention block + calibrated (.1, .9)
    probability spectrum routing to Hit (m^r, p, d) (step 4) or Diffs/Refer/Miss.
  - Bottom-right (Check and run, step 4): Atomic Read-Only Snapshot D_s (stamps V_s)
    with (1) Snapshot Condition Gate via H(c, V_s) and (2) Relational & Leak-Free
    Query Compiler (metric d(q_0(D_s, p)) + point-in-time feature window (t_i-w, t_i]),
    bidirectional (<->) execution on snapshot D_s, and verified return path to agents.
  - Bottom-left/center (Maintain, step 6): 3-stage incremental maintenance schematic
    (1. Dependency Stamp Filter V(dep(c)) with 2/5 shared check indicator ->
     2. Delta-Scoped Index Probe on Delta T -> 3. Guarded Single-Edit Repair & Replay),
    bidirectional (<->) stamps/probes arrow with PostgreSQL Database, and write-back (step 6).
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vecfig import PT, measure  # noqa: E402
import style  # noqa: E402
from style import (ACC, ACC_DK, ACC_PALE, AMBER, AMBER_PALE, EDGE, FACE, FIELD, INK, MUTED,  # noqa: E402
                   RED, RULE, SIDE, SLATE, TOP, WHITE)

NAME = 'architecture'
W, H = style.TEXTWIDTH, 95.6

TITLE, BODY, SMALL, TINY, STEP = 7.1, 6.1, 5.5, 5.0, 6.1
LEARN, LEARN_DK, LEARN_PALE = '#735EB0', '#523E8E', '#EFEBF9'
EXEC_C, EXEC_DK, EXEC_PALE = '#C97A1E', '#9B590C', '#FDF2E3'
MAINT_C, MAINT_DK, MAINT_PALE = '#13897B', '#0D665B', '#E5F5F2'
RED_PALE = '#FBE9E5'
REF = '#7A7670'
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

    def card_head(b, title_txt, sub_txt, band_fill, edge_c=EDGE, title_c=INK, sub_c=MUTED, bh=3.5):
        x, y, w, h = b
        rect(x, y, w, h, WHITE, edge_c, .2, r=.65)
        rect(x + .12, y + .12, w - .24, bh, band_fill, None, r=.55)
        rect(x + .12, y + .12 + bh / 2, w - .24, bh / 2, band_fill, None)
        yc = y + .12 + bh / 2
        tw = label(x + 1.25, yc, title_txt, TITLE, title_c, 'bold')
        if sub_txt:
            label(x + w - 1.15, yc, sub_txt, 4.9, sub_c, 'sans', 'right', width=w - tw - 2.5)

    def node3d(b, d=1.0, edge_c='#B8B4AC'):
        x, y, w, h = b
        s.poly([(x, y), (x + d, y - d), (x + w + d, y - d), (x + w, y)], '#F2F0EC', edge_c, .12)
        s.poly([(x + w, y), (x + w + d, y - d), (x + w + d, y + h - d), (x + w, y + h)],
               '#E6E3DD', edge_c, .12)
        rect(x, y, w, h, WHITE, edge_c, .18, r=.55)

    def step_badge(x, yc, n, color, r=1.42):
        s.circle(x, yc, r, color)
        label(x, yc, str(n), STEP, WHITE, 'bold', 'center')

    def mini_step(x, yc, n, color, r=.88):
        s.circle(x, yc, r, color)
        label(x, yc, str(n), 4.65, WHITE, 'bold', 'center')

    def check_mark(x, yc, ok, c=None, k=.92):
        if ok:
            s.poly([(x - .58 * k, yc + .02 * k), (x - .14 * k, yc + .46 * k), (x + .62 * k, yc - .52 * k)],
                   None, c or ACC, .25, closed=False)
        else:
            s.line(x - .46 * k, yc - .46 * k, x + .46 * k, yc + .46 * k, c or RED, .25)
            s.line(x - .46 * k, yc + .46 * k, x + .46 * k, yc - .46 * k, c or RED, .25)

    def pill(x, yc, txt, fill_c, text_c=WHITE, edge_c=None, size=4.6, pad=.75, h=1.82, wt='bold', dash=None):
        w = measure(txt, size, wt) + 2 * pad
        rect(x, yc - h / 2, w, h, fill_c, edge_c, .14 if edge_c else 0, r=.38, dash=dash)
        label(x + w / 2, yc, txt, size, text_c, wt, 'center')
        return w

    def person_icon(x, yc, c='#8A867E'):
        s.circle(x, yc - .62, .64, c)
        rect(x - 1.0, yc + .16, 2.0, 1.12, c, None, r=.54)

    def sparkle_icon(cx, cy, r, c):
        pts = []
        for k in range(8):
            a = math.pi / 4 * k - math.pi / 2
            rr = r if k % 2 == 0 else .30 * r
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        s.poly(pts, c, None)

    def shield_icon(cx, cy, r, fill_c, stroke_c):
        pts = [
            (cx, cy - r),
            (cx + .88 * r, cy - .62 * r),
            (cx + .78 * r, cy + .28 * r),
            (cx, cy + 1.02 * r),
            (cx - .78 * r, cy + .28 * r),
            (cx - .88 * r, cy - .62 * r),
        ]
        s.poly(pts, fill_c, stroke_c, .18)
        check_mark(cx, cy + .05 * r, True, stroke_c, k=.68)

    def key_icon(x, yc, c=ACC_DK):
        s.circle(x + .5, yc, .44, None, c, .19)
        s.line(x + .94, yc, x + 1.98, yc, c, .19)
        s.line(x + 1.52, yc, x + 1.52, yc + .38, c, .19)
        s.line(x + 1.88, yc, x + 1.88, yc + .38, c, .19)

    def join_icon(x, yc, c=ACC_DK):
        rect(x, yc - .48, .88, .96, ACC_PALE, c, .15, r=.14)
        rect(x + 1.14, yc - .48, .88, .96, WHITE, c, .15, r=.14)
        s.line(x + .88, yc, x + 1.14, yc, c, .19)

    def dom_icon(x, yc, c=MAINT_C):
        rect(x, yc - .48, 1.95, .96, MAINT_PALE, c, .15, r=.18)
        for dx_i in (.45, .98, 1.5):
            s.circle(x + dx_i, yc, .16, c)

    def share_dots(x, yc, n, col=ACC):
        span = (n - 1) * 1.18
        if n > 1:
            s.line(x, yc, x + span, yc, col, .18)
        for idx_d in range(n):
            s.circle(x + idx_d * 1.18, yc, .31, col)

    # =========================================================================
    # 1. Top Row: Concurrent Data Agents (1, 2, ..., N and Predictive P)
    # =========================================================================
    ag_y, ag_h = 1.6, 8.7
    ag_specs = (
        (1.6, 38.0, 'Agent 1' if en else '智能体 1',
         'first session' if en else '首次探索', None,
         'ask:' if en else '问：', 'Jan. electronics revenue?' if en else '1 月电子品类营业额？',
         'explores DB, answer verified' if en else '多轮探查数据库，结果已核验', LEARN),
        (45.2, 38.0, 'Agent 2' if en else '智能体 2',
         'before' if en else '写入前', 5,
         'ask:' if en else '问：', 'highest-revenue month?' if en else '电子营业额最高月份？',
         'reuses core, binds $d = \\mathrm{rank}$' if en else '复用核心定义，绑定月度排序 $d$', ACC_DK),
        (88.8, 38.4, 'Agent N' if en else '智能体 N',
         'after' if en else '写入后', 5,
         'ask:' if en else '问：', 'Sep. revenue vs. last year?' if en else '9 月电子营业额同比？',
         'reuses `rev 1` after repair ($d = \\Delta$)' if en else '修复后复用 `rev 1`（绑定同比 $d$）', MAINT_DK),
        (132.4, 41.2, 'Predictive agent P' if en else '预测智能体 P',
         'cutoff $t_i$' if en else '截点 $t_i$', None,
         'ask:' if en else '问：', 'will customer $u_i$ churn?' if en else '客户 $u_i$ 是否会流失？',
         'reuses leak-free feature ($\\leq t_i$)' if en else '跨任务复用防穿越特征（$\\leq t_i$）', EXEC_DK),
    )
    for ax, aw, aname, awhen, astep, aask, aq, anote, acol in ag_specs:
        node3d((ax, ag_y, aw, ag_h))
        person_icon(ax + 2.1, ag_y + 2.05, acol if aname.endswith('1') else '#7E7A72')
        label(ax + 3.85, ag_y + 2.05, aname, BODY, INK, 'bold')
        if awhen:
            rx_end = ax + aw - 1.05
            if astep is not None:
                mini_step(rx_end - .9, ag_y + 2.05, astep, MAINT_C, r=.86)
                rx_end -= 2.1
            is_hi = ('after' in awhen or '后' in awhen)
            label(rx_end, ag_y + 2.05, awhen, 4.75, MAINT_DK if is_hi else MUTED,
                  'bold' if is_hi else 'sans', 'right')
        w_ask = label(ax + 1.25, ag_y + 4.9, aask, 5.25, ACC_DK, 'bold')
        label(ax + 1.25 + w_ask + (.65 if en else 0), ag_y + 4.9, aq, 5.25, INK,
              width=aw - 2.2 - w_ask)
        label(ax + 1.25, ag_y + 7.25, anote, 4.75, acol, width=aw - 2.1)

    dots_cx = (45.2 + 38.0 + 88.8) / 2
    for k in (-1, 0, 1):
        s.circle(dots_cx + 1.25 * k, ag_y + ag_h / 2, .33, '#9E9A92')

    # =========================================================================
    # 2. Middle Band: MAVRA Shared Layer Container
    # =========================================================================
    my, mh = 13.4, 64.4
    rect(1.2, my, W - 2.4, mh, FIELD, '#B9D4F2', .22, r=1.15)
    rect(2.6, my + .9, .65, 2.0, ACC)
    label(3.85, my + 1.9, 'MAVRA', TITLE + .15, ACC_DK, 'bold')

    # -------------------------------------------------------------------------
    # (A) Left Component: PUBLISH (Steps 1-2)
    # -------------------------------------------------------------------------
    PUB = (2.4, 16.8, 41.2, 41.4)
    px, py, pw, ph = PUB
    card_head(PUB, 'Publish' if en else '发布',
              'session $\\rightarrow$ definition' if en else '会话 $\\rightarrow$ 可执行定义',
              LEARN_PALE, LEARN, INK, LEARN_DK)

    # Step 1 arrow: Agent 1 -> Publish (placed clear of MAVRA title)
    a1_x = px + 21.0
    route([(a1_x, ag_y + ag_h), (a1_x, py)], LEARN, THIN, length=.95)
    step_badge(a1_x + 2.8, 14.55, 1, LEARN)

    lx, lw = px + 1.15, pw - 2.3
    mid_px = px + pw / 2

    # Card P1: Agent 1 Session Log UI Window
    ly, lh = py + 4.15, 11.35
    rect(lx, ly, lw, lh, '#FAF9FC', '#B5ACD2', .16, r=.48)
    rect(lx + .1, ly + .1, lw - .2, 2.35, '#E9E4F4', None, r=.38)
    rect(lx + .1, ly + 1.2, lw - .2, 1.25, '#E9E4F4', None)
    for idx_d, dc in enumerate(('#D98276', '#E0B25B', '#68A884')):
        s.circle(lx + 1.0 + idx_d * 1.1, ly + 1.25, .32, dc)
    label(lx + 4.5, ly + 1.25, 'Agent 1 session log' if en else '智能体 1 会话日志', 4.8, LEARN_DK, 'bold')
    pill(lx + lw - (9.2 if en else 8.1), ly + 1.25,
         'verified' if en else '已核验', LEARN, WHITE, size=4.35, pad=.7, h=1.55)

    p1_rows = (
        ('Q', LEARN_PALE, LEARN_DK,
         '"Jan. 2001 electronics rev.?"' if en else '"2001年1月电子品类营业额？"'),
        ('SQL', TOP, INK,
         "`SUM(net_paid)..'Elec.' & 2001-01`" if en else "`SUM(net_paid)..'Elec.' & 01-01`"),
        ('Log', ACC_PALE, ACC_DK,
         'probes + Ans `2,754,299.60`' if en else '探查 + 核验答案 `2,754,299.60`'),
    )
    for idx_r, (rtag, rbg, rfg, rtxt) in enumerate(p1_rows):
        ry = ly + 3.85 + idx_r * 2.72
        tw_p = pill(lx + .85, ry, rtag, rbg, rfg, edge_c=rfg, size=4.3, pad=.62, h=1.62)
        label(lx + 1.35 + tw_p, ry, rtxt, 4.7, INK,
              width=lw - tw_p - (3.8 if idx_r == 2 else 1.8))
        if idx_r == 2:
            check_mark(lx + lw - 1.35, ry, True, ACC, k=.78)

    route([(mid_px, ly + lh), (mid_px, ly + lh + 1.05)], LEARN, .2, length=.65)

    # Card P2: Decompose Core vs Slot + Static Condition Synthesis
    ex_y, ex_h = ly + lh + 1.05, 9.65
    rect(lx, ex_y, lw, ex_h, WHITE, LEARN, .16, r=.48)
    sparkle_icon(lx + 1.75, ex_y + 1.65, 1.05, LEARN)
    label(lx + 3.25, ex_y + 1.65,
          'Extract & Derive $C$' if en else '结构提取与条件推导 $C$', 5.05, INK, 'bold')
    label(lx + lw - .9, ex_y + 1.65,
          'AST + probes' if en else '语法树 + 探针', 4.45, MUTED, 'sans', 'right')

    # Row A: Fixed Core (B, I) chip vs Lifted Slot p_0 chip
    r2a_y = ex_y + 4.55
    c_core_w = 25.8
    rect(lx + .85, r2a_y - 1.15, c_core_w, 2.3, LEARN_PALE, LEARN, .15, r=.35)
    label(lx + .85 + c_core_w / 2, r2a_y,
          'Core $(B,I)$: $F,\\mathrm{AGG}_e,K,\\mathcal{J},\\varphi,\\tau$' if en
          else '固定核 $(B,I)$: $F,\\mathrm{AGG}_e,K,\\mathcal{J},\\varphi,\\tau$',
          4.45, LEARN_DK, 'bold', 'center')
    rx_slot = lx + 1.35 + c_core_w
    sw_slot = lw - (rx_slot - lx) - .85
    rect(rx_slot, r2a_y - 1.15, sw_slot, 2.3, WHITE, LEARN, .15, r=.35, dash=(.55, .32))
    label(rx_slot + sw_slot / 2, r2a_y,
          'slot $p_0, d_0$' if en else '参数槽 $p_0,d_0$', 4.45, LEARN_DK, 'bold', 'center')

    # Row B: Derived executable conditions C(m^0) without LLM
    r2b_y = ex_y + 7.75
    s.line(lx + .85, ex_y + 6.25, lx + lw - .85, ex_y + 6.25, RULE, .12)
    key_icon(lx + 1.0, r2b_y, ACC_DK)
    label(lx + 3.25, r2b_y, 'unique $K$' if en else '键唯一 $K$', 4.5, INK)
    join_icon(lx + 12.6, r2b_y, ACC_DK)
    label(lx + 15.0, r2b_y, 'loss $\\leq b{+}\\varepsilon$' if en else '连接损失 $\\leq b{+}\\varepsilon$', 4.5, INK)
    dom_icon(lx + 26.8, r2b_y, MAINT_C)
    label(lx + 29.1, r2b_y, '`Dom` / null' if en else '值域/空值', 4.5, INK)

    route([(mid_px, ex_y + ex_h), (mid_px, ex_y + ex_h + 1.05)], LEARN, .2, length=.65)

    # Card P3: Admission Gates G1-G7 & Answer-Reproduction Replay
    vy, vh = ex_y + ex_h + 1.05, 9.0
    rect(lx, vy, lw, vh, WHITE, LEARN, .16, r=.48)
    shield_icon(lx + 1.85, vy + 1.65, 1.05, ACC_PALE, ACC_DK)
    label(lx + 3.35, vy + 1.65,
          'Admission Gates G1–G7' if en else '准入门禁 G1–G7 与重放', 5.05, INK, 'bold')
    label(lx + lw - .9, vy + 1.65,
          'replay oracle' if en else '源答案核验', 4.45, ACC_DK, 'bold', 'right')

    g1_y = vy + 4.45
    w_g15 = pill(lx + .85, g1_y, 'G1–G5', TOP, INK, edge_c=EDGE, size=4.2, pad=.52, h=1.58)
    label(lx + 1.35 + w_g15, g1_y,
          'trace math, grain $K$, read-only' if en else '算术链、粒度键 $K$ 与只读检查',
          4.55, INK, width=lw - w_g15 - 4.0)
    check_mark(lx + lw - 1.35, g1_y, True, ACC, k=.74)

    g2_y = vy + 7.15
    w_g67 = pill(lx + .85, g2_y, 'G6–G7', ACC_PALE, ACC_DK, edge_c=ACC, size=4.2, pad=.52, h=1.58)
    label(lx + 1.35 + w_g67, g2_y, '`Compile(I,p0)=Ans`', 4.4, ACC_DK, 'bold')
    check_mark(lx + 24.0, g2_y, True, ACC, k=.68)
    drop_txt = 'no $\\varphi$: $4.9\\times$' if en else '漏掉 $\\varphi$: $4.9\\times$'
    drop_w = measure(drop_txt, 4.05, 'bold') + 3.1
    drop_x = lx + lw - .85 - drop_w
    rect(drop_x, g2_y - .78, drop_w, 1.56, RED_PALE, '#E6A89E', .14, r=.35)
    label(drop_x + .6, g2_y, drop_txt, 4.05, RED, 'bold')
    check_mark(drop_x + drop_w - 1.0, g2_y, False, RED, k=.55)

    route([(mid_px, vy + vh), (mid_px, vy + vh + .95)], LEARN, .2, length=.62)

    # Card P4: Output Executable Definition m^0 = (B, I, C, E, 0)
    oy, oh = vy + vh + .95, 3.85
    rect(lx, oy, lw, oh, LEARN_PALE, LEARN_DK, .2, r=.46)
    pill(lx + .8, oy + oh / 2, 'out' if en else '输出', LEARN_DK, WHITE, size=4.35, pad=.62, h=1.7)
    label(lx + 6.4, oy + oh / 2, '$m^0$:' if en else '定义 $m^0$:', 5.0, LEARN_DK, 'bold')
    bx_cur = lx + (11.2 if en else 14.2)
    for f_txt, f_col in (('B: choices' if en else 'B 口径', LEARN_DK),
                         ('I(p)' if en else 'I 模板', ACC_DK),
                         ('C: 6' if en else 'C 条件', MAINT_DK),
                         ('E, $V_0$' if en else 'E 证据', SLATE)):
        bx_cur += pill(bx_cur, oy + oh / 2, f_txt, WHITE, f_col, edge_c=f_col, size=4.15, pad=.48, h=1.68) + .4

    # -------------------------------------------------------------------------
    # (B) Center: KNOWLEDGE BASE (Definitions M + Check outcomes H ONLY!)
    # -------------------------------------------------------------------------
    KB = (46.8, 16.8, 81.8, 41.4)
    kx, ky, kw, kh = KB
    rect(kx + .75, ky + .75, kw, kh, SIDE, EDGE, .12, r=.7)
    box(KB, WHITE, ACC, .22, r=.65)
    rect(kx, ky, kw, 3.5, ACC, None, r=.65)
    rect(kx, ky + 1.75, kw, 1.75, ACC, None)
    tw_kb = label(kx + 1.4, ky + 1.75, 'Knowledge base' if en else '共享知识库', TITLE, WHITE, 'bold')
    label(kx + kw - 1.3, ky + 1.75,
          'executable definitions $\\mathcal{M}$ & shared check outcomes $\\mathcal{H}$' if en
          else '跨智能体共享的可执行定义目录 $\\mathcal{M}$ 与条件检查表 $\\mathcal{H}$',
          4.8, WHITE, 'sans', 'right', width=kw - tw_kb - 2.8)

    # Step 2 thick arrow: Publish Output -> Knowledge base
    step2_y = oy + oh / 2
    route([(px + pw, step2_y), (kx, step2_y)], LEARN, THICK, length=.95)
    step_badge((px + pw + kx) / 2, step2_y - 2.5, 2, LEARN)

    # --- Sub-panel 1 (Left inside KB): Composable Definitions M ---
    dx, dy, dw, dh = kx + 1.2, ky + 4.2, 43.2, kh - 5.1
    label(dx + .15, dy + .95, 'Definitions $\\mathcal{M}$' if en else '可执行定义目录 $\\mathcal{M}$', BODY, ACC_DK, 'bold')
    label(dx + dw - .15, dy + .95, '$m^r = (B, I, C, E, r)$', 4.85, MUTED, 'sans', 'right')

    # Top Catalog Table (5 entries)
    cat_y, cat_h = dy + 2.15, 12.6
    rect(dx, cat_y, dw, cat_h, FACE, '#C8C4BC', .15, r=.44)
    cat_entries = (
        ('`join:item|store_sales`', 'r0 $\\rightarrow$ r1' if en else 'r0 $\\rightarrow$ r1', 'join'),
        ('`metric:Store revenue`', 'D01: after coupons' if en else 'D01: 扣券实付', 'hom'),
        ('`metric:Store revenue`', 'D02: before coupons' if en else 'D02: 券前总额', 'hom'),
        ('`metric:Return rate`', 'returns / sales' if en else '退货率指标', 'met'),
        ('`feature:cust:spend_90d`', 'entity $u$, $(t{-}90\\mathrm{d}, t]$' if en else '实体 $u$, $(t{-}90\\mathrm{d}, t]$', 'feat'),
    )
    cat_ys = []
    for idx_c, (ckey, cmeta, ckind) in enumerate(cat_entries):
        ry = cat_y + 1.38 + idx_c * 2.45
        if idx_c % 2 == 1:
            rect(dx + .25, ry - 1.15, dw - .5, 2.3, WHITE, None, r=.2)
        label(dx + .85, ry, ckey, 4.75, INK, width=dw - 17.5)
        if ckind == 'join':
            mini_step(dx + dw - 1.3, ry, 6, MAINT_C, r=.74)
            label(dx + dw - 2.25, ry, '$\\rightarrow$r1', 4.45, MAINT_DK, 'bold', 'right')
            mini_step(dx + dw - 6.35, ry, 2, LEARN, r=.74)
            label(dx + dw - 7.3, ry, 'r0', 4.45, LEARN_DK, 'bold', 'right')
        else:
            col_m = ACC_DK if ckind == 'hom' else (EXEC_DK if ckind == 'feat' else MUTED)
            label(dx + dw - .85, ry, cmeta, 4.45, col_m,
                  'bold' if ckind in ('hom', 'feat') else 'sans', 'right')
        cat_ys.append(ry)

    # Expanded Definition Tuple Anatomy: metric:Electronics revenue
    mx, my_card = dx, cat_y + cat_h + .95
    mw_card, mh_card = dw, dh - (cat_h + 3.1)
    rect(mx, my_card, mw_card, mh_card, WHITE, ACC, .2, r=.46)
    rect(mx + .12, my_card + .12, mw_card - .24, 2.65, ACC_PALE, None, r=.36)
    label(mx + .85, my_card + 1.42, '`metric:Electronics revenue`', 4.95, INK, 'bold')
    mini_step(mx + mw_card - 1.25, my_card + 1.42, 6, MAINT_C, r=.78)
    label(mx + mw_card - 2.3, my_card + 1.42, '$\\rightarrow$1', 4.6, MAINT_DK, 'bold', 'right')
    mini_step(mx + mw_card - 6.75, my_card + 1.42, 2, LEARN, r=.78)
    label(mx + mw_card - 7.8, my_card + 1.42, 'rev 0', 4.6, LEARN_DK, 'bold', 'right')

    # Band B (Semantic Choices)
    b_yc = my_card + 4.15
    pill(mx + .8, b_yc, 'B', LEARN_PALE, LEARN_DK, edge_c=LEARN, size=4.35, pad=.58, h=1.65)
    label(mx + 3.8, b_yc,
          'store sales · `net_paid` · sale date · Electronics' if en
          else '门店销售 · 扣券实付 · 销售日期 · 电子品类',
          4.65, INK, width=mw_card - 4.6)
    s.line(mx + .7, my_card + 5.45, mx + mw_card - .7, my_card + 5.45, RULE, .13)

    # Band I (3-line Relational Implementation + Compositional Join + Slots)
    i_y1 = my_card + 6.8
    i_y2 = my_card + 9.05
    i_y3 = my_card + 11.3
    pill(mx + .8, i_y1, 'I', ACC_PALE, ACC_DK, edge_c=ACC, size=4.35, pad=.68, h=1.65)
    label(mx + 3.8, i_y1,
          '`store_sales` · `SUM(ss_net_paid)` · $K$ · $\\tau$' if en
          else '`store_sales` · `SUM(ss_net_paid)` · 粒度 $K$ · $\\tau$',
          4.65, INK, width=mw_card - 4.5)
    label(mx + 3.8, i_y2,
          'joins `join:item|store_sales` + `date_dim`' if en
          else '引用 `join:item|store_sales` + `date_dim`',
          4.55, ACC_DK, width=mw_card - 4.5)
    label(mx + 3.8, i_y3,
          "$\\varphi$: `i_category='Electronics'`  |  slots $(p, d)$" if en
          else "$\\varphi$: `i_category='Electronics'`  |  参数 $(p, d)$",
          4.55, INK, width=mw_card - 4.5)
    s.line(mx + .7, my_card + 12.6, mx + mw_card - .7, my_card + 12.6, RULE, .13)

    # Band C (Derived Data Conditions referencing H)
    c_yc = my_card + 14.0
    pill(mx + .8, c_yc, 'C', MAINT_PALE, MAINT_DK, edge_c=MAINT_C, size=4.35, pad=.58, h=1.65)
    key_icon(mx + 3.85, c_yc, ACC_DK)
    label(mx + 6.35, c_yc, '$\\times 3$', 4.45, INK)
    join_icon(mx + 9.65, c_yc, ACC_DK)
    label(mx + 12.1, c_yc, '$\\times 2$', 4.45, INK)
    dom_icon(mx + 15.35, c_yc, MAINT_C)
    label(mx + 18.0, c_yc,
          'refs by `id(c)` $\\rightarrow \\mathcal{H}$' if en else '按签名 `id(c)` 引用 $\\mathcal{H}$',
          4.6, MAINT_DK, 'bold', width=mw_card - 18.8)
    s.line(mx + .7, my_card + 15.35, mx + mw_card - .7, my_card + 15.35, RULE, .13)

    # Band E (Provenance & Version Stamps)
    e_yc = my_card + 16.8
    pill(mx + .8, e_yc, 'E', TOP, SLATE, edge_c=SLATE, size=4.35, pad=.6, h=1.65)
    label(mx + 3.8, e_yc,
          'trace, Ans `2.75M`, G1–G7, $V_m$: $\\langle 0,0,0\\rangle{\\rightarrow}\\langle 1,0,0\\rangle$' if en
          else '轨迹、核验答案、门禁与版本向量 $V_m$: $\\langle 0,0,0\\rangle{\\rightarrow}\\langle 1,0,0\\rangle$',
          4.5, SLATE, width=mw_card - 4.5)

    # --- Sub-panel 2 (Right inside KB): Shared Check Outcomes H ---
    hx = dx + dw + 2.7
    hy, hw, hh = dy, kx + kw - 1.2 - hx, dh
    label(hx + .15, hy + .95, 'Check outcomes $\\mathcal{H}$' if en else '共享检查表 $\\mathcal{H}$', BODY, ACC_DK, 'bold')
    label(hx + hw - .15, hy + .95, '$(\\mathrm{id}(c), V(\\mathrm{dep}(c)))$', 4.65, MUTED, 'sans', 'right')

    hc_y, hc_h = hy + 2.15, hh - 2.15
    rect(hx, hc_y, hw, hc_h, '#FAFCFE', '#9BBCE0', .18, r=.46)
    rect(hx + .12, hc_y + .12, hw - .24, 2.35, '#E6F0FB', None, r=.36)
    label(hx + .9, hc_y + 1.28, 'Condition `id(c)`' if en else '数据条件 `id(c)`', 4.4, ACC_DK, 'bold')
    label(hx + 19.9, hc_y + 1.28, 'Shared' if en else '共享', 4.4, ACC_DK, 'bold', 'center')
    label(hx + hw - .9, hc_y + 1.28, 'Verdict' if en else '版本结论', 4.4, ACC_DK, 'bold', 'right')

    h_rows = (
        ('key', '`store_sales.K`', 4, '@v0', True, None),
        ('key', '`date_dim.sk`', 4, '@v0', True, None),
        ('join', '`sales` $\\rightarrow$ `date`', 3, '@v0', True, None),
        ('join', '`sales` $\\rightarrow$ `item`', 2, '@v0,1', True, None),
        ('dom', '`Dom(i_cat)`', 1, '@v0,1', True, None),
        ('key', '`item.sk`', 2, '@v0', True, None),
        ('key', '`item.sk` (dup `17`)', 0, '@v1', False, 6),
        ('key', "`item.sk` (`'Y'`)", 0, '@v1', True, 6),
    )
    h_ys = []
    for idx_h, (hkind, htxt, nshare, hver, hok, hstep) in enumerate(h_rows):
        ry = hc_y + 3.85 + idx_h * 3.45
        if hstep == 6 and not hok:
            rect(hx + .55, ry - 1.48, hw - 1.1, 2.96, RED_PALE, '#E6A89E', .14, r=.3)
        elif hstep == 6 and hok:
            rect(hx + .55, ry - 1.48, hw - 1.1, 2.96, MAINT_PALE, '#8BCAC1', .14, r=.3)
        elif idx_h % 2 == 1:
            rect(hx + .55, ry - 1.48, hw - 1.1, 2.96, WHITE, None, r=.25)

        ic_x = hx + .95
        if hkind == 'key':
            key_icon(ic_x, ry, (MAINT_DK if hstep == 6 else ACC_DK) if hok else RED)
        elif hkind == 'join':
            join_icon(ic_x, ry, ACC_DK)
        else:
            dom_icon(ic_x, ry, MAINT_C)

        label(hx + 3.35, ry, htxt, 4.55, INK if hok else RED,
              'bold' if hstep == 6 else 'sans', width=15.2 if nshare > 0 else 19.2)
        if nshare > 0:
            share_dots(hx + 18.7, ry, min(nshare, 3), ACC)
        if hstep == 6:
            label(hx + hw - 5.3, ry, hver, 4.45, MAINT_DK if hok else RED, 'bold', 'right')
            check_mark(hx + hw - 3.8, ry, hok, MAINT_DK if hok else RED, k=.68)
            mini_step(hx + hw - 1.65, ry, hstep, MAINT_C, r=.76)
        else:
            label(hx + hw - 3.3, ry, hver, 4.45, MUTED, 'sans', 'right')
            check_mark(hx + hw - 1.65, ry, True, ACC, k=.68)
        h_ys.append(ry)

    # Single-flight summary footer inside H
    sf_y = hc_y + hc_h - 1.55
    s.line(hx + .8, sf_y - 1.35, hx + hw - .8, sf_y - 1.35, '#D2DFEE', .13)
    label(hx + hw / 2, sf_y,
          'single-flight · 1 check serves all sharing defs' if en
          else '单航班合并 · 一次校验供全部共享定义复用',
          4.35, ACC_DK, 'bold', 'center')

    # Orthogonal compositional & condition reference wires inside Knowledge base
    ch_x1 = dx + dw + .85
    ch_x2 = dx + dw + 1.75
    # 1) Band I joins -> catalog join:item|store_sales
    route([(mx + mw_card, i_y2), (ch_x1, i_y2), (ch_x1, cat_ys[0]), (dx + dw, cat_ys[0])],
          REF, .18, length=.58, radius=.32)
    # 2) Store revenue -> date_dim.sk @v0
    route([(dx + dw, cat_ys[1]), (ch_x2, cat_ys[1]), (ch_x2, h_ys[1]), (hx + .55, h_ys[1])],
          REF, .18, length=.58, radius=.32)
    # 3) Band C -> item.sk @v0
    route([(mx + mw_card, c_yc), (ch_x2, c_yc), (ch_x2, h_ys[5]), (hx + .55, h_ys[5])],
          REF, .18, length=.58, radius=.32)

    # -------------------------------------------------------------------------
    # (C) Bottom-Left+Center: MAINTAIN (Step 6) — 3 Rich Schematic Cards
    # -------------------------------------------------------------------------
    MAINT = (2.4, 60.4, 126.2, 16.4)
    qx, qy, qw, qh = MAINT
    rect(qx, qy, qw, qh, WHITE, MAINT_C, .2, r=.65)
    sb_w = 19.4
    rect(qx + .12, qy + .12, sb_w, qh - .24, MAINT_PALE, None, r=.55)
    rect(qx + sb_w / 2, qy + .12, sb_w / 2 + .12, qh - .24, MAINT_PALE, None)
    label(qx + 1.25, qy + 3.4, 'Maintain' if en else '维护', TITLE, INK, 'bold')
    label(qx + 1.25, qy + 6.7, 'on write' if en else '写入触发', 4.85, MAINT_DK, 'bold')
    mini_step(qx + (12.8 if en else 12.2), qy + 6.7, 5, MAINT_C, r=.78)
    label(qx + 1.25, qy + 9.8, 'stamps $V(T)$' if en else '表版本戳 $V(T)$', 4.65, MUTED)
    label(qx + 1.25, qy + 12.4, '& delta $\\Delta T$' if en else '与增量 $\\Delta T$', 4.65, MUTED)

    sc_y, sc_h = qy + .95, qh - 1.9
    s1_x, s1_w = qx + sb_w + 1.1, 33.4
    s2_x, s2_w = s1_x + s1_w + 1.7, 33.4
    s3_x, s3_w = s2_x + s2_w + 1.7, qw - (sb_w + 1.1 + 33.4 * 2 + 3.4) - 1.0

    def maint_card_head(cx, cw, num, title_s, border_c='#A8D8D1', bg_c='#FAFCFC'):
        rect(cx, sc_y, cw, sc_h, bg_c, border_c, .17, r=.46)
        rect(cx + .1, sc_y + .1, cw - .2, 2.75, MAINT_PALE, None, r=.36)
        pill(cx + .75, sc_y + 1.48, str(num), MAINT_C, WHITE, size=4.2, pad=.52, h=1.55)
        label(cx + 3.25, sc_y + 1.48, title_s, 4.85, INK, 'bold', width=cw - 4.0)

    # Stage 1: Dependency Stamp Filter & Shared H
    maint_card_head(s1_x, s1_w, 1,
                    'Version Filter $V(\\mathrm{dep}(c))$' if en else '依赖版本筛选 $V(\\mathrm{dep}(c))$')
    # Three table stamp mini-badges
    c_y1 = sc_y + 4.95
    pill(s1_x + .8, c_y1, '`sales` v0', FACE, MUTED, edge_c='#CFCBC4', size=4.15, pad=.48, h=1.78, wt='sans')
    pill(s1_x + 11.0, c_y1, '`date` v0', FACE, MUTED, edge_c='#CFCBC4', size=4.15, pad=.48, h=1.78, wt='sans')
    pill(s1_x + 20.5, c_y1, '`item` 0$\\rightarrow$1', AMBER_PALE, EXEC_DK, edge_c=AMBER, size=4.15, pad=.5, h=1.78)
    # 5-block progress indicator (2 rerun, 3 skipped)
    c_y2 = sc_y + 8.55
    for b_i in range(5):
        bx_m = s1_x + 1.0 + b_i * 1.95
        filled = (b_i < 2)
        rect(bx_m, c_y2 - .72, 1.5, 1.44, MAINT_C if filled else WHITE, MAINT_C, .15, r=.18)
    label(s1_x + 11.4, c_y2,
          'rerun 2/5 once' if en else '仅重查 2/5 项一次', 4.65, MAINT_DK, 'bold')
    label(s1_x + s1_w / 2, sc_y + 12.15,
          'reuse $\\mathcal{H}$ across SR, RA, RR, ER' if en else '结果在 SR, RA, RR, ER 间共享',
          4.45, MUTED, 'sans', 'center')

    route([(s1_x + s1_w, sc_y + sc_h / 2), (s2_x, sc_y + sc_h / 2)], MAINT_C, .24, length=.72)

    # Stage 2: Delta-Scoped Index Probe on Delta T
    maint_card_head(s2_x, s2_w, 2,
                    'Delta Probe on $\\Delta T$' if en else '批次增量探针 $\\Delta T$')
    p_y = sc_y + 4.05
    p_h = 5.15
    # Base indexed table block + Delta block + index probe connector
    b_w1 = 15.6
    b_w2 = 13.4
    rect(s2_x + .9, p_y, b_w1, p_h, '#EDEBE6', '#BFB9B0', .14, r=.34)
    label(s2_x + .9 + b_w1 / 2, p_y + 1.75, '`item` base', 4.45, INK, 'bold', 'center')
    label(s2_x + .9 + b_w1 / 2, p_y + 3.75, '1,000 idx keys' if en else '1,000 索引键', 4.2, MUTED, 'sans', 'center')
    dx_b = s2_x + s2_w - .9 - b_w2
    rect(dx_b, p_y, b_w2, p_h, RED_PALE, RED, .17, r=.34)
    label(dx_b + b_w2 / 2, p_y + 1.75, '$\\Delta\\mathrm{item}$', 4.5, RED, 'bold', 'center')
    label(dx_b + b_w2 / 2, p_y + 3.75, "`sk=17, 'N'`", 4.2, INK, 'sans', 'center')
    route([(dx_b, p_y + p_h / 2), (s2_x + .9 + b_w1, p_y + p_h / 2)], RED, .22, length=.62)
    label(s2_x + s2_w / 2, sc_y + 12.15,
          'dup `key 17` (`1001/1000` $\\times$) · no full scan' if en
          else '免全表扫描检出键 `17` 重复 (`1001/1000`)',
          4.45, RED, 'bold', 'center')

    route([(s2_x + s2_w, sc_y + sc_h / 2), (s3_x, sc_y + sc_h / 2)], MAINT_C, .24, length=.72)

    # Stage 3: Guarded Single-Edit Repair & Replay
    maint_card_head(s3_x, s3_w, 3,
                    'Single-Edit Repair $\\mathcal{E}(x,c)$' if en else '受限单步修复 $\\mathcal{E}(x,c)$',
                    border_c=MAINT_C, bg_c='#F4FBF9')
    r3_y1 = sc_y + 5.25
    rect(s3_x + .85, r3_y1 - 1.35, s3_w - 1.7, 2.7, WHITE, MAINT_C, .16, r=.34)
    label(s3_x + 1.5, r3_y1, "`+ i_is_current='Y'`", 4.45, MAINT_DK, 'bold')
    label(s3_x + s3_w - 1.4, r3_y1,
          'Ans $\\rightarrow$ `r1`' if en else '重放通过$\\rightarrow$`r1`',
          4.35, MAINT_DK, 'bold', 'right')
    r3_y2 = sc_y + 8.85
    pill(s3_x + .85, r3_y2,
         '$\\neq 1$ edit $\\rightarrow$ retire $\\perp$' if en else '无或多重补丁 $\\rightarrow$ 退役 $\\perp$',
         FACE, MUTED, edge_c='#CFCBC4', size=4.05, pad=.46, h=1.72, wt='sans')
    dom_p_txt = 'new `Dom` $\\rightarrow$ pending' if en else '新值域 $\\rightarrow$ 挂起'
    dom_p_w = measure(dom_p_txt, 4.05, 'sans') + .92
    pill(s3_x + s3_w - .85 - dom_p_w, r3_y2,
         dom_p_txt, AMBER_PALE, EXEC_DK, edge_c=AMBER, size=4.05, pad=.46, h=1.72, wt='sans')
    label(s3_x + s3_w / 2, sc_y + 12.15,
          'sole edit restoring $C$ & source Ans' if en else '唯一恢复 $C$ 且复现源答案时自动升版',
          4.45, MAINT_DK, 'bold', 'center')

    # Step 6 thick arrow: Maintain Stage 3 -> Knowledge base (into H)
    s6_x = s3_x + s3_w / 2
    route([(s6_x, qy), (s6_x, ky + kh)], MAINT_C, THICK, length=.88)
    step_badge(s6_x + 2.6, (qy + ky + kh) / 2, 6, MAINT_C, r=1.18)

    # -------------------------------------------------------------------------
    # (D) Top-Right: LOOKUP (Step 3) — Visual Index + Cross-Encoder + Spectrum
    # -------------------------------------------------------------------------
    LOOK = (131.6, 16.8, 42.6, 25.4)
    lx_k, ly_k, lw_k, lh_k = LOOK
    card_head(LOOK, 'Lookup' if en else '查找',
              'no SQL · no online LLM' if en else '不生 SQL · 免在线 LLM',
              ACC_PALE, ACC, INK, ACC_DK)

    # Request bus from Agents 2, N, P into Lookup (Step 3)
    bus_y = 11.9
    c_a2 = 45.2 + 38.0 / 2
    c_an = 88.8 + 38.4 / 2
    c_ap = 132.4 + 18.0
    req_x = lx_k + 12.5
    s.line(c_a2, bus_y, c_ap, bus_y, ACC, .25)
    for cx_ag in (c_a2, c_an, c_ap):
        s.line(cx_ag, ag_y + ag_h, cx_ag, bus_y, ACC, .23)
    route([(req_x, bus_y), (req_x, ly_k)], ACC, THIN, length=.95)
    step_badge(req_x - 2.9, 14.55, 3, ACC)
    label(req_x + 1.2, 14.65, 'request $\\rho$' if en else '请求 $\\rho$', 4.85, ACC_DK, 'bold')

    # Catalog sync arrow: Knowledge base -> Lookup
    sync_y = ly_k + 6.8
    route([(kx + kw, sync_y), (lx_k, sync_y)], REF, .22, dash=(.62, .38), length=.78)

    # Top row inside Lookup: (1) Alias & Dense Recall  ->  (2) Cross-Encoder x3
    t_y, t_h = ly_k + 4.05, 10.1
    t1_x, t1_w = lx_k + 1.05, 19.3
    t2_x, t2_w = t1_x + t1_w + 1.6, lw_k - 2.1 - t1_w - 1.6

    # Module 1: Alias Hash + bge-m3 Vector Neighborhood + Top-K Grid
    rect(t1_x, t_y, t1_w, t_h, '#F8FBFF', '#9EC0E6', .16, r=.45)
    label(t1_x + t1_w / 2, t_y + 1.35, '1. Alias & Recall' if en else '1. 别名与向量召回', 4.75, ACC_DK, 'bold', 'center')
    vcx, vcy = t1_x + 4.35, t_y + 5.95
    s.circle(vcx, vcy, 2.85, WHITE, '#8AB4E2', .15)
    s.circle(vcx, vcy, 1.85, '#EDF5FE', '#79A8DF', .12)
    sparkle_icon(vcx - .2, vcy, .78, EXEC_C)
    for dx_v, dy_v, col_v in ((-.95, -.75, ACC), (.9, -.65, ACC), (.65, .85, ACC),
                              (-1.95, 1.35, '#B8C8DC'), (2.05, .3, '#B8C8DC')):
        s.circle(vcx + dx_v, vcy + dy_v, .28, col_v)
    # Right side of Module 1: alias chip + 2x2 top-K candidate chips
    gx = t1_x + 8.1
    pill(gx, t_y + 3.65, 'alias $O(1)$' if en else '别名直达', WHITE, ACC_DK, edge_c=ACC, size=4.0, pad=.48, h=1.55)
    cand_tags = (('D01', True), ('D02', True), ('ER', True), ('top8', False))
    for idx_g, (ctag, chi) in enumerate(cand_tags):
        col_i, row_i = idx_g % 2, idx_g // 2
        cx_g = gx + col_i * 5.25
        cy_g = t_y + 5.5 + row_i * 2.1
        rect(cx_g, cy_g, 4.85, 1.75, ACC_PALE if chi else WHITE, ACC if chi else '#C5C1B9', .13, r=.24)
        label(cx_g + 2.42, cy_g + .88, ctag, 3.95, ACC_DK if chi else MUTED, 'bold' if chi else 'sans', 'center')

    route([(t1_x + t1_w, t_y + t_h / 2), (t2_x, t_y + t_h / 2)], ACC, .22, length=.65)

    # Module 2: Catalog-Trained Cross-Encoder x3 (Token Pair + Attention Stack)
    rect(t2_x, t_y, t2_w, t_h, '#F8FBFF', '#9EC0E6', .16, r=.45)
    label(t2_x + t2_w / 2, t_y + 1.35, '2. Matcher $\\times 3$' if en else '2. 目录判别器 $\\times 3$', 4.75, ACC_DK, 'bold', 'center')
    # Token strip: [rho] [choices] [diffs] centered cleanly inside Module 2
    tok_y = t_y + 3.55
    tok_specs = (('$\\rho$', ACC, WHITE, 3.8), ('choices', LEARN_PALE, LEARN_DK, 6.8), ('diffs', AMBER_PALE, EXEC_DK, 5.4))
    tot_tok_w = sum(tw_i for _, _, _, tw_i in tok_specs) + .45 * (len(tok_specs) - 1)
    tx_cur = t2_x + (t2_w - tot_tok_w) / 2
    tok_centers = []
    for t_lbl, t_bg, t_fg, t_w in tok_specs:
        rect(tx_cur, tok_y - .8, t_w, 1.6, t_bg, t_fg if t_bg != ACC else ACC_DK, .12, r=.24)
        label(tx_cur + t_w / 2, tok_y, t_lbl, 3.85, t_fg, 'bold', 'center')
        tok_centers.append(tx_cur + t_w / 2)
        tx_cur += t_w + .45
    # Stacked XLM-R x3 bar
    att_y = t_y + 6.35
    for st_off in (.55, .28, 0.0):
        rect(t2_x + 1.15 + st_off, att_y - .95 - st_off * .42, t2_w - 2.8, 1.85, WHITE, ACC, .13, r=.26)
    for tc_x in tok_centers:
        s.line(tc_x, tok_y + .8, tc_x, att_y - 1.35, '#8AB4E2', .13)
    label(t2_x + t2_w / 2, att_y, 'XLM-R $\\times 3 \\rightarrow p$' if en else '交叉编码 $\\times 3 \\rightarrow p$',
          4.15, INK, 'bold', 'center')
    label(t2_x + t2_w / 2, t_y + 8.85,
          'catalog self-supervised' if en else '目录自监督离线训练',
          4.1, LEARN_DK, 'bold', 'center')

    # Middle row inside Lookup: Calibrated Decision Spectrum (.1, .9)
    sp_y = t_y + t_h + 1.6
    label(lx_k + 1.2, sp_y, '$p$:', 4.6, INK, 'bold')
    bar_lx, bar_lw, bar_lh = lx_k + 4.4, lw_k - 5.6, 2.05
    w_miss = bar_lw * .18
    w_ref = bar_lw * .54
    w_hit = bar_lw - w_miss - w_ref
    rect(bar_lx, sp_y - bar_lh / 2, w_miss, bar_lh, '#E4E1DB', None, r=.25)
    rect(bar_lx + w_miss, sp_y - bar_lh / 2, w_ref, bar_lh, AMBER_PALE, None)
    rect(bar_lx + w_miss + w_ref, sp_y - bar_lh / 2, w_hit, bar_lh, ACC, None, r=.25)
    rect(bar_lx, sp_y - bar_lh / 2, bar_lw, bar_lh, None, '#9E9A92', .14, r=.25)
    s.line(bar_lx + w_miss, sp_y - bar_lh / 2 - .25, bar_lx + w_miss, sp_y + bar_lh / 2 + .25, INK, .18)
    s.line(bar_lx + w_miss + w_ref, sp_y - bar_lh / 2 - .25, bar_lx + w_miss + w_ref, sp_y + bar_lh / 2 + .25, INK, .18)
    label(bar_lx + w_miss / 2, sp_y, '<.1', 3.85, MUTED, 'bold', 'center')
    label(bar_lx + w_miss + w_ref / 2, sp_y,
          '.1  refer / diffs  .9' if en else '.1  歧义确认 / 同名  .9', 3.95, EXEC_DK, 'bold', 'center')
    label(bar_lx + w_miss + w_ref + w_hit / 2, sp_y, '$\\geq$.9', 3.9, WHITE, 'bold', 'center')

    # Bottom row inside Lookup: 2-Way Dispatch (Hit vs Diffs/Refer/Miss)
    dec_y, dec_h = sp_y + 1.85, 5.15
    b1_x, b1_w = lx_k + 1.05, 19.6
    b2_x, b2_w = b1_x + b1_w + 1.25, lw_k - 2.1 - b1_w - 1.25
    route([(bar_lx + w_miss + w_ref + w_hit / 2, sp_y + bar_lh / 2),
           (bar_lx + w_miss + w_ref + w_hit / 2, dec_y - .45),
           (b1_x + b1_w / 2, dec_y - .45),
           (b1_x + b1_w / 2, dec_y)], ACC, .19, length=.55, radius=.25)
    route([(bar_lx + w_miss + w_ref / 2, sp_y + bar_lh / 2),
           (b2_x + b2_w / 2, dec_y)], AMBER, .19, length=.55)

    rect(b1_x, dec_y, b1_w, dec_h, ACC_PALE, ACC, .18, r=.42)
    label(b1_x + b1_w / 2, dec_y + 1.7, 'Hit $(m^r, p, d)$' if en else '唯一命中 $(m^r,p,d)$', 4.75, ACC_DK, 'bold', 'center')
    label(b1_x + b1_w / 2, dec_y + 3.75, 'to snapshot $D_s$' if en else '进入快照 $D_s$ 执行', 4.35, ACC_DK, 'sans', 'center')

    rect(b2_x, dec_y, b2_w, dec_h, AMBER_PALE, AMBER, .16, r=.42)
    label(b2_x + b2_w / 2, dec_y + 1.7, 'Diffs / Refer / Miss' if en else '同名差异 / 确认 / 未中', 4.65, EXEC_DK, 'bold', 'center')
    label(b2_x + b2_w / 2, dec_y + 3.75, 'confirm$\\rightarrow$alias | explore' if en else '确认写别名 / 探索库', 4.25, MUTED, 'sans', 'center')

    # Ambiguous/Miss dashed return lane (lane 1: x = 175.15 up to agent request bus)
    ret_amb_x = 175.15
    route([(b2_x + b2_w, dec_y + dec_h / 2), (ret_amb_x, dec_y + dec_h / 2),
           (ret_amb_x, bus_y), (c_ap, bus_y)],
          AMBER, .2, heads='end', dash=(.55, .35), length=.72, radius=.35)

    # -------------------------------------------------------------------------
    # (E) Bottom-Right: CHECK AND RUN (Step 4) — Snapshot Gate + Compiler + <-> DB
    # -------------------------------------------------------------------------
    EXEC = (131.6, 44.8, 42.6, 32.0)
    ex, ey, ew, eh = EXEC
    card_head(EXEC, 'Check and run' if en else '检查并执行',
              '`REPEATABLE READ` $D_s$' if en else '可重复读快照 $D_s$',
              EXEC_PALE, EXEC_C, INK, EXEC_DK)

    # Step 4 arrow: Lookup Hit -> Check and run
    hit_cx = b1_x + b1_w / 2
    route([(hit_cx, dec_y + dec_h), (hit_cx, ey)], EXEC_C, THIN, length=.88)
    step_badge(hit_cx + 2.9, (ly_k + lh_k + ey) / 2, 4, EXEC_C, r=1.22)

    # Inner dashed container: One Read-Only Transaction Snapshot D_s
    sx_in, sy_in, sw_in, sh_in = ex + 1.05, ey + 4.15, ew - 2.1, 22.85
    rect(sx_in, sy_in, sw_in, sh_in, '#FFFDF9', EXEC_C, .18, r=.48, dash=(.72, .4))
    label(sx_in + sw_in / 2, sy_in + 1.48,
          'One Read-Only Snapshot $D_s$ (stamps $V_s$)' if en else '同一只读事务快照 $D_s$（读取版本 $V_s$）',
          4.7, EXEC_DK, 'bold', 'center')

    # Sub-card 1: Snapshot Condition Gate via H(c, V_s)
    st1_y, st1_h = sy_in + 2.75, 6.75
    rect(sx_in + .85, st1_y, sw_in - 1.7, st1_h, WHITE, '#E2BE8E', .15, r=.38)
    shield_icon(sx_in + 2.65, st1_y + 2.0, 1.08, EXEC_PALE, EXEC_DK)
    label(sx_in + 4.3, st1_y + 1.95,
          '1. Validate $C(m^r)$ at $V_s$' if en else '1. 快照条件门禁 $C(m^r)$', 4.75, INK, 'bold')
    check_mark(sx_in + sw_in - 2.0, st1_y + 1.95, True, ACC, k=.72)
    pill(sx_in + 1.5, st1_y + 4.85,
         '$\\mathcal{H}(c, V_s)$ hit $\\rightarrow O(1)$' if en else '命中 $\\mathcal{H}(c,V_s) \\rightarrow O(1)$',
         ACC_PALE, ACC_DK, edge_c=ACC, size=4.05, pad=.5, h=1.65)
    miss_q_txt = 'miss $\\rightarrow Q_c(D_s)$' if en else '未中 $\\rightarrow Q_c(D_s)$'
    miss_q_w = measure(miss_q_txt, 4.05, 'sans') + .96
    pill(sx_in + sw_in - 1.5 - miss_q_w, st1_y + 4.85,
         miss_q_txt, FACE, INK, edge_c='#C5C1B9', size=4.05, pad=.48, h=1.65, wt='sans')

    # Read arrow from Check outcomes H -> Validate C(m^r)
    h_read_y = st1_y + 2.6
    route([(kx + kw, h_read_y), (sx_in + .85, h_read_y)], REF, .22, dash=(.62, .38), length=.78)

    route([(sx_in + sw_in / 2, st1_y + st1_h), (sx_in + sw_in / 2, st1_y + st1_h + .95)],
          EXEC_C, .2, length=.58)

    # Sub-card 2: Relational & Leak-Free Query Compiler
    st2_y, st2_h = st1_y + st1_h + .95, 11.55
    rect(sx_in + .85, st2_y, sw_in - 1.7, st2_h, WHITE, '#E2BE8E', .15, r=.38)
    pill(sx_in + 1.5, st2_y + 1.8, 'SQL', EXEC_PALE, EXEC_DK, edge_c=EXEC_C, size=4.1, pad=.52, h=1.62)
    label(sx_in + 6.3, st2_y + 1.8,
          '2. Bind & Compile on $D_s$' if en else '2. 绑定参数并编译查询', 4.75, INK, 'bold')

    # Track M: Analytical Metric
    tm_y = st2_y + 4.75
    w_pm = pill(sx_in + 1.5, tm_y, 'Metric' if en else '指标', ACC_PALE, ACC_DK, edge_c=ACC, size=4.0, pad=.48, h=1.58)
    label(sx_in + 2.1 + w_pm, tm_y,
          '$d(q_0(D_s, p))$ · `rev 1` (`\'Y\'`)' if en else '$d(q_0(D_s,p))$ · `rev 1` (`\'Y\'`)',
          4.45, INK, width=sw_in - w_pm - 3.6)

    s.line(sx_in + 1.5, st2_y + 6.55, sx_in + sw_in - 1.5, st2_y + 6.55, RULE, .12)

    # Track F: Predictive Feature with Labeled Point-in-Time Anti-Leakage Window!
    tf_y = st2_y + 8.95
    w_pf = pill(sx_in + 1.5, tf_y, 'Feature' if en else '特征', EXEC_PALE, EXEC_DK, edge_c=EXEC_C, size=4.0, pad=.46, h=1.58)
    label(sx_in + 2.0 + w_pf, tf_y, '$(u_i, t_i)$:', 4.35, INK, 'bold')
    # Mini anti-leakage timeline: [t_i - w ======o==o| t_i]  x > t_i
    tl_x1 = sx_in + 19.6
    tl_x2 = sx_in + sw_in - 1.7
    tl_cut = tl_x1 + (tl_x2 - tl_x1) * .66
    s.line(tl_x1, tf_y, tl_x2, tf_y, '#B5B1A8', .18)
    rect(tl_x1 + 1.2, tf_y - .85, tl_cut - (tl_x1 + 1.2), 1.7, MAINT_PALE, MAINT_C, .14, r=.22)
    for px_dot in (.28, .58, .84):
        s.circle(tl_x1 + 1.2 + (tl_cut - tl_x1 - 1.2) * px_dot, tf_y, .26, MAINT_DK)
    s.line(tl_cut, tf_y - 1.25, tl_cut, tf_y + 1.25, EXEC_DK, .32)
    label(tl_cut, tf_y - 1.9, '$\\leq t_i$', 3.85, MAINT_DK, 'bold', 'center')
    check_mark(tl_cut + (tl_x2 - tl_cut) * .52, tf_y, False, RED, k=.58)

    # Verified Answer / Feature Output Bar + Upward Return Arrow (lane 2: x = 176.3)
    ans_y, ans_h = sy_in + sh_in + .75, 3.45
    rect(sx_in, ans_y, sw_in, ans_h, EXEC_PALE, EXEC_C, .18, r=.42)
    check_mark(sx_in + 1.8, ans_y + ans_h / 2, True, EXEC_DK, k=.76)
    label(sx_in + 3.3, ans_y + ans_h / 2,
          'Verified answer / leak-free features' if en else '返回经核验答案 ／ 防穿越特征表',
          4.7, EXEC_DK, 'bold')

    ret_ans_x = 176.25
    ag_p_right = 132.4 + 41.2
    route([(sx_in + sw_in, ans_y + ans_h / 2), (ret_ans_x, ans_y + ans_h / 2),
           (ret_ans_x, ag_y + ag_h / 2), (ag_p_right, ag_y + ag_h / 2)],
          EXEC_C, .25, heads='end', length=.82, radius=.45)

    # =========================================================================
    # 3. Bottom Band: ETL Job (Step 5) and PostgreSQL Database with Snapshot D_s
    # =========================================================================
    db_y, db_h = 81.5, 12.5
    ETL = (1.6, db_y + .3, 22.0, db_h - .6)
    tx, ty, tw_e, th_e = ETL
    for off in (.85, .42, 0.0):
        rect(tx + off, ty - off, tw_e - .85, th_e, WHITE, '#B5B1A8', .14, r=.45)
    label(tx + 1.15, ty + 2.8, 'ETL job' if en else 'ETL 作业', TITLE, INK, 'bold')
    label(tx + 1.15, ty + 6.0, 'loads `item`' if en else '追加 `item`', 4.85, MAINT_DK, 'bold')
    label(tx + 1.15, ty + 8.9, "history (`17,'N'`)" if en else "历史行 (`17,'N'`)", 4.5, MUTED)

    DB = (28.4, db_y, 146.4, db_h)
    bx, by, bw, bh_d = DB
    d_slab = 1.0
    s.poly([(bx, by), (bx + d_slab, by - d_slab), (bx + bw + d_slab, by - d_slab), (bx + bw, by)],
           '#F2F0EC', '#B8B4AC', .12)
    s.poly([(bx + bw, by), (bx + bw + d_slab, by - d_slab), (bx + bw + d_slab, by + bh_d - d_slab), (bx + bw, by + bh_d)],
           '#E6E3DD', '#B8B4AC', .12)
    rect(bx, by, bw, bh_d, FACE, '#B8B4AC', .18, r=.55)

    # Step 5 arrow: ETL -> Database
    etl_ay = ty + th_e / 2
    route([(tx + tw_e - .85, etl_ay), (bx, etl_ay)], MAINT_C, THICK, length=.9)
    step_badge((tx + tw_e - .85 + bx) / 2, etl_ay - 2.6, 5, MAINT_C, r=1.28)

    # Left DB Header + Transactional Trigger Metadata Chips
    label(bx + 1.3, by + 2.65, 'Database', TITLE, INK, 'bold')
    pill(bx + 1.3, by + 6.15, '`mavra_versions` $V(T)$', WHITE, MAINT_DK, edge_c=MAINT_C, size=4.0, pad=.48, h=1.68, wt='sans')
    pill(bx + 1.3, by + 9.05, '`etl_batch_log` $\\Delta T$', WHITE, EXEC_DK, edge_c=AMBER, size=4.0, pad=.48, h=1.68, wt='sans')

    ctop, ch_in = by + .85, bh_d - 1.7

    # 1) item table (with schema column headers + current/new rows)
    ix, iw = bx + 23.2, 44.2
    rect(ix, ctop, iw, ch_in, WHITE, AMBER, .18, r=.4)
    rect(ix + .12, ctop + .12, iw - .24, 2.25, AMBER_PALE, None, r=.3)
    label(ix + .85, ctop + 1.22, '`item`', 5.0, INK, 'bold')
    mini_step(ix + iw - 12.6, ctop + 1.22, 5, MAINT_C, r=.76)
    label(ix + iw - .85, ctop + 1.22, 'v0 $\\rightarrow$ v1', 4.65, EXEC_DK, 'bold', 'right')
    label(ix + .85, ctop + 3.65, '`i_item_sk  i_category    i_is_current`', 4.05, MUTED)
    s.line(ix + .65, ctop + 4.75, ix + iw - .65, ctop + 4.75, RULE, .12)
    label(ix + .85, ctop + 6.15, "`17         'Electronics' 'Y'`", 4.3, INK)
    label(ix + iw - .85, ctop + 6.15, 'current' if en else '当前行', 4.25, MUTED, 'sans', 'right')
    rect(ix + .45, ctop + 7.45, iw - .9, 2.65, AMBER_PALE, None, r=.24)
    label(ix + .85, ctop + 8.8, "`17         'Electronics' 'N'`", 4.3, INK)
    label(ix + iw - .85, ctop + 8.8, 'new $\\Delta T$' if en else '新增 $\\Delta T$', 4.25, EXEC_DK, 'bold', 'right')

    # 2) store_sales & date_dim tables (clean 1.1 mm gaps before snapshot D_s)
    for tx_c, tw_c, tname_c, tcols_c in (
        (ix + iw + 1.1, 17.5, '`store_sales`', '`K, date, paid`'),
        (ix + iw + 19.7, 15.2, '`date_dim`', '`sk, yr, moy`'),
    ):
        rect(tx_c, ctop, tw_c, ch_in, WHITE, EDGE, .14, r=.4)
        rect(tx_c + .12, ctop + .12, tw_c - .24, 2.25, TOP, None, r=.3)
        label(tx_c + .7, ctop + 1.22, tname_c, 4.65, INK, 'bold')
        label(tx_c + tw_c - .65, ctop + 1.22, 'v0', 4.2, MUTED, 'sans', 'right')
        label(tx_c + .7, ctop + 3.65, tcols_c, 3.95, MUTED)
        for r_i in range(3):
            rect(tx_c + .75, ctop + 5.15 + r_i * 1.75, tw_c - 1.5, .85, '#E4E1DB', None, r=.18)

    # 3) Snapshot D_s aligned directly beneath Check and run
    sn_x, sn_w = ex + .4, ew - .8
    rect(sn_x, ctop, sn_w, ch_in, WHITE, None, r=.42)
    rect(sn_x + .12, ctop + .12, sn_w - .24, 2.25, EXEC_PALE, None, r=.32)
    rect(sn_x, ctop, sn_w, ch_in, None, EXEC_C, .2, r=.42, dash=(.78, .42))
    label(sn_x + .9, ctop + 1.22, 'snapshot $D_s$' if en else '一致性快照 $D_s$', 4.85, EXEC_DK, 'bold')
    label(sn_x + sn_w - .85, ctop + 1.22, 'stamps $V_s$ · RO' if en else '版本 $V_s$ · 只读', 4.25, EXEC_DK, 'sans', 'right')
    slice_names = ('`item`@$v_s$', '`sales`@$v_s$', '`date`@$v_s$')
    mini_w = (sn_w - 2.0 - 1.4) / 3
    for k_m, sl_lbl in enumerate(slice_names):
        mx_s = sn_x + 1.0 + k_m * (mini_w + .7)
        rect(mx_s, ctop + 3.05, mini_w, ch_in - 3.85, FACE, '#C9C4BC', .12, r=.25)
        rect(mx_s + .1, ctop + 3.15, mini_w - .2, 1.85, '#F5E8D3', None, r=.18)
        label(mx_s + mini_w / 2, ctop + 4.08, sl_lbl, 3.75, EXEC_DK, 'bold', 'center')
        for r_j in range(2):
            rect(mx_s + .65, ctop + 5.75 + r_j * 1.65, mini_w - 1.3, .7, '#DEDAD2', None, r=.15)

    # =========================================================================
    # 4. Prominent Bidirectional Database Interaction Arrows (<->)
    # =========================================================================
    maint_db_x = ix + iw / 2
    route([(maint_db_x, qy + qh), (maint_db_x, ctop)],
          MAINT_C, .32, heads='both', dash=(.72, .4), length=1.02)
    label(maint_db_x + 1.4, 79.15,
          'stamps $V(T) \\leftrightarrow \\Delta T$ probes' if en else '读版本戳 $V(T) \\leftrightarrow \\Delta T$ 探针',
          4.45, MAINT_DK, 'bold')

    snap_cx = sn_x + sn_w / 2
    route([(snap_cx, ey + eh), (snap_cx, ctop)],
          EXEC_C, .34, heads='both', dash=(.72, .4), length=1.06)
    label(snap_cx + 1.4, 79.15,
          'SQL $q(D_s) \\leftrightarrow$ rows' if en else '快照查询 $q(D_s) \\leftrightarrow$ 结果',
          4.45, EXEC_DK, 'bold')


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
