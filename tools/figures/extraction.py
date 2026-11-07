"""Checked publication (Section IV-B), single column: two drafts of one session.

Agent 1's verified session (January electronics revenue, learning task M5-L1)
is drafted into a definition whose month becomes the period input. Compiled
for January, draft A, which lacks the category filter, returns January
revenue over all categories and is rejected; draft B reproduces the verified
answer and is published.

Values come from the recorded runs on the TPC-DS fixture: the verified answer
2,754,299.60 (exp/2026-10-01-workload-characterization, M5-L1 sessions) and a
rejected draft whose compiled SQL returned 13,532,799.00
(exp/2026-10-31-diverse-scenarios/case-evidence.json, M5-L1, failed gate G7).
The JSON lines are abridged to the fields that differ.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import measure  # noqa: E402
from style import INK, MUTED, RED, WHITE  # noqa: E402
from smallparts import (BLUE, BLUE_PALE, BLUE_TXT, BODY, CODE, KEYC, LABEL, LEARN, LEARN_PALE,  # noqa: E402
                        LINE, RED_PALE, SMALL, arrow, baseline, card, parts, person, sparkle, step,
                        verdict)

NAME = 'extraction'
W, H = style.COLUMN, 39.4
VERIFIED, WRONG_VALUE = '2,754,299.60', '13,532,799.00'

LABELS = {
    'en': {
        'session': "Agent 1's verified session", 'answer': 'verified answer', 'cat': 'Electronics',
        'period': r'$\leftarrow$ becomes the period', 'llm': 'LLM drafts a definition',
        'drafts': ('(a) Draft A', '(b) Draft B'), 'missing': 'no category filter',
        'gate': 'run for January: same answer?', 'verdict': ('rejected', 'published'),
    },
    'zh': {
        'session': '智能体 1 经核验的会话', 'answer': '核验答案', 'cat': '电子',
        'period': r'$\leftarrow$ 变为期间参数', 'llm': 'LLM 起草定义',
        'drafts': ('(a) 草稿 A', '(b) 草稿 B'), 'missing': '缺少品类过滤',
        'gate': '按 1 月执行：答案一致？', 'verdict': ('不予发布', '发布'),
    },
}


def draw(s, lang):
    L = LABELS[lang]
    text = s.text

    # The verified session (step 1 of Fig. 2 hands it to Publish).
    sx, sy, sw, sh, band = 1.0, 1.0, 82.6, 10.4, 3.5
    card(s, sx, sy, sw, sh, band, LEARN_PALE)
    yb = sy + .15 + band / 2
    step(s, sx + 2.2, yb, 1)
    person(s, sx + 5.1, yb, LEARN)
    text(sx + 7.0, baseline(yb, LABEL), L['session'], LABEL, INK, 'bold')
    vw = text(sx + sw - 1.2, baseline(yb, CODE), f'`{VERIFIED}`', CODE, INK, align='right')
    text(sx + sw - 2.2 - vw, baseline(yb, SMALL), L['answer'], SMALL, MUTED, align='right')
    y1, y2 = sy + band + 3.1, sy + band + 5.65
    text(sx + 1.2, y1, '`SELECT SUM(ss_net_paid) FROM store_sales JOIN item ... JOIN date_dim ...`',
         CODE, INK, width=sw - 2.4)
    head = f"`WHERE i_category = '{L['cat']}' AND `"
    hw, lit = measure(head, CODE), '`d_moy = 1`'
    lw = measure(lit, CODE)
    s.rect(sx + 1.2 + hw - .35, y2 - 1.75, lw + .7, 2.3, LEARN_PALE, LEARN, .14, r=.35)
    end = parts(s, sx + 1.2, y2, [(head, INK), (lit, INK), ('` AND ...`', INK)], CODE)
    text(end + 1.6, y2, L['period'], SMALL, LEARN, width=sx + sw - 1.2 - end - 1.6)

    # The learning agent drafts a definition; two possible drafts.
    dw = 39.8
    dxs = (sx, sx + sw - dw)
    centres = [x + dw / 2 for x in dxs]
    mid = (centres[0] + centres[1]) / 2
    cy, ch = sy + sh + 2.4, 2.9
    cw = measure(L['llm'], SMALL, 'bold') + 5.2
    s.line(mid, sy + sh, mid, cy - ch / 2, LEARN, LINE)
    s.rect(mid - cw / 2, cy - ch / 2, cw, ch, LEARN_PALE, LEARN, LINE, r=1.45)
    sparkle(s, mid - cw / 2 + 1.9, cy, .95, LEARN)
    text(mid - cw / 2 + 3.4, baseline(cy, SMALL), L['llm'], SMALL, INK, 'bold')
    dy = cy + ch / 2 + 2.6
    for k, cx in enumerate(centres):
        x_from = mid - cw / 2 if k == 0 else mid + cw / 2
        arrow(s, [(x_from, cy), (cx, cy), (cx, dy)], LEARN)

    band_d, pitch = 3.2, 2.45
    dh = band_d + 1.6 + 3 * pitch
    keyw = measure('`  `', CODE)                 # continuation indent
    for i, x in enumerate(dxs):
        ok = i == 1
        card(s, x, dy, dw, dh, band_d, BLUE_PALE if ok else RED_PALE, BLUE if ok else RED)
        text(x + 1.2, baseline(dy + .1 + band_d / 2, BODY), L['drafts'][i], BODY, INK, 'bold')
        y = dy + band_d + 2.5
        parts(s, x + 1.2, y, [('`"measure"`', KEYC), ('`: "sum(ss_net_paid)"`', INK)], CODE)
        fx = parts(s, x + 1.2, y + pitch, [('`"filters"`', KEYC), ('`: `', INK)], CODE)
        if not ok:
            ew = measure('`{}`', CODE)
            s.rect(fx - .35, y + pitch - 1.75, ew + .7, 2.3, RED_PALE, RED, .14, r=.35)
            text(fx, y + pitch, '`{}`', CODE, INK)
            nx = fx + ew + 1.6
            text(nx, y + pitch, L['missing'], SMALL, RED, 'bold', width=x + dw - 1.2 - nx)
        else:
            parts(s, fx, y + pitch, [('`{`', INK), ('`"item"`', KEYC), ('`:`', INK)], CODE)
            value = f"`\"i_category = '{L['cat']}'\"`"
            vw2 = measure(value, CODE)
            vx = x + 1.2 + keyw
            s.rect(vx - .35, y + 2 * pitch - 1.75, vw2 + .7, 2.3, BLUE_PALE, BLUE, .14, r=.35)
            end = text(vx + vw2 + .55, y + 2 * pitch, '`}`', CODE, INK) + vx + vw2 + .55
            text(vx, y + 2 * pitch, value, CODE, INK)
            assert end < x + dw - 1.0, end

    # One check for both: compile for January and compare with the verified answer.
    ry, rh = dy + dh + 4.6, 4.4
    for cx in centres:
        arrow(s, [(cx, dy + dh), (cx, ry)])
    gy = dy + dh + 2.3
    gw = measure(L['gate'], SMALL, 'bold') + 3.2
    s.rect(mid - gw / 2, gy - 1.4, gw, 2.8, WHITE, LEARN, LINE, r=1.4)
    text(mid, baseline(gy, SMALL), L['gate'], SMALL, INK, 'bold', 'center')
    assert mid - gw / 2 > centres[0] + 1.0, gw

    for i, (value, ok) in enumerate(((WRONG_VALUE, False), (VERIFIED, True))):
        x, c = dxs[i], (BLUE_TXT if ok else RED)
        s.rect(x, ry, dw, rh, BLUE_PALE if ok else RED_PALE, None, r=.5)
        yc = ry + rh / 2
        vw2 = measure(f'`{value}`', CODE + .3)
        tw = measure(L['verdict'][i], BODY, 'bold')
        total = 2.1 + 1.2 + vw2 + 1.6 + tw + (3.4 if ok else 0)
        xx = centres[i] - total / 2
        verdict(s, xx + 1.05, yc, ok)
        xx += 3.3
        xx += text(xx, baseline(yc, CODE + .3), f'`{value}`', CODE + .3, c) + 1.6
        xx += text(xx, baseline(yc, BODY), L['verdict'][i], BODY, c, 'bold')
        if ok:
            step(s, xx + 2.2, yc, 2)
    assert ry + rh < H - .3, ry
