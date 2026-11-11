"""Accurate and efficient lookup (Figure 4): monthly row-contribution fingerprint in G and online admission.

Single column (84.6 mm wide). Organized into two layers:
  (a) Offline / Post-hoc Evidence & Monthly Row-Contribution Fingerprint (Graph G):
      Illustrates the 3-row store_sales example (tickets 101, 102, 103) and three
      revenue definitions X (sales only), Y (INNER JOIN store, drops 102B in 02-09),
      and Z (INNER JOIN item, drops 0 rows).
      Shows fp(m, ym) = SUM(hash(K, ym, e)):
        - X and Z match in every month -> same computation (certified X ==_P Z)
        - X and Y differ in 2002-09 (missing h(102B,09,30)) -> distinct definitions
          with contrast delta={join store}, yet identical in 2002-10!
  (b) Online Constraint-Explaining Admission (Step 3):
      Resolves 4 cases without generating SQL upfront:
        1. Grounded hit (Res = empty, P holds) -> Bind & reuse
        2. Contrast / Partial hit (Res != empty) -> Partial hit + local completion
        3. Indifference test on surviving S={X,Y}: 2002-10 fingerprints match ->
           return immediately without asking; 2002-09 differs -> ask 1 question on delta
        4. Tentative similarity hit -> Stratified audit gate U_g(t) <= alpha with
           3-way label (equiv / distinct / unprovable)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import PT, measure  # noqa: E402
from style import ACC, ACC_DK, ACC_PALE, AMBER_PALE, EDGE, FACE, INK, MUTED, RED, RULE, WHITE  # noqa: E402
from smallparts import LEARN, LEARN_PALE, MAINT_C, RED_PALE, step  # noqa: E402

NAME = 'lookup'
W, H = style.COLUMN, 62.0

OCHRE = '#9A6500'
TEAL_PALE = '#E4F5F2'


def baseline(yc, size):
    return yc + .34 * size * PT


def draw(s, lang):
    text, rect = s.text, s.rect

    def label(x, yc, txt, size=5.2, color=INK, wt='sans', align='left', width=None):
        return text(x, baseline(yc, size), txt, size, color, wt, align, width)

    def check_mark(x, yc, ok, c=None):
        if ok:
            s.poly([(x - .55, yc), (x - .12, yc + .45), (x + .6, yc - .5)], None, c or ACC, .25, closed=False)
        else:
            s.line(x - .48, yc - .48, x + .48, yc + .48, c or RED, .25)
            s.line(x - .48, yc + .48, x + .48, yc - .48, c or RED, .25)

    def tag_pill(x, yc, txt, col, fill):
        w = measure(txt, 4.6, 'bold') + 1.1
        rect(x, yc - 0.9, w, 1.8, fill, col, .14, r=.28)
        label(x + w / 2, yc, txt, 4.6, col, 'bold', 'center')
        return w

    # =========================================================================
    # Top Panel (a): Monthly Row-Contribution Fingerprint & Graph G
    # =========================================================================
    y1, h1 = 0.5, 29.2
    rect(0.6, y1, W - 1.2, h1, WHITE, EDGE, .18, r=.55)
    rect(0.7, y1 + 0.1, W - 1.4, 2.8, ACC, None, r=.45)
    rect(0.7, y1 + 1.5, W - 1.4, 1.4, ACC, None)
    label(1.5, y1 + 1.5,
          '(a) Monthly Row-Contribution Fingerprint & Evidence Graph $G$' if lang == 'en'
          else '(a) 按月行级贡献指纹与事后证据关联图 $G$',
          5.4, WHITE, 'bold')
    label(W - 1.4, y1 + 1.5,
          '`fp = SUM(hash(K, ym, e))`' if lang == 'en' else 'fp = SUM(hash(粒度键, 月份, 数值))',
          4.7, WHITE, 'sans', 'right')

    # --- Left sub-box: 3-row store_sales table + 3 definitions (X, Y, Z) ---
    tx, ty, tw, th = 1.3, y1 + 3.4, 30.2, 11.4
    rect(tx, ty, tw, th, WHITE, EDGE, .15, r=.35)
    rect(tx + .1, ty + .1, tw - .2, 2.0, FACE, None, r=.25)
    label(tx + 0.7, ty + 1.1,
          '`store_sales` (grain $K$: ticket+item)' if lang == 'en' else '销售表 `store_sales` ($K$: 小票+商品)',
          4.65, INK, 'bold')

    # Table header
    hy = ty + 3.05
    cols = [(tx + 0.7, 'K (tkt,item)'), (tx + 10.6, 'ym ($\\tau$)'), (tx + 17.8, 'store'), (tx + 24.0, 'paid ($e$)')]
    for cx, ctitle in cols:
        label(cx, hy, ctitle, 4.4, MUTED, 'bold')
    s.line(tx + 0.5, hy + 1.0, tx + tw - 0.5, hy + 1.0, RULE, .14)

    rows = [
        ('`101, A`', '`02-09`', '`S1`', '`50`', False),
        ('`102, B`', '`02-09`', '`NULL`', '`30`', True),
        ('`103, A`', '`02-10`', '`S2`', '`20`', False),
    ]
    for r_i, (rk, rym, rst, rval, is_null) in enumerate(rows):
        ry = hy + 2.25 + r_i * 2.15
        if is_null:
            rect(tx + 0.4, ry - 0.9, tw - 0.8, 1.85, AMBER_PALE, None, r=.2)
        label(tx + 0.7, ry, rk, 4.5, INK)
        label(tx + 10.6, ry, rym, 4.5, INK)
        label(tx + 17.8, ry, rst, 4.5, RED if is_null else INK, 'bold' if is_null else 'sans')
        label(tx + 24.5, ry, rval, 4.5, INK)

    # --- Right sub-box: Three definitions X, Y, Z and their SQL joins ---
    dx, dy, dw, dh = 32.2, y1 + 3.4, W - 33.5, 11.4
    rect(dx, dy, dw, dh, FACE, EDGE, .15, r=.35)
    rect(dx + .1, dy + .1, dw - .2, 2.0, ACC_PALE, None, r=.25)
    label(dx + 0.8, dy + 1.1,
          'Three definitions of "revenue" (`SUM(paid)`)' if lang == 'en'
          else '三条“营业额”定义（均对净支付额求和，连接不同）',
          4.65, ACC_DK, 'bold')

    defs_info = [
        ('`X`:', '`FROM store_sales` (no dim join)',
         'keeps all 3 rows' if lang == 'en' else '保留全部 3 行', ACC_DK),
        ('`Y`:', '`JOIN store` (inner join on `store`)',
         'drops `102B` (`store=NULL`)' if lang == 'en' else '丢掉 `102B`（门店为空）', OCHRE),
        ('`Z`:', '`JOIN item` (inner join on `item`)',
         'every row has item (0 lost)' if lang == 'en' else '每行都有商品（0 丢失）', ACC_DK),
    ]
    for d_i, (d_tag, d_sql, d_note, d_col) in enumerate(defs_info):
        ry = dy + 3.45 + d_i * 2.75
        label(dx + 0.8, ry, d_tag, 4.7, d_col, 'bold')
        label(dx + 4.5, ry, d_sql, 4.5, INK)
        label(dx + dw - 0.8, ry, d_note, 4.45, d_col, 'bold', 'right')

    # --- Middle table inside Panel (a): Monthly Fingerprint Matrix ---
    fy, fh = y1 + 15.4, 10.6
    fx, fw = 1.3, W - 2.6
    rect(fx, fy, fw, fh, WHITE, ACC, .16, r=.35)
    rect(fx + .1, fy + .1, fw - .2, 2.05, ACC_PALE, None, r=.25)
    label(fx + 0.8, fy + 1.1, 'Def', 4.6, ACC_DK, 'bold')
    label(fx + 6.5, fy + 1.1,
          '`2002-09` Fingerprint' if lang == 'en' else '`2002-09` 月度指纹',
          4.6, ACC_DK, 'bold')
    label(fx + 43.5, fy + 1.1,
          '`2002-10` Fingerprint' if lang == 'en' else '`2002-10` 月度指纹',
          4.6, ACC_DK, 'bold')
    label(fx + fw - 0.8, fy + 1.1,
          'Relation in Graph $G$' if lang == 'en' else '关联图 $G$ 中的判定结论',
          4.6, ACC_DK, 'bold', 'right')

    fp_rows = [
        ('`X`', '$h(\\mathtt{101A},09,50) + h(\\mathtt{102B},09,30)$', '$h(\\mathtt{103A},10,20)$',
         'Base definition' if lang == 'en' else '基准定义', INK, None),
        ('`Z`', '$h(\\mathtt{101A},09,50) + h(\\mathtt{102B},09,30)$', '$h(\\mathtt{103A},10,20)$',
         'All months $=$ $\\rightarrow$ `X` $\\equiv_P$ `Z` (R2)' if lang == 'en' else '各月全同 $\\rightarrow$ `X` $\\equiv_P$ `Z`',
         ACC_DK, ACC_PALE),
        ('`Y`', '$h(\\mathtt{101A},09,50)$  (missing `102B`!)', '$h(\\mathtt{103A},10,20)$',
         '09 $\\neq$, 10 $=$ $\\rightarrow$ $\\delta=\\{\\mathcal{J}_{\\mathrm{store}}\\}$' if lang == 'en' else '9月不同、10月同 $\\rightarrow$ 差异边 $\\delta$',
         OCHRE, AMBER_PALE),
    ]
    for f_i, (f_def, fp_09, fp_10, fp_rel, f_col, f_bg) in enumerate(fp_rows):
        ry = fy + 3.35 + f_i * 2.55
        if f_bg:
            rect(fx + 0.4, ry - 0.95, fw - 0.8, 2.05, f_bg, None, r=.2)
        label(fx + 0.9, ry, f_def, 4.7, f_col, 'bold')
        label(fx + 6.5, ry, fp_09, 4.5, RED if 'missing' in fp_09 else INK, 'bold' if 'missing' in fp_09 else 'sans')
        label(fx + 43.5, ry, fp_10, 4.5, ACC_DK if f_i > 0 else INK, 'bold' if f_i > 0 else 'sans')
        label(fx + fw - 0.8, ry, fp_rel, 4.5, f_col, 'bold', 'right')

    # Bottom note inside Panel (a): Order-independent + Incremental on Delta T
    ny = fy + fh + 1.55
    check_mark(2.2, ny, True, ACC)
    label(3.3, ny,
          'Order-independent & incremental on $\\Delta T$ (93 defs / 2.88M rows: 3.9 s; $+6$k rows: 0.24 s)'
          if lang == 'en' else
          '加法求和与行序无关，追加批次 $\\Delta T$ 仅算新行累加（288万行93定义 3.9s；+6千行更新 0.24s）',
          4.5, INK, 'bold')

    # =========================================================================
    # Bottom Panel (b): Online Request Admission (Step 3)
    # =========================================================================
    y2, h2 = y1 + h1 + 0.8, 30.8
    rect(0.6, y2, W - 1.2, h2, FACE, EDGE, .18, r=.55)
    rect(0.7, y2 + 0.1, W - 1.4, 2.75, ACC_PALE, None, r=.45)
    step(s, 2.2, y2 + 1.48, 3, r=1.05)
    label(3.8, y2 + 1.48,
          '(b) Online Constraint-Explaining Admission (No Upfront SQL Generation)' if lang == 'en'
          else '(b) 在线约束解释准入（无需预先为新请求生成完整 SQL）',
          5.35, INK, 'bold')

    # Legend bar for constraint tags
    ly_leg = y2 + 4.05
    rect(1.3, ly_leg - 1.05, W - 2.6, 2.1, WHITE, RULE, .14, r=.28)
    lx_cur = 1.9
    for c_col, c_fill, c_txt in (
        (ACC_DK, ACC_PALE, 'grounded $\\Phi$' if lang == 'en' else '核验模板 $\\Phi$'),
        (LEARN, LEARN_PALE, 'param $p$' if lang == 'en' else '参数 $p$'),
        (MAINT_C, TEAL_PALE, 'derivation $d$' if lang == 'en' else '派生 $d$'),
        (OCHRE, AMBER_PALE, 'contrast $\\delta$' if lang == 'en' else '差异 $\\delta$'),
        (RED, RED_PALE, 'residue $\\mathrm{Res}$' if lang == 'en' else '未解释残余 $\\mathrm{Res}$'),
    ):
        w_t = tag_pill(lx_cur, ly_leg, c_txt, c_col, c_fill)
        lx_cur += w_t + 1.45

    cases = (
        ('Case 1: Grounded hit or certified equivalent (`X` $\\equiv_P$ `Z`)' if lang == 'en'
         else '情形 1：核验模板命中或经由条件等价边复用（`X` $\\equiv_P$ `Z`）',
         '"`highest month` [d] of `turnover` [$\\Phi$] `in 2002` [p]"',
         '$\\mathrm{Res}=\\emptyset$, $P$ holds $\\rightarrow$ Bind $(p,d)$ & reuse `X` directly' if lang == 'en'
         else '$\\mathrm{Res}=\\emptyset$ 且前提 $P$ 成立 $\\rightarrow$ 直接绑定 $(p,d)$ 复用 `X`',
         ACC_DK, ACC_PALE, True),
        ('Case 2: Unexplained modifier $\\rightarrow$ Partial hit' if lang == 'en'
         else '情形 2：存在未解释修饰词 $\\rightarrow$ 拒绝直接复用并转为部分命中',
         '"`revenue` [$\\Phi$] `net of returns` [Res] `in Sep.` [p]"',
         '$\\mathrm{Res}=\\{\\text{net of returns}\\}\\neq\\emptyset \\rightarrow$ Partial hit (`X` + complete anti-join)' if lang == 'en'
         else '$\\mathrm{Res}\\neq\\emptyset \\rightarrow$ 部分命中（传入 `X` 仅补全退货反连接）',
         RED, RED_PALE, False),
        ('Case 3: Underspecified request ($S=\\{\\mathrm{X},\\mathrm{Y}\\}$) $\\rightarrow$ Period fingerprint check' if lang == 'en'
         else '情形 3：未指明门店差异（候选 $S=\\{\\mathrm{X},\\mathrm{Y}\\}$）$\\rightarrow$ 查当期指纹判同值',
         'Ask `2002-10`: $\\mathrm{fp}(\\mathrm{X},10)=\\mathrm{fp}(\\mathrm{Y},10)$ | Ask `2002-09`: $\\mathrm{fp}(\\mathrm{X},09)\\neq\\mathrm{fp}(\\mathrm{Y},09)$',
         '`2002-10` agrees $\\rightarrow$ return `20` without asking; `2002-09` differs $\\rightarrow$ ask 1 question on $\\delta$' if lang == 'en'
         else '问 10 月指纹相同免问直接返回 `20`；问 9 月指纹不同仅就门店差异 $\\delta$ 追问 1 次',
         OCHRE, AMBER_PALE, True),
        ('Case 4: Tentative similarity match $\\rightarrow$ 3-way audited risk bound' if lang == 'en'
         else '情形 4：待审相似匹配 $\\rightarrow$ 三值审计标签与分层误命中率上界',
         'Unverified phrasing in stratum $g$: gate by confidence sequence $U_g(t) \\leq \\alpha$',
         'If $U_g(t)\\leq\\alpha$: serve; else audit & label (*equiv* / *distinct* / *unprovable*)' if lang == 'en'
         else '$U_g(t)\\leq\\alpha$ 则放行；否则探索并打三值标签（等价 / 不同 / 无法判定）',
         LEARN, LEARN_PALE, True),
    )

    cy_start = ly_leg + 1.65
    ch_case = 5.6
    for idx, (head_c, req_c, out_c, col_c, fill_c, is_ok) in enumerate(cases):
        yc_box = cy_start + idx * (ch_case + 0.58)
        rect(1.3, yc_box, W - 2.6, ch_case, WHITE, col_c, .15, r=.38)
        rect(1.4, yc_box + 0.1, W - 2.8, 1.78, fill_c, None, r=.28)
        label(2.0, yc_box + 0.95, head_c, 4.75, col_c, 'bold')
        label(2.0, yc_box + 2.82, req_c, 4.65, INK, width=W - 4.0)
        out_clean = out_c.replace('**', '').replace('*', '')
        check_mark(2.4, yc_box + 4.55, is_ok, col_c)
        label(3.5, yc_box + 4.55, out_clean, 4.65, col_c if not is_ok else INK, 'bold', width=W - 5.4)

    assert y2 + h2 <= H - 0.2, y2 + h2


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
