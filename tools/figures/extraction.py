"""Figure 3: verifiable relational kernel extraction (steps 1-2), single column.

Visual workflow across three panels:
(a) Verified source session: natural-language question -> verified answer via G1/G2
    arithmetic provenance and G5 read-only SQL, with scope predicate phi and period
    literal p_0 highlighted inside the canonicalized query.
(b) Extract kernel I & runtime slots; derive C: G3 separates phi into the star join
    graph (mini tables item, store_sales, date_dim with crow's-foot N:1 joins and
    condition markers 1-5) from runtime slots (p, d), while deriving KeyUnique (G4)
    and unmatched join-loss gauges matched to M5-L1.
(c) Example-blind replay before publication: linear bar comparison on D_{s_0} shows
    G6 source SQL matching G7 Keep phi (2,754,299.60 -> Publish) while G7 Omit phi
    inflates 4.9x to 13,532,799.00 (Reject).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import PT, measure  # noqa: E402

NAME = 'extraction'
W, H = style.COLUMN, 63.2

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
    card(.5, 12.6, '(a) Source session & derivation DAG' if en else '(a) 源会话与推导图', 1)
    # Right header gates: [G1-G2] deriv.  [G3] read-only
    r_text = 'read-only' if en else '只读'
    w_r = measure(r_text, 4.9)
    xr = W - 1.6 - w_r
    label(xr, 2.25, r_text, 4.9, MUTED)
    wg3 = gate_pill(xr - .6, 2.25, 'G3', 'right')
    t_text = 'deriv.' if en else '推导图'
    w_t = measure(t_text, 4.9)
    xt = xr - .6 - wg3 - 1.3 - w_t
    label(xt, 2.25, t_text, 4.9, MUTED)
    gate_pill(xt - .6, 2.25, 'G1–G2' if en else 'G1-G2', 'right')

    # Row 1: User question bubble -> verified answer pill
    yc1 = 6.05
    person_icon(2.6, yc1)
    s.rect(4.5, yc1 - 1.5, 31.2, 3.0, SOFT_BG, SUB_EDGE, .15, r=.45)
    s.rect(5.1, yc1 - .95, 2.8, 1.9, LEARN_DK, None, r=.35)
    label(6.5, yc1, 'Q', 4.9, WHITE, 'bold', 'center')
    label(8.6, yc1, 'Jan. 2001 electronics revenue?' if en else '2001年1月电子品类营业额？',
          5.6, INK, width=26.6)
    s.route([(36.2, yc1), (47.4, yc1)], MUTED, .2, length=.8)
    label(41.8, yc1 - 1.1, '0 raw rows' if en else '零原始行', 4.8, MUTED, 'sans', 'center')

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
    p0_lbl = '`d_year=2001, d_moy=1`' if en else '`d_year=2001,d_moy=1`'
    w_p0 = W - 2.3 - x_sql
    p0_cx = x_sql + w_p0 / 2
    s.rect(x_sql, yc2 - 1.25, w_p0, 2.5, LEARN_PALE, LEARN, .18, r=.4, dash=(.55, .35))
    label(x_sql + .85, yc2, p0_lbl, 4.9, INK, width=w_p0 - 5.2)
    label(x_sql + w_p0 - .8, yc2, '$p_0$', 5.2, LEARN_DK, 'bold', 'right')

    # Catalog join grounding chip + Dual split arrows (panel a bottom 13.1 -> panel b top 15.1)
    w_cat = pill(1.6, 14.1, 'Catalog `join:` in $\\mathcal{M}$' if en else '复用 $\\mathcal{M}$ 中 `join:`',
                 SOFT_BG, NAVY_EDGE, ACC_DK, size=4.45, font='bold', pad_x=.85, h=1.55, r=.35)
    s.route([(1.6 + w_cat, 14.1), (1.6 + w_cat + 2.2, 14.1), (1.6 + w_cat + 2.2, 15.1)],
            ACC, .2, dash=(.55, .3), length=.7)
    s.route([(phi_cx, 13.1), (phi_cx, 15.1)], ACC, .24, length=.8)
    label(phi_cx + 1.0, 14.1, r'fixed $\varphi \to I$' if en else r'固定 $\varphi \to I$', 4.8, ACC_DK, 'bold')
    s.route([(p0_cx, 13.1), (p0_cx, 15.1)], LEARN, .24, length=.8)
    label(p0_cx - 1.0, 14.1, r'slot $p_0$' if en else r'槽位 $p_0$', 4.8, LEARN_DK, 'bold', 'right')

    # ------------------------------------------------------------------ (b)
    card(15.1, 27.3, '(b) Compose kernel $I$ & condition DAG $C$' if en
         else '(b) 组合核图 $I$ 与条件有向图 $C$')
    s_text = 'join DAG, N:1' if en else '连接 DAG, N:1'
    ws = measure(s_text, 4.9)
    label(W - 1.6, 16.85, s_text, 4.9, MUTED, align='right')
    gate_pill(W - 1.6 - ws - .6, 16.85, 'G4', 'right')

    # Left subcard: Kernel graph I relational join DAG
    s.rect(1.6, 19.0, 54.7, 15.8, SOFT_BG, NAVY_EDGE, .18, r=.45)
    label(2.4, 20.3, 'Kernel graph $I$' if en else '关系核图 $I$', 5.5, ACC_DK, 'bold')
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
    label((j1_x0 + j1_x1) / 2, j1_y - 1.45, '`join:`' if en else '复用边', 4.2, ACC_DK, 'bold', 'center')
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
    label(rx0 + rw / 2, 20.4, 'Runtime slots $(p,d)$' if en else '运行期槽位 $(p,d)$', 5.5, LEARN_DK, 'bold', 'center')
    s.route([(date_x + date_w, ys_d[1]), (rx0, ys_d[1])], LEARN, .18, dash=(.55, .35), length=.7)

    slot_rows = (
        (22.1, WHITE, LEARN, '$p_0$: Jan. 2001 $\\cdot$ id' if en else '$p_0$: 2001/1 $\\cdot$ 原值'),
        (26.4, LEARN_PALE, LEARN_EDGE, 'Reuse: month + rank' if en else '复用: 月份 + 排名'),
        (30.7, LEARN_PALE, LEARN_EDGE, 'Reuse: 2 periods + $\\Delta$' if en else '复用: 两期 + 差值 $\\Delta$'),
    )
    for sy, fill, edge_c, txt in slot_rows:
        s.rect(rx0 + .9, sy, rw - 1.8, 3.4, fill, edge_c, .15, r=.38)
        label(rx0 + rw / 2, sy + 1.7, txt, 5.0, INK if fill == WHITE else LEARN_DK,
              'bold' if fill == WHITE else 'sans', 'center', width=rw - 2.4)

    # Bottom strip of (b): Derived checks C(I) with icons & gauges
    s.line(1.6, 35.4, W - 1.6, 35.4, RULE, .15)
    s.line(45.2, 35.9, 45.2, 41.8, RULE, .14)

    # Left: KeyUnique condition nodes 1, 2, 4 -> H + G5
    ky1, ky2 = 37.15, 40.35
    wk = key_icon(1.8, ky1, INK, k=.95)
    tw_ku = label(1.8 + wk + .7, ky1, 'KeyUnique nodes $\\to \\mathcal{H}$' if en else '键唯一节点 $\\to \\mathcal{H}$',
                  5.1, INK, 'bold')
    gate_pill(1.8 + wk + .7 + tw_ku + .8, ky1, 'G5')
    kx = 2.0
    for idx, tname in ((1, '`store_sales.K`'), (2, '`item`'), (4, '`date_dim`')):
        cond_marker(kx, ky2, idx, r=.74)
        kx += 1.05 + label(kx + 1.05, ky2, tname, 4.4, INK) + 1.05

    # Right: Join-loss edges 3 and 5
    gx0 = 46.2
    wg = gauge_icon(gx0, ky1)
    label(gx0 + wg + .8, ky1, r'Join-loss edges ($\leq b+0.1$ pp)' if en else r'连接丢行边 ($\leq b+0.1$ pp)',
          5.1, INK, 'bold', width=W - gx0 - wg - 2.6)
    g1x = gx0 + .8
    cond_marker(g1x, ky2, 3, r=.78)
    gauge(g1x + 1.3, ky2, 8.2, 0.0, .1, 1.5, h=1.25)
    label(g1x + 10.1, ky2, '`0.00%`', 5.0, ACC_DK)

    g2x = g1x + 17.6
    cond_marker(g2x, ky2, 5, r=.78)
    gauge(g2x + 1.3, ky2, 8.2, 1.0305, .1, 1.5, h=1.25)
    label(g2x + 10.1, ky2, '`1.03%`', 5.0, ACC_DK)

    # ------------------------------------------------------------------ (c)
    s.route([(W / 2, 42.4), (W / 2, 44.0)], ACC, .24, length=.75)
    card(44.0, 18.7, '(c) Example-blind replay before publication' if en
         else '(c) 发布前盲示例重编译验证', 2)
    label(W - 1.6, 45.75, 'no draft SQL' if en else '弃用草稿 SQL', 5.0, MUTED, align='right')

    x_axis, bar_max = 31.2, 20.5
    x_target = x_axis + bar_max * (2754299.60 / 13532799.00)
    replay_rows = (
        (49.75, SOFT_BG, SUB_EDGE, 'G6', 'Source SQL ($D_{s_0}$)' if en else '源 SQL ($D_{s_0}$)',
         2754299.60, SLATE, None, 'target' if en else '源基准', None),
        (53.45, ACC_PALE, NAVY_EDGE, 'G7', r'Keep $\varphi$ $(I,p_0,d_0)$' if en else r'保留 $\varphi$ $(I,p_0,d_0)$',
         2754299.60, ACC, True, 'Publish' if en else '发布', '1.0x'),
        (57.15, RED_PALE, RED_EDGE, 'G7', r"Omit $\varphi$ (no `'Elec.'`)" if en else r"漏掉 $\varphi$",
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
    s.line(x_axis, 48.0, x_axis, 58.9, CARD_EDGE, .15)
    s.line(x_target, 48.0, x_target, 58.9, ACC_DK, .18, dash=(.55, .35))

    label(1.7, 60.75, 'Evidence on $(D_{s_0},p_0,d_0)$; cross-period validity relies on graph invariants G4–G5 & P1–P3.' if en
          else '仅对 $(D_{s_0},p_0,d_0)$ 给出复现证据；跨期正确性依赖图不变量 G4–G5 与 P1–P3。', 4.85, MUTED, width=W - 3.4)


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
