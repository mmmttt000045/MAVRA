"""Definition retrieval (Section IV-C), single column: what goes in, the four sub-steps, what comes out.

Input: an agent's request in its own words (here "in-store takings in March
2026", one of many wordings for store revenue) and the catalog, which holds two
definitions both named store revenue: D01 sums the net amount paid after
coupons, D02 the sales amount before coupons.

1. Alias table: the request without its parameters (year, month) is looked up
   among wordings that agents have confirmed; a hit is answered at once.
2. Recall: bge-m3 embeds the request; the 8 definitions with the highest cosine
   similarity are the candidates (definitions are embedded once).
3. Judge: a cross-encoder (XLM-RoBERTa, 12 layers) reads the request together
   with each candidate, rendered as its text, its attributes (amount basis, ...),
   and its differences from same-name and same-group definitions; the [CLS]
   vector gives p, the probability that the two are consistent. Three seeds
   are averaged. Its training data is built offline from the catalog; that is
   drawn in Fig. 3(d), with the other ways knowledge enters M.
4. Decide: p >= 0.9 accepts, p < 0.1 rejects, anything between is uncertain.

Output: one accepted definition is a hit; several are definitions sharing a
name, returned with how they differ; any uncertain candidate makes the reply a
reference for the agent to confirm, and a confirmed wording is stored as an
alias; nothing left means the catalog lacks it.

Look: the palette, frames and sub-step numbering of Figs. 2, 3 and 5 (navy for
accepted, brown for refer, cool greys); the whole figure is Fig. 2's step 3,
whose badge sits on the request arrow as in Fig. 2.

Data: the candidates and scores are the ensemble's in the end-to-end run
(exp/2026-11-10-lookup-facets/results-ft/serve-ens3/responses-first.jsonl):
request s01 recalls D01 D02 D07 D04 D08 D06 D22 D12 and scores D01 1.00, D02
1.00, the rest 0.00; request w01 scores D07 1.00, D08 0.33.
Thresholds 0.1/0.9 and k = 8 as in serve.py.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from smallparts import HEAD_T, KEYC, LINE, SMALL, TAG, baseline  # noqa: E402

NAME = 'lookup'
W, H = style.COLUMN, 62.4
TINY = 4.6

# Palette of Figs. 2, 3 and 5 (extraction.py, maintenance.py), so the method figures read as one set.
INK, MUTED, WHITE = '#1F2328', '#596068', '#FFFFFF'
EDGE, SUB_EDGE, RULE = '#737B84', '#B6BEC7', '#CFD5DC'
BAND, SPACE_BG = '#ECEFF3', '#F7F8FA'
ACC, ACC_DK, ACC_PALE, NAVY_EDGE = '#24416B', '#1B3254', '#EDF1F7', '#9EB1CC'
AMBER, AMBER_PALE = '#7D5C38', '#F4EFE8'             # refer / uncertain, and the peer differences (Fig. 2)
RED = '#942B2B'
LEARN = '#46506E'                                    # Fig. 3's learning colour (the offline training note)
GREY_TOK, DEF_TOK, LOW_BAR = '#CFD5DC', '#9AA3AD', '#AEB6BF'
LO, HI = .1, .9
RECALLED = ('D01', 'D02', 'D07', 'D04', 'D08', 'D06', 'D22', 'D12')   # top 8 for the walkthrough request
SCORES = ((('`D01`', 1.00), ('`D02`', 1.00), (None, 0.00)),
          (('`D07`', 1.00), ('`D08`', 0.33), (None, 0.00)))

LABELS = {
    'en': {
        'input': 'Input', 'output': 'Output',
        'req': ('in-store takings', 'in Mar. 2026?'),
        'syn': ('also: store turnover,', 'offline shops’ sales, …'),
        'catalog': 'catalog, 26 definitions',
        'cards': (('`D01`', 'store revenue', 'after coupons'), ('`D02`', 'store revenue', 'before coupons')),
        's1': 'Alias table', 's1_note': 'wordings agents confirmed',
        'key': 'key: request without year, month',
        'alias_rows': (('store turnover', '`D01 D02`'), ('net store profit', '`D07`')),
        'miss': 'miss', 'hit_note': 'hit: reply at once',
        's2': 'Recall', 's2_note': 'bge-m3, cosine, top 8',
        's3': 'Judge', 's3_note': 'cross-encoder (XLM-R, 12 layers) ×3, mean $\\hat{y}$',
        'trained': 'trained offline: Fig. 3(d)',
        'seg': (('request', 'in-store takings…'), ('definition', '`sum(ss_net_paid)`'),
                ('attributes', 'after coupons'), ('differences', '`D02`: before')),
        'layer': 'Transformer layers ×12: request and definition tokens attend to each other',
        's4': 'Decide', 's4_note': 'thresholds .1, .9',
        'cols': ('in-store takings', 'store profit'),
        'rest': '6 others',
        'zones': ('reject', 'refer', 'accept'),
        'replies': (
            ('Diffs', ACC, 'in-store takings', (('`D01` + `D02`', ACC_DK), (', differ in amount basis', MUTED))),
            ('Hit', ACC, 'return rate by units', (('`D17`', ACC_DK),)),
            ('Refer', AMBER, 'store profit', (('`D07` or `D08`?', INK), (' agent confirms', MUTED))),
            ('Miss', MUTED, 'sales per m² of stores', (('not in catalog', MUTED),)),
        ),
        'to_alias': 'stored as alias',
    },
    'zh': {
        'input': '输入', 'output': '输出',
        'req': ('2026 年 3 月实体店', '的收入是多少？'),
        'syn': ('其他说法：门店流水、', '线下卖了多少钱等'),
        'catalog': '目录，26 条定义',
        'cards': (('`D01`', '门店营业额', '扣券后实付'), ('`D02`', '门店营业额', '扣券前')),
        's1': '别名表', 's1_note': '智能体确认过的说法',
        'key': '键：去掉年、月等参数的请求',
        'alias_rows': (('门店流水', '`D01 D02`'), ('门店净利润', '`D07`')),
        'miss': '未命中', 'hit_note': '命中：直接回复',
        's2': '召回', 's2_note': 'bge-m3，余弦相似度，前 8 条',
        's3': '判别', 's3_note': '交叉编码器（XLM-R，12 层）×3，$\\hat{y}$ 取平均',
        'trained': '离线训练：见图 3(d)',
        'seg': (('请求', '实体店的收入…'), ('定义', '`sum(ss_net_paid)`'),
                ('属性', '扣券后实付'), ('区别', '`D02`：扣券前')),
        'layer': '12 层 Transformer：请求与定义的 token 互相注意',
        's4': '判定', 's4_note': '阈值 .1、.9',
        'cols': ('实体店的收入', '门店利润'),
        'rest': '其余 6 条',
        'zones': ('排除', '参考', '接受'),
        'replies': (
            ('Diffs', ACC, '实体店的收入', (('`D01` + `D02`', ACC_DK), ('，金额口径不同', MUTED))),
            ('Hit', ACC, '按件数算的门店退货率', (('`D17`', ACC_DK),)),
            ('Refer', AMBER, '门店利润', (('`D07` 还是 `D08`？', INK), ('智能体确认', MUTED))),
            ('Miss', MUTED, '门店坪效', (('目录中没有', MUTED),)),
        ),
        'to_alias': '存为别名',
    },
}


def arrow(s, points, color=MUTED, sw=LINE):
    s.route(points, color, sw, length=.9, radius=.6)


def mark(s, x, yc, ok, k=.9):
    """A thin check (navy) or cross (red) centred on (x, yc)."""
    if ok:
        s.poly([(x - .62 * k, yc), (x - .15 * k, yc + .5 * k), (x + .65 * k, yc - .55 * k)], None, ACC, .26,
               closed=False)
    else:
        s.line(x - .5 * k, yc - .5 * k, x + .5 * k, yc + .5 * k, RED, .26)
        s.line(x - .5 * k, yc + .5 * k, x + .5 * k, yc - .5 * k, RED, .26)


def key_icon(s, x, yc, color, k=1.0, sw=.17):
    """A small key, bow at the left (an alias key); returns its width."""
    r = .4 * k
    s.circle(x + r, yc, r, None, color, sw)
    x1 = x + 2 * r
    s.line(x1, yc, x1 + 1.3 * k, yc, color, sw)
    for t in (.75, 1.15):
        s.line(x1 + t * k, yc, x1 + t * k, yc + .42 * k, color, sw)
    return 2 * r + 1.3 * k


def person(s, x, yc, color='#68707A'):
    s.circle(x, yc - .7, .72, color)
    s.rect(x - 1.1, yc + .18, 2.2, 1.25, color, None, r=.62)


def card(s, x, y, w, h, band_h, band=BAND, edge=EDGE, sw=LINE):
    """A frame with a tinted title band (the cards of Figs. 3 and 5)."""
    s.rect(x, y, w, h, WHITE, edge, sw, r=.5)
    i = sw / 2 + .05
    s.rect(x + i, y + i, w - 2 * i, band_h, band, None, r=.4)
    s.rect(x + i, y + i + band_h / 2, w - 2 * i, band_h / 2, band, None)


def io_tag(s, x, yc, label):
    """Input / Output: a dark label; returns its width."""
    w = measure(label, TAG, 'bold') + 1.6
    s.rect(x, yc - 1.15, w, 2.3, INK, None, r=.5)
    s.text(x + .8, baseline(yc, TAG), label, TAG, WHITE, 'bold')
    return w


def step_badge(s, x, yc, n, r=.95):
    """Fig. 2's step badge (step 3, lookup, is navy there)."""
    s.circle(x, yc, r, ACC)
    s.text(x, baseline(yc, 5.2), str(n), 5.2, WHITE, 'bold', 'center')


