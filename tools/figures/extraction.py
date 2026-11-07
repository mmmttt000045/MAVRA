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
from style import INK, MUTED, RED  # noqa: E402
from smallparts import BLUE_TXT, BODY, CODE, LABEL, LIGHT, SMALL, arrow, box, mark  # noqa: E402

NAME = 'extraction'
W, H = style.COLUMN, 39.0
VERIFIED, WRONG_VALUE = '2,754,299.60', '13,532,799.00'

LABELS = {
    'en': {
        'session': "Agent 1's verified session", 'answer': 'verified answer', 'cat': 'Electronics',
        'draft_note': ('LLM drafts a definition;', 'the month becomes the period'),
        'drafts': ('(a) Draft A', '(b) Draft B'), 'missing': 'no category filter',
        'run_note': ('compile for January', 'and run'),
        'verdict': ('differs: rejected', 'matches: published'),
    },
    'zh': {
        'session': '智能体 1 经核验的会话', 'answer': '核验答案', 'cat': '电子',
        'draft_note': ('LLM 起草定义，', '月份变为期间参数'),
        'drafts': ('(a) 草稿 A', '(b) 草稿 B'), 'missing': '缺少品类过滤',
        'run_note': ('按 1 月编译', '并执行'),
        'verdict': ('不一致：不予发布', '一致：发布'),
    },
}


def draw(s, lang):
    L = LABELS[lang]
    text = s.text

    # The verified session.
    sx, sy, sw, sh = 1.0, 1.0, 82.6, 10.4
    box(s, sx, sy, sw, sh)
    text(sx + 1.2, sy + 3.1, L['session'], LABEL, INK, 'bold')
    vw = text(sx + sw - 1.2, sy + 3.1, f'`{VERIFIED}`', CODE, INK, align='right')
    text(sx + sw - 2.2 - vw, sy + 3.1, L['answer'], SMALL, MUTED, align='right')
    text(sx + 1.2, sy + 6.0, '`SELECT SUM(ss_net_paid) FROM store_sales JOIN item ... JOIN date_dim ...`',
         CODE, INK, width=sw - 2.4)
    head = f"`WHERE i_category = '{L['cat']}' AND `"
    hw = measure(head, CODE)
    lit = '`d_moy = 1`'
    lw = measure(lit, CODE)
    y2 = sy + 8.5
    s.rect(sx + 1.2 + hw - .3, y2 - 1.7, lw + .6, 2.2, LIGHT, None, r=.3)
    text(sx + 1.2, y2, head, CODE, INK)
    text(sx + 1.2 + hw, y2, lit, CODE, INK)
    text(sx + 1.2 + hw + lw, y2, '` AND ...`', CODE, INK)

    # Two drafts of the same session.
    dw = 39.8
    dxs = (sx, sx + sw - dw)
    centres = [x + dw / 2 for x in dxs]
    dy = sy + sh + 5.4
    for cx in centres:
        arrow(s, [(cx, sy + sh), (cx, dy)])
    mid = (centres[0] + centres[1]) / 2
    for j, line in enumerate(L['draft_note']):
        text(mid, sy + sh + 2.3 + 2.4 * j, line, SMALL, MUTED, align='center',
             width=centres[1] - centres[0] - 3.0)
    rows = 3
    dh = 3.9 + 2.4 * rows + .6
    keyw = measure('`  `', CODE)                 # continuation indent
    for i, x in enumerate(dxs):
        box(s, x, dy, dw, dh)
        text(x + 1.2, dy + 3.0, L['drafts'][i], BODY, INK, 'bold')
        y = dy + 5.6
        text(x + 1.2, y, '`"measure": "sum(ss_net_paid)"`', CODE, INK, width=dw - 2.4)
        if i == 0:
            text(x + 1.2, y + 2.4, '`"filters": {}`', CODE, INK)
            text(x + 1.2 + keyw, y + 4.8, L['missing'], SMALL, RED, width=dw - 2.4 - keyw)
        else:
            text(x + 1.2, y + 2.4, '`"filters": {"item":`', CODE, INK)
            text(x + 1.2 + keyw, y + 4.8, f"`\"i_category = '{L['cat']}'\"}}`", CODE, INK,
                 width=dw - 2.4 - keyw)

    # Compile each draft for January and compare with the verified answer.
    ry = dy + dh + 5.2
    for cx in centres:
        arrow(s, [(cx, dy + dh), (cx, ry - 1.2)])
    for j, line in enumerate(L['run_note']):
        text(mid, dy + dh + 2.5 + 2.3 * j, line, SMALL, MUTED, align='center',
             width=centres[1] - centres[0] - 3.0)
    for i, (value, ok) in enumerate(((WRONG_VALUE, False), (VERIFIED, True))):
        c = BLUE_TXT if ok else RED
        vy = ry + 1.2
        w = measure(f'`{value}`', CODE + .3)
        x0 = centres[i] - (w + 2.2) / 2
        text(x0, vy, f'`{value}`', CODE + .3, c)
        mark(s, x0 + w + 1.4, vy - .75, ok)
        text(centres[i], vy + 2.7, L['verdict'][i], SMALL, c, align='center', width=dw)
    assert ry + 4.6 < H, ry


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
