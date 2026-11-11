"""Accurate lookup (Section IV-C), single column: what goes in, the four steps, what comes out.

Input: an agent's request in its own words (here "in-store takings in March
2001", one of many wordings for store revenue) and the catalog, which holds two
definitions both named store revenue: D01 sums the net amount paid after
coupons, D02 the sales amount before coupons.

1. Alias table: the request without its parameters (year, month) is looked up
   among wordings that agents have confirmed; a hit is answered at once.
2. Recall: bge-m3 embeds the request; the 8 definitions with the highest cosine
   similarity are the candidates (definitions are embedded once).
3. Judge: a cross-encoder (XLM-RoBERTa, 12 layers) reads the request together
   with each candidate, rendered as its text, its choices (amount basis, ...),
   and its differences from same-name and same-group definitions; the [CLS]
   vector gives p, the probability that the two are consistent. Three seeds
   are averaged.
4. Decide: p >= 0.9 accepts, p < 0.1 rejects, anything between is uncertain.

Output: one accepted definition is a hit; several are definitions sharing a
name, returned with how they differ; any uncertain candidate makes the reply a
reference for the agent to confirm, and a confirmed wording is stored as an
alias; nothing left means the catalog lacks it.

Offline, once per catalog: intents are enumerated from the definitions'
choices, an LLM writes each in many wordings, and the consistency rule labels
every (wording, definition) pair, which trains the judge.

Data: the candidates and scores are the ensemble's in the end-to-end run
(exp/2026-11-10-lookup-facets/results-ft/serve-ens3/responses-first.jsonl):
request s01 recalls D01 D02 D07 D04 D08 D06 D22 D12 and scores D01 1.00, D02
1.00, the rest 0.00; request w01 scores D07 1.00, D08 0.33. Wordings are
generated training questions (train-xl.jsonl; shortened in English).
Thresholds 0.1/0.9 and k = 8 as in serve.py.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import AMBER, AMBER_PALE, EDGE, INK, MUTED, RED, RULE, WHITE  # noqa: E402
from smallparts import (BAND, BLUE, BLUE_PALE, BLUE_TXT, HEAD_T, KEYC, LEARN, LEARN_PALE, LINE, SMALL, TAG,  # noqa: E402
                        arrow, baseline, card, key_icon, mark, person, sparkle)

NAME = 'lookup'
W, H = style.COLUMN, 76.0
TINY = 4.6
GREY_TOK = '#C9C6C0'
SPACE_BG = '#FAFAF8'
C_REQ, C_DEF, C_CHO, C_DIF = BLUE, EDGE, KEYC, LEARN          # token segments of the judge's input
C_INT = (BLUE_TXT, KEYC, MUTED)                               # three intents and their wordings
LO, HI = .1, .9
RECALLED = ('D01', 'D02', 'D07', 'D04', 'D08', 'D06', 'D22', 'D12')   # top 8 for the walkthrough request
SCORES = ((('`D01`', 1.00), ('`D02`', 1.00), (None, 0.00)),
          (('`D07`', 1.00), ('`D08`', 0.33), (None, 0.00)))

LABELS = {
    'en': {
        'input': 'Input', 'output': 'Output',
        'req': ('in-store takings', 'in Mar. 2001?'),
        'syn': ('also: store turnover,', 'offline shops’ sales, …'),
        'catalog': 'catalog, 26 definitions',
        'cards': (('`D01`', 'store revenue', 'after coupons'), ('`D02`', 'store revenue', 'before coupons')),
        's1': 'alias table', 's1_note': 'wordings agents confirmed',
        'key': 'key: request without year, month',
        'alias_rows': (('store turnover', '`D01 D02`'), ('net store profit', '`D07`')),
        'miss': 'miss', 'hit_note': 'hit: reply at once',
        's2': 'recall', 's2_note': 'bge-m3, cosine, top 8',
        's3': 'judge', 's3_note': 'cross-encoder (XLM-R, 12 layers) ×3, mean $p$',
        'pair': 'one pass per candidate',
        'seg': (('request', 'in-store takings…'), ('definition', '`sum(ss_net_paid)`'),
                ('choices', 'after coupons'), ('differences', '`D02`: before')),
        'layer': 'Transformer layers ×12: request and definition tokens attend to each other',
        's4': 'decide', 's4_note': 'thresholds .1, .9',
        'cols': ('in-store takings', 'store profit'),
        'rest': '6 others',
        'zones': ('reject', 'refer', 'accept'),
        'replies': (
            ('same name', BLUE, 'in-store takings', (('`D01` + `D02`', BLUE_TXT), (', differ in amount basis', MUTED))),
            ('hit', BLUE, 'return rate by units', (('`D17`', BLUE_TXT),)),
            ('refer', AMBER, 'store profit', (('`D07` or `D08`?', INK), (' agent confirms', MUTED))),
            ('none', MUTED, 'sales per m² of stores', (('not in catalog', MUTED),)),
        ),
        'to_alias': 'stored as alias',
        'off': 'Offline, once per catalog: the judge’s training data', 'off_note': 'labels by rule, no annotation',
        'intents': ('store · revenue', '+ after coupons', 'web · units'),
        'rows': ('takings of Changsha stores, Q3?', 'how much did offline shops sell?',
                 'store income after coupons, ex tax?', 'units the web store sold last year?'),
        'train': 'train',
    },
    'zh': {
        'input': '输入', 'output': '输出',
        'req': ('2001 年 3 月实体店', '的收入是多少？'),
        'syn': ('其他说法：门店流水、', '线下卖了多少钱等'),
        'catalog': '目录，26 条定义',
        'cards': (('`D01`', '门店营业额', '扣券后实付'), ('`D02`', '门店营业额', '扣券前')),
        's1': '别名表', 's1_note': '智能体确认过的说法',
        'key': '键：去掉年、月等参数的请求',
        'alias_rows': (('门店流水', '`D01 D02`'), ('门店净利润', '`D07`')),
        'miss': '未命中', 'hit_note': '命中：直接回复',
        's2': '召回', 's2_note': 'bge-m3，余弦相似度，前 8 条',
        's3': '判别', 's3_note': '交叉编码器（XLM-R，12 层）×3，$p$ 取平均',
        'pair': '每个候选算一次',
        'seg': (('请求', '实体店的收入…'), ('定义', '`sum(ss_net_paid)`'),
                ('口径', '扣券后实付'), ('区别', '`D02`：扣券前')),
        'layer': '12 层 Transformer：请求与定义的 token 互相注意',
        's4': '判定', 's4_note': '阈值 .1、.9',
        'cols': ('实体店的收入', '门店利润'),
        'rest': '其余 6 条',
        'zones': ('排除', '参考', '接受'),
        'replies': (
            ('同名', BLUE, '实体店的收入', (('`D01` + `D02`', BLUE_TXT), ('，金额口径不同', MUTED))),
            ('命中', BLUE, '按件数算的门店退货率', (('`D17`', BLUE_TXT),)),
            ('参考', AMBER, '门店利润', (('`D07` 还是 `D08`？', INK), ('智能体确认', MUTED))),
            ('没有', MUTED, '门店坪效', (('目录中没有', MUTED),)),
        ),
        'to_alias': '存为别名',
        'off': '离线，每个目录一次：判别器的训练数据', 'off_note': '规则打标签，无需人工标注',
        'intents': ('门店 · 销售额', '+ 扣券后实付', '网店 · 销量'),
        'rows': ('长沙线下店上季度流水多少？', '上个月北京线下店卖了多少钱？', '深圳店里券后税外的收入？', '去年网店卖了多少件？'),
        'train': '训练',
    },
}


def io_tag(s, x, yc, label):
    """Input / Output: a dark label; returns its width."""
    w = measure(label, TAG, 'bold') + 1.6
    s.rect(x, yc - 1.15, w, 2.3, INK, None, r=.5)
    s.text(x + .8, baseline(yc, TAG), label, TAG, WHITE, 'bold')
    return w


def badge(s, x, yc, n):
    """Sub-step number of the lookup (1-4), dark blue."""
    s.circle(x, yc, 1.05, BLUE_TXT)
    s.text(x, baseline(yc, 5.2), str(n), 5.2, WHITE, 'bold', 'center')


def step_box(s, x, y, w, h, n, title, note, band_h=2.6):
    """A step: frame, pale-blue title band with number, title and note; returns the band's bottom."""
    card(s, x, y, w, h, band_h, band=BLUE_PALE)
    yc = y + band_h / 2 + .05
    badge(s, x + 1.5, yc, n)
    end = x + 3.0 + s.text(x + 3.0, baseline(yc, HEAD_T), title, HEAD_T, INK, 'bold')
    s.text(x + w - .8, baseline(yc, TINY), note, TINY, MUTED, align='right', width=x + w - end - 2.0)
    return y + band_h


