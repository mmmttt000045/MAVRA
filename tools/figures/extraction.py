"""Figure 3: verifiable relational kernel extraction (steps 1-2), single column.

Visual workflow across three panels:
(a) Verified source session: natural-language question -> verified answer via G1/G2
    arithmetic provenance and G5 read-only SQL, with scope predicate phi and period
    literal p_0 highlighted inside the canonicalized query.
(b) Extract kernel I & runtime slots; derive C: G3 separates phi into the star join
    graph (mini tables item, store_sales, date_dim with crow's-foot N:1 joins and
    condition markers 1-5) from runtime slots (p, d), while deriving KeyUnique (G4)
    and unmatched join-loss gauges matched to M5-L1.
(c) Recompilation equivalence check on D_{s_0}: the source SQL and the candidate keeping
    phi both give 2,754,299.60 (Publish), while the draft omitting phi inflates 4.9x to
    13,532,799.00 (Reject).
(d) Lookup training data from M (offline, once per catalog; moved here from Fig. 4): intents
    enumerated from the published definitions' attributes go through an LLM into wordings,
    which the consistency rule labels against D01/D02 to train the judge of Fig. 4.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import PT, measure  # noqa: E402

NAME = 'extraction'
W, H = style.COLUMN, 84.6 + 6.2
DY = 6.2                                         # (b) grew by the dependency-graph strip

INK, MUTED = '#1F2328', '#596068'
CARD_EDGE, SUB_EDGE, RULE = '#737B84', '#B6BEC7', '#CFD5DC'
HEAD_BAND, TABLE_HEAD, SOFT_BG, WHITE = '#ECEFF3', '#E8ECF1', '#F7F8FA', '#FFFFFF'
SLATE = '#4E5D6C'
ACC, ACC_DK, ACC_PALE, NAVY_EDGE, GAUGE_TOL = '#24416B', '#1B3254', '#EDF1F7', '#9EB1CC', '#C5D3E8'
LEARN, LEARN_DK, LEARN_PALE, LEARN_EDGE = '#46506E', '#323A52', '#EFF1F6', '#B0B7CA'
RED, RED_PALE, RED_EDGE = '#942B2B', '#F6EDED', '#CCA6A6'


def draw(s, lang):
    en = lang == 'en'

    def label(x, yc, text, size=6.0, color=INK, font='sans', align='left', width=None):
        return s.text(x, yc + .34 * size * PT, text, size, color, font, align, width)

    def pill(x, yc, text, bg, edge=None, fg=INK, size=5.0, font='sans', pad_x=1.1, h=2.3, r=.45, dash=None):
        tw = measure(text, size, font)
        w = tw + 2 * pad_x
        s.rect(x, yc - h / 2, w, h, bg, edge, .14 if edge else 0, r=r, dash=dash)
        label(x + pad_x, yc, text, size, fg, font)
        return w

    def step_badge(x, yc, n, color=LEARN, r=1.1):
        s.circle(x, yc, r, color)
        label(x, yc, str(n), 5.5, WHITE, 'bold', 'center')

    def cond_marker(x, yc, i, r=.8, halo=False):
        if halo:
            s.circle(x, yc, r + .22, WHITE)
        s.circle(x, yc, r, SLATE)
        label(x, yc, str(i), 4.6, WHITE, 'bold', 'center')

    def gate_pill(x, yc, code, align='left', size=4.8):
        w = measure(code, size, 'bold') + 1.3
        x0 = {'left': x, 'center': x - w / 2, 'right': x - w}[align]
        s.rect(x0, yc - 1.05, w, 2.1, LEARN_PALE, LEARN, .14, r=.4)
        label(x0 + w / 2, yc, code, size, LEARN_DK, 'bold', 'center')
        return w

    def check_mark(x, yc, ok, color=None, k=.8, sw=.26):
        c = color or (ACC if ok else RED)
        if ok:
            s.poly([(x - .62 * k, yc), (x - .15 * k, yc + .5 * k), (x + .65 * k, yc - .55 * k)],
                   None, c, sw, closed=False)
        else:
            s.line(x - .5 * k, yc - .5 * k, x + .5 * k, yc + .5 * k, c, sw)
            s.line(x - .5 * k, yc + .5 * k, x + .5 * k, yc - .5 * k, c, sw)

    def person_icon(x, yc, color='#68707A'):
        s.circle(x, yc - .68, .66, color)
        s.rect(x - 1.0, yc + .16, 2.0, 1.15, color, None, r=.55)

    def key_icon(x, yc, color=INK, k=.85, sw=.16):
        r = .4 * k
        s.circle(x + r, yc, r, None, color, sw)
        x1 = x + 2 * r
        s.line(x1, yc, x1 + 1.3 * k, yc, color, sw)
        for t in (.75, 1.15):
            s.line(x1 + t * k, yc, x1 + t * k, yc + .42 * k, color, sw)
        return 2 * r + 1.3 * k

    def crow(x, yc, d, color=CARD_EDGE, sw=.16, spread=.68, length=1.35):
        for dy in (-spread, 0, spread):
            s.line(x + d * length, yc, x, yc + dy, color, sw)

    def one_bar(x, yc, d, color=CARD_EDGE, sw=.16, at=.72, half=.68):
        s.line(x + d * at, yc - half, x + d * at, yc + half, color, sw)

    def gauge(x, yc, w, val, tol, vmax, h=1.25, color=ACC):
        sc = w / vmax
        y0 = yc - h / 2
        bound = min(val + tol, vmax)
        s.rect(x, y0, w, h, WHITE, None)
        s.rect(x + bound * sc, y0, w - bound * sc, h, RED_PALE, None)
        if val > 0:
            s.rect(x, y0, val * sc, h, color, None)
        s.rect(x + val * sc, y0, tol * sc, h, GAUGE_TOL, None)
        s.rect(x, y0, w, h, None, CARD_EDGE, .12)
        s.line(x + bound * sc, y0 - .28, x + bound * sc, y0 + h + .28, RED, .22)

    def gauge_icon(x, yc):
        gauge(x, yc, 2.5, .85, .4, 2.5, h=1.0)
        return 2.5

    def card(y, h, title, badge=None):
        s.rect(.6, y, W - 1.2, h, WHITE, CARD_EDGE, .18, r=.55)
        s.rect(.7, y + .1, W - 1.4, 3.3, HEAD_BAND, None, r=.45)
        s.rect(.7, y + 1.8, W - 1.4, 1.6, HEAD_BAND, None)
        s.line(.6, y + 3.4, W - .6, y + 3.4, RULE, .14)
        x = 1.6
        if badge is not None:
            step_badge(2.3, y + 1.75, badge, LEARN, r=1.05)
            x = 4.1
        label(x, y + 1.75, title, 6.7, INK, 'bold')
        return y + 3.4

    def mini_table(x, y, w, name, n_rows, role=None, head=2.2, row_h=2.55):
        s.rect(x, y, w, head + n_rows * row_h, WHITE, CARD_EDGE, .16, r=.42)
        s.rect(x + .1, y + .1, w - .2, head - .1, TABLE_HEAD, None, r=.32)
        s.rect(x + .1, y + head / 2, w - .2, head / 2 - .02, TABLE_HEAD, None)
        s.line(x, y + head, x + w, y + head, CARD_EDGE, .12)
        label(x + .65, y + head / 2, name, 4.9, INK, 'sans')
        if role:
            label(x + w - .65, y + head / 2, role, 4.9, ACC_DK, 'bold', 'right')
        ys = []
        for k in range(n_rows):
            if k:
                s.line(x + .25, y + head + k * row_h, x + w - .25, y + head + k * row_h, RULE, .1)
            ys.append(y + head + (k + .5) * row_h)
        return ys

    # ------------------------------------------------------------------ (a)
    card(.5, 12.6, '(a) Confirmed session & query lineage' if en else '(a) 源会话与推导图', 1)
    # Right header gates: [G1-G2] deriv.  [G3] read-only
    r_text = 'read-only' if en else '只读'
    w_r = measure(r_text, 4.9)
    xr = W - 1.6 - w_r
    label(xr, 2.25, r_text, 4.9, MUTED)
    wg3 = gate_pill(xr - .6, 2.25, 'SQL', 'right')
    t_text = 'verified' if en else '已核验'
    w_t = measure(t_text, 4.9)
    xt = xr - .6 - wg3 - 1.3 - w_t
    label(xt, 2.25, t_text, 4.9, MUTED)
    gate_pill(xt - .6, 2.25, 'Lineage' if en else '血缘', 'right')

    # Row 1: User question bubble -> verified answer pill
    yc1 = 6.05
    person_icon(2.6, yc1)
    s.rect(4.5, yc1 - 1.5, 31.2, 3.0, SOFT_BG, SUB_EDGE, .15, r=.45)
    s.rect(5.1, yc1 - .95, 2.8, 1.9, LEARN_DK, None, r=.35)
    label(6.5, yc1, 'Q', 4.9, WHITE, 'bold', 'center')
    label(8.6, yc1, 'Jan. 2026 electronics revenue?' if en else '2026年1月电子品类营业额？',
          5.6, INK, width=26.6)
    s.route([(36.2, yc1), (47.4, yc1)], MUTED, .2, length=.8)
    label(41.8, yc1 - 1.1, 'query lineage' if en else '查询血缘', 4.8, MUTED, 'sans', 'center')

    s.rect(48.0, yc1 - 1.5, W - 49.6, 3.0, ACC_PALE, NAVY_EDGE, .16, r=.45)
    check_mark(49.9, yc1, True, ACC, k=.8)
    label(51.6, yc1, '`2,754,299.60`', 5.8, ACC_DK, 'sans', width=15.0)
    pill(W - 14.3, yc1, 'verified' if en else '已核验', WHITE, NAVY_EDGE, ACC_DK, size=4.8,
         font='bold', pad_x=1.2, h=1.9, r=.35)

    # Row 2: Canonicalized SQL split bar showing phi vs p_0
    yc2 = 10.45
    s.rect(1.6, yc2 - 1.85, W - 3.2, 3.7, '#FAFBFD', RULE, .15, r=.45)
    s.rect(2.2, yc2 - .95, 5.2, 1.9, SLATE, None, r=.35)
    label(4.8, yc2, 'SQL', 4.8, WHITE, 'bold', 'center')
    x_sql = 8.1
    x_sql += label(x_sql, yc2, '`SUM(ss_net_paid)` ... `WHERE`', 4.9, INK) + .8
    # Highlighted scope predicate pill (phi)
    phi_lbl = "`i_category='Electronics'`"
    w_phi = measure(phi_lbl, 4.9) + measure(r'$\varphi$', 5.3, 'bold') + 2.4
    phi_cx = x_sql + w_phi / 2
    s.rect(x_sql, yc2 - 1.25, w_phi, 2.5, ACC_PALE, ACC, .18, r=.4)
    label(x_sql + .9, yc2, phi_lbl, 4.9, INK)
    label(x_sql + w_phi - .85, yc2, r'$\varphi$', 5.3, ACC_DK, 'bold', 'right')
    x_sql += w_phi + .65
    x_sql += label(x_sql, yc2, '`AND`', 4.8, MUTED) + .65
    # Highlighted period binding pill (p_0)
    p0_lbl = '`d_year=2026, d_moy=1`' if en else '`d_year=2026,d_moy=1`'
    w_p0 = W - 2.3 - x_sql
    p0_cx = x_sql + w_p0 / 2
    s.rect(x_sql, yc2 - 1.25, w_p0, 2.5, LEARN_PALE, LEARN, .18, r=.4, dash=(.55, .35))
    label(x_sql + .85, yc2, p0_lbl, 4.9, INK, width=w_p0 - 5.2)
    label(x_sql + w_p0 - .8, yc2, '$p_0$', 5.2, LEARN_DK, 'bold', 'right')

    # Catalog join grounding chip + Dual split arrows (panel a bottom 13.1 -> panel b top 15.1)
    w_cat = pill(1.6, 14.1, 'Verified joins in $\\mathcal{M}$' if en else '复用 $\\mathcal{M}$ 中已验证连接',
                 SOFT_BG, NAVY_EDGE, ACC_DK, size=4.45, font='bold', pad_x=.85, h=1.55, r=.35)
    s.route([(1.6 + w_cat, 14.1), (1.6 + w_cat + 2.2, 14.1), (1.6 + w_cat + 2.2, 15.1)],
            ACC, .2, dash=(.55, .3), length=.7)
    s.route([(phi_cx, 13.1), (phi_cx, 15.1)], ACC, .24, length=.8)
    label(phi_cx + 1.0, 14.1, r'fixed $\varphi \to I$' if en else r'固定 $\varphi \to I$', 4.8, ACC_DK, 'bold')
    s.route([(p0_cx, 13.1), (p0_cx, 15.1)], LEARN, .24, length=.8)
    label(p0_cx - 1.0, 14.1, r'param $p_0$' if en else r'参数 $p_0$', 4.8, LEARN_DK, 'bold', 'right')

    # ------------------------------------------------------------------ (b)
    card(15.1, 27.3 + DY, '(b) Extract core query $I$ & constraints $C$' if en
         else '(b) 提取核心查询 $I$ 与约束 $C$')
    s_text = 'join DAG, N:1' if en else '连接 DAG, N:1'
    ws = measure(s_text, 4.9)
    label(W - 1.6, 16.85, s_text, 4.9, MUTED, align='right')
    gate_pill(W - 1.6 - ws - .6, 16.85, 'Static' if en else '静态', 'right')

    # Left subcard: Kernel graph I relational join DAG
    s.rect(1.6, 19.0, 54.7, 15.8, SOFT_BG, NAVY_EDGE, .18, r=.45)
    label(2.4, 20.3, 'Core query $I$' if en else '核心查询 $I$', 5.5, ACC_DK, 'bold')
    cx_chk = 55.5
    for chk_txt in ('no dates' if en else '无日期', 'DAG, N:1' if en else 'N:1 有向无环'):
        tw = measure(chk_txt, 4.8)
        cx_chk -= tw
        label(cx_chk, 20.3, chk_txt, 4.8, MUTED)
        cx_chk -= 1.2
        check_mark(cx_chk, 20.3, True, ACC, k=.65, sw=.22)
        cx_chk -= 1.4

    # 3 Mini tables aligned horizontally at join rows
    row_h, head_h = 2.55, 2.2
    ty = 21.8
    item_x, item_w = 2.3, 14.6
    fact_x, fact_w = 22.0, 17.7
    date_x, date_w = 44.5, 11.1

    ys_f = mini_table(fact_x, ty, fact_w, '`store_sales`', 3, role='$F$', head=head_h, row_h=row_h)
    ys_i = mini_table(item_x, ty, item_w, '`item`', 2, head=head_h, row_h=row_h)
    dy = ty + 2 * row_h - .15  # aligns date_dim row 0 (date_sk) with store_sales row 2 (sold_date_sk)
    ys_d = mini_table(date_x, dy, date_w, '`date_dim`', 2, head=head_h, row_h=row_h)

    # Fact columns
    key_icon(fact_x + .5, ys_f[0], INK)
    label(fact_x + 2.75, ys_f[0], '`K:(item,tkt)`', 4.8, INK, width=12.4)
    cond_marker(fact_x + fact_w - 1.1, ys_f[0], 1, r=.78)

    label(fact_x + .75, ys_f[1], r'$\Sigma$', 5.2, ACC_DK, 'bold')
    label(fact_x + 2.75, ys_f[1], '`ss_net_paid`', 4.8, INK, width=14.0)

    label(fact_x + .75, ys_f[2], r'$\tau$', 5.2, LEARN_DK, 'bold')
    label(fact_x + 2.75, ys_f[2], '`sold_date_sk`', 4.8, INK, width=14.0)

    # Item columns: row 0 item_sk, row 1 highlighted phi filter
    key_icon(item_x + .5, ys_i[0], INK)
    label(item_x + 2.75, ys_i[0], '`item_sk`', 4.8, INK, width=9.4)
    cond_marker(item_x + item_w - 1.1, ys_i[0], 2, r=.78)

    s.rect(item_x + .15, ys_i[1] - row_h / 2 + .1, item_w - .3, row_h - .2, ACC_PALE, None, r=.2)
    label(item_x + .7, ys_i[1], "`'Elec.'`", 4.8, ACC_DK)
    s.rect(item_x + item_w - 3.6, ys_i[1] - .9, 3.0, 1.8, ACC, None, r=.35)
    label(item_x + item_w - 2.1, ys_i[1], r'$\varphi$', 4.9, WHITE, 'bold', 'center')

    # Date_dim columns: row 0 date_sk, row 1 highlighted period slot
    key_icon(date_x + .42, ys_d[0], INK)
    label(date_x + 2.4, ys_d[0], '`date_sk`', 4.8, INK, width=6.6)
    cond_marker(date_x + date_w - 1.0, ys_d[0], 4, r=.78)

    s.rect(date_x + .15, ys_d[1] - row_h / 2 + .1, date_w - .3, row_h - .2, LEARN_PALE, None, r=.2)
    label(date_x + .55, ys_d[1], '`yr,moy`', 4.8, LEARN_DK)
    s.rect(date_x + date_w - 2.8, ys_d[1] - .85, 2.3, 1.7, WHITE, LEARN, .14, r=.35, dash=(.4, .25))
    label(date_x + date_w - 1.65, ys_d[1], '$p$', 4.8, LEARN_DK, 'bold', 'center')

    # N:1 Crow's-foot joins with condition markers 3 and 5
    # 1) item (1) --< store_sales (N) along ys_f[0] == ys_i[0]
    j1_x0, j1_x1, j1_y = item_x + item_w, fact_x, ys_f[0]
    s.line(j1_x0, j1_y, j1_x1, j1_y, CARD_EDGE, .18)
    one_bar(j1_x0, j1_y, +1)
    crow(j1_x1, j1_y, -1)
    label((j1_x0 + j1_x1) / 2, j1_y - 1.45, 'N:1', 4.2, ACC_DK, 'bold', 'center')
    cond_marker((j1_x0 + j1_x1) / 2, j1_y, 3, r=.78, halo=True)

    # 2) store_sales (N) >-- date_dim (1) along ys_f[2] == ys_d[0]
    j2_x0, j2_x1, j2_y = fact_x + fact_w, date_x, ys_f[2]
    s.line(j2_x0, j2_y, j2_x1, j2_y, CARD_EDGE, .18)
    crow(j2_x0, j2_y, +1)
    one_bar(j2_x1, j2_y, -1)
    label((j2_x0 + j2_x1) / 2, j2_y - 1.45, r'$\tau$', 5.0, LEARN_DK, 'bold', 'center')
    cond_marker((j2_x0 + j2_x1) / 2, j2_y, 5, r=.78, halo=True)

    # Right subcard: Runtime slots (p, d) + dashed connector from date_dim slot p
    rx0, rw = 57.6, W - 59.2
    s.rect(rx0, 19.0, rw, 15.8, '#FAFBFD', LEARN, .16, r=.45, dash=(.65, .4))
    label(rx0 + rw / 2, 20.4, 'Query params $(p,d)$' if en else '查询参数 $(p,d)$', 5.5, LEARN_DK, 'bold', 'center')
    s.route([(date_x + date_w, ys_d[1]), (rx0, ys_d[1])], LEARN, .18, dash=(.55, .35), length=.7)

    slot_rows = (
        (22.1, WHITE, LEARN, '$p_0$: Jan. 2026 $\\cdot$ id' if en else '$p_0$: 2026/1 $\\cdot$ 原值'),
        (26.4, LEARN_PALE, LEARN_EDGE, 'Reuse: month + rank' if en else '复用: 月份 + 排名'),
        (30.7, LEARN_PALE, LEARN_EDGE, 'Reuse: 2 periods + $\\Delta$' if en else '复用: 两期 + 差值 $\\Delta$'),
    )
    for sy, fill, edge_c, txt in slot_rows:
        s.rect(rx0 + .9, sy, rw - 1.8, 3.4, fill, edge_c, .15, r=.38)
        label(rx0 + rw / 2, sy + 1.7, txt, 5.0, INK if fill == WHITE else LEARN_DK,
              'bold' if fill == WHITE else 'sans', 'center', width=rw - 2.4)

    # Bottom strip of (b): the dependency graph G that C(I) creates for the new definition, T -> c -> x
    # (Section 4.1: H deduplicates shared checks along T -> c -> x). Checks 1-5 are the markers above and the rows
    # of Fig. 5; dep(c) gives the T -> c edges; the losses are the M5-L1 join statistics (1.03% = 10,305 of 10^6
    # store_sales rows without a date match, exp/2026-10-08-optimize trace).
    G0 = 35.4
    s.line(1.6, G0, W - 1.6, G0, RULE, .15)
    hy_g = G0 + 1.5
    e_g = 1.8 + label(1.8, hy_g, 'Dependency graph $\\mathcal{G}$' if en else '依赖图 $\\mathcal{G}$', 5.1, INK, 'bold')
    label(e_g + 1.0, hy_g, r'$T \to c \to x$', 4.9, MUTED)
    r_txt = r'baselines on $D_{s_0}$' if en else r'在 $D_{s_0}$ 上记录基线'
    w_rt = measure(r_txt, 4.8)
    label(W - 1.6, hy_g, r_txt, 4.8, MUTED, align='right')
    gate_pill(W - 1.6 - w_rt - .6, hy_g, 'DB', 'right')

    ty_g, cy_g, xy_g = G0 + 3.6, G0 + 7.3, G0 + 11.4         # rows: tables, constraint nodes, definition
    for yv, tag in ((ty_g, '$T$'), (cy_g, r'$c\in\mathcal{H}$'), (xy_g, r'$x\in\mathcal{M}$')):
        label(1.8, yv, tag, 4.7, MUTED)

    # constraint nodes, ordered so that no T -> c edge crosses another
    cxs = {2: 14.0, 3: 28.0, 1: 42.0, 5: 56.0, 4: 70.0}
    nw, nh = 13.0, 2.4
    for i, cxv in cxs.items():
        s.rect(cxv - nw / 2, cy_g - nh / 2, nw, nh, WHITE, SUB_EDGE, .14, r=.4)
        x = cxv - nw / 2 + .9
        cond_marker(x, cy_g, i, r=.7)
        x += 1.2
        if i in (3, 5):
            val = 0.0 if i == 3 else 1.0305
            gauge(x, cy_g, 5.2, val, .1, 1.5, h=1.05)
            label(x + 5.7, cy_g, '`0.00%`' if i == 3 else '`1.03%`', 4.6, ACC_DK)
        else:
            x += key_icon(x, cy_g, INK, k=.72) + .45
            label(x, cy_g, {1: 'grain `K`', 2: '`item_sk`', 4: '`date_sk`'}[i], 4.5, INK,
                  width=cxv + nw / 2 - x - .3)

    # tables, each above the checks that depend on it
    tables = (('`item`', 21.0, (2, 3)), ('`store_sales`', 42.0, (3, 1, 5)), ('`date_dim`', 63.0, (5, 4)))
    th = 1.9
    for name, txv, deps in tables:
        tw_ = measure(name, 4.6) + 2.0
        s.rect(txv - tw_ / 2, ty_g - th / 2, tw_, th, TABLE_HEAD, CARD_EDGE, .14, r=.35)
        label(txv, ty_g, name, 4.6, INK, align='center')
        ports = [txv + (k - (len(deps) - 1) / 2) * min(2.4, tw_ / len(deps)) for k in range(len(deps))]
        for px_, i in zip(ports, deps):
            s.line(px_, ty_g + th / 2, cxs[i], cy_g - nh / 2, CARD_EDGE, .14)

    # the new definition, fed by its five checks
    x_lbl = r'$x=m^0$: Electronics revenue (ER)' if en else r'$x=m^0$：电子品类营业额 (ER)'
    xw = measure(x_lbl, 4.8, 'bold') + 2.4
    xcx = 42.0
    s.rect(xcx - xw / 2, xy_g - 1.0, xw, 2.0, ACC, None, r=.45)
    label(xcx, xy_g, x_lbl, 4.8, WHITE, 'bold', 'center')
    for k, i in enumerate((2, 3, 1, 5, 4)):           # landing points spread over the node, so edges fan in
        s.line(cxs[i], cy_g + nh / 2, xcx + (k - 2) * min(6.0, xw / 5), xy_g - 1.0, ACC, .16)
    assert xy_g + 1.0 <= 15.1 + 27.3 + DY - .5, 'definition node leaves panel (b)'
    sh_txt = r'1, 4, 5 shared in $\mathcal{H}$ (Fig. 5)' if en else r'1、4、5 在 $\mathcal{H}$ 中共享（图 5）'
    label(xcx + xw / 2 + 1.2, xy_g, sh_txt, 4.5, MUTED)
    assert xcx + xw / 2 + 1.2 + measure(sh_txt, 4.5) < W - 1.6, 'sharing note runs past the card'
    assert cxs[4] + nw / 2 < W - 1.6 and cxs[2] - nw / 2 > 1.8 + measure(r'$c\in\mathcal{H}$', 4.7) + .5

    # ------------------------------------------------------------------ (c)
    s.route([(W / 2, 42.4 + DY), (W / 2, 44.0 + DY)], ACC, .24, length=.75)
    card(44.0 + DY, 18.7, '(c) Recompilation equivalence check' if en
         else '(c) 重编译等价性验证', 2)
    label(W - 1.6, 45.75 + DY, 'compiled from $I$' if en else '由 $I$ 编译', 5.0, MUTED, align='right')

    x_axis, bar_max = 31.2, 20.5
    x_target = x_axis + bar_max * (2754299.60 / 13532799.00)
    replay_rows = (
        (49.75 + DY, SOFT_BG, SUB_EDGE, 'Src', 'Source SQL ($D_{s_0}$)' if en else '源 SQL ($D_{s_0}$)',
         2754299.60, SLATE, None, 'target' if en else '源基准', None),
        (53.45 + DY, ACC_PALE, NAVY_EDGE, 'Cand.', r'Keep $\varphi$ $(I,p_0,d_0)$' if en else r'保留 $\varphi$ $(I,p_0,d_0)$',
         2754299.60, ACC, True, 'Publish' if en else '发布', '1.0x'),
        (57.15 + DY, RED_PALE, RED_EDGE, 'Cand.', r"Omit $\varphi$ (no `'Elec.'`)" if en else r"漏掉 $\varphi$",
         13532799.00, RED, False, 'Reject' if en else '拒绝', r'$4.9\times$'),
    )
    for yc, row_bg, row_edge, gcode, row_lbl, val, bcol, ok, v_text, mult in replay_rows:
        s.rect(1.6, yc - 1.55, W - 3.2, 3.1, row_bg, row_edge, .14, r=.38)
        wg = gate_pill(2.2, yc, gcode)
        label(2.2 + wg + .8, yc, row_lbl, 5.2, bcol if ok is not None else INK,
              'bold' if ok is not None else 'sans', width=x_axis - (2.2 + wg + 1.2))
        bw = bar_max * (val / 13532799.00)
        s.rect(x_axis, yc - .75, bw, 1.5, bcol, None, r=.2)
        if mult == r'$4.9\times$':
            label(x_axis + bw / 2, yc, mult, 4.9, WHITE, 'bold', 'center')
        vx = x_axis + bw + .9
        label(vx, yc, f'`{val:,.2f}`', 5.2, bcol if ok is not None else INK)
        # Right verdict pill
        px0, pw = W - 16.0, 13.8
        if ok is None:
            s.rect(px0, yc - 1.1, pw, 2.2, WHITE, SUB_EDGE, .14, r=.35)
            label(px0 + pw / 2, yc, v_text, 5.0, MUTED, 'bold', 'center')
        else:
            s.rect(px0, yc - 1.1, pw, 2.2, bcol, None, r=.35)
            check_mark(px0 + 2.5, yc, ok, WHITE, k=.75, sw=.26)
            label(px0 + 4.4, yc, v_text, 5.2, WHITE, 'bold')

    # Axis & target vertical dashed reference line across the 3 replay bars
    s.line(x_axis, 48.0 + DY, x_axis, 58.9 + DY, CARD_EDGE, .15)
    s.line(x_target, 48.0 + DY, x_target, 58.9 + DY, ACC_DK, .18, dash=(.55, .35))

    label(1.7, 60.75 + DY, 'Checks equivalence on $(D_{s_0},p_0,d_0)$; cross-period validity relies on structural constraints & domain assumptions.' if en
          else '仅在 $(D_{s_0},p_0,d_0)$ 上检验等价性；跨期正确性依赖结构约束与领域假设。', 4.85, MUTED, width=W - 3.4)

    # ------------------------------------------------------------------ (d)
    # Offline, once per catalog: the published definitions' attributes become the lookup judge's training data
    # (moved here from Fig. 4, which now shows only the online lookup). Wordings are generated training questions
    # (exp/2026-11-10-lookup-facets/train-xl.jsonl, shortened); labels follow the consistency rule.
    d_top = 64.7 + DY
    s.route([(W / 2, 62.9 + DY), (W / 2, d_top)], ACC, .24, length=.75)
    label(W / 2 + 1.0, (62.7 + DY + d_top) / 2, r'publish $m^0 \to \mathcal{M}$' if en else r'发布 $m^0 \to \mathcal{M}$',
          4.6, ACC_DK, 'bold')
    b_d = card(d_top, 19.4, '(d) Lookup training data from $\\mathcal{M}$' if en else '(d) 由 $\\mathcal{M}$ 合成查找训练数据')
    label(W - 1.6, d_top + 1.75, 'offline, once per catalog' if en else '离线，每个定义库一次', 5.0, MUTED, align='right')

    ATTR = '#8A5A00'                                  # attribute values (ochre, as Fig. 2's attribute chips)
    int_cols = (ACC_DK, ATTR, MUTED)
    hy = b_d + 1.45                                   # column headers
    rows_y = [hy + 2.75 + 2.3 * k for k in range(4)]   # clear of the two-line D01/D02 headers
    px = 24.0                                         # phrasing column
    c1, c2 = W - 9.2, W - 3.7                         # label columns
    label(1.6, hy, 'intents from $B(I)$' if en else '由 $B(I)$ 枚举意图', 4.5, MUTED)
    label(px + 1.0, hy, 'LLM phrasing' if en else '大模型改写的问法', 4.5, MUTED)
    for c, did, attr in ((c1, 'D01', 'after' if en else '扣券后'), (c2, 'D02', 'before' if en else '扣券前')):
        label(c, hy - .55, f'`{did}`', 4.6, ACC_DK, align='center')
        label(c, hy + 1.0, attr, 3.9, ATTR, align='center')

    phrasings = (('takings of Changsha stores, Q3?', 0, (True, True)),
                 ('how much did offline shops sell?', 0, (True, True)),
                 ('store income after coupons, ex tax?', 1, (True, False)),
                 ('units the web store sold last year?', 2, (False, False)))
    if not en:
        phrasings = (('长沙线下店上季度流水多少？', 0, (True, True)), ('上个月北京线下店卖了多少钱？', 0, (True, True)),
                     ('深圳店里券后税外的收入？', 1, (True, False)), ('去年网店卖了多少件？', 2, (False, False)))
    for k, ((text, it, labs), yc) in enumerate(zip(phrasings, rows_y)):
        if k:
            s.line(px + .4, yc - 1.15, W - 1.6, yc - 1.15, RULE, .1)
        s.rect(px + .1, yc - .78, .5, 1.56, int_cols[it], None, r=.2)
        label(px + 1.1, yc, text, 4.9, INK, width=c1 - 3.2 - px - 1.1)
        for c, ok in zip((c1, c2), labs):
            check_mark(c, yc, ok, k=.62, sw=.24)

    # intents (from the attributes of M's definitions) -> LLM -> wordings
    iw, ih = 14.4, 1.75
    inty = [(rows_y[0] + rows_y[1]) / 2, rows_y[2], rows_y[3]]
    assert min(b - a for a, b in zip(inty, inty[1:])) >= ih + .3, 'intent pills touch'
    intents = ('store · revenue', '+ after coupons', 'web · units') if en else ('门店 · 销售额', '+ 扣券后实付', '网店 · 销量')
    sx, sy = 1.6 + iw + 4.6, inty[1]
    jx = sx - 2.5
    for k, (txt, yc) in enumerate(zip(intents, inty)):
        s.rect(1.6, yc - ih / 2, iw, ih, WHITE, int_cols[k], .16, r=ih / 2)
        label(1.6 + iw / 2, yc, txt, 4.6, int_cols[k], align='center', width=iw - .6)
        pts = [(1.6 + iw + .1, yc), (jx, yc)] + ([(jx, sy)] if abs(yc - sy) > 1e-6 else [])
        s.route(pts, int_cols[k], .15, heads=None, radius=.4)
    s.line(jx, sy, sx - 1.15, sy, LEARN, .15)
    kk = .28 * 1.1                                    # four-pointed star, the LLM mark used in Figs. 2 and 4
    s.poly([(sx, sy - 1.1), (sx + kk, sy - kk), (sx + 1.1, sy), (sx + kk, sy + kk), (sx, sy + 1.1),
            (sx - kk, sy + kk), (sx - 1.1, sy), (sx - kk, sy - kk)], LEARN, None)
    llm_w = measure('LLM', 4.2, 'bold')
    label(sx, sy + 2.0, 'LLM', 4.2, LEARN, 'bold', 'center')
    fan_x = sx + 1.9
    assert jx < sx - llm_w / 2 - .4 and sx + llm_w / 2 + .3 < fan_x, 'LLM label touches the routes'
    for yc in rows_y:
        mid = [(fan_x, sy), (fan_x, yc)] if abs(yc - sy) > 1e-6 else []
        s.route([(sx + 1.2, sy)] + mid + [(px - .3, yc)], LEARN, .14, radius=.4, length=.6)

    label(1.7, d_top + 19.4 - 1.45, 'Labels by Definition 4.1, no annotation; peers (`D02` for “after coupons”) are hard negatives. Trains the judge of Fig. 4.'
          if en else '标签由定义 4.1 自动给出，无需人工标注；同组同伴（如“扣券后”问法下的 D02）即难负例；用于训练图 4 的判别器。',
          4.6, MUTED, width=W - 3.4)
    assert d_top + 19.4 <= H - .3, (d_top + 19.4, H)


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
