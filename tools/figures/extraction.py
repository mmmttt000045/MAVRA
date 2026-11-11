"""Definition extraction, generalization boundary, condition derivation, and publication gates (Figure 3).

Single column (84.6 mm wide). Preserves the join-tree + condition-markers + G6/G7
reproduction skeleton while explicitly showing:
  1. The 3-layer generalization boundary (Fixed core I vs. Parameter slot p vs.
     Supported derivations d) extracted from Agent 1's verified session;
  2. Both structural conditions (1-5) and probe-lifted assumptions (6: domain probe
     on item.i_category) stored in H at (id(c), V(dep(c)));
  3. Gates G1-G7, highlighting how G7 (Compile(I, p0)) rejects an incomplete draft
     that dropped filter phi even though raw session SQL passed G6.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import PT, measure  # noqa: E402
from style import ACC, ACC_DK, ACC_PALE, AMBER_PALE, EDGE, FACE, INK, MUTED, RED, RULE, WHITE  # noqa: E402
from smallparts import LEARN, LEARN_PALE, MAINT_C, RED_PALE, step  # noqa: E402

NAME = 'extraction'
W, H = style.COLUMN, 54.0

OCHRE = '#9A6500'
TEAL_PALE = '#E4F5F2'


def baseline(yc, size):
    return yc + .34 * size * PT


def draw(s, lang):
    text, rect = s.text, s.rect

    def label(x, yc, txt, size=5.5, color=INK, wt='sans', align='left', width=None):
        return text(x, baseline(yc, size), txt, size, color, wt, align, width)

    def gbadge(x, yc, tag, col=LEARN, fill=LEARN_PALE):
        w = measure(tag, 5.0, 'bold') + 1.4
        rect(x, yc - 1.05, w, 2.1, fill, col, .16, r=.35)
        label(x + w / 2, yc, tag, 5.0, col, 'bold', 'center')
        return w

    def cmark(x, yc, n, col=ACC_DK):
        s.circle(x, yc, 0.95, col)
        label(x, yc, str(n), 4.9, WHITE, 'bold', 'center')

    def check_mark(x, yc, ok, c=None):
        if ok:
            s.poly([(x - .55, yc), (x - .12, yc + .45), (x + .6, yc - .5)], None, c or ACC, .25, closed=False)
        else:
            s.line(x - .48, yc - .48, x + .48, yc + .48, c or RED, .25)
            s.line(x - .48, yc + .48, x + .48, yc - .48, c or RED, .25)

    # =========================================================================
    # 1. Top Box: Agent 1's Verified Session & Exploration Probe (Step 1)
    # =========================================================================
    y1, h1 = 0.6, 11.4
    rect(0.6, y1, W - 1.2, h1, WHITE, EDGE, .18, r=.55)
    rect(0.7, y1 + 0.1, W - 1.4, 2.9, LEARN_PALE, None, r=.45)
    step(s, 2.2, y1 + 1.55, 1, r=1.1)
    label(3.8, y1 + 1.55, "Agent 1's verified session" if lang == 'en' else '智能体 1 经核验的会话', 5.8, INK, 'bold')
    gbadge(29.8, y1 + 1.55, 'G1')
    gbadge(34.2, y1 + 1.55, 'G2')
    label(W - 1.4, y1 + 1.55, 'verified `2,754,299.60`' if lang == 'en' else '核验值 `2,754,299.60`', 5.3, LEARN, 'bold', 'right')

    # SQL + probe inside session box
    label(1.6, y1 + 4.5, '`SELECT SUM(ss_net_paid) FROM store_sales JOIN item ... JOIN date_dim ...`', 5.1, INK)
    gbadge(W - 5.4, y1 + 4.5, 'G5')

    # Second SQL line with boxed phi and p
    ly2 = y1 + 7.2
    w_wh = label(1.6, ly2, '`WHERE `', 5.1, INK)
    x_phi = 1.6 + w_wh
    phi_txt = "`i_category = 'Electronics'`"
    w_phi = measure(phi_txt, 5.1) + 1.0
    rect(x_phi, ly2 - 1.15, w_phi, 2.2, ACC_PALE, ACC, .16, r=.3)
    label(x_phi + 0.5, ly2, phi_txt, 5.1, ACC_DK)
    label(x_phi + w_phi + 0.3, ly2 - 0.5, '$\\varphi$', 5.3, ACC_DK, 'bold')

    x_and = x_phi + w_phi + 2.2
    w_and = label(x_and, ly2, '`AND `', 5.1, INK)
    x_p = x_and + w_and
    p_txt = '`d_year = 2001 AND d_moy = 1`'
    w_p = measure(p_txt, 5.1) + 1.0
    rect(x_p, ly2 - 1.15, w_p, 2.2, LEARN_PALE, LEARN, .16, r=.3, dash=(.6, .35))
    label(x_p + 0.5, ly2, p_txt, 5.1, LEARN)
    label(x_p + w_p + 0.3, ly2 - 0.5, '$p$', 5.3, LEARN, 'bold')

    # Probe line
    ly3 = y1 + 9.9
    rect(1.6, ly3 - 1.05, W - 3.2, 2.1, TEAL_PALE, MAINT_C, .14, r=.3)
    label(2.2, ly3, 'Exploration probe:' if lang == 'en' else '探索探查：', 5.0, MAINT_C, 'bold')
    label(18.5 if lang == 'en' else 11.5, ly3, '`SELECT DISTINCT i_category FROM item` $\\rightarrow$ observed domain lifted to `6`', 4.95, INK, width=W - 20.5)

    # =========================================================================
    # 2. Middle Box: Structured Implementation I & 3-Layer Boundary (G3)
    # =========================================================================
    y2, h2 = y1 + h1 + 1.0, 18.8
    rect(0.6, y2, W - 1.2, h2, FACE, EDGE, .18, r=.55)
    label(1.6, y2 + 1.7, 'Structured Implementation $I$ & Generalization Boundary' if lang == 'en' else '结构化实现 $I$ 与三层泛化边界', 5.7, ACC_DK, 'bold')
    gbadge(W - 5.4, y2 + 1.7, 'G3', ACC_DK, ACC_PALE)

    # Three table boxes in join tree: item, store_sales (F), date_dim
    ty = y2 + 3.4
    th = 9.8
    # item
    ix, iw = 1.4, 21.8
    rect(ix, ty, iw, th, WHITE, EDGE, .16, r=.4)
    rect(ix + .1, ty + .1, iw - .2, 2.2, '#ECEAE5', None, r=.3)
    label(ix + 0.8, ty + 1.2, '`item`', 5.3, INK, 'bold')
    label(ix + 0.8, ty + 3.9, '`i_item_sk` (PK)', 4.9, INK)
    cmark(ix + iw - 1.5, ty + 3.9, 2)
    label(ix + 0.8, ty + 6.4, '`i_category`', 4.9, INK)
    rect(ix + 12.2, ty + 5.4, 3.2, 1.9, ACC, None, r=.3)
    label(ix + 13.8, ty + 6.4, '$\\varphi$', 4.9, WHITE, 'bold', 'center')
    cmark(ix + iw - 1.5, ty + 6.4, 6, MAINT_C)
    label(ix + 0.8, ty + 8.6, 'fixed domain filter' if lang == 'en' else '固定业务过滤', 4.6, ACC_DK, 'bold')

    # store_sales (F)
    fx, fw = 28.4, 27.6
    rect(fx, ty, fw, th, WHITE, ACC, .2, r=.4)
    rect(fx + .1, ty + .1, fw - .2, 2.2, ACC_PALE, None, r=.3)
    label(fx + 0.8, ty + 1.2, '`store_sales`', 5.3, ACC_DK, 'bold')
    label(fx + fw - 1.0, ty + 1.2, '$F$', 5.3, ACC_DK, 'bold', 'right')
    label(fx + 0.8, ty + 3.6, '`ss_sold_date_sk`', 4.9, INK)
    label(fx + 0.8, ty + 5.6, '`ss_item_sk, ss_ticket` ($K$)', 4.85, INK)
    cmark(fx + fw - 1.5, ty + 5.6, 1)
    label(fx + 0.8, ty + 7.9, '`SUM(ss_net_paid)` ($e$)', 4.9, ACC_DK, 'bold')

    # date_dim
    dx, dw = 61.2, 21.8
    rect(dx, ty, dw, th, WHITE, EDGE, .16, r=.4)
    rect(dx + .1, ty + .1, dw - .2, 2.2, '#ECEAE5', None, r=.3)
    label(dx + 0.8, ty + 1.2, '`date_dim`', 5.3, INK, 'bold')
    label(dx + 0.8, ty + 3.9, '`d_date_sk` (PK)', 4.9, INK)
    cmark(dx + dw - 1.5, ty + 3.9, 4)
    rect(dx + 0.8, ty + 5.3, dw - 1.6, 3.8, LEARN_PALE, LEARN, .15, r=.3, dash=(.6, .35))
    label(dx + 1.4, ty + 6.6, '`d_year, d_moy`', 4.85, LEARN, 'bold')
    label(dx + 1.4, ty + 8.3, 'param slot $p$' if lang == 'en' else '参数槽 $p$', 4.6, LEARN, 'bold')

    # Join lines & condition markers 3 and 5
    jy1 = ty + 4.8
    s.line(ix + iw, jy1, fx, jy1, INK, .2)
    cmark((ix + iw + fx) / 2, jy1, 3)
    label((ix + iw + fx) / 2, jy1 - 1.8, 'inner', 4.6, MUTED, 'sans', 'center')

    jy2 = ty + 3.9
    s.line(fx + fw, jy2, dx, jy2, INK, .2)
    cmark((fx + fw + dx) / 2, jy2, 5)
    label((fx + fw + dx) / 2, jy2 - 1.8, '$\\tau$', 5.0, MUTED, 'bold', 'center')

    # 3-Layer Generalization Strip at bottom of Middle Box
    gy_s = ty + th + 0.7
    gh_s = 4.3
    rect(1.4, gy_s, W - 2.8, gh_s, WHITE, ACC, .15, r=.35)
    label(2.0, gy_s + 1.35, 'Fixed core $I$:' if lang == 'en' else '固定核心 $I$：', 4.85, ACC_DK, 'bold')
    label(13.8 if lang == 'en' else 13.5, gy_s + 1.35, '$F, e, K, \\mathcal{J}, \\varphi, \\tau$ (change $\\rightarrow$ new def.)  |  ' if lang == 'en' else '$F, e, K, \\mathcal{J}, \\varphi, \\tau$（改变则建新定义） | ', 4.8, INK)
    label(47.0 if lang == 'en' else 44.5, gy_s + 1.35, 'Param $p$:' if lang == 'en' else '参数 $p$：', 4.85, LEARN, 'bold')
    label(55.2 if lang == 'en' else 52.0, gy_s + 1.35, 'period / cutoff $(u_i,t_i)$' if lang == 'en' else '期间 / 预测截点 $(u_i,t_i)$', 4.8, INK)
    label(2.0, gy_s + 3.2, 'Allowed derivations $d$:' if lang == 'en' else '允许派生操作 $d$：', 4.85, OCHRE, 'bold')
    label(20.5 if lang == 'en' else 17.5, gy_s + 3.2, 'slice/rank by $\\mathcal{J}$-reachable attributes (`d_moy`, `i_brand`), period diff/ratio' if lang == 'en' else '按 $\\mathcal{J}$ 可达属性切片或排名（如 `d_moy`）、期间差值/同比', 4.8, INK)

    # =========================================================================
    # 3. Lower-Middle Box: Derived & Lifted Conditions C(m^r) (Step 2)
    # =========================================================================
    y3, h3 = y2 + h2 + 1.0, 12.6
    rect(0.6, y3, W - 1.2, h3, WHITE, EDGE, .18, r=.55)
    rect(0.7, y3 + 0.1, W - 1.4, 2.8, ACC_PALE, None, r=.45)
    step(s, 2.2, y3 + 1.5, 2, r=1.1)
    label(3.8, y3 + 1.5, 'Conditions $C(m^r)$ derived & checked at publication' if lang == 'en' else '发布时推导并检验的条件集 $C(m^r)$', 5.6, INK, 'bold')
    label(W - 1.4, y3 + 1.5, 'indexed in $\\mathcal{H}$' if lang == 'en' else '存入 $\\mathcal{H}$', 5.0, ACC_DK, 'bold', 'right')

    # Left column: KeyUnique (1, 2, 4) + ProbeDomain (6)
    cy0 = y3 + 4.2
    cmark(2.2, cy0, 1)
    label(3.6, cy0, '`KeyUnique(store_sales.K)`: $10^6=10^6$', 4.8, INK)
    gbadge(38.0, cy0, 'G4')

    cy1 = cy0 + 2.4
    cmark(2.2, cy1, 2)
    label(3.6, cy1, '`KeyUnique(item.i_item_sk)`: $1000=1000$', 4.8, INK)

    cy2 = cy1 + 2.4
    cmark(2.2, cy2, 4)
    label(3.6, cy2, '`KeyUnique(date_dim.d_date_sk)`: $1096$', 4.8, INK)

    cy3 = cy2 + 2.4
    cmark(2.2, cy3, 6, MAINT_C)
    label(3.6, cy3, '`Domain(item.i_category)` $\\subseteq$ observed (10)' if lang == 'en' else '`Domain(item.i_category)` $\\subseteq$ 探查值集', 4.8, MAINT_C, 'bold')

    # Divider line
    s.line(43.8, y3 + 3.2, 43.8, y3 + h3 - 0.6, RULE, .15)

    # Right column: JoinCompleteness (3, 5)
    label(45.0, cy0, 'Unmatched loss $\\leq b + 0.1\\,\\mathrm{pt}$:' if lang == 'en' else '连接未匹配率 $\\leq b + 0.1\\,\\mathrm{pt}$：', 4.85, ACC_DK, 'bold')
    cmark(45.8, cy1 + 0.3, 3)
    label(47.2, cy1 + 0.3, '`sales` $\\rightarrow$ `item`: `0.00%` ($b=0$)', 4.8, INK)
    cmark(45.8, cy2 + 0.6, 5)
    label(47.2, cy2 + 0.6, '`sales` $\\rightarrow$ `date`: `1.03%` ($b=1.03\\%$)', 4.8, INK)
    label(45.0, cy3, 'Exact if $b=0$ (Proposition 3)' if lang == 'en' else '$b=0$ 时保证精确聚合（命题 3）', 4.75, MUTED)

    # =========================================================================
    # 4. Bottom Strip: Answer Reproduction Gates G6 vs. G7
    # =========================================================================
    y4 = y3 + h3 + 1.0
    rows_g = (
        ('G6', 'raw session SQL' if lang == 'en' else '原始会话 SQL', 11.5, '2,754,299.60', True),
        ('G7', '`Compile(I, p0)`', 11.5, '2,754,299.60 (published)', True),
        ('G7', 'draft $I\'$ dropping $\\varphi$' if lang == 'en' else '漏掉过滤 $\\varphi$ 的草稿 $I\'$', 33.5, '13,532,799.00 (rejected)', False),
    )
    for idx, (gt, lbl_txt, bar_w, val_txt, ok) in enumerate(rows_g):
        ry = y4 + 1.1 + idx * 2.55
        gbadge(0.8, ry, gt, ACC_DK if ok else RED, ACC_PALE if ok else RED_PALE)
        label(5.6, ry, lbl_txt, 4.9, INK if ok else RED, 'bold' if not ok else 'sans')
        bx0 = 24.5
        rect(bx0, ry - 0.85, bar_w, 1.7, ACC if ok else RED, None, r=.25)
        check_mark(bx0 + bar_w + 1.3, ry, ok, ACC if ok else RED)
        label(bx0 + bar_w + 2.4, ry, f'`{val_txt}`', 4.85, ACC_DK if ok else RED, 'bold' if not ok else 'sans')


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