def pill(s, x, yc, label, color, w, size=TAG):
    s.rect(x, yc - 1.1, w, 2.2, WHITE, color, .16, r=1.1)
    s.text(x + w / 2, baseline(yc, size), label, size, color, align='center', width=w - .4)


def star(s, x, y, r, color):
    s.poly([(x + (r if j == 0 else .42 * r) * math.cos(math.radians(90 + 36 * (2 * i + j))),
             y - (r if j == 0 else .42 * r) * math.sin(math.radians(90 + 36 * (2 * i + j)))) for i in range(5) for j in (0, 1)],
           color, None)


def draw(s, lang):
    L = LABELS[lang]
    text = s.text
    x0, x1 = 3.2, 81.4                               # boxes; lanes at 1.8 (alias loop) and 82.9 (training)
    lane_l, lane_r = 1.7, 83.0

    # ===== Input: the request and the catalog =====
    ya = 1.0
    io_tag(s, x0, ya + 1.15, L['input'])
    pc = ya + 5.6
    person(s, x0 + 1.2, pc, EDGE)
    bx, bw = x0 + 3.4, 18.4
    by0, bh = ya + 2.6, 5.9
    s.rect(bx, by0, bw, bh, WHITE, BLUE, .2, r=1.0)
    s.poly([(bx + .1, pc - .6), (bx - 1.0, pc + .15), (bx + .1, pc + .6)], WHITE, None)
    s.line(bx - 1.0, pc + .15, bx, pc - .62, BLUE, .2)
    s.line(bx - 1.0, pc + .15, bx, pc + .62, BLUE, .2)
    for k, ln in enumerate(L['req']):
        text(bx + bw / 2, baseline(by0 + 1.75 + 2.4 * k, SMALL), ln, SMALL, BLUE_TXT, align='center', width=bw - .8)
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
        card(s, x, cy, cw, ch, cbh, band=BLUE_PALE)
        e = x + .7 + text(x + .7, baseline(cy + cbh / 2 + .05, TAG), did, TAG, BLUE_TXT)
        text(e + .7, baseline(cy + cbh / 2 + .05, TAG), name, TAG, INK, width=x + cw - e - 1.3)
        text(x + .7, baseline(cy + cbh + crow / 2, TAG), amount, TAG, KEYC, 'bold', width=cw - 1.2)
    cat_bottom = cy + ch
    end_input = max(by0 + bh, cat_bottom)

    # ===== Row 1: alias table (1) -> recall (2) =====
    r1 = end_input + 1.6
    h1 = 12.4
    w1 = 34.4
    b1 = step_box(s, x0, r1, w1, h1, 1, L['s1'], L['s1_note'])
    text(x0 + 1.0, baseline(b1 + 1.3, TINY), L['key'], TINY, MUTED, width=w1 - 1.8)
    trow = 2.0
    for k, (wd, ids) in enumerate(L['alias_rows']):
        yc = b1 + 3.4 + trow * k
        if k:
            s.line(x0 + .6, yc - trow / 2, x0 + w1 - .6, yc - trow / 2, RULE, .1)
        key_icon(s, x0 + 1.0, yc, BLUE_TXT, k=.6)
        text(x0 + 3.2, baseline(yc, TINY), wd, TINY, INK)
        text(x0 + w1 - .8, baseline(yc, TINY), ids, TINY, BLUE_TXT, align='right')
    my = b1 + 3.4 + trow * 2 - .2
    mark(s, x0 + 1.6, my, False, k=.55)
    text(x0 + 2.8, baseline(my, TINY), L['miss'], TINY, RED, 'bold')
    text(x0 + w1 - .8, baseline(my, TINY), L['hit_note'], TINY, BLUE_TXT, align='right')
    # request -> alias table
    arrow(s, [(bx + bw / 2, by0 + bh + .2), (bx + bw / 2, r1 - .4)], BLUE)
    # Recall: the embedding space, and the 8 candidates.
    x2 = x0 + w1 + 3.0
    w2 = x1 - x2
    b2 = step_box(s, x2, r1, w2, h1, 2, L['s2'], L['s2_note'])
    arrow(s, [(x0 + w1 + .2, my), (x2 - .4, my)], BLUE)
    ex, ey, ew, eh = x2 + .9, b1 + .8, 17.0, h1 - (b1 - r1) - 1.6
    s.rect(ex, ey, ew, eh, SPACE_BG, RULE, .12, r=.4)
    qx, qy = ex + 7.0, ey + eh / 2
    pts = [(-1.4, -.9, 'D01'), (-1.05, .7, 'D02'), (1.4, -1.2, ''), (1.7, 1.15, ''), (.3, 2.1, ''), (-.2, -2.2, ''),
           (2.5, .1, ''), (-2.35, 1.45, ''), (5.3, -2.4, ''), (6.6, 1.6, ''), (8.4, -.8, ''), (-4.6, -2.6, ''),
           (5.0, 2.9, ''), (8.6, 2.7, ''), (-4.9, 2.7, '')]
    rad = 3.2
    s.circle(qx, qy, rad, None, BLUE, .16)
    for dx, dy, lab in pts:
        inside = math.hypot(dx, dy) < rad
        s.circle(qx + dx, qy + dy, .4, BLUE if lab else ('#9DB9E0' if inside else GREY_TOK), None)
        if lab:
            text(qx - rad - .35, baseline(qy + dy, TINY - .5), f'`{lab}`', TINY - .5, BLUE_TXT, align='right')
    star(s, qx, qy, .95, AMBER)
    # catalog -> recall (definitions embedded once)
    arrow(s, [(cx + cw / 2, cat_bottom + .2), (cx + cw / 2, r1 - .4)], EDGE)
    # candidate chips
    gx = ex + ew + 1.4
    cwid = (x2 + w2 - .8 - gx - 3 * .5) / 4
    for i, d in enumerate(RECALLED):
        r, c = divmod(i, 4)
        xx = gx + c * (cwid + .5)
        yy = b1 + 1.4 + r * 2.9
        hot = d in ('D01', 'D02')
        s.rect(xx, yy, cwid, 2.2, BLUE_PALE if hot else WHITE, BLUE if hot else EDGE, .14, r=.4)
        text(xx + cwid / 2, baseline(yy + 1.1, TINY), f'`{d}`', TINY, BLUE_TXT if hot else INK, align='center')

    # ===== Row 2: judge (3, right) -> decide (4, left) =====
    r2 = r1 + h1 + 1.8
    h2 = 20.4
    w4 = 22.0
    x3 = x0 + w4 + 3.0
    w3 = x1 - x3
    for d in (1.0, .5):                              # three seeds
        s.rect(x3 + d, r2 - d, w3, h2, WHITE, RULE, .12, r=.5)
    b3 = step_box(s, x3, r2, w3, h2, 3, L['s3'], L['s3_note'])
    # recall -> judge
    arrow(s, [(gx + 2 * cwid, b1 + 1.4 + 2.9 + 2.2 + .2), (gx + 2 * cwid, r2 - 1.3)], BLUE)
    text(gx + 2 * cwid + .7, baseline(r2 - .95, TINY), '×8', TINY, BLUE_TXT, 'bold')
    # Tokens: [CLS] request [SEP][SEP] definition | choices | differences [SEP]
    segs = [(1, INK), (6, C_REQ), (2, GREY_TOK), (8, C_DEF), (5, C_CHO), (5, C_DIF), (1, GREY_TOK)]
    tok, gap = 1.42, .3
    n = sum(k for k, _ in segs)
    span = n * tok + (n - 1) * gap
    tx0 = x3 + 4.2
    assert tx0 + span < x3 + w3 - .8, (tx0 + span, x3 + w3)
    ty = r2 + h2 - 6.2
    xs, cols = [], []
    for k, c in segs:
        for _ in range(k):
            xs.append(tx0 + len(xs) * (tok + gap))
            cols.append(c)
    for x, c in zip(xs, cols):
        s.rect(x, ty, tok, tok, c, None, r=.25)
    text(xs[0] + tok / 2, baseline(ty + tok + 1.2, TINY - .6), '[CLS]', TINY - .6, INK, align='center')
    start = 0
    seg_lab = iter(L['seg'])
    for k, c in segs:
        if c in (C_REQ, C_DEF, C_CHO, C_DIF):
            name, example = next(seg_lab)
            a, b = xs[start], xs[start + k - 1] + tok
            s.line(a, ty + tok + .45, b, ty + tok + .45, c, .22)
            ink = MUTED if c == C_DEF else c
            text((a + b) / 2, baseline(ty + tok + 1.5, TINY), name, TINY, ink, 'bold', align='center', width=b - a + 3.0)
            text((a + b) / 2, baseline(ty + tok + 3.3, TINY - .3), example, TINY - .3, ink, align='center',
                 width=b - a + 1.4)
        start += k
    # Transformer layers above the tokens.
    lay_h, lay_gap = 1.5, .5
    lay_bot = ty - 3.0
    lay_x0, lay_x1 = xs[0] - .5, xs[-1] + tok + .5
    cls_x0 = xs[0] + tok / 2
    ys_l = [lay_bot - lay_h - k * (lay_h + lay_gap) for k in range(3)]
    for yy in ys_l:
        s.rect(lay_x0, yy, lay_x1 - lay_x0, lay_h, '#F3F2EE', EDGE, .12, r=.35)
    text(cls_x0 + 1.4, baseline(ys_l[-1] + lay_h / 2, TINY - .6), L['layer'], TINY - .6, MUTED)
    for x in xs[1:]:                                  # each token enters the first layer
        s.line(x + tok / 2, ty - .15, x + tok / 2, ys_l[0] + lay_h + .05, '#DAD7D1', .1)
    # Attention: a request token reads the definition, choice and difference tokens.
    q_i = 3
    for j, c in ((n - 3, C_DIF), (n - 8, C_CHO), (12, C_DEF)):
        p0, p3 = (xs[q_i] + tok / 2, ty - .15), (xs[j] + tok / 2, ty - .15)
        hgt = 1.0 + (p3[0] - p0[0]) * .045
        s.curve(p0, (p0[0], ty - hgt - .4), (p3[0], ty - hgt - .4), p3, c, .2)
    # [CLS] rises through the layers to the head; p leaves to the left, into step 4.
    cls_x = xs[0] + tok / 2
    top_l = ys_l[-1]
    s.line(cls_x, ty, cls_x, ys_l[0] + lay_h, INK, .18)
    for a, b in zip(ys_l[1:], ys_l[:-1]):
        s.line(cls_x, a + lay_h, cls_x, b, INK, .18)
    hy = b3 + 1.7
    s.line(cls_x, top_l, cls_x, hy + .85, INK, .18)
    s.rect(cls_x - .85, hy - .85, 1.7, 1.7, INK, None, r=.3)
    text(cls_x, baseline(hy, TINY - .4), 'σ', TINY - .4, WHITE, align='center')
    arrow(s, [(cls_x - .95, hy), (x3 - .4, hy)], INK)
    text(x3 - 1.2, baseline(hy - 1.35, TAG), r'$p$', TAG, INK, align='right')
    # MLP note right of the head
    text(cls_x + 1.4, baseline(hy, TINY - .6), '[CLS] → MLP → σ', TINY - .6, MUTED)

    # Decide: p of each candidate against the two thresholds, for two requests.
    b4 = step_box(s, x0, r2, w4, h2, 4, L['s4'], L['s4_note'])
    gx0, gx1 = x0 + 7.0, x0 + w4 - .9
    sc = lambda p: gx0 + (gx1 - gx0) * p  # noqa: E731
    rowh = 1.45
    zone_cols = ('#EFEEEA', AMBER_PALE, BLUE_PALE)
    yy0 = b4 + .6
    for g, (title, items) in enumerate(zip(L['cols'], SCORES)):
        y_t = yy0 + g * (3 * rowh + 3.0)
        text(x0 + .9, baseline(y_t + .7, TINY), title, TINY, BLUE_TXT if g == 0 else INK, 'bold', width=w4 - 1.6)
        y0 = y_t + 1.6
        for (a, b), zc in zip(((0, LO), (LO, HI), (HI, 1)), zone_cols):
            s.rect(sc(a), y0, sc(b) - sc(a), 3 * rowh, zc, None)
        for t, tc in ((LO, AMBER), (HI, BLUE)):
            s.line(sc(t), y0 - .2, sc(t), y0 + 3 * rowh + .2, tc, .16)
        for k, (lab, p) in enumerate(items):
            yc = y0 + rowh * (k + .5)
            text(gx0 - .5, baseline(yc, TINY - .3), lab or L['rest'], TINY - .3, INK if lab else MUTED, align='right')
            w = max(sc(p) - gx0, .3)
            s.rect(gx0, yc - .42, w, .84, BLUE if p >= HI else (AMBER if p >= LO else EDGE), None, r=.15)
    zy = yy0 + (3 * rowh + 3.0) + 1.6 + 3 * rowh + 1.1
    for (a, b), zl, zc in zip(((0, LO), (LO, HI), (HI, 1)), L['zones'], (MUTED, AMBER, BLUE_TXT)):
        xc = (sc(a) + sc(b)) / 2
        text(xc + (1.1 if a == 0 else (-.9 if b == 1 else 0)), baseline(zy, TINY - .6), zl, TINY - .6, zc, align='center')
    assert zy + .8 < r2 + h2, (zy, r2 + h2)

    # ===== Output: the four replies =====
    ro = r2 + h2 + 1.8
    io_tag(s, x0, ro + 1.15, L['output'])
    pitch = 2.6
    bwid = 10.2
    reqx = x0 + bwid + 1.2
    outx = x0 + 36.0
    rows_o = []
    for k, (lab, bc, req, out) in enumerate(L['replies']):
        yc = ro + 3.3 + pitch * k
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
            arrow(s, [(end, yc), (end + 1.8, yc)], BLUE_TXT)
            end += 2.2
            end += key_icon(s, end, yc, BLUE_TXT, k=.65) + .5
            end += text(end, baseline(yc, TAG), L['to_alias'], TAG, BLUE_TXT, 'bold')
        assert end < lane_r - 1.0, (k, end)
    # decide -> output
    arrow(s, [(x0 + w4 / 2, r2 + h2 + .2), (x0 + w4 / 2, ro + .6)], EDGE)
    # confirmed wording -> alias table (left lane)
    yr = rows_o[2]
    s.route([(x0 - .2, yr), (lane_l, yr), (lane_l, r1 + 7.0), (x0 - .4, r1 + 7.0)], BLUE_TXT, .18, dash=(.7, .45),
            length=.8, radius=.5)
    out_end = ro + 3.3 + pitch * 3 + 1.2

    # ===== Offline: how the judge's training data is made =====
    yo = out_end + 1.2
    ho = H - yo - .5
    s.rect(x0, yo, x1 - x0, ho, '#FBFAFD', LEARN, .16, r=.5, dash=(.9, .5))
    text(x0 + 1.0, baseline(yo + 1.4, TAG), L['off'], TAG, LEARN, 'bold')
    text(x1 - .8, baseline(yo + 1.4, TINY), L['off_note'], TINY, LEARN, align='right')
    top = yo + 3.0
    mx, mx1 = x0 + 25.0, x1 - .8
    colx = (mx1 - 5.0, mx1 - 1.6)
    for c, lab in zip(colx, ('`D01`', '`D02`')):
        text(c, baseline(top + .5, TINY), lab, TINY, BLUE_TXT, align='center')
    pitch_o = 2.2
    rows_y = [top + 2.1 + pitch_o * k for k in range(4)]
    intent_of = (0, 0, 1, 2)
    labels = ((True, True), (True, True), (True, False), (False, False))
    for k, yc in enumerate(rows_y):
        if k:
            s.line(mx + .4, yc - pitch_o / 2, mx1, yc - pitch_o / 2, RULE, .1)
        s.rect(mx + .1, yc - .8, .5, 1.6, C_INT[intent_of[k]], None, r=.2)
        text(mx + 1.1, baseline(yc, TINY), L['rows'][k], TINY, INK, width=colx[0] - mx - 3.2)
        for c, ok in zip(colx, labels[k]):
            mark(s, c, yc, ok, k=.55)
    iw = 15.6
    inty = [(rows_y[0] + rows_y[1]) / 2, rows_y[2], rows_y[3]]
    sx, sy = x0 + iw + 4.4, (inty[0] + inty[2]) / 2
    for k, (label, yc) in enumerate(zip(L['intents'], inty)):
        pill(s, x0 + .8, yc, label, C_INT[k], iw, size=TINY)
        s.route([(x0 + .8 + iw + .15, yc), (sx - 1.5, yc), (sx - 1.5, sy), (sx - 1.2, sy)], C_INT[k], .15, heads=None, radius=.4)
    sparkle(s, sx, sy, 1.15, LEARN)
    text(sx, baseline(sy + 2.0, TINY - .6), 'LLM', TINY - .6, LEARN, 'bold', align='center')
    for yc in rows_y:
        s.route([(sx + 1.3, sy), (sx + 2.0, sy), (sx + 2.0, yc), (mx - .25, yc)], LEARN, .13, radius=.4, length=.6)
    assert rows_y[-1] + 1.1 < yo + ho, (rows_y[-1], yo + ho)
    # training lane: offline -> judge (right lane)
    s.route([(x1 + .2, yo + ho / 2), (lane_r, yo + ho / 2), (lane_r, r2 + h2 / 2), (x1 + 1.3, r2 + h2 / 2)], LEARN, .2,
            dash=(.8, .5), length=.85, radius=.5)
    text(lane_r - .5, baseline(yo - .9, TINY), L['train'], TINY, LEARN, 'bold', align='right')
