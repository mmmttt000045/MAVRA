"""Figure 3: a verified session becomes a reusable, replay-checked definition.

Reading order: source -> fixed core / runtime bindings -> replay -> publish or
reject. Conditions 1--5 match Figure 5. Replay values come from M5-L1 and the
archived missing-category-filter counterexample (tools/figures/README.md).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import PT  # noqa: E402
from style import ACC, ACC_DK, ACC_PALE, EDGE, INK, MUTED, RED, RULE, WHITE  # noqa: E402
from smallparts import LEARN, LEARN_PALE, RED_PALE, mark, step  # noqa: E402

NAME = 'extraction'
W, H = style.COLUMN, 63.2


def draw(s, lang):
    en = lang == 'en'

    def label(x, yc, text, size=6.5, color=INK, font='sans', align='left', width=None):
        return s.text(x, yc + .34 * size * PT, text, size, color, font, align, width)

    def card(y, h, title, color, fill, badge=None):
        s.rect(.6, y, W - 1.2, h, WHITE, EDGE, .18, r=.55)
        s.rect(.7, y + .1, W - 1.4, 3.6, fill, None, r=.45)
        x = 1.7
        if badge is not None:
            step(s, 2.4, y + 1.9, badge, r=1.15)
            x = 4.3
        label(x, y + 1.9, title, 7.0, color, 'bold', width=W - x - 1.8)

    card(.5, 10.7, '(a) Verified source session' if en else '(a) 经核验的源会话', LEARN, LEARN_PALE, 1)
    label(1.7, 6.2, 'Jan. 2001 electronics revenue?' if en else '2001 年 1 月电子品类营业额？', 6.7)
    label(W - 1.7, 6.2, '`2,754,299.60`', 6.7, LEARN, 'sans', 'right', width=25.0)
    label(1.7, 9.2, 'G1-2: evidence + arithmetic; G5: read-only source SQL' if en
          else 'G1-2：来源证据与算术链；G5：源 SQL 只读', color=MUTED, width=W - 3.4)
    s.route([(W / 2, 11.2), (W / 2, 13.0)], LEARN, .25, length=.85)

    card(13.0, 23.8, '(b) Extract core; separate runtime bindings' if en
         else '(b) 抽取固定核心，分离运行期绑定', ACC_DK, ACC_PALE)
    s.line(49.7, 17.4, 49.7, 29.1, RULE, .18)
    label(1.7, 18.5, 'Fixed implementation $I$ (G3)' if en else '固定实现 $I$（G3）', 6.7, ACC_DK, 'bold', width=47.0)
    label(1.7, 21.4, '`store_sales`; $K$: (item, ticket)' if en else '`store_sales`；$K$：商品、小票', width=47.0)
    label(1.7, 24.1, '`SUM(ss_net_paid)`; sale date $\\tau$' if en else '`SUM(ss_net_paid)`；销售日期 $\\tau$', width=47.0)
    label(1.7, 26.8, 'many-to-one joins: `item`, `date_dim`' if en else '多对一连接：`item`、`date_dim`', width=47.0)
    label(1.7, 29.5, "$\\varphi$: `i_category = 'Electronics'`", color=ACC_DK, width=47.0)
    label(51.0, 18.5, 'Runtime $(p,d)$' if en else '运行期 $(p,d)$', 6.7, LEARN, 'bold', width=31.8)
    label(51.0, 21.4, '$p_0$: Jan. 2001' if en else '$p_0$：2001 年 1 月', width=31.8)
    label(51.0, 24.1, '$d_0$: identity' if en else '$d_0$：直接取总额', width=31.8)
    label(51.0, 26.8, 'Reuse: month + rank' if en else '复用：月份＋排名', width=31.8)
    label(51.0, 29.5, 'or two periods + $\\Delta$' if en else '或两期间＋差值 $\\Delta$', width=31.8)
    s.line(1.7, 31.0, W - 1.7, 31.0, RULE, .18)
    label(1.7, 32.4, 'Derive/check $C$: 1 fact grain (G4); 2 item key; 4 date key' if en
          else '派生并检查 $C$：1 事实粒度（G4）；2 商品键；4 日期键', color=MUTED, width=W - 3.4)
    label(1.7, 35.2, '3 item-join loss; 5 date-join loss (see Fig. 5)' if en
          else '3 商品连接丢行；5 日期连接丢行（见图 5）', color=MUTED, width=W - 3.4)
    s.route([(W / 2, 36.8), (W / 2, 38.2)], ACC, .25, length=.75)

    card(38.2, 24.4, '(c) Replay before publication' if en else '(c) 发布前回放验证', LEARN, LEARN_PALE, 2)
    label(1.7, 43.6, 'G6: source SQL reproduces the verified answer' if en
          else 'G6：源 SQL 复现核验答案', width=W - 3.4)
    label(1.7, 46.7, 'G7: recompile $I$ with $(p_0,d_0)$; compare with the same answer' if en
          else 'G7：仅由 $I$ 与 $(p_0,d_0)$ 重编译，对照同一核验答案', width=W - 3.4)
    rows = ((50.6, True, 'Keep $\\varphi$' if en else '保留 $\\varphi$', '2,754,299.60', 'publish' if en else '发布'),
            (54.7, False, 'Omit $\\varphi$' if en else '遗漏 $\\varphi$', '13,532,799.00', 'reject' if en else '拒绝'))
    for yc, ok, candidate, answer, outcome in rows:
        col, fill = (ACC_DK, ACC_PALE) if ok else (RED, RED_PALE)
        s.rect(1.7, yc - 1.55, W - 3.4, 3.1, fill, None, r=.4)
        label(2.7, yc, candidate, 6.7, col, 'bold', width=20.0)
        s.route([(25.0, yc), (29.0, yc)], col, .2, length=.8)
        label(31.0, yc, f'`{answer}`', 6.7, col, width=27.0)
        mark(s, 61.0, yc, ok, k=.85)
        label(64.0, yc, outcome, 6.7, col, 'bold', width=17.0)
    label(1.7, 59.9, 'Evidence for $(D_{s_0},p_0,d_0)$; not a proof for every parameter.' if en
          else '证据限于 $(D_{s_0},p_0,d_0)$，并非所有参数下的等价证明。', color=MUTED, width=W - 3.4)


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
