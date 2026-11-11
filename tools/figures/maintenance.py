"""Figure 5: shared validation followed by explicit repair admission.

The 7-condition / 15-reference matrix compares shared checks with full rechecks
per definition. Repair follows Figure 2's item-17 history insert. Counts prune
candidates; publication requires all conditions AND source-answer replay, with
exactly one passing edit. Domain failures remain pending.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import PT  # noqa: E402
from style import ACC, ACC_DK, ACC_PALE, EDGE, INK, MUTED, RED, RULE, WHITE  # noqa: E402
from smallparts import MAINT_C, mark, step  # noqa: E402

NAME = 'maintenance'
W, H = style.COLUMN, 75.2
TEAL_PALE = '#E4F5F2'


def draw(s, lang):
    en = lang == 'en'

    def label(x, yc, text, size=6.5, color=INK, font='sans', align='left', width=None):
        return s.text(x, yc + .34 * size * PT, text, size, color, font, align, width)

    def card(y, h, title, badge=None):
        s.rect(.6, y, W - 1.2, h, WHITE, EDGE, .18, r=.55)
        s.rect(.7, y + .1, W - 1.4, 3.6, TEAL_PALE, None, r=.45)
        x = 1.7
        if badge is not None:
            step(s, 2.4, y + 1.9, badge, r=1.15)
            x = 4.3
        label(x, y + 1.9, title, 7.0, MAINT_C, 'bold', width=W - x - 1.8)

    card(.5, 34.1, '(a) Share checks after a write' if en else '(a) 写入后共享条件检查', 5)
    label(W - 1.7, 2.4, '7 checks, 15 refs' if en else '7 项检查，15 条引用', color=MAINT_C, align='right', width=25.0)
    label(1.7, 6.4, 'Condition' if en else '条件', color=MUTED)
    xs = (39.0, 44.5, 50.0, 55.5)
    for x, name in zip(xs, ('SR', 'RA', 'RR', 'ER')):
        label(x, 6.4, name, font='bold', align='center')
    label(66.5, 6.4, 'item' if en else '商品', color=MAINT_C, align='center', width=13.0)
    label(78.0, 6.4, 'sales' if en else '销售', color=MAINT_C, align='center', width=11.0)
    s.line(1.0, 8.0, W - 1.0, 8.0, RULE, .18)
    rows = (
        ('`store_sales.K`', (0, 2, 3), False, True),
        ('`item.i_item_sk`', (3,), True, False),
        ('`store_sales` $\\to$ `item`', (3,), True, True),
        ('`date_dim.d_date_sk`', (0, 1, 2, 3), False, False),
        ('`store_sales` $\\to$ `date`', (0, 2, 3), False, True),
        ('`store_returns.K_r`', (1, 2), False, False),
        ('`store_returns` $\\to$ `date`', (1,), False, False),
    )
    for index, (condition, refs, item, sales) in enumerate(rows):
        yc = 9.7 + 2.65 * index
        if item:
            s.rect(1.0, yc - 1.2, W - 2.0, 2.4, TEAL_PALE, None, r=.3)
        label(1.7, yc, str(index + 1), color=MUTED, font='bold', width=2.0)
        label(4.4, yc, condition, width=32.0)
        if len(refs) > 1:
            s.line(xs[min(refs)], yc, xs[max(refs)], yc, ACC, .18)
        for ref in refs:
            s.circle(xs[ref], yc, .55, ACC)
        for x, rerun in ((66.5, item), (78.0, sales)):
            if rerun:
                s.circle(x, yc, .55, MAINT_C)
        if index == 1:
            mark(s, 69.0, yc, False, k=.75)
    s.line(1.0, 26.8, W - 1.0, 26.8, RULE, .18)
    label(1.7, 28.6, 'New checks / full checks per definition:' if en else '新检查次数／逐定义全检次数：', color=MUTED, width=57.0)
    label(66.5, 28.6, '2 / 5', 6.7, MAINT_C, 'bold', 'center', width=13.0)
    label(78.0, 28.6, '3 / 12', 6.7, MAINT_C, 'bold', 'center', width=11.0)
    label(1.7, 31.8, 'Blue: shared references; teal: checks run once for all agents.' if en
          else '蓝点：共享引用；绿点：跨所有智能体仅检查一次。', color=MUTED, width=W - 3.4)

    card(36.0, 38.6, '(b) Repair: prune, verify, then require a unique edit' if en
         else '(b) 修复：候选剪枝、验证，再判定唯一修改', 6)
    label(1.7, 41.7, "Index probe on $\\Delta T$: key `17` $\\to$ duplicate" if en
          else "索引探测 $\\Delta T$ 中的键 `17` $\\to$ 重复", width=47.0)
    label(W - 1.7, 41.7, '1,001 rows; 1,000 keys' if en else '1,001 行；1,000 个键', color=MUTED, align='right', width=33.0)

    s.rect(1.7, 44.1, 31.7, 20.0, WHITE, RULE, .18, r=.45)
    label(2.7, 46.3, 'Filters ($\\leq 20$ values)' if en else '候选过滤（$\\leq 20$ 种值）', 6.5, INK, 'bold', width=29.7)
    label(2.7, 49.4, '`i_is_current`:', color=MUTED, width=29.7)
    label(2.7, 52.5, "`'Y'`: 1,000 rows $\\to$ keep" if en else "`'Y'`：1,000 行，保留", color=ACC_DK, width=29.7)
    label(2.7, 55.6, "`'N'`: 1 row $\\to$ prune" if en else "`'N'`：1 行，剪除", color=MUTED, width=29.7)
    label(2.7, 58.7, 'category: 200-201; prune' if en else '品类：200-201 行，剪除', color=MUTED, width=29.7)
    label(2.7, 62.0, 'Pruning only; not admission.' if en else '仅为剪枝，尚未通过准入。', color=MUTED, width=29.7)
    s.route([(33.4, 54.0), (37.0, 54.0)], MAINT_C, .25, length=.85)

    s.rect(37.0, 44.1, W - 38.7, 20.0, ACC_PALE, ACC, .2, r=.45)
    label(38.2, 46.3, 'A candidate must pass BOTH' if en else '每个候选必须同时通过', 6.7, ACC_DK, 'bold', width=W - 40.5)
    label(38.2, 50.0, '1. All $C(x\\oplus e)$ hold on current $D$' if en else '1. 当前 $D$ 上全部 $C(x\\oplus e)$ 成立', width=W - 40.5)
    label(38.2, 54.0, '2. Replay the source answer from $E_x$' if en else '2. 回放复现 $E_x$ 中的源核验答案', width=W - 40.5)
    label(38.2, 57.2, '`2,754,299.60` = source' if en else '`2,754,299.60` = 源答案', color=ACC_DK, width=W - 43.0)
    mark(s, W - 3.3, 57.2, True, k=.8)
    label(38.2, 61.3, 'Key uniqueness alone is insufficient.' if en else '键唯一性不能单独决定发布。', color=MUTED, width=W - 40.5)

    s.route([(60.0, 64.1), (60.0, 66.1)], ACC, .25, length=.85)
    s.rect(1.7, 66.1, W - 3.4, 3.6, ACC_PALE, None, r=.4)
    label(2.7, 67.9, "Exactly 1 passes $\\to$ publish $r+1$: `i_is_current='Y'`" if en
          else "唯一候选通过 $\\to$ 发布 $r+1$：`i_is_current='Y'`", 6.7, ACC_DK, 'bold', width=W - 5.4)
    label(1.7, 72.4, '0 or $>1$ pass: retire; domain check fails: pending' if en
          else '无候选或多个候选通过：退役；值域检查失败：待确认', color=RED, width=W - 3.4)


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
