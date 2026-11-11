"""MAVRA system overview (Figure 2): shared knowledge base and four runtime components.

Double column (178.0 mm wide, 89.0 mm high).
Layout and visual abstraction:
  - Top row: Concurrent data agents (Agent 1 first session, Agent 2 before write,
    ..., Agent N after write, and Predictive agent P).
  - Center: Knowledge base storing ONLY shared domain knowledge and validity state:
      (1) Definitions catalog: m^r = (B, I, C, E, r) for metrics, features, and joins
      (2) Check outcomes H: condition verdicts indexed by (id(c), V(dep(c)))
  - Left: Publish — takes an Agent 1 session log UI card, runs visual Extract and
    Verify (G1-G7 replay) stages, produces executable definition m^0, and passes it
    into the Knowledge base (steps 1-2).
  - Top-right: Lookup — abstract visual pipeline (Alias & Recall -> Catalog Matcher)
    synced from catalog definitions, branching cleanly to Hit (m^r, p, d) or Diffs/Miss (step 3).
  - Bottom-right: Check and run — executes within one read-only snapshot D_s:
    (1) Validate C(m^r) via H at V_s, (2) Bind (p, d) or cutoff (u_i, <= t_i) & run SQL,
    connected by a prominent bidirectional arrow (<->) to snapshot D_s in Database and
    returning verified answers/features to the agents (step 4).
  - Bottom-center: Maintain — abstract 3-stage visual pipeline (1. Version Filter ->
    2. Delta Check on Delta T -> 3. Repair or Retire), bidirectional arrow (<->) with
    Database, and write-back arrow (step 6) to Knowledge base after ETL write (step 5).
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
W, H = style.TEXTWIDTH, 89.2

TITLE, BODY, SMALL, TINY, STEP = 7.2, 6.3, 5.7, 5.25, 6.2
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

    def card_head(b, title_txt, sub_txt, band_fill, edge_c=EDGE, title_c=INK, sub_c=MUTED, bh=3.6):
        x, y, w, h = b
        rect(x, y, w, h, WHITE, edge_c, .2, r=.65)
        rect(x + .12, y + .12, w - .24, bh, band_fill, None, r=.55)
        rect(x + .12, y + .12 + bh / 2, w - .24, bh / 2, band_fill, None)
        yc = y + .12 + bh / 2
        tw = label(x + 1.3, yc, title_txt, TITLE, title_c, 'bold')
        if sub_txt:
            label(x + w - 1.2, yc, sub_txt, TINY, sub_c, 'sans', 'right', width=w - tw - 2.6)

    def node3d(b, d=1.1, edge_c='#B8B4AC'):
        x, y, w, h = b
        s.poly([(x, y), (x + d, y - d), (x + w + d, y - d), (x + w, y)], '#F2F0EC', edge_c, .12)
        s.poly([(x + w, y), (x + w + d, y - d), (x + w + d, y + h - d), (x + w, y + h)],
               '#E6E3DD', edge_c, .12)
        rect(x, y, w, h, WHITE, edge_c, .18, r=.55)

    def step_badge(x, yc, n, color, r=1.45):
        s.circle(x, yc, r, color)
        label(x, yc, str(n), STEP, WHITE, 'bold', 'center')

    def mini_step(x, yc, n, color, r=1.0):
        s.circle(x, yc, r, color)
        label(x, yc, str(n), 4.9, WHITE, 'bold', 'center')

    def check_mark(x, yc, ok, c=None, k=1.0):
        if ok:
            s.poly([(x - .58 * k, yc + .02 * k), (x - .14 * k, yc + .46 * k), (x + .62 * k, yc - .52 * k)],
                   None, c or ACC, .26, closed=False)
        else:
            s.line(x - .46 * k, yc - .46 * k, x + .46 * k, yc + .46 * k, c or RED, .26)
            s.line(x - .46 * k, yc + .46 * k, x + .46 * k, yc - .46 * k, c or RED, .26)

    def pill(x, yc, txt, fill_c, text_c=WHITE, edge_c=None, size=5.0, pad=1.1, h=2.05, wt='bold'):
        w = measure(txt, size, wt) + 2 * pad
        rect(x, yc - h / 2, w, h, fill_c, edge_c, .14 if edge_c else 0, r=.42)
        label(x + w / 2, yc, txt, size, text_c, wt, 'center')
        return w

    def person_icon(x, yc, c='#8A867E'):
        s.circle(x, yc - .65, .68, c)
        rect(x - 1.05, yc + .18, 2.1, 1.18, c, None, r=.58)

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
        check_mark(cx, cy + .05 * r, True, stroke_c, k=.72)

    def key_icon(x, yc, c=ACC_DK):
        s.circle(x + .55, yc, .48, None, c, .2)
        s.line(x + 1.03, yc, x + 2.15, yc, c, .2)
        s.line(x + 1.65, yc, x + 1.65, yc + .42, c, .2)
        s.line(x + 2.05, yc, x + 2.05, yc + .42, c, .2)

    def join_icon(x, yc, c=ACC_DK):
        rect(x, yc - .52, .95, 1.04, ACC_PALE, c, .15, r=.15)
        rect(x + 1.25, yc - .52, .95, 1.04, WHITE, c, .15, r=.15)
        s.line(x + .95, yc, x + 1.25, yc, c, .2)

    def dom_icon(x, yc, c=MAINT_C):
        rect(x, yc - .52, 2.1, 1.04, MAINT_PALE, c, .15, r=.2)
        for dx in (.48, 1.05, 1.62):
            s.circle(x + dx, yc, .18, c)

    def patch_badge(cx, cy, r, fill_c, stroke_c):
        rect(cx - r, cy - r, 2 * r, 2 * r, fill_c, stroke_c, .18, r=.45)
        s.line(cx - .52 * r, cy, cx + .52 * r, cy, stroke_c, .26)
        s.line(cx, cy - .52 * r, cx, cy + .52 * r, stroke_c, .26)

    # =========================================================================
    # 1. Top Row: Data Agents (Analytical 1, 2, ..., N and Predictive P)
    # =========================================================================
    ag_y, ag_h = 1.8, 8.8
    ag_specs = (
        (1.6, 37.8, 'Agent 1' if en else '智能体 1',
         'first session' if en else '首次会话', None,
         'ask:' if en else '问：', 'Jan. electronics revenue?' if en else '1 月电子品类营业额？',
         'explores DB, answer verified' if en else '探索数据库，答案经核验', LEARN),
        (45.8, 37.8, 'Agent 2' if en else '智能体 2',
         'before' if en else '写入前', 5,
         'ask:' if en else '问：', 'highest-revenue month?' if en else '电子营业额最高月份？',
         'reuses monthly aggregates' if en else '直接复用月度聚合', ACC_DK),
        (90.0, 37.8, 'Agent N' if en else '智能体 N',
         'after' if en else '写入后', 5,
         'ask:' if en else '问：', 'Sep. revenue vs. last year?' if en else '9 月营业额同比？',
         'reuses it after repair' if en else '维护修复后安全复用', MAINT_DK),
        (134.2, 39.2, 'Predictive agent P' if en else '预测智能体 P',
         '', None,
         'ask:' if en else '问：', 'will a customer churn?' if en else '客户是否会流失？',
         'reuses customer feature' if en else '跨任务复用客户特征', EXEC_DK),
    )
    for ax, aw, aname, awhen, astep, aask, aq, anote, acol in ag_specs:
        node3d((ax, ag_y, aw, ag_h))
        person_icon(ax + 2.2, ag_y + 2.1, acol if aname.endswith('1') else '#7E7A72')
        label(ax + 4.0, ag_y + 2.1, aname, BODY, INK, 'bold')
        if awhen:
            rx_end = ax + aw - 1.1
            if astep is not None:
                mini_step(rx_end - 1.0, ag_y + 2.1, astep, MAINT_C, r=.95)
                rx_end -= 2.3
            label(rx_end, ag_y + 2.1, awhen, TINY, MAINT_DK if 'after' in awhen or '后' in awhen else MUTED,
                  'bold' if ('after' in awhen or '后' in awhen) else 'sans', 'right')
        w_ask = label(ax + 1.3, ag_y + 5.0, aask, SMALL, ACC_DK, 'bold')
        label(ax + 1.3 + w_ask + (.7 if en else 0), ag_y + 5.0, aq, SMALL, INK,
              width=aw - 2.3 - w_ask)
        label(ax + 1.3, ag_y + 7.3, anote, TINY, acol, width=aw - 2.2)

    dots_cx = (45.8 + 37.8 + 90.0) / 2
    for k in (-1, 0, 1):
        s.circle(dots_cx + 1.35 * k, ag_y + ag_h / 2, .35, '#9E9A92')

    # =========================================================================
    # 2. Middle Band: MAVRA Shared Layer Container
    # =========================================================================
    my, mh = 13.6, 59.8
    rect(1.2, my, W - 2.4, mh, FIELD, '#B9D4F2', .22, r=1.2)
    rect(2.8, my + 1.0, .65, 2.1, ACC)
    label(4.1, my + 2.05, 'MAVRA', TITLE + .2, ACC_DK, 'bold')

    # -------------------------------------------------------------------------
    # (A) Left Component: PUBLISH (Steps 1-2) — Session Log -> Extract -> Verify -> m^0
    # -------------------------------------------------------------------------
    PUB = (2.6, 17.2, 40.0, 38.2)
    px, py, pw, ph = PUB
    card_head(PUB, 'Publish' if en else '发布',
              'session to definition' if en else '会话转定义',
              LEARN_PALE, LEARN, INK, LEARN_DK)

    # Step 1 arrow: Agent 1 -> Publish
    a1_x = px + 18.0
    route([(a1_x, ag_y + ag_h), (a1_x, py)], LEARN, THIN, length=1.0)
    step_badge(a1_x + 2.8, 14.0, 1, LEARN)

    # 1) Input: Sleek Agent Session Log UI window
    lx, ly, lw, lh = px + 1.4, py + 4.5, pw - 2.8, 11.3
    rect(lx, ly, lw, lh, '#FAF9FC', '#B9B0D4', .16, r=.5)
    rect(lx + .1, ly + .1, lw - .2, 2.45, '#EAE6F3', None, r=.4)
    rect(lx + .1, ly + 1.25, lw - .2, 1.3, '#EAE6F3', None)
    for idx_d, dc in enumerate(('#D98276', '#E0B25B', '#68A884')):
        s.circle(lx + 1.1 + idx_d * 1.15, ly + 1.3, .34, dc)
    label(lx + 4.8, ly + 1.3, 'Agent session log' if en else '智能体会话日志', TINY, LEARN_DK, 'bold')
    pill(lx + lw - 9.8 if en else lx + lw - 8.6, ly + 1.3,
         'verified' if en else '已核验', LEARN, WHITE, size=4.55, pad=.8, h=1.65)

    log_rows = (
        ('Q', LEARN_PALE, LEARN_DK, '"Jan. electronics rev.?"' if en else '"1 月电子品类营业额？"'),
        ('SQL', TOP, INK, 'trace + schema/col probes' if en else '查询轨迹 + 表列探查记录'),
        ('Ans', ACC_PALE, ACC_DK, '`2,754,299.60`' if en else '核验结果 `2,754,299.60`'),
    )
    for idx_r, (rtag, rbg, rfg, rtxt) in enumerate(log_rows):
        ry = ly + 3.95 + idx_r * 2.75
        tw_p = pill(lx + 1.0, ry, rtag, rbg, rfg, edge_c=rfg, size=4.5, pad=.75, h=1.7)
        label(lx + 1.6 + tw_p, ry, rtxt, TINY, INK, width=lw - tw_p - (4.2 if idx_r == 2 else 2.2))
        if idx_r == 2:
            check_mark(lx + lw - 1.5, ry, True, ACC, k=.85)

    mid_px = px + pw / 2
    route([(mid_px, ly + lh), (mid_px, ly + lh + 1.5)], LEARN, THIN, length=.72)

    # 2) Processing Stage 1: Extract (LLM icon + core vs param visual)
    ex_y, ex_h = ly + lh + 1.5, 6.4
    rect(lx, ex_y, lw, ex_h, WHITE, LEARN, .16, r=.48)
    rect(lx + .8, ex_y + .9, 4.6, 4.6, LEARN_PALE, None, r=.45)
    sparkle_icon(lx + 3.1, ex_y + 3.2, 1.55, LEARN)
    label(lx + 6.2, ex_y + 2.0, 'Extract & derive' if en else '结构提取与条件推导', SMALL, INK, 'bold')
    w_c1 = pill(lx + 6.2, ex_y + 4.55, 'core B, I + conds C' if en else '固定 B, I + 条件 C',
                LEARN_PALE, LEARN_DK, edge_c=LEARN, size=4.55, pad=.75, h=1.85)
    rx_p = lx + 6.8 + w_c1
    pw_p = lw - (rx_p - lx) - .9
    rect(rx_p, ex_y + 4.55 - .92, pw_p, 1.85, WHITE, LEARN, .14, r=.4, dash=(.55, .35))
    label(rx_p + pw_p / 2, ex_y + 4.55, 'param $p_0$' if en else '参数 $p_0$', 4.55, LEARN_DK, 'bold', 'center')

    route([(mid_px, ex_y + ex_h), (mid_px, ex_y + ex_h + 1.45)], LEARN, THIN, length=.72)

    # 3) Processing Stage 2: Verify (Shield G1-G7 + replay match visual)
    vy, vh = ex_y + ex_h + 1.45, 6.4
    rect(lx, vy, lw, vh, WHITE, LEARN, .16, r=.48)
    rect(lx + .8, vy + .9, 4.6, 4.6, ACC_PALE, None, r=.45)
    shield_icon(lx + 3.1, vy + 3.2, 1.55, WHITE, ACC_DK)
    label(lx + 6.2, vy + 2.0, 'Verify gates G1–G7' if en else '准入验证门禁 G1–G7', SMALL, INK, 'bold')
    label(lx + 6.2, vy + 4.55,
          'grain/joins + replay `= Ans`' if en else '粒度连接 + 编译重放核验',
          4.8, ACC_DK, 'bold', width=lw - 9.2)
    check_mark(lx + lw - 1.6, vy + 4.55, True, ACC, k=.9)

    route([(mid_px, vy + vh), (mid_px, vy + vh + 1.45)], LEARN, THIN, length=.72)

    # 4) Output Card: Executable Definition m^0 = (B, I, C, E, 0)
    oy, oh = vy + vh + 1.45, 4.35
    rect(lx, oy, lw, oh, LEARN_PALE, LEARN_DK, .2, r=.48)
    pill(lx + .9, oy + oh / 2, 'out' if en else '输出', LEARN_DK, WHITE, size=4.55, pad=.72, h=1.85)
    label(lx + 7.2, oy + oh / 2, 'Definition $m^0$' if en else '可执行定义 $m^0$', SMALL, LEARN_DK, 'bold')
    bx_cur = lx + lw - 15.2
    for f_let, f_col in (('B', LEARN_DK), ('I', ACC_DK), ('C', MAINT_DK), ('E', SLATE)):
        bx_cur += pill(bx_cur, oy + oh / 2, f_let, WHITE, f_col, edge_c=f_col, size=4.55, pad=.65, h=1.8) + .45

    # -------------------------------------------------------------------------
    # (B) Center: KNOWLEDGE BASE (Definitions + Check outcomes H ONLY!)
    # -------------------------------------------------------------------------
    KB = (46.8, 17.2, 82.4, 38.2)
    kx, ky, kw, kh = KB
    rect(kx + .8, ky + .8, kw, kh, SIDE, EDGE, .12, r=.7)
    box(KB, WHITE, ACC, .22, r=.65)
    rect(kx, ky, kw, 3.6, ACC, None, r=.65)
    rect(kx, ky + 1.8, kw, 1.8, ACC, None)
    tw_kb = label(kx + 1.5, ky + 1.8, 'Knowledge base' if en else '知识库', TITLE, WHITE, 'bold')
    label(kx + kw - 1.4, ky + 1.8,
          'shared definitions & check outcomes' if en else '跨智能体共享的可执行定义与检查结果',
          TINY, WHITE, 'sans', 'right', width=kw - tw_kb - 3.0)

    # --- Sub-panel 1 (Left inside KB): Definitions Catalog ---
    dx, dy, dw, dh = kx + 1.3, ky + 4.5, 46.8, kh - 5.7
    label(dx + .2, dy + 1.0, 'Definitions' if en else '计算定义目录', BODY, ACC_DK, 'bold')
    label(dx + dw - .2, dy + 1.0, '$m^r = (B, I, C, E, r)$', TINY, MUTED, 'sans', 'right')

    # Compact catalog directory card (top of Definitions)
    cat_y, cat_h = dy + 2.35, 11.3
    rect(dx, cat_y, dw, cat_h, FACE, '#C8C4BC', .15, r=.45)
    cat_entries = (
        ('`join:item|store_sales`', 'rev 0 $\\rightarrow$ 1' if en else '修订 0 $\\rightarrow$ 1', True),
        ('`metric:Store revenue`', 'D01 net / D02 gross' if en else 'D01 扣券 / D02 券前', False),
        ('`metric:Return rate`', 'metric' if en else '分析指标', False),
        ('`feature:spend_90d`', 'entity feature' if en else '预测特征', False),
    )
    cat_ys = []
    for idx_c, (ckey, cmeta, is_join) in enumerate(cat_entries):
        ry = cat_y + 1.5 + idx_c * 2.7
        if idx_c > 0:
            s.line(dx + .8, ry - 1.35, dx + dw - .8, ry - 1.35, WHITE, .28)
        label(dx + 1.0, ry, ckey, 5.1, INK, width=dw - 17.5)
        if is_join:
            label(dx + dw - 1.0, ry, cmeta, 4.85, MAINT_DK, 'bold', 'right')
        else:
            label(dx + dw - 1.0, ry, cmeta, 4.8, ACC_DK if 'D01' in cmeta else MUTED,
                  'bold' if 'D01' in cmeta else 'sans', 'right')
        cat_ys.append(ry)

    # Featured expanded definition card (bottom of Definitions)
    mx, my_card, mw_card, mh_card = dx, cat_y + cat_h + 1.15, dw, dh - (cat_h + 3.5)
    rect(mx, my_card, mw_card, mh_card, WHITE, ACC, .2, r=.48)
    rect(mx + .12, my_card + .12, mw_card - .24, 2.85, ACC_PALE, None, r=.38)
    label(mx + 1.0, my_card + 1.52, '`metric:Electronics revenue`', 5.25, INK, 'bold')
    mini_step(mx + mw_card - 1.4, my_card + 1.52, 6, MAINT_C, r=.86)
    label(mx + mw_card - 2.55, my_card + 1.52, '$\\rightarrow$ 1', 4.85, MAINT_DK, 'bold', 'right')
    mini_step(mx + mw_card - 7.05, my_card + 1.52, 2, LEARN, r=.86)
    label(mx + mw_card - 8.2, my_card + 1.52, 'rev 0', 4.85, LEARN_DK, 'bold', 'right')

    f_rows = (
        ('B', LEARN_DK, LEARN_PALE,
         'Electronics sales, net paid' if en else '电子品类销售额（扣券实付口径）'),
        ('I', ACC_DK, ACC_PALE,
         '`store_sales` · `SUM(ss_net_paid)` + `join`' if en else '`store_sales` · `SUM(ss_net_paid)` + 连接引用'),
        ('C', MAINT_DK, MAINT_PALE, None),
        ('E', SLATE, TOP,
         'session trace, answer, stamps $V$' if en else '来源会话、核验答案与基线版本 $V$'),
    )
    row_ys = []
    for idx_f, (ftag, fcol, fbg, ftxt) in enumerate(f_rows):
        ry = my_card + 4.45 + idx_f * 3.1
        pill(mx + 1.0, ry, ftag, fbg, fcol, edge_c=fcol, size=4.55, pad=.7, h=1.78)
        if ftxt is not None:
            label(mx + 4.4, ry, ftxt, 5.0, INK, width=mw_card - 5.4)
        else:
            key_icon(mx + 4.6, ry, ACC_DK)
            join_icon(mx + 8.0, ry, ACC_DK)
            dom_icon(mx + 11.4, ry, MAINT_C)
            label(mx + 14.5, ry,
                  'refs by `id(c)` to outcomes $\\mathcal{H}$' if en else '按签名 `id(c)` 引用共享检查结果',
                  4.95, INK, width=mw_card - 15.5)
        row_ys.append(ry)

    # Step 2 thick arrow: Publish Output Card -> Knowledge base
    step2_y = oy + oh / 2
    route([(px + pw, step2_y), (kx, step2_y)], LEARN, THICK, length=1.0)
    step_badge((px + pw + kx) / 2, step2_y - 2.6, 2, LEARN)

    # --- Sub-panel 2 (Right inside KB): Shared Check Outcomes H ---
    hx, hy, hw, hh = dx + dw + 2.8, dy, kx + kw - 1.3 - (dx + dw + 2.8), dh
    label(hx + .2, hy + 1.0, 'Check outcomes $\\mathcal{H}$' if en else '共享检查结果 $\\mathcal{H}$', BODY, ACC_DK, 'bold')

    hc_y, hc_h = hy + 2.35, hh - 2.35
    rect(hx, hc_y, hw, hc_h, '#FAFCFE', '#9BBCE0', .18, r=.48)
    rect(hx + .12, hc_y + .12, hw - .24, 2.65, '#E6F0FB', None, r=.38)
    label(hx + hw / 2, hc_y + 1.42, 'key: $(\\mathrm{id}(c), V(\\mathrm{dep}(c)))$', 4.85, ACC_DK, 'bold', 'center')

    h_items = (
        ('key', '`date_dim` @v0', True, '×3', None),
        ('join', '`sales` $\\rightarrow$ `date` @v0', True, None, None),
        ('key', '`item` @v0', True, None, None),
        ('key', '`item` @v1', False, None, 6),
        ('key', "`item` (`'Y'`) @v1", True, None, 6),
    )
    h_ys = []
    for idx_h, (hkind, htxt, hok, hshare, hstep) in enumerate(h_items):
        ry = hc_y + 4.75 + idx_h * 5.02
        bg = WHITE if hok else RED_PALE
        ec = '#D2DFEE' if hok else '#E6A89E'
        if hstep == 6 and hok:
            bg, ec = MAINT_PALE, '#8BCAC1'
        rect(hx + .9, ry - 1.82, hw - 1.8, 3.64, bg, ec, .14, r=.38)
        if hkind == 'key':
            key_icon(hx + 1.55, ry, ACC_DK if hok else RED)
        else:
            join_icon(hx + 1.55, ry, ACC_DK)
        label(hx + 4.3, ry, htxt, 4.9, INK if hok else RED, width=hw - 10.4)
        if hshare:
            pill(hx + hw - 7.7, ry, hshare, ACC_PALE, ACC_DK, edge_c=ACC, size=4.35, pad=.52, h=1.62)
            check_mark(hx + hw - 2.15, ry, True, ACC, k=.78)
        elif hstep:
            check_mark(hx + hw - 4.35, ry, hok, MAINT_DK if hok else RED, k=.78)
            mini_step(hx + hw - 2.05, ry, hstep, MAINT_C, r=.86)
        else:
            check_mark(hx + hw - 2.15, ry, hok, ACC, k=.78)
        h_ys.append(ry)

    # Clean orthogonal key-reference connectors inside Knowledge base (NO diagonal crossings!)
    ch_x1 = dx + dw + .95
    ch_x2 = dx + dw + 1.85
    # 1) Row I -> join:item|store_sales (lane ch_x1)
    route([(mx + mw_card, row_ys[1]), (ch_x1, row_ys[1]), (ch_x1, cat_ys[0]), (dx + dw, cat_ys[0])],
          REF, .18, length=.62, radius=.35)
    # 2) Store revenue -> date_dim @v0 (lane ch_x2)
    route([(dx + dw, cat_ys[1]), (ch_x2, cat_ys[1]), (ch_x2, h_ys[0]), (hx + .9, h_ys[0])],
          REF, .18, length=.62, radius=.35)
    # 3) Row C -> item @v0 (orthogonal step via ch_x2)
    route([(mx + mw_card, row_ys[2]), (ch_x2, row_ys[2]), (ch_x2, h_ys[2]), (hx + .9, h_ys[2])],
          REF, .18, length=.62, radius=.35)

    # -------------------------------------------------------------------------
    # (C) Bottom-Left+Center: MAINTAIN (Step 6) — 3 Visual Stage Cards
    # -------------------------------------------------------------------------
    MAINT = (2.6, 57.8, 126.6, 14.2)
    qx, qy, qw, qh = MAINT
    rect(qx, qy, qw, qh, WHITE, MAINT_C, .2, r=.65)
    rect(qx + .12, qy + .12, 20.6, qh - .24, MAINT_PALE, None, r=.55)
    rect(qx + 10.4, qy + .12, 10.3, qh - .24, MAINT_PALE, None)
    label(qx + 1.5, qy + 4.5, 'Maintain' if en else '维护', TITLE, INK, 'bold')
    label(qx + 1.5, qy + 7.9, 'after writes:' if en else '数据写入后：', SMALL, MAINT_DK, 'bold')
    label(qx + 1.5, qy + 10.7, 'validate & repair' if en else '增量检验与修复', TINY, MAINT_DK)

    sc_y, sc_h = qy + 1.15, qh - 2.3
    s1_x, s1_w = qx + 22.0, 31.8
    s2_x, s2_w = s1_x + s1_w + 3.2, 31.8
    s3_x, s3_w = s2_x + s2_w + 3.2, qw - (22.0 + 31.8 * 2 + 6.4) - 1.3

    # Stage 1: Version Filter & Shared Reuse
    rect(s1_x, sc_y, s1_w, sc_h, '#FAFCFC', '#B6DDD8', .16, r=.48)
    pill(s1_x + 1.0, sc_y + 2.05, '1', MAINT_C, WHITE, size=4.55, pad=.65, h=1.72)
    label(s1_x + 3.8, sc_y + 2.05, 'Version Filter' if en else '版本筛选与共享', SMALL, INK, 'bold')
    rect(s1_x + 1.1, sc_y + 4.1, 13.4, 3.75, FACE, '#CFCBC4', .14, r=.35)
    label(s1_x + 7.8, sc_y + 5.98, '`date` v0: skip' if en else '`date` v0 免检', 4.6, MUTED, 'sans', 'center')
    rect(s1_x + 15.3, sc_y + 4.1, 15.4, 3.75, AMBER_PALE, AMBER, .16, r=.35)
    label(s1_x + 23.0, sc_y + 5.98, '`item` v0$\\rightarrow$1', 4.6, EXEC_DK, 'bold', 'center')
    label(s1_x + s1_w / 2, sc_y + 9.95,
          'skip unchanged; share $\\mathcal{H}$' if en else '跳过未变表；跨定义共享 $\\mathcal{H}$',
          TINY, MAINT_DK, 'sans', 'center')

    route([(s1_x + s1_w, sc_y + sc_h / 2), (s2_x, sc_y + sc_h / 2)], MAINT_C, .24, length=.8)

    # Stage 2: Incremental Delta Check on Delta T
    rect(s2_x, sc_y, s2_w, sc_h, '#FAFCFC', '#B6DDD8', .16, r=.48)
    pill(s2_x + 1.0, sc_y + 2.05, '2', MAINT_C, WHITE, size=4.55, pad=.65, h=1.72)
    label(s2_x + 3.8, sc_y + 2.05, 'Delta Check' if en else '增量批次检查', SMALL, INK, 'bold')
    bar_x, bar_y, bar_w, bar_h = s2_x + 1.3, sc_y + 4.2, s2_w - 2.6, 3.6
    rect(bar_x, bar_y, bar_w * .62, bar_h, '#E7E4DF', '#C5C1B9', .14, r=.3)
    label(bar_x + bar_w * .31, bar_y + bar_h / 2, 'base rows' if en else '存量旧行', 4.5, MUTED, 'sans', 'center')
    rect(bar_x + bar_w * .64, bar_y, bar_w * .36, bar_h, RED_PALE, RED, .18, r=.3)
    label(bar_x + bar_w * .82, bar_y + bar_h / 2, '$\\Delta T$ $\\times$' if en else '$\\Delta T$ 违例', 4.6, RED, 'bold', 'center')
    label(s2_x + s2_w / 2, sc_y + 9.95,
          'probe $\\Delta T$ only (`key 17` dup)' if en else '仅查新增批次 $\\Delta T$（发现键 17 重复）',
          TINY, INK, 'sans', 'center')

    route([(s2_x + s2_w, sc_y + sc_h / 2), (s3_x, sc_y + sc_h / 2)], MAINT_C, .24, length=.8)

    # Stage 3: Single-Edit Repair or Retire
    rect(s3_x, sc_y, s3_w, sc_h, MAINT_PALE, MAINT_C, .2, r=.48)
    pill(s3_x + 1.0, sc_y + 2.05, '3', MAINT_C, WHITE, size=4.55, pad=.65, h=1.72)
    label(s3_x + 3.8, sc_y + 2.05, 'Repair or Retire' if en else '受限修复或挂起', SMALL, INK, 'bold')
    patch_badge(s3_x + 3.0, sc_y + 5.98, 1.55, WHITE, MAINT_DK)
    pill(s3_x + 5.3, sc_y + 5.98, "`is_current='Y'` $\\rightarrow$ rev 1",
         WHITE, MAINT_DK, edge_c=MAINT_C, size=4.55, pad=.72, h=2.15)
    label(s3_x + s3_w / 2, sc_y + 9.95,
          'unique patch + replay; else pending/retire' if en else '唯一补丁+重放通过；否则挂起或弃用',
          4.75, MAINT_DK, 'sans', 'center')

    # Step 6 thick arrow: Maintain Stage 3 -> Knowledge base
    s6_x = s3_x + s3_w / 2
    route([(s6_x, qy), (s6_x, ky + kh)], MAINT_C, THICK, length=.95)
    step_badge(s6_x + 2.7, (qy + ky + kh) / 2, 6, MAINT_C)

    # -------------------------------------------------------------------------
    # (D) Top-Right: LOOKUP (Step 3) — Simple Abstract Visual Pipeline
    # -------------------------------------------------------------------------
    LOOK = (133.0, 17.2, 40.2, 24.8)
    lx_k, ly_k, lw_k, lh_k = LOOK
    card_head(LOOK, 'Lookup' if en else '查找',
              'no SQL, no LLM' if en else '不生 SQL · 免在线 LLM',
              ACC_PALE, ACC, INK, ACC_DK)

    # Request bus from Agents 2, N, P into Lookup (Step 3)
    bus_y = 12.1
    c_a2 = 45.8 + 37.8 / 2
    c_an = 90.0 + 37.8 / 2
    c_ap = 134.2 + 39.2 / 2
    req_x = lx_k + 14.5
    s.line(c_a2, bus_y, c_ap, bus_y, ACC, .26)
    for cx_ag in (c_a2, c_an, c_ap):
        s.line(cx_ag, ag_y + ag_h, cx_ag, bus_y, ACC, .24)
    route([(req_x, bus_y), (req_x, ly_k)], ACC, THIN, length=1.0)
    step_badge(req_x - 3.0, 14.8, 3, ACC)
    label(req_x + 1.3, 14.9, 'request $\\rho$' if en else '请求 $\\rho$', TINY, ACC_DK, 'bold')

    # Catalog sync/read arrow: Knowledge base (Definitions) -> Lookup
    sync_y = ly_k + 8.6
    route([(kx + kw, sync_y), (lx_k, sync_y)], REF, .22, dash=(.65, .4), length=.85)

    # Abstract 2-tile visual pipeline inside Lookup
    t1_x, t_y, t1_w, t_h = lx_k + 1.3, ly_k + 4.5, 17.4, 11.0
    t2_x, t2_w = t1_x + t1_w + 2.2, lw_k - 3.4 - t1_w - 2.2

    # Tile 1: Alias & Vector Index
    rect(t1_x, t_y, t1_w, t_h, '#F8FBFF', '#9EC0E6', .16, r=.48)
    label(t1_x + t1_w / 2, t_y + 1.75, 'Alias & Recall' if en else '别名与向量召回', 5.05, ACC_DK, 'bold', 'center')
    vcx, vcy = t1_x + t1_w / 2, t_y + 5.8
    s.circle(vcx, vcy, 2.45, WHITE, '#8AB4E2', .15)
    sparkle_icon(vcx - .3, vcy, .92, EXEC_C)
    for dx_v, dy_v, col_v in ((-1.25, -.85, ACC), (1.05, -.75, ACC), (.85, 1.05, ACC),
                              (-1.05, 1.15, '#B8C8DC'), (1.6, .2, '#B8C8DC')):
        s.circle(vcx + dx_v, vcy + dy_v, .34, col_v)
    label(t1_x + t1_w / 2, t_y + 9.55, 'alias or top-$K$' if en else '别名直达 / top-$K$', 4.7, MUTED, 'sans', 'center')

    route([(t1_x + t1_w, t_y + t_h / 2), (t2_x, t_y + t_h / 2)], ACC, .22, length=.72)

    # Tile 2: Catalog-Trained Matcher
    rect(t2_x, t_y, t2_w, t_h, '#F8FBFF', '#9EC0E6', .16, r=.48)
    label(t2_x + t2_w / 2, t_y + 1.75, 'Matcher' if en else '目录判别器', 5.05, ACC_DK, 'bold', 'center')
    mcx, mcy = t2_x + t2_w / 2, t_y + 5.7
    for off_k in (1.0, .5, 0.0):
        rect(mcx - 5.0 + off_k, mcy - 1.65 - off_k * .52, 9.6, 3.2, WHITE, ACC, .15, r=.32)
    rect(mcx - 4.2, mcy - .95, 5.8, .72, ACC, None, r=.2)
    rect(mcx - 4.2, mcy + .25, 3.5, .72, AMBER, None, r=.2)
    check_mark(mcx + 3.2, mcy - .1, True, ACC, k=.72)
    label(t2_x + t2_w / 2, t_y + 9.55, 'choice consistency' if en else '口径选项判别', 4.7, MUTED, 'sans', 'center')

    # Clean 2-branch fork FROM Matcher to Hit (left) and Diffs/Miss (right)!
    dec_y, dec_h = t_y + t_h + 1.8, 5.9
    b1_x, b1_w = lx_k + 1.3, 18.2
    b2_x, b2_w = b1_x + b1_w + 1.3, lw_k - 3.4 - b1_w - 1.3
    m_out_x = t2_x + t2_w / 2
    fork_y = t_y + t_h + .85
    s.line(m_out_x, t_y + t_h, m_out_x, fork_y, ACC, .2)
    route([(m_out_x, fork_y), (b1_x + b1_w / 2, fork_y), (b1_x + b1_w / 2, dec_y)],
          ACC, .2, length=.62, radius=.3)
    route([(m_out_x, fork_y), (b2_x + b2_w / 2, fork_y), (b2_x + b2_w / 2, dec_y)],
          AMBER, .2, length=.62, radius=.3)

    # Branch 1 (Left): Direct hit -> goes down to Check & run (Step 4)
    rect(b1_x, dec_y, b1_w, dec_h, ACC_PALE, ACC, .18, r=.45)
    label(b1_x + b1_w / 2, dec_y + 1.95, 'Hit $(m^r, p, d)$' if en else '唯一命中 $(m^r,p,d)$', 4.95, ACC_DK, 'bold', 'center')
    label(b1_x + b1_w / 2, dec_y + 4.25, 'to execution' if en else '进入快照执行', 4.6, ACC_DK, 'sans', 'center')

    # Branch 2 (Right): Ambiguous / Miss -> connected return dashed arrow to agent bus!
    rect(b2_x, dec_y, b2_w, dec_h, AMBER_PALE, AMBER, .16, r=.45)
    label(b2_x + b2_w / 2, dec_y + 1.95, 'Diffs / Miss' if en else '同名歧义 / 未命中', 4.9, EXEC_DK, 'bold', 'center')
    label(b2_x + b2_w / 2, dec_y + 4.25, 'confirm or explore' if en else '返回差异或探索', 4.55, MUTED, 'sans', 'center')
    ret_amb_x = lx_k + lw_k - 1.0
    route([(b2_x + b2_w, dec_y + dec_h / 2), (ret_amb_x, dec_y + dec_h / 2),
           (ret_amb_x, bus_y)], AMBER, .2, heads='end', dash=(.55, .35), length=.75, radius=.35)

    # -------------------------------------------------------------------------
    # (E) Bottom-Right: CHECK AND RUN (Step 4) — Snapshot Execution + <-> DB
    # -------------------------------------------------------------------------
    EXEC = (133.0, 45.0, 40.2, 27.0)
    ex, ey, ew, eh = EXEC
    card_head(EXEC, 'Check and run' if en else '检查并执行',
              'snapshot $D_s$' if en else '单快照 $D_s$',
              EXEC_PALE, EXEC_C, INK, EXEC_DK)

    # Step 4 arrow: Lookup Hit -> Check and run
    hit_cx = b1_x + b1_w / 2
    route([(hit_cx, dec_y + dec_h), (hit_cx, ey)], EXEC_C, THIN, length=.9)
    step_badge(hit_cx + 3.0, (ly_k + lh_k + ey) / 2, 4, EXEC_C)

    # Inner dashed frame: Single Read-Only Transaction Snapshot D_s
    sx_in, sy_in, sw_in, sh_in = ex + 1.3, ey + 4.4, ew - 2.6, 16.9
    rect(sx_in, sy_in, sw_in, sh_in, '#FFFDF9', EXEC_C, .18, r=.5, dash=(.75, .42))
    label(sx_in + sw_in / 2, sy_in + 1.6,
          'One read-only snapshot $D_s$' if en else '同一只读事务快照 $D_s$',
          4.95, EXEC_DK, 'bold', 'center')

    # Step A inside Snapshot D_s: Validate C(m^r) via H
    st1_y, st1_h = sy_in + 2.9, 5.8
    rect(sx_in + 1.0, st1_y, sw_in - 2.0, st1_h, WHITE, '#E2BE8E', .15, r=.4)
    shield_icon(sx_in + 3.1, st1_y + st1_h / 2, 1.32, EXEC_PALE, EXEC_DK)
    label(sx_in + 5.3, st1_y + 1.9, '1. Validate $C(m^r)$ at $V_s$' if en else '1. 核验快照条件 $C(m^r)$', 4.95, INK, 'bold')
    label(sx_in + 5.3, st1_y + 4.15, 'reuse $\\mathcal{H}$ or run $Q_c$ once' if en else '复用 $\\mathcal{H}$ 或单次执行 $Q_c$',
          4.6, MUTED, width=sw_in - 8.8)
    check_mark(sx_in + sw_in - 2.1, st1_y + st1_h / 2, True, ACC, k=.78)

    # Read arrow from Check outcomes H -> Validate C(m^r)
    h_read_y = st1_y + st1_h / 2
    route([(kx + kw, h_read_y), (sx_in + 1.0, h_read_y)], REF, .22, dash=(.65, .4), length=.85)

    route([(sx_in + sw_in / 2, st1_y + st1_h), (sx_in + sw_in / 2, st1_y + st1_h + 1.2)],
          EXEC_C, .2, length=.62)

    # Step B inside Snapshot D_s: Bind & Execute Compiled SQL
    st2_y, st2_h = st1_y + st1_h + 1.2, 5.9
    rect(sx_in + 1.0, st2_y, sw_in - 2.0, st2_h, WHITE, '#E2BE8E', .15, r=.4)
    pill(sx_in + 1.7, st2_y + st2_h / 2, 'SQL', EXEC_PALE, EXEC_DK, edge_c=EXEC_C, size=4.45, pad=.58, h=1.82)
    label(sx_in + 7.0, st2_y + 1.9, '2. Bind & Execute Query' if en else '2. 绑定参数并执行查询', 4.95, INK, 'bold')
    label(sx_in + 7.0, st2_y + 4.2,
          'metric $(p, d)$ / feature $(u_i, \\leq t_i)$' if en else '指标 $(p,d)$ ／ 特征截点 $(u_i,\\leq t_i)$',
          4.6, EXEC_DK, width=sw_in - 8.4)

    # Verified Answer output bar + clean upward return arrow to Consumer Agent bus!
    ans_y, ans_h = sy_in + sh_in + .95, 3.8
    rect(sx_in, ans_y, sw_in, ans_h, EXEC_PALE, EXEC_C, .18, r=.42)
    check_mark(sx_in + 1.9, ans_y + ans_h / 2, True, EXEC_DK, k=.82)
    label(sx_in + 3.5, ans_y + ans_h / 2,
          'Verified answer / features' if en else '返回经核验答案／特征表',
          5.0, EXEC_DK, 'bold')

    # Return arrow along right lane up to the consumer agents (with upward arrows to Agent row)
    ret_x = 175.3
    route([(sx_in + sw_in, ans_y + ans_h / 2), (ret_x, ans_y + ans_h / 2),
           (ret_x, bus_y), (c_ap, bus_y)],
          EXEC_C, .24, heads='end', length=.85, radius=.5)

    # =========================================================================
    # 3. Bottom Band: ETL Job (Step 5) and Database with Snapshot D_s
    # =========================================================================
    db_y, db_h = 77.4, 10.4
    ETL = (2.6, db_y + .3, 23.4, db_h - .6)
    tx, ty, tw_e, th_e = ETL
    for off in (.9, .45, 0.0):
        rect(tx + off, ty - off, tw_e - .9, th_e, WHITE, '#B5B1A8', .14, r=.45)
    label(tx + 1.3, ty + 3.2, 'ETL job' if en else 'ETL 作业', TITLE, INK, 'bold')
    label(tx + 1.3, ty + 6.6, 'loads `item` history' if en else '装载 `item` 历史', TINY, MAINT_DK, 'bold', width=tw_e - 2.4)

    DB = (30.2, db_y, 144.8, db_h)
    bx, by, bw, bh_d = DB
    d_slab = 1.1
    s.poly([(bx, by), (bx + d_slab, by - d_slab), (bx + bw + d_slab, by - d_slab), (bx + bw, by)],
           '#F2F0EC', '#B8B4AC', .12)
    s.poly([(bx + bw, by), (bx + bw + d_slab, by - d_slab), (bx + bw + d_slab, by + bh_d - d_slab), (bx + bw, by + bh_d)],
           '#E6E3DD', '#B8B4AC', .12)
    rect(bx, by, bw, bh_d, FACE, '#B8B4AC', .18, r=.55)

    # Step 5 arrow: ETL -> Database
    etl_ay = ty + th_e / 2
    route([(tx + tw_e - .9, etl_ay), (bx, etl_ay)], MAINT_C, THICK, length=.95)
    step_badge((tx + tw_e - .9 + bx) / 2, etl_ay - 2.7, 5, MAINT_C)

    label(bx + 1.6, by + 3.3, 'Database', TITLE, INK, 'bold')
    label(bx + 1.6, by + 6.1, 'stamps $V(T)$ &' if en else '维护表版本戳 $V(T)$', TINY, MUTED)
    label(bx + 1.6, by + 8.3, 'deltas $\\Delta T$' if en else '与追加批次 $\\Delta T$', TINY, MUTED)

    ctop, ch_in = by + .9, bh_d - 1.8

    # 1) item table
    ix, iw = bx + 23.6, 44.4
    rect(ix, ctop, iw, ch_in, WHITE, AMBER, .18, r=.4)
    rect(ix + .12, ctop + .12, iw - .24, 2.3, AMBER_PALE, None, r=.3)
    label(ix + .9, ctop + 1.25, '`item`', 5.2, INK, 'bold')
    mini_step(ix + iw - 13.8, ctop + 1.25, 5, MAINT_C, r=.82)
    label(ix + iw - .9, ctop + 1.25, 'batch 0 $\\rightarrow$ 1', 4.85, EXEC_DK, 'bold', 'right')
    label(ix + .9, ctop + 4.1, "`17  'Electronics'  'Y'`", 4.75, INK)
    label(ix + iw - .9, ctop + 4.1, 'current' if en else '当前行', 4.65, MUTED, 'sans', 'right')
    rect(ix + .5, ctop + 5.45, iw - 1.0, 2.6, AMBER_PALE, None, r=.25)
    label(ix + .9, ctop + 6.75, "`17  'Electronics'  'N'`", 4.75, INK)
    label(ix + iw - .9, ctop + 6.75, 'new $\\Delta T$' if en else '新增 $\\Delta T$', 4.65, EXEC_DK, 'bold', 'right')

    # 2) store_sales & date_dim
    for tx_c, tw_c, tname_c in ((ix + iw + 1.8, 17.4, '`store_sales`'),
                                (ix + iw + 20.8, 15.0, '`date_dim`')):
        rect(tx_c, ctop, tw_c, ch_in, WHITE, EDGE, .14, r=.4)
        rect(tx_c + .12, ctop + .12, tw_c - .24, 2.3, TOP, None, r=.3)
        label(tx_c + .8, ctop + 1.25, tname_c, 4.9, INK, 'bold')
        for r_i in range(3):
            rect(tx_c + .9, ctop + 3.2 + r_i * 1.65, tw_c - 1.8, .85, '#E4E1DB', None, r=.2)

    # 3) Snapshot D_s aligned directly beneath Check and run
    sn_x, sn_w = ex + .6, ew - 1.2
    rect(sn_x, ctop, sn_w, ch_in, WHITE, EXEC_C, .2, r=.4, dash=(.75, .42))
    label(sn_x + 1.1, ctop + 1.7, 'snapshot $D_s$' if en else '一致性快照 $D_s$', 5.05, EXEC_DK, 'bold')
    label(sn_x + sn_w - 1.0, ctop + 1.7, 'read-only' if en else '只读视图', 4.6, MUTED, 'sans', 'right')
    mini_w = (sn_w - 2.4 - 1.6) / 3
    for k_m in range(3):
        mx_s = sn_x + 1.2 + k_m * (mini_w + .8)
        rect(mx_s, ctop + 3.2, mini_w, ch_in - 4.1, FACE, '#C9C4BC', .12, r=.25)
        rect(mx_s + .12, ctop + 3.32, mini_w - .24, 1.1, EXEC_PALE, None, r=.2)

    # =========================================================================
    # 4. Prominent Bidirectional Database Interaction Arrows (<->)
    # =========================================================================
    maint_db_x = ix + iw / 2
    route([(maint_db_x, qy + qh), (maint_db_x, ctop)],
          MAINT_C, .32, heads='both', dash=(.75, .42), length=1.1)
    label(maint_db_x + 1.5, 74.85,
          'stamps & $\\Delta T$ checks' if en else '读版本与增量检查', 4.65, MAINT_DK)

    snap_cx = sn_x + sn_w / 2
    route([(snap_cx, ey + eh), (snap_cx, ctop)],
          EXEC_C, .34, heads='both', dash=(.75, .42), length=1.15)
    label(snap_cx + 1.5, 74.85,
          'query $\\leftrightarrow$ results' if en else '快照查询 $\\leftrightarrow$ 结果', 4.65, EXEC_DK, 'bold')


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
