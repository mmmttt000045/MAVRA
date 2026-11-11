"""Shared-layer architecture (Figure 2): three shared state stores and four coordinating modules.

Double column (178.0 mm wide). Places the three shared states at the visual center:
  1. Computation definitions: m^r = (B, I, C, E, r) for metrics and features
  2. Request & equivalence evidence (G): grounded request templates Phi(m),
     certified equivalence edges (u ==_P m), and field-difference edges delta(u,m)
  3. Validation evidence (H, H_tx): condition outcomes indexed by (id(c), V(dep(c)))
     shared across definitions and agents

Around the catalog sit four modules:
  - Publish (steps 1-2): extracts m^0, passes G1-G7, writes definition, template, and checks
  - Lookup (step 3): explains request constraints A(rho) via G & I, checks residue/audit
  - Maintain (steps 5-6): filters writes (table stamps + batch delta), rechecks once in H,
    AND simultaneously repairs/retires definitions in State 1 and suspends broken
    equivalence edges/rewrites in State 2
  - Check and run (step 4) + Feature compile (P): verifies required conditions and runs
    compiled SQL in one repeatable-read snapshot s
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vecfig import PT, measure  # noqa: E402
import style  # noqa: E402
from style import (ACC, ACC_DK, ACC_PALE, AMBER_PALE, EDGE, FACE, FIELD, INK, MUTED,  # noqa: E402
                   RED, RULE, SIDE, SLATE, TOP, WHITE)

NAME = 'architecture'
W, H = style.TEXTWIDTH, 70.0

TITLE, BODY, NOTE, SMALL, JS, STEP = 7.1, 6.4, 6.2, 5.8, 5.5, 6.2
LEARN, USE, EXEC_C = '#6B56A6', ACC, '#C97A1E'
LEARN_PALE = '#EFECF7'
KEYC = '#8A5A00'
REF = '#6F6B66'
OCHRE = '#9A6500'
MAINT_C = '#13897B'
MAINT_PALE = '#E4F5F2'
RED_PALE = '#FBE9E5'
THIN, THICK = .22, .46


def baseline(y_center, size):
    return y_center + .34 * size * PT


def draw(s, lang):
    text, rect, route = s.text, s.rect, s.route

    def label(x, yc, txt, size=SMALL, color=INK, wt='sans', align='left', width=None):
        return text(x, baseline(yc, size), txt, size, color, wt, align, width)

    def box(b, fill=WHITE, edge=EDGE, sw=.16, r=.55, dash=None):
        rect(*b, fill, edge, sw, r=r, dash=dash)

    def card_head(b, title_txt, sub_txt, band_fill, edge_c=EDGE, title_c=INK, sub_c=MUTED, bh=3.1):
        x, y, w, h = b
        rect(x, y, w, h, WHITE, edge_c, .18, r=.55)
        rect(x + .12, y + .12, w - .24, bh, band_fill, None, r=.45)
        rect(x + .12, y + .12 + bh / 2, w - .24, bh / 2, band_fill, None)
        yc = y + .12 + bh / 2
        tw = label(x + 1.0, yc, title_txt, BODY, title_c, 'bold')
        if sub_txt:
            label(x + w - 1.0, yc, sub_txt, JS - .2, sub_c, 'sans', 'right', width=w - tw - 2.6)

    def step(x, yc, n, color):
        s.circle(x, yc, 1.35, color)
        label(x, yc, str(n), STEP - .4, WHITE, 'bold', 'center')

    def mark(x, yc, ok, c=None):
        if ok:
            s.poly([(x - .58, yc), (x - .14, yc + .46), (x + .62, yc - .52)], None, c or ACC, .25, closed=False)
        else:
            s.line(x - .48, yc - .48, x + .48, yc + .48, c or RED, .25)
            s.line(x - .48, yc + .48, x + .48, yc - .48, c or RED, .25)

    def pill(x, yc, txt, fill_c, w=3.2):
        rect(x, yc - 1.05, w, 2.1, fill_c, None, r=.5)
        label(x + w / 2, yc, txt, 5.3, WHITE, 'bold', 'center')

    # =========================================================================
    # 1. Top row: Data Agents (Analytical 1, 2, ..., N and Predictive P)
    # =========================================================================
    ag_y, ag_h, ag_w = 1.0, 7.6, 36.8
    ag_xs = (1.5, 44.5, 92.5, 139.7)
    ag_info = (
        ('1', 'Agent 1' if lang == 'en' else '智能体 1', 'first session' if lang == 'en' else '首次会话',
         '"Jan. electronics revenue?"', 'explores DB; answer verified' if lang == 'en' else '探索数据库；答案经核验', LEARN),
        ('2', 'Agent 2' if lang == 'en' else '智能体 2', 'before write' if lang == 'en' else '更新前',
         '"Best month for elec. turnover?"', 'grounded template + rank deriv.' if lang == 'en' else '绑定接地模板与排名派生', USE),
        ('N', 'Agent N' if lang == 'en' else '智能体 N', 'after write' if lang == 'en' else '更新后',
         '"Sep. revenue vs. last year?"', 'reuses repaired rev 1' if lang == 'en' else '维护修复后复用修订版 1', MAINT_C),
        ('P', 'Predictive agent P' if lang == 'en' else '预测智能体 P', 'cutoff t_i' if lang == 'en' else '截点 t_i',
         '"Will customer churn?"', 'reuses feature `spend_90d`' if lang == 'en' else '复用客户特征 `spend_90d`', EXEC_C),
    )
    for x, (tag, name, when, q, act, col) in zip(ag_xs, ag_info):
        box((x, ag_y, ag_w, ag_h), WHITE, col, .18)
        pill(x + 1.0, ag_y + 1.8, tag, col, w=3.0)
        label(x + 4.6, ag_y + 1.8, name, BODY, INK, 'bold')
        label(x + ag_w - 1.0, ag_y + 1.8, when, JS - .2, col, 'bold', 'right')
        label(x + 1.0, ag_y + 4.2, q, SMALL, INK, width=ag_w - 2.0)
        label(x + 1.0, ag_y + 6.3, act, JS - .1, col, width=ag_w - 2.0)

    dots_x = (ag_xs[1] + ag_w + ag_xs[2]) / 2
    for k in (-1, 0, 1):
        s.circle(dots_x + 1.3 * k, ag_y + ag_h / 2, .32, EDGE)

    # =========================================================================
    # 2. Middle Band: MAVRA Shared Layer
    # =========================================================================
    fy, fh = 10.6, 46.8
    rect(1.5, fy, W - 3.0, fh, FIELD, ACC, .18, r=1.0)
    rect(2.8, fy + 0.9, 0.6, 2.0, ACC)
    label(4.0, fy + 1.9, 'MAVRA', BODY + .2, ACC_DK, 'bold')

    # ---- Left Module: PUBLISH (Steps 1-2) ----
    PUB = (2.8, fy + 3.6, 24.5, fh - 4.8)
    px, py, pw, ph = PUB
    card_head(PUB, 'Publish' if lang == 'en' else '发布 (Publish)', 'C1', LEARN_PALE, LEARN, LEARN, LEARN)
    # Step 1 arrow from Agent 1 into Publish (to the right of the MAVRA title)
    a1_x = px + pw - 4.2
    route([(ag_xs[0] + ag_w / 2, ag_y + ag_h), (ag_xs[0] + ag_w / 2, fy + 0.6), (a1_x, fy + 0.6), (a1_x, py)], LEARN, THIN, length=.85, radius=.4)
    step(a1_x + 2.2, fy + 2.0, 1, LEARN)

    # Inside Publish: 3-layer separation + G1-G7 gates
    ly = py + 4.2
    rect(px + 1.0, ly, pw - 2.0, 14.8, LEARN_PALE, LEARN, .14, r=.4)
    label(px + 1.6, ly + 2.0, 'Extract & generalize' if lang == 'en' else '提取与泛化边界', SMALL, LEARN, 'bold')
    p_items = (
        ('Fixed $I$:', 'measure, grain,'),
        ('', 'joins $\\mathcal{J}$, $\\varphi$, $\\tau$'),
        ('Param $p$:', 'period / $(u_i,t_i)$'),
        ('Deriv. $d$:', 'slice, rank, diff'),
        ('Conds $C$:', 'struct. + probes'),
    ) if lang == 'en' else (
        ('固定 $I$：', '度量、粒度、$\\mathcal{J}$'),
        ('', '过滤 $\\varphi$、时间 $\\tau$'),
        ('参数 $p$：', '期间 / $(u_i,t_i)$'),
        ('派生 $d$：', '切片/排名/差值'),
        ('条件 $C$：', '结构 + 探查提升'),
    )
    for idx, (k_txt, v_txt) in enumerate(p_items):
        yy = ly + 4.4 + idx * 2.35
        if k_txt:
            label(px + 1.5, yy, k_txt, JS - .35, LEARN, 'bold')
        label(px + 9.3, yy, v_txt, JS - .35, INK, width=pw - 10.1)

    gy = ly + 16.0
    rect(px + 1.0, gy, pw - 2.0, 21.0, WHITE, LEARN, .15, r=.4)
    label(px + 1.8, gy + 2.1, 'Admission gates G1-G7' if lang == 'en' else '发布准入检查 G1-G7', SMALL, INK, 'bold')
    gates = (
        ('G1-2', 'source & chain'),
        ('G3', 'joins, param $p$'),
        ('G4', 'grain $K$ unique'),
        ('G5', 'read-only review'),
        ('G6', 'raw SQL replay'),
        ('G7', '`Compile(I,p0)`'),
    ) if lang == 'en' else (
        ('G1-2', '来源与计算链'),
        ('G3', '连接与参数 $p$'),
        ('G4', '粒度键 $K$ 唯一'),
        ('G5', '只读静态审查'),
        ('G6', '原 SQL 复现答案'),
        ('G7', '`Compile(I,p0)`'),
    )
    for idx, (g_tag, g_desc) in enumerate(gates):
        yy = gy + 4.8 + idx * 2.65
        mark(px + 2.0, yy, True, LEARN)
        label(px + 3.0, yy, g_tag, JS - .3, LEARN, 'bold')
        label(px + 7.8, yy, g_desc, JS - .3, INK, width=pw - 8.6)

    # ---- Center: SHARED CATALOG with Three Explicit States ----
    CAT = (30.2, fy + 1.0, 91.6, fh - 2.2)
    cx, cy, cw, ch = CAT
    rect(cx + 0.7, cy + 0.7, cw, ch, SIDE, EDGE, .12, r=.6)
    box(CAT, WHITE, ACC, .2)
    rect(cx, cy, cw, 3.2, ACC, None, r=.55)
    rect(cx, cy + 1.6, cw, 1.6, ACC, None)
    label(cx + 1.4, cy + 1.6, 'Shared Catalog: Three Linked States' if lang == 'en' else '共享目录：三类关联状态', TITLE, WHITE, 'bold')
    label(cx + cw - 1.4, cy + 1.6, 'definitions + reuse evidence + data verdicts' if lang == 'en' else '计算定义 + 请求与等价证据 + 数据验证证据', JS - .1, WHITE, 'sans', 'right')

    # State 1: Computation Definitions (B, I, C, E, r)
    S1 = (cx + 1.2, cy + 4.0, cw - 2.4, 13.2)
    s1x, s1y, s1w, s1h = S1
    card_head(S1, '1. Computation Definitions  $m^r = (B, I, C, E, r)$' if lang == 'en' else '1. 计算定义  $m^r = (B, I, C, E, r)$',
              r'rev 0 $\rightarrow$ rev 1' if lang == 'en' else r'修订 0 $\rightarrow$ 1', ACC_PALE, ACC, ACC_DK, ACC_DK, bh=2.8)
    label(s1x + 1.2, s1y + 4.4, '`ER` (`Electronics revenue`):', JS, ACC_DK, 'bold')
    label(s1x + 25.5, s1y + 4.4, '$B$: net electronics sales  |  $E$: s094 (`2,754,299.60`)' if lang == 'en' else '$B$：电子净销售额  |  $E$：s094 (`2,754,299.60`)', JS - .2, INK, width=s1w - 26.5)
    label(s1x + 1.2, s1y + 6.9, '$I$: `F=store_sales`, `e=SUM(ss_net_paid)`, `K=(item_sk,ticket)`, `J: item,date_dim`, $\\varphi$: `category=\'Elec.\'`', JS - .25, INK, width=s1w - 2.4)
    label(s1x + 1.2, s1y + 9.3, '$C(m^r)$: grain & join unique, completeness, probe domain  |  rev 1 join filter: `i_is_current=\'Y\'`' if lang == 'en' else '$C(m^r)$：粒度与连接唯一、完整性、探查值域  |  修订 1 过滤：`i_is_current=\'Y\'`', JS - .25, MAINT_C, 'bold', width=s1w - 2.4)
    label(s1x + 1.2, s1y + 11.7, 'Also in catalog: `ER_r1` (key-range)  |  `ET` (`incl. tax`)  |  `ENR` (`net of returns`)  |  `feature:spend_90d` $(u_i,t_i)$', JS - .3, MUTED, width=s1w - 2.4)

    # State 2: Request and Equivalence Evidence (G)
    S2 = (cx + 1.2, s1y + s1h + 1.0, cw - 2.4, 13.6)
    s2x, s2y, s2w, s2h = S2
    card_head(S2, '2. Request & Equivalence Evidence ($G$)' if lang == 'en' else '2. 请求适用性与条件等价证据 ($G$)',
              'publish, misses, audits' if lang == 'en' else '发布、未命中与审计后积累', AMBER_PALE, OCHRE, OCHRE, OCHRE, bh=2.8)
    label(s2x + 1.2, s2y + 4.5, 'Templates $\\Phi(\\mathrm{ER})$:' if lang == 'en' else '接地模板 $\\Phi(\\mathrm{ER})$：', JS - .15, OCHRE, 'bold')
    label(s2x + 19.5, s2y + 4.5, '"electronics revenue in `<p>`" (step 2)  |  "electronics turnover in `<p>`" (verified miss)', JS - .25, INK, width=s2w - 20.5)
    label(s2x + 1.2, s2y + 7.0, 'Equivalence ($u \\equiv_P\\; m$):' if lang == 'en' else '条件等价 ($u \\equiv_P\\; m$)：', JS - .15, ACC_DK, 'bold')
    label(s2x + 21.8, s2y + 7.0, '`ER`  $\\equiv_{\\mathrm{R3}}$  `ER_r1` under $P$: `Contiguous(date_dim)` (suspended if $P$ fails)' if lang == 'en' else '`ER`  $\\equiv_{\\mathrm{R3}}$  `ER_r1`，前提 $P$：`date_dim` 按月连续（$P$ 失效时挂起）', JS - .25, INK, width=s2w - 22.8)
    label(s2x + 1.2, s2y + 9.5, 'Diff. edges $\\delta(u,m)$:' if lang == 'en' else '字段差异边 $\\delta(u,m)$：', JS - .15, RED, 'bold')
    label(s2x + 19.5, s2y + 9.5, '`ER` $\\leftrightarrow_{\\delta=\\{e\\}}$ `ET` ("incl. tax")   |   `ER` $\\leftrightarrow_{\\delta=\\{\\varphi\\}}$ `ENR` ("net of returns")', JS - .25, INK, width=s2w - 20.5)
    label(s2x + 1.2, s2y + 12.0, 'Audit bound $U_g(t)$:' if lang == 'en' else '分层审计界 $U_g(t)$：', JS - .15, INK, 'bold')
    label(s2x + 19.5, s2y + 12.0, '$U_g(t) \\leq \\alpha$ gates tentative hits; 3-way labels (equivalent / distinct / unprovable)' if lang == 'en' else '$U_g(t) \\leq \\alpha$ 门控试探命中；三类标签（已证等价 / 确认不同 / 无法判定）', JS - .25, MUTED, width=s2w - 20.5)

    # State 3: Validation Evidence (H, H_tx)
    S3 = (cx + 1.2, s2y + s2h + 1.0, cw - 2.4, 11.8)
    s3x, s3y, s3w, s3h = S3
    card_head(S3, '3. Validation Evidence ($\\mathcal{H}, \\mathcal{H}_{\\mathrm{tx}}$)' if lang == 'en' else '3. 数据验证证据 ($\\mathcal{H}, \\mathcal{H}_{\\mathrm{tx}}$)',
              'key: (id(c), V(dep(c)))' if lang == 'en' else '按 (条件签名, 依赖表版本) 索引', MAINT_PALE, MAINT_C, MAINT_C, MAINT_C, bh=2.8)
    label(s3x + 1.2, s3y + 4.5, '`KeyUnique(date_dim.d_date_sk) @ v0`:', JS - .25, INK, 'bold')
    label(s3x + 34.8, s3y + 4.5, '`pass (1096/1096)` — shared across `ER`, `ET`, `ENR`, `spend_90d`' if lang == 'en' else '`通过 (1096/1096)` — 由 `ER`、`ET`、`ENR` 与 `spend_90d` 共享', JS - .25, ACC_DK, width=s3w - 35.8)
    label(s3x + 1.2, s3y + 7.0, '`KeyUnique(item.i_item_sk) @ v1`:', JS - .25, RED, 'bold')
    label(s3x + 31.2, s3y + 7.0, '`fail (1001/1000)` $\\rightarrow$ repaired (`i_is_current=\'Y\'`) $\\rightarrow$ `pass`' if lang == 'en' else '`失败 (1001/1000)` $\\rightarrow$ 加 `i_is_current=\'Y\'` 修复 $\\rightarrow$ `通过`', JS - .25, INK, width=s3w - 32.2)
    label(s3x + 1.2, s3y + 9.5, '`Contiguous(date_dim) @ v_rekey`:', JS - .25, OCHRE, 'bold')
    label(s3x + 31.2, s3y + 9.5, 'premise $P_{\\mathrm{R3}}$ check; failure suspends `ER` $\\equiv_{\\mathrm{R3}}$ `ER_r1` in State 2' if lang == 'en' else '检验前提 $P_{\\mathrm{R3}}$；违例时挂起状态 2 中的 `ER` $\\equiv_{\\mathrm{R3}}$ `ER_r1`', JS - .25, MUTED, width=s3w - 32.2)

    # Step 2 arrows: Publish writes into State 1, State 2, State 3
    route([(px + pw, s1y + 4.5), (s1x, s1y + 4.5)], LEARN, THICK, length=.9)
    route([(px + pw, s2y + 4.5), (s2x, s2y + 4.5)], LEARN, THIN, length=.8)
    route([(px + pw, s3y + 4.5), (s3x, s3y + 4.5)], LEARN, THIN, length=.8)
    step((px + pw + cx) / 2, s1y + 2.0, 2, LEARN)

    # ---- Right-Top Module: LOOKUP (Step 3) ----
    LOOK = (124.6, fy + 3.6, 26.2, 20.2)
    lx, ly, lw, lh = LOOK
    card_head(LOOK, 'Lookup' if lang == 'en' else '查找 (Lookup)', 'C2', ACC_PALE, USE, ACC_DK, ACC_DK)

    # Arrows from Agent 2, Agent N, Agent P into Lookup
    l2_x, ln_x, lp_x = lx + 5.0, lx + 13.0, lx + 21.0
    route([(ag_xs[1] + ag_w / 2, ag_y + ag_h), (ag_xs[1] + ag_w / 2, fy + 1.4), (l2_x, fy + 1.4), (l2_x, ly)], USE, THIN, length=.85, radius=.4)
    step(l2_x - 2.6, fy + 2.2, 3, USE)
    route([(ag_xs[2] + ag_w / 2, ag_y + ag_h), (ag_xs[2] + ag_w / 2, fy + 0.7), (ln_x, fy + 0.7), (ln_x, ly)], MAINT_C, THIN, length=.85, radius=.4)
    route([(ag_xs[3] + ag_w / 2, ag_y + ag_h), (ag_xs[3] + ag_w / 2, fy + 1.4), (lp_x, fy + 1.4), (lp_x, ly)], EXEC_C, THIN, length=.85, radius=.4)

    # Lookup reads State 1, State 2, State 3
    route([(s1x + s1w, s1y + 6.5), (lx, s1y + 6.5)], USE, THIN, length=.85)
    route([(s2x + s2w, s2y + 5.5), (lx, s2y + 5.5)], USE, THIN, length=.85)

    l_steps = (
        ('1.', 'Parse $A(\\rho)$, recall $K$'),
        ('2.', 'Explain via $I, p, d$; check $\\mathrm{Res}$'),
        ('3.', 'If $|S|>1$: indifference test'),
        ('4.', 'Tentative: serve if $U_g(t)\\leq\\alpha$'),
        ('5.', 'Check $C(m^r)$ & premise $P$'),
    ) if lang == 'en' else (
        ('1.', '解析 $A(\\rho)$，召回候选 $K$'),
        ('2.', '由 $I, p, d$ 解释并检残余 $\\mathrm{Res}$'),
        ('3.', '多候选存活：快照同值检验'),
        ('4.', '试探命中：$U_g(t)\\leq\\alpha$ 免审计'),
        ('5.', '核验条件 $C(m^r)$ 与前提 $P$'),
    )
    for idx, (num_s, txt_s) in enumerate(l_steps):
        yy = ly + 4.8 + idx * 3.0
        label(lx + 1.0, yy, num_s, JS - .25, ACC_DK, 'bold')
        label(lx + 3.0, yy, txt_s, JS - .3, INK, width=lw - 3.6)

    # ---- Right-Bottom Module: MAINTAIN (Steps 5-6) ----
    MAINT = (124.6, ly + lh + 2.4, 26.2, fh - (ly - fy + lh + 3.6))
    qx, qy, qw, qh = MAINT
    card_head(MAINT, 'Maintain' if lang == 'en' else '维护 (Maintain)', 'C3', MAINT_PALE, MAINT_C, MAINT_C, MAINT_C)
    step(qx + qw - 2.2, qy + 1.5, 6, MAINT_C)

    # Pending / Rev 1 handoff between Lookup and Maintain
    route([(lx + 6.5, ly + lh), (lx + 6.5, qy)], MAINT_C, THIN, length=.8)
    label(lx + 7.4, (ly + lh + qy) / 2, 'pending' if lang == 'en' else '待验证', JS - .3, MAINT_C, 'bold')
    route([(lx + lw - 5.5, qy), (lx + lw - 5.5, ly + lh)], MAINT_C, THIN, length=.8)
    label(lx + lw - 6.4, (ly + lh + qy) / 2, 'rev 1', JS - .3, MAINT_C, 'bold', 'right')

    m_steps = (
        ('Filter:', 'stamps $V(T)$ + batch $\\Delta T$'),
        ('Share:', 'recheck $\\Delta C$ once in $\\mathcal{H}$'),
        ('On $C$:', '1-edit patch + regression'),
        ('', "(`i_is_current='Y'` $\\rightarrow$ `rev 1`)"),
        ('On $P$:', 'suspend $u\\equiv_P\\; m$ in $G$'),
        ('', '& roll back rewrite `ER_r1`'),
    ) if lang == 'en' else (
        ('筛选：', '版本 $V(T)$ + $\\Delta T$'),
        ('共享：', '在 $\\mathcal{H}$ 重验一次'),
        ('$C$ 败：', '单步补丁+回归'),
        ('', "(`i_is_current='Y'` $\\rightarrow$ `rev 1`)"),
        ('$P$ 败：', '挂起等价边 $u\\equiv_P m$'),
        ('', '回退改写 `ER_r1`'),
    )
    for idx, (k_m, v_m) in enumerate(m_steps):
        yy = qy + 4.6 + idx * 2.55
        if k_m:
            label(qx + 1.0, yy, k_m, JS - .3, RED if 'P' in k_m else MAINT_C, 'bold')
        label(qx + 6.4 if k_m else qx + 1.8, yy, v_m, JS - .35, INK, width=qw - (7.0 if k_m else 2.4))

    # Crucial dual-maintenance write-back arrows from Maintain to State 1, State 2, State 3!
    # 1) To State 3 (H verdicts)
    route([(qx, s3y + 7.0), (s3x + s3w, s3y + 7.0)], MAINT_C, THICK, length=.9)
    # 2) To State 2 (suspend equivalence edge when P fails)
    route([(qx, qy + 14.5), (123.1, qy + 14.5), (123.1, s2y + 7.0), (s2x + s2w, s2y + 7.0)], RED, THICK, dash=(.8, .45), length=.9, radius=.4)
    # 3) To State 1 (publish repaired rev 1, routed cleanly in the channel between Catalog and Lookup)
    route([(qx, qy + 9.5), (122.4, qy + 9.5), (122.4, s1y + 9.3), (s1x + s1w, s1y + 9.3)], MAINT_C, THICK, length=.9, radius=.4)

    # ---- Far-Right Modules: CHECK AND RUN (Step 4) & FEATURE COMPILE (P) ----
    EXEC = (153.4, fy + 3.6, 21.8, 25.4)
    ex, ey, ew, eh = EXEC
    card_head(EXEC, 'Check & run' if lang == 'en' else '检查并执行', '$s$', AMBER_PALE, EXEC_C, EXEC_C, EXEC_C)
    route([(lx + lw, ly + 5.5), (ex, ly + 5.5)], EXEC_C, THIN, length=.85)
    step((lx + lw + ex) / 2, ly + 2.8, 4, EXEC_C)

    e_lines = (
        '1 `REPEATABLE READ` $s$',
        'Read version $v_s(\\mathrm{dep}(c))$',
        'Hit $\\mathcal{H}_{\\mathrm{tx}}$ or run $Q_c(D_s)$',
        'Verify $C(m^r) \\wedge P$ hold',
        'Run compiled $q(D_s)$:',
    ) if lang == 'en' else (
        '开启只读事务快照 $s$',
        '读取版本计数 $v_s$',
        '命中 $\\mathcal{H}_{\\mathrm{tx}}$ 或跑 $Q_c$',
        '确认 $C(m^r)$ 与前提 $P$',
        '同快照执行 $q(D_s)$：',
    )
    for idx, el in enumerate(e_lines):
        yy = ey + 4.8 + idx * 2.65
        mark(ex + 1.5, yy, True, EXEC_C)
        label(ex + 2.6, yy, el, JS - .35, INK, width=ew - 3.2)

    rect(ex + 1.0, ey + 17.0, ew - 2.0, 7.2, FACE, EDGE, .12, r=.35)
    sql_lines = ('SUM(ss_net_paid)', "i_category='Elec.'", "i_is_current='Y'")
    for idx, sl in enumerate(sql_lines):
        label(ex + 1.4, ey + 18.6 + idx * 2.1, f'`{sl}`', JS - .55, INK, width=ew - 2.6)

    FEAT = (153.4, ey + eh + 1.6, 21.8, fh - (ey - fy + eh + 2.8))
    fx, fy_b, fw, fh_b = FEAT
    card_head(FEAT, 'Feature compile' if lang == 'en' else '特征编译', 'P', AMBER_PALE, EXEC_C, INK, EXEC_C)
    route([(lx + lw, ly + 15.0), (152.0, ly + 15.0), (152.0, fy_b + 4.5), (fx, fy_b + 4.5)], EXEC_C, THIN, length=.8, radius=.4)
    label(fx + 1.0, fy_b + 4.6, '`spend_90d` at $(u_i, t_i)$', JS - .3, INK, 'bold', width=fw - 2.0)
    label(fx + 1.0, fy_b + 7.1, 'window $t_i - 90\\mathrm{d} < t \\leq t_i$', JS - .35, EXEC_C, width=fw - 2.0)
    label(fx + 1.0, fy_b + 9.5, 'leakage audit on view' if lang == 'en' else '截断视图时间泄漏审计', JS - .4, MUTED, width=fw - 2.0)

    # =========================================================================
    # 3. Bottom Row: ETL Writes (Step 5) and Database with Snapshot
    # =========================================================================
    by, bh_db = 59.0, 9.8
    ETL = (1.5, by, 25.8, bh_db)
    tx, ty, tw_, th_ = ETL
    box(ETL, WHITE, MAINT_C, .18)
    label(tx + 1.2, ty + 2.4, 'Writes / ETL' if lang == 'en' else '数据库写入 / ETL', BODY, MAINT_C, 'bold')
    step(tx + tw_ - 2.2, ty + 2.2, 5, MAINT_C)
    label(tx + 1.2, ty + 5.1, '1. `sales` append ($\\Delta T$)' if lang == 'en' else '1. 追加 `sales` 批次 ($\\Delta T$)', JS - .2, INK, width=tw_ - 2.2)
    label(tx + 1.2, ty + 7.5, '2. `item` history (`key 17` dup)' if lang == 'en' else '2. 装载 `item` 历史 (`key 17`)', JS - .2, RED, 'bold', width=tw_ - 2.2)

    DB = (30.2, by, 145.0, bh_db)
    bx, by, bw, bh_db = DB
    box(DB, FACE, EDGE, .18)
    label(bx + 1.4, by + 2.6, 'Database' if lang == 'en' else '底层数据库', TITLE, INK, 'bold')
    label(bx + 1.4, by + 5.2, 'trigger advances $V(T)$' if lang == 'en' else '触发器推进表版本 $V(T)$', JS - .25, MUTED)
    label(bx + 1.4, by + 7.5, 'and logs $\\Delta T$' if lang == 'en' else '并记录插入批次 $\\Delta T$', JS - .25, MUTED)

    route([(tx + tw_, ty + th_ / 2), (bx, ty + th_ / 2)], MAINT_C, THICK, length=.9)

    # Table cards inside Database
    t_cards = (
        (bx + 26.5, 25.0, '`store_sales`', r'$V$: `v0` $\rightarrow$ `v1` ($\Delta T$)', False),
        (bx + 53.0, 23.5, '`date_dim`', '$V$: `v0` (1096 keys)', False),
        (bx + 78.0, 41.5, '`item`', r'$V$: `v0` $\rightarrow$ `v1` (`key 17` $\times 2$)', True),
    )
    for x0, w0, t_n, v_n, hot in t_cards:
        rect(x0, by + 1.0, w0, bh_db - 2.0, WHITE, RED if hot else EDGE, .18 if hot else .14, r=.35)
        rect(x0 + .12, by + 1.12, w0 - .24, 2.4, RED_PALE if hot else TOP, None, r=.25)
        label(x0 + 0.8, by + 2.3, t_n, JS - .1, RED if hot else INK, 'bold')
        label(x0 + 0.8, by + 5.4, v_n, JS - .25, RED if hot else MUTED, width=w0 - 1.4)
        if hot:
            label(x0 + 0.8, by + 7.5, "`17, 'Elec.', 'Y'`  +  `17, 'Elec.', 'N'`", JS - .35, INK, width=w0 - 1.4)

    # Snapshot box inside Database aligned under Check & run
    sn_x = ex - 0.5
    sn_w = bx + bw - 1.2 - sn_x
    rect(sn_x, by + 1.0, sn_w, bh_db - 2.0, WHITE, EXEC_C, .2, r=.35, dash=(.8, .45))
    label(sn_x + 1.0, by + 2.8, 'Snapshot $s$' if lang == 'en' else '只读快照 $s$', SMALL, EXEC_C, 'bold')
    label(sn_x + 1.0, by + 5.3, 'checks & SQL read' if lang == 'en' else '条件检查与 SQL 读取', JS - .3, INK)
    label(sn_x + 1.0, by + 7.4, 'identical state $D_s$' if lang == 'en' else '同一数据库状态 $D_s$', JS - .3, EXEC_C, 'bold')

    # Arrows between Maintain / Check & run and Database
    m_db_x = qx + qw / 2
    route([(m_db_x, by), (m_db_x, qy + qh)], MAINT_C, .26, heads='both', dash=(.7, .45), length=.85)
    route([(ex + ew, ey + 20.0), (176.0, ey + 20.0), (176.0, by + 4.8), (sn_x + sn_w, by + 4.8)],
          EXEC_C, .26, heads='both', dash=(.7, .45), length=.8, radius=.4)


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
