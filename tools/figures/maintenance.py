"""Figure 5: shared validation followed by explicit repair admission (steps 5-6), single column.

Visual workflow across two panels:
(a) Share checks after a write: 7 conditions referenced 15 times across SR, RA, RR, ER
    in H; item and sales writes (bolts) trigger incremental rechecks once across all
    agents (unit-square work-saving gauges: 2/5 after item load, 3/12 after sales append).
(b) Repair: prune, verify, then require a unique edit: mini table diff on item (key 17, 'N'),
    visual horizontal bar pruning against the 1,000 distinct-key threshold, two-gate card
    (C(x + delta) on D and Repro on D_{s_0}) chained to (iii) Hist, and three-way admission
    outcome pills (Publish m^{r+1}, Retire, Pending).
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import PT, measure  # noqa: E402

NAME = 'maintenance'
W, H = style.COLUMN, 75.2

INK, MUTED = '#1F2328', '#596068'
CARD_EDGE, SUB_EDGE, RULE = '#737B84', '#B6BEC7', '#CFD5DC'
HEAD_BAND, TABLE_HEAD, SOFT_BG, WHITE = '#ECEFF3', '#EAECEF', '#F7F8FA', '#FFFFFF'
SLATE, BAR_MUTED, GRID_DOT = '#4E5D6C', '#C2C8D0', '#D8DDE3'
ACC, ACC_DK, ACC_PALE, NAVY_SOFT, NAVY_EDGE, GAUGE_TOL = '#24416B', '#1B3254', '#EDF1F7', '#F8FAFC', '#9EB1CC', '#C5D3E8'
MAINT_C, MAINT_DK, MAINT_PALE, MAINT_EDGE, ROW_TINT = '#2E5B58', '#214442', '#EBF1F0', '#9DB8B5', '#EFF3F2'
AMBER, AMBER_PALE, AMBER_EDGE = '#7D5C38', '#F4EFE8', '#C2B19C'
RED, RED_PALE, RED_EDGE = '#942B2B', '#F6EDED', '#CCA6A6'


def draw(s, lang):
    en = lang == 'en'

    def label(x, yc, text, size=6.0, color=INK, font='sans', align='left', width=None):
        return s.text(x, yc + .34 * size * PT, text, size, color, font, align, width)

    def step_badge(x, yc, n, color=MAINT_C, r=1.1):
        s.circle(x, yc, r, color)
        label(x, yc, str(n), 5.5, WHITE, 'bold', 'center')

    def cond_marker(x, yc, i, r=.78):
        s.circle(x, yc, r, SLATE)
        label(x, yc, str(i), 4.5, WHITE, 'bold', 'center')

    def check_mark(x, yc, ok, color=None, k=.75, sw=.25):
        c = color or (ACC if ok else RED)
        if ok:
            s.poly([(x - .62 * k, yc), (x - .15 * k, yc + .5 * k), (x + .65 * k, yc - .55 * k)],
                   None, c, sw, closed=False)
        else:
            s.line(x - .5 * k, yc - .5 * k, x + .5 * k, yc + .5 * k, c, sw)
            s.line(x - .5 * k, yc + .5 * k, x + .5 * k, yc - .5 * k, c, sw)

    def bang_badge(x, yc, color=AMBER, r=.85):
        s.circle(x, yc, r, color)
        label(x, yc, '!', 5.0, WHITE, 'bold', 'center')

    def key_icon(x, yc, color=INK, k=.85, sw=.16):
        r = .4 * k
        s.circle(x + r, yc, r, None, color, sw)
        x1 = x + 2 * r
        s.line(x1, yc, x1 + 1.3 * k, yc, color, sw)
        for t in (.75, 1.15):
            s.line(x1 + t * k, yc, x1 + t * k, yc + .42 * k, color, sw)
        return 2 * r + 1.3 * k

    def gauge_icon(x, yc):
        w, h = 2.4, .95
        y0 = yc - h / 2
        s.rect(x, y0, w, h, WHITE, None)
        s.rect(x + 1.25, y0, w - 1.25, h, RED_PALE, None)
        s.rect(x, y0, .82, h, ACC, None)
        s.rect(x + .82, y0, .43, h, GAUGE_TOL, None)
        s.rect(x, y0, w, h, None, CARD_EDGE, .11)
        s.line(x + 1.25, y0 - .22, x + 1.25, y0 + h + .22, RED, .18)
        return w

    def bolt(x, yc, h=1.8, color=MAINT_C):
        k = h / 2
        s.poly([(x + .32 * k, yc - k), (x - .44 * k, yc + .14 * k), (x - .02 * k, yc + .14 * k),
                (x - .32 * k, yc + k), (x + .44 * k, yc - .14 * k), (x + .02 * k, yc - .14 * k)],
               color, None)

    def rerun_icon(x, yc, r=.6, color=MAINT_C, sw=.19):
        t0, t1 = math.radians(70), math.radians(345)
        ts = [t0 + (t1 - t0) * i / 20 for i in range(21)]
        s.poly([(x + r * math.cos(t), yc - r * math.sin(t)) for t in ts], None, color, sw, closed=False)
        t = t1
        ang = math.atan2(-math.cos(t), -math.sin(t))
        ex, ey = x + r * math.cos(t), yc - r * math.sin(t)
        s.head(ex + .22 * math.cos(ang), ey + .22 * math.sin(ang), ang, color, length=.85 * r + .18)

    def units(x, yc, n, filled, color=MAINT_C, cell=.76, gap=.2, per_row=6):
        rows = -(-n // per_row)
        top = yc - (rows * cell + (rows - 1) * gap) / 2
        for i in range(n):
            r, c = divmod(i, per_row)
            cx, cy = x + c * (cell + gap), top + r * (cell + gap)
            if i < filled:
                s.rect(cx, cy, cell, cell, color, None, r=.1)
            else:
                s.rect(cx + .06, cy + .06, cell - .12, cell - .12, WHITE, color, .12, r=.1)
        return min(n, per_row) * (cell + gap) - gap

    def card(y, h, title, badge=None):
        s.rect(.6, y, W - 1.2, h, WHITE, CARD_EDGE, .18, r=.55)
        s.rect(.7, y + .1, W - 1.4, 3.3, HEAD_BAND, None, r=.45)
        s.rect(.7, y + 1.8, W - 1.4, 1.6, HEAD_BAND, None)
        s.line(.6, y + 3.4, W - .6, y + 3.4, RULE, .14)
        step_badge(2.3, y + 1.75, badge, MAINT_C, r=1.05)
        label(4.1, y + 1.75, title, 6.7, INK, 'bold')
        return y + 3.4

    # ------------------------------------------------------------------ (a)
    card(.5, 33.6, '(a) Share checks after a write' if en else '(a) 写入后共享条件检查', 5)
    label(W - 1.6, 2.25, r'7 checks, 15 refs in $\mathcal{H}$' if en else r'$\mathcal{H}$ 中 7 项检查、15 处引用',
          5.3, MUTED, align='right')

    yc_hdr = 5.9
    hx = 1.7
    hx += key_icon(hx, yc_hdr, MUTED) + .55
    hx += label(hx, yc_hdr, 'Key', 4.9, MUTED) + 1.3
    hx += gauge_icon(hx, yc_hdr) + .55
    label(hx, yc_hdr, 'Loss', 4.9, MUTED)

    xs = (37.8, 43.0, 48.2, 53.4)
    for x, name in zip(xs, ('SR', 'RA', 'RR', 'ER')):
        s.rect(x - 2.1, yc_hdr - 1.15, 4.2, 2.3, '#F2F4F7', SUB_EDGE, .13, r=.35)
        label(x, yc_hdr, name, 5.1, INK, 'bold', 'center')

    wx = (62.6, 76.2)
    for x, tbl in zip(wx, ('`item`', '`store_sales`')):
        w_tbl = measure(tbl, 4.9, 'bold')
        w_box = max(10.6, w_tbl + 3.0)
        s.rect(x - w_box / 2, yc_hdr - 1.15, w_box, 2.3, MAINT_PALE, MAINT_EDGE, .14, r=.35)
        bx = x - (1.8 + w_tbl) / 2
        bolt(bx + .45, yc_hdr, 1.75, MAINT_DK)
        label(bx + 1.5, yc_hdr, tbl, 4.9, MAINT_DK, 'bold')

    s.line(1.0, 7.8, W - 1.0, 7.8, RULE, .15)

    rows = (
        ('key', '`store_sales.K`', (0, 2, 3), False, True),
        ('key', '`item.i_item_sk`', (3,), True, False),
        ('loss', '`store_sales` $\\to$ `item`', (3,), True, True),
        ('key', '`date_dim.d_date_sk`', (0, 1, 2, 3), False, False),
        ('loss', '`store_sales` $\\to$ `date_dim`', (0, 2, 3), False, True),
        ('key', '`store_returns.K_r`', (1, 2), False, False),
        ('loss', '`store_returns` $\\to$ `date_dim`', (1,), False, False),
    )
    for idx, (fam, cond, refs, hit_item, hit_sales) in enumerate(rows):
        yc = 9.25 + 2.35 * idx
        if hit_item:
            s.rect(1.0, yc - 1.1, W - 2.0, 2.2, ROW_TINT, None, r=.3)
        cond_marker(2.3, yc, idx + 1, r=.76)
        if fam == 'key':
            key_icon(3.6, yc, INK, k=.82)
        else:
            gauge_icon(3.6, yc)
        label(6.7, yc, cond, 5.1, INK, width=28.2)

        for cx in xs:
            s.circle(cx, yc, .2, GRID_DOT)
        if len(refs) > 1:
            s.line(xs[min(refs)], yc, xs[max(refs)], yc, ACC, .18)
        for r in refs:
            s.circle(xs[r], yc, .55, ACC)

        for col_i, (cx, hit) in enumerate(zip(wx, (hit_item, hit_sales))):
            if idx == 1 and col_i == 0:
                s.rect(cx - 3.6, yc - .95, 7.2, 1.9, RED_PALE, RED_EDGE, .13, r=.35)
                rerun_icon(cx - 1.5, yc, .56, RED)
                check_mark(cx + 1.5, yc, False, RED, k=.7)
            elif hit:
                rerun_icon(cx, yc, .58, MAINT_C)
            else:
                s.line(cx - .8, yc, cx + .8, yc, RULE, .18)

    s.line(1.0, 25.4, W - 1.0, 25.4, RULE, .15)
    yt = 28.0
    label(1.7, yt, 'Checks run / full per-def:' if en else '实际检查／逐定义全检：', 5.4, INK, width=36.0)
    for x, (ours, whole) in zip(wx, ((2, 5), (3, 12))):
        uw = min(whole, 6) * .96 - .2
        lbl = f'{ours}/{whole}'
        lw = measure(lbl, 5.7, 'bold')
        sx = x - (uw + 1.0 + lw) / 2
        units(sx, yt, whole, ours, MAINT_C, per_row=6)
        label(sx + uw + 1.0, yt, lbl, 5.7, MAINT_DK, 'bold')

    # Bottom visual icon key
    s.line(1.7, 30.2, W - 1.7, 30.2, RULE, .12)
    yk = 32.0
    kx = 1.8
    s.line(kx, yk, kx + 2.4, yk, ACC, .18)
    s.circle(kx, yk, .45, ACC)
    s.circle(kx + 2.4, yk, .45, ACC)
    kx += 3.2 + label(kx + 3.2, yk, r'shared in $\mathcal{H}$' if en else r'$\mathcal{H}$ 中共享', 4.9, MUTED) + 2.2
    rerun_icon(kx + .5, yk, .5, MAINT_C)
    kx += 1.5 + label(kx + 1.5, yk, 'run once' if en else '全智能体跑 1 次', 4.9, MUTED) + 2.2
    uw = units(kx, yk, 1, 1, MAINT_C)
    kx += uw + .6 + label(kx + uw + .6, yk, 'executed' if en else '实际执行', 4.9, MUTED) + 2.2
    units(kx, yk, 1, 0, MAINT_C)
    label(kx + uw + .6, yk, 'saved vs. full recheck' if en else '省去的全检次数', 4.9, MUTED)

    # ------------------------------------------------------------------ (b)
    s.route([(W / 2, 34.1), (W / 2, 35.6)], MAINT_C, .24, length=.75)
    card(35.6, 39.0, '(b) Repair: prune, verify, then require a unique edit' if en
         else '(b) 修复：剪枝、验证，再判定唯一修改', 6)
    d_lbl = r'insert-only $\Delta T$' if en else r'仅追加 $\Delta T$'
    dw = measure(d_lbl, 4.9, 'bold') + 1.8
    s.rect(W - 1.6 - dw, 37.35 - 1.0, dw, 2.0, MAINT_PALE, MAINT_EDGE, .13, r=.35)
    label(W - 1.6 - dw / 2, 37.35, d_lbl, 4.9, MAINT_DK, 'bold', 'center')

    # Top strip: failing check + mini item table diff
    s.rect(1.6, 39.6, W - 3.2, 5.5, SOFT_BG, SUB_EDGE, .15, r=.42)
    cond_marker(3.0, 41.1, 2, r=.75)
    wk = key_icon(4.2, 41.1, INK, k=.82)
    xt = 4.2 + wk + .6
    xt += label(xt, 41.1, '`item.i_item_sk`', 5.2, INK) + 1.0
    label(xt, 41.1, r'`v0` $\to$ `v1`', 5.1, MAINT_DK, 'bold')
    check_mark(3.0, 43.65, False, RED, k=.72)
    label(4.2, 43.65, '1,001 rows / 1,000 keys (ratio 1.001)' if en else '1,001 行 / 1,000 键',
          5.0, RED, 'bold', width=31.0)

    s.line(36.2, 40.0, 36.2, 44.7, RULE, .14)
    # Two-row mini table diff
    tx0, tw = 37.0, W - 38.6
    r1y, r2y = 40.0, 42.55
    s.rect(tx0, r1y, tw, 2.2, WHITE, RULE, .13, r=.3)
    label(tx0 + 1.0, r1y + 1.1, '`17`', 5.0, MUTED)
    label(tx0 + 6.5, r1y + 1.1, "`'Electronics'`", 5.0, MUTED)
    label(tx0 + 23.8, r1y + 1.1, "`'Y'`", 5.0, INK)
    label(tx0 + tw - 1.0, r1y + 1.1, 'existing' if en else '原有行', 4.8, MUTED, align='right')

    s.rect(tx0, r2y, tw, 2.2, RED_PALE, RED_EDGE, .15, r=.3)
    label(tx0 + .7, r2y + 1.1, '`+17`', 5.0, RED, 'bold')
    label(tx0 + 6.5, r2y + 1.1, "`'Electronics'`", 5.0, INK)
    label(tx0 + 23.8, r2y + 1.1, "`'N'`", 5.0, RED, 'bold')
    check_mark(tx0 + tw - 1.8, r2y + 1.1, False, RED, k=.68)
    label(tx0 + tw - 3.3, r2y + 1.1, 'dup' if en else '重复', 4.9, RED, 'bold', 'right')

    # Middle row: 1. Bar-chart pruning card -> 2. Gate verification card
    my, mh = 46.0, 19.3
    lx0, lw = 1.6, 41.6
    s.rect(lx0, my, lw, mh, WHITE, SUB_EDGE, .16, r=.42)
    label(lx0 + .9, my + 1.65, r'1. Prune ($\leq 20$ vals)' if en else r'1. 剪枝 ($\leq 20$ 取值)',
          5.4, INK, 'bold')

    x_bar, x_key = lx0 + 17.5, lx0 + 33.8
    bw_key = x_key - x_bar
    label(x_key, my + 1.65, 'keys: 1k' if en else '键: 1k', 4.9, MAINT_DK, 'bold', 'center')
    s.line(x_key, my + 2.7, x_key, my + 12.6, MAINT_C, .2, dash=(.55, .35))

    # Horizontal bar rows
    # Row 1: current='Y' -> 1,000 (hits x_key -> keep)
    yb1 = my + 4.7
    label(x_bar - .7, yb1, "`current='Y'`", 5.0, ACC_DK, align='right')
    s.rect(x_bar, yb1 - .72, bw_key, 1.44, ACC, None, r=.2)
    label(x_bar + bw_key / 2, yb1, '`1,000`', 4.8, WHITE, 'bold', 'center')
    check_mark(x_key + 1.3, yb1, True, ACC, k=.7)
    label(x_key + 2.4, yb1, 'keep' if en else '留', 4.9, ACC_DK, 'bold', width=lx0 + lw - (x_key + 2.8))

    # Row 2: current='N' -> 1
    yb2 = my + 7.6
    label(x_bar - .7, yb2, "`current='N'`", 5.0, MUTED, align='right')
    s.rect(x_bar, yb2 - .68, .45, 1.36, BAR_MUTED, None)
    label(x_bar + 1.1, yb2, '`1`', 5.0, MUTED)
    check_mark(x_key + 1.3, yb2, False, RED, k=.65)

    # Row 3: category x5 -> 200-201
    yb3 = my + 10.8
    label(x_bar - .7, yb3, r'`category` $\times 5$', 5.0, MUTED, align='right')
    for k, rcnt in enumerate((200, 200, 200, 200, 201)):
        s.rect(x_bar, yb3 - 1.18 + k * .52, bw_key * (rcnt / 1000.0), .38, BAR_MUTED, None)
    label(x_bar + bw_key * .201 + .7, yb3, '`200–201`', 4.9, MUTED)
    check_mark(x_key + 1.3, yb3, False, RED, k=.65)

    # Row 4: price (50) skipped, cleanly separated below the 1k bar-chart threshold
    s.line(lx0 + .8, my + 13.05, lx0 + lw - .8, my + 13.05, RULE, .1)
    yb4 = my + 14.65
    wp = label(x_bar - .7, yb4, '`price` (50)', 4.9, MUTED, align='right')
    s.line(x_bar - .9 - wp, yb4 - .05, x_bar - .5, yb4 - .05, MUTED, .14)
    label(x_bar, yb4, '>20 vals: skip (not tried)' if en else '超过 20 值：跳过',
          4.9, MUTED, width=lx0 + lw - x_bar - .8)

    s.line(lx0 + .8, my + 16.4, lx0 + lw - .8, my + 16.4, RULE, .12)
    label(lx0 + lw / 2, my + 17.85, 'Counts prune only; not admission.' if en else '行数仅剪枝，不决定准入。',
          4.9, MUTED, 'sans', 'center')

    # Arrow from Prune -> Must pass BOTH
    rx0 = 46.2
    rw = W - 1.6 - rx0
    s.route([(lx0 + lw, my + 9.2), (rx0, my + 9.2)], ACC, .24, length=.8)
    label((lx0 + lw + rx0) / 2, my + 8.0, r'$\delta$', 5.2, ACC_DK, 'bold', 'center')

    # Right card: 2. Must pass (i)-(iii)
    s.rect(rx0, my, rw, mh, NAVY_SOFT, ACC, .2, r=.42)
    label(rx0 + .9, my + 1.65, '2. Must pass (i)–(iii)' if en else '2. 候选须通过 (i)–(iii)', 5.4, ACC_DK, 'bold')
    s.rect(rx0 + rw - 4.4, my + .7, 3.5, 1.9, ACC_PALE, NAVY_EDGE, .13, r=.35)
    label(rx0 + rw - 2.65, my + 1.65, "`'Y'`", 4.9, ACC_DK, 'bold', 'center')

    # Gate subcard (i)
    s1y = my + 3.1
    s.rect(rx0 + .9, s1y, rw - 1.8, 5.5, WHITE, SUB_EDGE, .14, r=.38)
    s.rect(rx0 + 1.5, s1y + .55, 3.2, 1.9, ACC_PALE, NAVY_EDGE, .12, r=.3)
    label(rx0 + 3.1, s1y + 1.5, '(i)', 4.9, ACC_DK, 'bold', 'center')
    label(rx0 + 5.3, s1y + 1.5, r'All $C(x\oplus\delta)$ on $D_s$' if en else r'快照 $D_s$ 全 $C$ 成立',
          5.3, INK, 'bold')
    check_mark(rx0 + rw - 2.2, s1y + 1.5, True, ACC, k=.75)
    krow_y = s1y + 4.0
    wk = key_icon(rx0 + 1.6, krow_y, MUTED, k=.8)
    kx2 = rx0 + 1.6 + wk + .6
    kx2 += label(kx2, krow_y, '`1,000=1,000`', 4.9, MUTED) + 1.8
    wg = gauge_icon(kx2, krow_y)
    label(kx2 + wg + .6, krow_y, 'joins ok' if en else '连接正常', 4.9, MUTED)

    # Gate subcard (ii)
    s2y = my + 9.4
    s.rect(rx0 + .9, s2y, rw - 1.8, 5.5, WHITE, SUB_EDGE, .14, r=.38)
    s.rect(rx0 + 1.5, s2y + .55, 3.2, 1.9, ACC_PALE, NAVY_EDGE, .12, r=.3)
    label(rx0 + 3.1, s2y + 1.5, '(ii)', 4.9, ACC_DK, 'bold', 'center')
    label(rx0 + 5.3, s2y + 1.5, r'Repro on $D_{s_0}$ ($E_x$)' if en else r'$D_{s_0}$ 答案复现',
          5.3, INK, 'bold')
    check_mark(rx0 + rw - 2.2, s2y + 1.5, True, ACC, k=.75)
    label(rx0 + 1.6, s2y + 4.0, '`2,754,299.60` = source' if en else '`2,754,299.60` = 源答案',
          5.0, ACC_DK, width=rw - 3.4)

    # Gate (iii) chain strip
    s3y = my + 15.6
    s.rect(rx0 + .9, s3y, rw - 1.8, 2.8, SOFT_BG, RULE, .13, r=.35)
    label(rx0 + 1.6, s3y + 1.4, r'(iii) Hist: untouched $D_s=D_{s_0}$' if en else r'(iii) Hist: 未变历史桶不变',
          4.9, ACC_DK, 'bold', width=rw - 5.2)
    check_mark(rx0 + rw - 2.2, s3y + 1.4, True, ACC, k=.7)

    # Bottom 3-way admission outcome pills (y = 67.2..73.8)
    oy, oh = 67.2, 6.6
    c1x, c1w = 1.6, 35.0
    s.route([(rx0 + rw / 2, my + mh), (rx0 + rw / 2, 66.25), (c1x + c1w / 2, 66.25), (c1x + c1w / 2, oy)],
            ACC, .24, length=.75, radius=.4)

    # Card 1: Unique pass -> Publish m^{r+1}
    s.rect(c1x, oy, c1w, oh, ACC_PALE, ACC, .2, r=.42)
    s.circle(c1x + 1.9, oy + 1.85, .82, ACC)
    check_mark(c1x + 1.9, oy + 1.85, True, WHITE, k=.55, sw=.24)
    label(c1x + 3.4, oy + 1.85, r'Unique ($|\mathcal{E}_{\mathrm{ok}}|=1$)' if en else r'唯一通过 ($|\mathcal{E}_{\mathrm{ok}}|=1$)',
          5.2, ACC_DK, 'bold')
    label(c1x + 1.4, oy + 4.75, "Publish $m^{r+1}$: +`i_is_current='Y'`" if en else "发布 $m^{r+1}$: +`i_is_current='Y'`",
          5.0, ACC_DK, 'bold', width=c1w - 2.2)

    # Card 2: 0 or >1 pass / NULL -> Retire
    c2x, c2w = 37.8, 23.2
    s.rect(c2x, oy, c2w, oh, RED_PALE, RED_EDGE, .15, r=.42)
    check_mark(c2x + 1.8, oy + 1.85, False, RED, k=.7)
    label(c2x + 3.2, oy + 1.85, '$0$ or $>1$ / NULL' if en else '0 或多候选 / 空值',
          5.1, RED, 'bold')
    label(c2x + 1.4, oy + 4.75, r'Retire $\bot$ (stop)' if en else r'停用 $\bot$（不再复用）',
          5.0, RED, 'bold', width=c2w - 2.2)

    # Card 3: Scale failure -> Pending
    c3x, c3w = 62.2, W - 63.8
    s.rect(c3x, oy, c3w, oh, AMBER_PALE, AMBER_EDGE, .15, r=.42)
    bang_badge(c3x + 1.8, oy + 1.85, AMBER, r=.8)
    label(c3x + 3.2, oy + 1.85, 'Scale (7)' if en else '尺度 (7)', 5.1, AMBER, 'bold')
    label(c3x + 1.4, oy + 4.75, 'Pending (confirm)' if en else 'Pending（待确认）',
          5.0, AMBER, 'bold', width=c3w - 2.2)


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