def step_box(s, x, y, w, h, n, title, note, band_h=2.6):
    """A sub-step: grey title band with '<n>. title' (as Fig. 2's lookup and Fig. 5's repair) and a note."""
    card(s, x, y, w, h, band_h)
    s.line(x, y + band_h + .1, x + w, y + band_h + .1, RULE, .12)
    yc = y + band_h / 2 + .05
    end = x + 1.0 + s.text(x + 1.0, baseline(yc, HEAD_T), f'{n}. {title}', HEAD_T, INK, 'bold')
    s.text(x + w - .8, baseline(yc, TINY), note, TINY, MUTED, align='right', width=x + w - end - 2.0)
    return y + band_h


def star(s, x, y, r, color):
    s.poly([(x + (r if j == 0 else .42 * r) * math.cos(math.radians(90 + 36 * (2 * i + j))),
             y - (r if j == 0 else .42 * r) * math.sin(math.radians(90 + 36 * (2 * i + j)))) for i in range(5) for j in (0, 1)],
           color, None)


def draw(s, lang):
    L = LABELS[lang]
    text = s.text
    x0, x1 = 3.2, 83.4                               # boxes; the left lane (1.7) carries the alias loop
    lane_l = 1.7

    # ===== Input: the request and the catalog =====
    ya = 1.0
    io_tag(s, x0, ya + 1.15, L['input'])
    pc = ya + 5.6
    person(s, x0 + 1.2, pc)
    bx, bw = x0 + 3.4, 18.4
    by0, bh = ya + 2.6, 5.9
    s.rect(bx, by0, bw, bh, WHITE, ACC, .2, r=1.0)
    s.poly([(bx + .1, pc - .6), (bx - 1.0, pc + .15), (bx + .1, pc + .6)], WHITE, None)
    s.line(bx - 1.0, pc + .15, bx, pc - .62, ACC, .2)
    s.line(bx - 1.0, pc + .15, bx, pc + .62, ACC, .2)
    for k, ln in enumerate(L['req']):
        text(bx + bw / 2, baseline(by0 + 1.75 + 2.4 * k, SMALL), ln, SMALL, ACC_DK, align='center', width=bw - .8)
    sx_ = bx + bw + 1.2
    for k, ln in enumerate(L['syn']):
        text(sx_, baseline(by0 + 1.9 + 2.1 * k, TINY), ln, TINY, MUTED)
    # Catalog: two definitions that share a name, and the rest stacked behind.
    cx = x0 + 45.6
    text(cx, baseline(ya + 1.15, TINY), L['catalog'], TINY, MUTED)
    cw, cbh, crow = 14.6, 2.2, 2.1
    ch = cbh + crow
    cy = ya + 2.7
    for d in (1.1, .55):                             # the other 24 definitions, stacked behind
        s.rect(cx + cw + .8 + d, cy + d, cw, ch, WHITE, RULE, .12, r=.5)
    for i, (did, name, amount) in enumerate(L['cards']):
        x = cx + i * (cw + .8)
        card(s, x, cy, cw, ch, cbh, band=ACC_PALE)
        e = x + .7 + text(x + .7, baseline(cy + cbh / 2 + .05, TAG), did, TAG, ACC_DK)
        text(e + .7, baseline(cy + cbh / 2 + .05, TAG), name, TAG, INK, width=x + cw - e - 1.3)
        text(x + .7, baseline(cy + cbh + crow / 2, TAG), amount, TAG, KEYC, 'bold', width=cw - 1.2)
    cat_bottom = cy + ch
    end_input = max(by0 + bh, cat_bottom)

    # ===== Row 1: alias table (1) -> recall (2) =====
    r1 = end_input + 2.2                             # room for Fig. 2's step-3 badge on the request arrow
    h1 = 12.4
    w1 = 34.4
    b1 = step_box(s, x0, r1, w1, h1, 1, L['s1'], L['s1_note'])
    text(x0 + 1.0, baseline(b1 + 1.3, TINY), L['key'], TINY, MUTED, width=w1 - 1.8)
    trow = 2.0
    for k, (wd, ids) in enumerate(L['alias_rows']):
        yc = b1 + 3.4 + trow * k
        if k:
            s.line(x0 + .6, yc - trow / 2, x0 + w1 - .6, yc - trow / 2, RULE, .1)
        key_icon(s, x0 + 1.0, yc, ACC_DK, k=.6)
        text(x0 + 3.2, baseline(yc, TINY), wd, TINY, INK)
        text(x0 + w1 - .8, baseline(yc, TINY), ids, TINY, ACC_DK, align='right')
    # Bottom line: a hit is answered here (left); a miss leaves right, into recall, so the arrow starts at "miss".
    my = b1 + 3.4 + trow * 2 - .2
    text(x0 + 1.0, baseline(my, TINY), L['hit_note'], TINY, ACC_DK)
    miss_w = measure(L['miss'], TINY, 'bold')
    text(x0 + w1 - .8, baseline(my, TINY), L['miss'], TINY, RED, 'bold', align='right')
    mark(s, x0 + w1 - .8 - miss_w - .9, my, False, k=.55)
    # request -> alias table, carrying Fig. 2's step-3 badge
    ax_r = bx + bw / 2
    arrow(s, [(ax_r, by0 + bh + .2), (ax_r, r1 - .4)], ACC)
    step_badge(s, ax_r - 1.6, (by0 + bh + r1) / 2, 3)
    assert by0 + bh + .1 < (by0 + bh + r1) / 2 - .95 and (by0 + bh + r1) / 2 + .95 < r1 - .1, 'step badge touches'
    # Recall: the embedding space, and the 8 candidates.
    x2 = x0 + w1 + 3.0
    w2 = x1 - x2
    b2 = step_box(s, x2, r1, w2, h1, 2, L['s2'], L['s2_note'])
    arrow(s, [(x0 + w1 + .2, my), (x2 - .4, my)], ACC)
    ex, ey, ew, eh = x2 + .9, b1 + .8, 17.0, h1 - (b1 - r1) - 1.6
    s.rect(ex, ey, ew, eh, SPACE_BG, RULE, .12, r=.4)
    qx, qy = ex + 7.0, ey + eh / 2
    pts = [(-1.4, -.9, 'D01'), (-1.05, .7, 'D02'), (1.4, -1.2, ''), (1.7, 1.15, ''), (.3, 2.1, ''), (-.2, -2.2, ''),
           (2.5, .1, ''), (-2.35, 1.45, ''), (5.3, -2.4, ''), (6.6, 1.6, ''), (8.4, -.8, ''), (-4.6, -2.6, ''),
           (5.0, 2.9, ''), (8.6, 2.7, ''), (-4.9, 2.7, '')]
    rad = 3.2
    s.circle(qx, qy, rad, None, ACC, .16)
    lab_x = qx - rad - 1.0                           # labels clear of the circle, tied to their points by leaders
    for dx, dy, lab in pts:
        inside = math.hypot(dx, dy) < rad
        if lab:
            s.line(lab_x + .25, qy + dy, qx + dx - .45, qy + dy, ACC, .1)
            text(lab_x, baseline(qy + dy, TINY - .5), f'`{lab}`', TINY - .5, ACC_DK, align='right')
        s.circle(qx + dx, qy + dy, .4, ACC if lab else (NAVY_EDGE if inside else '#CDD3DA'), None)
    assert lab_x - measure('`D01`', TINY - .5) > ex + .3, 'recall labels leave the embedding panel'
    star(s, qx, qy, .95, AMBER)
    # catalog -> recall (definitions embedded once)
    arrow(s, [(cx + cw / 2, cat_bottom + .2), (cx + cw / 2, r1 - .4)])
    # candidate chips
    gx = ex + ew + 1.4
    cwid = (x2 + w2 - .8 - gx - 3 * .5) / 4
    for i, d in enumerate(RECALLED):
        r, c = divmod(i, 4)
        xx = gx + c * (cwid + .5)
        yy = b1 + 1.4 + r * 2.9
        hot = d in ('D01', 'D02')
        s.rect(xx, yy, cwid, 2.2, ACC_PALE if hot else WHITE, ACC if hot else EDGE, .14, r=.4)
        text(xx + cwid / 2, baseline(yy + 1.1, TINY), f'`{d}`', TINY, ACC_DK if hot else INK, align='center')

    # ===== Row 2: judge (3, right) -> decide (4, left) =====
    seed_d = 1.0                                     # offset of the stacked seed frames behind the judge
    r2 = r1 + h1 + seed_d + 1.8                      # room for the x8 arrow above the stacked frames
    h2 = 20.4
    w4 = 22.0
    x3 = x0 + w4 + 3.0
    w3 = x1 - x3 - seed_d                            # the back seed frame ends at x1
    for d in (seed_d, seed_d / 2):                   # three seeds
        s.rect(x3 + d, r2 - d, w3, h2, WHITE, RULE, .12, r=.5)
    b3 = step_box(s, x3, r2, w3, h2, 3, L['s3'], L['s3_note'])
    # recall -> judge: one pass per candidate; the arrow stops on the back seed frame
    ax_ = gx + 2 * cwid + .75                        # centre of the 4 x 2 chip grid
    arrow(s, [(ax_, b1 + 1.4 + 2.9 + 2.2 + .2), (ax_, r2 - seed_d - .15)], ACC)
    text(ax_ + .6, baseline((r1 + h1 + r2 - seed_d) / 2, TINY), '×8', TINY, ACC_DK, 'bold')
    # Tokens: [CLS] request [SEP][SEP] definition | attributes | differences [SEP]
    REQ, DEF, ATT, DIF = 'req', 'def', 'att', 'dif'
    segs = [(1, 'cls'), (6, REQ), (2, 'sep'), (8, DEF), (5, ATT), (5, DIF), (1, 'sep')]
    tok_fill = {'cls': (INK, None), 'sep': (GREY_TOK, None), REQ: (ACC, None), DEF: (DEF_TOK, None),
                ATT: (ACC_PALE, NAVY_EDGE), DIF: (AMBER, None)}
    seg_ink = {REQ: (ACC, ACC_DK, ACC_DK), DEF: (DEF_TOK, MUTED, MUTED), ATT: (NAVY_EDGE, ACC_DK, KEYC),
               DIF: (AMBER, AMBER, AMBER)}           # underline, name, example
    tok, gap = 1.42, .3
    n = sum(k for k, _ in segs)
    span = n * tok + (n - 1) * gap
    tx0 = x3 + 4.2
    assert tx0 + span < x3 + w3 - .8, (tx0 + span, x3 + w3)
    ty = r2 + h2 - 6.2
    xs, kinds = [], []
    for k, kind in segs:
        for _ in range(k):
            xs.append(tx0 + len(xs) * (tok + gap))
            kinds.append(kind)

    def tokens():
        for x, kind in zip(xs, kinds):
            fill, edge = tok_fill[kind]
            if edge:
                s.rect(x + .06, ty + .06, tok - .12, tok - .12, fill, edge, .12, r=.25)
            else:
                s.rect(x, ty, tok, tok, fill, None, r=.25)

    tokens()
    text(xs[0] + tok / 2, baseline(ty + tok + 1.2, TINY - .6), '[CLS]', TINY - .6, INK, align='center')
    start = 0
    seg_lab = iter(L['seg'])
    for k, kind in segs:
        if kind in seg_ink:
            name, example = next(seg_lab)
            under, ink_n, ink_e = seg_ink[kind]
            a, b = xs[start], xs[start + k - 1] + tok
            s.line(a, ty + tok + .45, b, ty + tok + .45, under, .22)
            text((a + b) / 2, baseline(ty + tok + 1.5, TINY), name, TINY, ink_n, 'bold', align='center', width=b - a + 3.0)
            text((a + b) / 2, baseline(ty + tok + 3.3, TINY - .3), example, TINY - .3, ink_e, align='center',
                 width=b - a + 1.4)
        start += k
    # Transformer layers above the tokens.
    lay_h, lay_gap = 1.5, .5
    lay_bot = ty - 3.0
    lay_x0, lay_x1 = xs[0] - .5, xs[-1] + tok + .5
    cls_x0 = xs[0] + tok / 2
    ys_l = [lay_bot - lay_h - k * (lay_h + lay_gap) for k in range(3)]
    for yy in ys_l:
        s.rect(lay_x0, yy, lay_x1 - lay_x0, lay_h, '#F1F3F5', SUB_EDGE, .12, r=.35)
    text(cls_x0 + 1.4, baseline(ys_l[-1] + lay_h / 2, TINY - .6), L['layer'], TINY - .6, MUTED)
    for x in xs[1:]:                                  # each token enters the first layer
        s.line(x + tok / 2, ty - .15, x + tok / 2, ys_l[0] + lay_h + .05, '#DDE1E6', .1)
    # Attention: request tokens read the definition, attribute and difference tokens. The three arcs start at
    # different request tokens and nest (outer arc = farther segment), so none overlap; a white halo keeps
    # them legible where they cross the token connectors.
    room = ty - lay_bot                               # free height between tokens and the first layer
    arcs = ((2, n - 3, AMBER, .80), (4, n - 8, ACC_DK, .58), (6, 12, DEF_TOK, .36))
    for q_i, j, c, frac in arcs:
        p0, p3 = (xs[q_i] + tok / 2, ty - .15), (xs[j] + tok / 2, ty - .15)
        ctrl = ty - .15 - frac * room / .75           # a cubic with level controls peaks at 3/4 of their height
        for colour, width in ((WHITE, .55), (c, .2)):
            s.curve(p0, (p0[0], ctrl), (p3[0], ctrl), p3, colour, width)
    assert arcs[0][1] > arcs[1][1] > arcs[2][1] and arcs[0][0] < arcs[1][0] < arcs[2][0], 'arcs must nest'
    assert kinds[arcs[0][1]] == DIF and kinds[arcs[1][1]] == ATT and kinds[arcs[2][1]] == DEF, 'arc targets'
    tokens()                                          # tokens back on top of the arcs' halos
    # [CLS] rises through the layers to the head; \hat{y} leaves to the left, into step 4.
    cls_x = xs[0] + tok / 2
    top_l = ys_l[-1]
    s.line(cls_x, ty, cls_x, ys_l[0] + lay_h, INK, .18)
    for a, b in zip(ys_l[1:], ys_l[:-1]):
        s.line(cls_x, a + lay_h, cls_x, b, INK, .18)
    hy = b3 + 1.7
    s.line(cls_x, top_l, cls_x, hy + .85, INK, .18)
    s.rect(cls_x - .85, hy - .85, 1.7, 1.7, INK, None, r=.3)
    text(cls_x, baseline(hy, TINY - .4), 'σ', TINY - .4, WHITE, align='center')
    arrow(s, [(cls_x - .95, hy), (x0 + w4 + .25, hy)], INK)       # into step 4's frame
    text((x0 + w4 + x3) / 2, baseline(hy - 1.35, TAG), r'$\hat{y}$', TAG, INK, align='center')
    head_end = cls_x + 1.4 + text(cls_x + 1.4, baseline(hy, TINY - .6), '[CLS] → MLP → σ', TINY - .6, MUTED)
    # where the judge comes from: its training data is built offline with the catalog (Fig. 3(d))
    tr_w = measure(L['trained'], TINY - .6, 'bold')
    text(x3 + w3 - .8, baseline(hy, TINY - .6), L['trained'], TINY - .6, LEARN, 'bold', align='right')
    assert head_end + 1.5 < x3 + w3 - .8 - tr_w, 'training note overlaps the head note'

    # Decide: p of each candidate against the two thresholds, for two requests.
    b4 = step_box(s, x0, r2, w4, h2, 4, L['s4'], L['s4_note'])
    gx0, gx1 = x0 + 7.0, x0 + w4 - .9
    sc = lambda p: gx0 + (gx1 - gx0) * p  # noqa: E731
    rowh = 1.45
    zone_cols = (BAND, AMBER_PALE, ACC_PALE)
    yy0 = b4 + .6
    for g, (title, items) in enumerate(zip(L['cols'], SCORES)):
        y_t = yy0 + g * (3 * rowh + 3.0)
        text(x0 + .9, baseline(y_t + .7, TINY), title, TINY, ACC_DK if g == 0 else INK, 'bold', width=w4 - 1.6)
        y0 = y_t + 1.6
        for (a, b), zc in zip(((0, LO), (LO, HI), (HI, 1)), zone_cols):
            s.rect(sc(a), y0, sc(b) - sc(a), 3 * rowh, zc, None)
        for t, tc in ((LO, AMBER), (HI, ACC)):
            s.line(sc(t), y0 - .2, sc(t), y0 + 3 * rowh + .2, tc, .16)
        for k, (lab, p) in enumerate(items):
            yc = y0 + rowh * (k + .5)
            text(gx0 - .5, baseline(yc, TINY - .3), lab or L['rest'], TINY - .3, INK if lab else MUTED, align='right')
            w = max(sc(p) - gx0, .3)
            s.rect(gx0, yc - .42, w, .84, ACC if p >= HI else (AMBER if p >= LO else LOW_BAR), None, r=.15)
    zy = yy0 + (3 * rowh + 3.0) + 1.6 + 3 * rowh + 1.1
    # Zone names under the axis: the narrow outer zones are labelled flush with the axis ends, so no label runs
    # past the chart.
    for (a, b), zl, zc, al in zip(((0, LO), (LO, HI), (HI, 1)), L['zones'], (MUTED, AMBER, ACC_DK),
                                  ('left', 'center', 'right')):
        xz = {'left': gx0, 'center': (sc(a) + sc(b)) / 2, 'right': gx1}[al]
        text(xz, baseline(zy, TINY - .6), zl, TINY - .6, zc, align=al)
    assert zy + .8 < r2 + h2, (zy, r2 + h2)

    # ===== Output: the four replies =====
    ro = r2 + h2 + 1.8
    io_tag(s, x0, ro + 1.15, L['output'])
    pitch = 2.6
    bwid = 10.2
    reqx = x0 + bwid + 1.2
    outx = x0 + 36.0
    first_o = 3.7                                    # first reply row: its pill clears the Output tag by .4
    rows_o = []
    for k, (lab, bc, req, out) in enumerate(L['replies']):
        yc = ro + first_o + pitch * k
        rows_o.append(yc)
        s.rect(x0, yc - 1.0, bwid, 2.0, bc, None, r=1.0)
        text(x0 + bwid / 2, baseline(yc, TAG), lab, TAG, WHITE, 'bold', align='center', width=bwid - .3)
        text(reqx, baseline(yc, TAG), req, TAG, INK, width=outx - reqx - 3.0)
        arrow(s, [(outx - 2.6, yc), (outx - .6, yc)])
        end = outx
        for label, color in out:
            end += text(end, baseline(yc, TAG), label, TAG, color)
        if bc == AMBER:
            end += .8
            arrow(s, [(end, yc), (end + 1.8, yc)], ACC_DK)
            end += 2.2
            end += key_icon(s, end, yc, ACC_DK, k=.65) + .5
            end += text(end, baseline(yc, TAG), L['to_alias'], TAG, ACC_DK, 'bold')
        assert end < x1, (k, end)
    # decide -> output
    arrow(s, [(x0 + w4 / 2, r2 + h2 + .2), (x0 + w4 / 2, ro + .6)])
    # confirmed wording -> alias table (left lane)
    yr = rows_o[2]
    s.route([(x0 - .2, yr), (lane_l, yr), (lane_l, r1 + 7.0), (x0 - .4, r1 + 7.0)], ACC_DK, .18, dash=(.7, .45),
            length=.8, radius=.5)
    out_end = ro + first_o + pitch * 3 + 1.2
    assert out_end + .3 <= H <= out_end + .9, (out_end, H)
