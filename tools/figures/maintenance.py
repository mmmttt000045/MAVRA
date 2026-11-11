"""Validity Maintenance & Snapshot-Bound Execution (Section IV-D/E), single column.

Three-part layout aligned with C3 and the C2-C3 linkage:
  (a) Two-stage write filtering (table version stamps V(T) + insert-batch
      delta checks on Delta T) and shared check outcomes in H.
  (b) Dual maintenance when conditions fail:
      - Left: C2 conditional equivalence edge ER ==_{R3} ER_r1 suspended and
        rewrite rolled back when premise P_{R3} breaks.
      - Right: Definition validity recovery via single-edit filter repair
        (i_is_current='Y' -> ER r2) or marking pending with diff when a
        probe-lifted assumption sees a new domain value.
  (c) Compact snapshot-bound execution timeline showing REPEATABLE READ
      snapshot s reading transactional stamp v_s, reusing H_tx(c, v_s), and
      running q(D_s) on the same snapshot.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from vecfig import PT  # noqa: E402
from style import ACC, ACC_DK, ACC_PALE, AMBER_PALE, EDGE, FACE, INK, MUTED, RED, RULE, WHITE  # noqa: E402
from smallparts import LEARN, LEARN_PALE, MAINT_C, RED_PALE, step  # noqa: E402

NAME = 'maintenance'
W, H = style.COLUMN, 55.6

OCHRE = '#9A6500'
TEAL_PALE = '#E4F5F2'


def baseline(yc, size):
    return yc + .34 * size * PT


def draw(s, lang):
    rect = s.rect
    text = s.text

    def label(x, yc, txt, size=5.0, color=INK, font='sans', align='left', width=None):
        return text(x, baseline(yc, size), txt, size, color, font, align, width=width)

    def check_mark(x, yc, ok, c=None):
        if ok:
            s.poly([(x - .55, yc), (x - .12, yc + .45), (x + .6, yc - .5)], None, c or ACC, .25, closed=False)
        else:
            s.line(x - .48, yc - .48, x + .48, yc + .48, c or RED, .25)
            s.line(x - .48, yc + .48, x + .48, yc - .48, c or RED, .25)

    # =========================================================================
    # Panel (a): Two-Stage Write Filtering & Shared Validation Table H
    # =========================================================================
    y1, h1 = 0.5, 20.6
    rect(0.6, y1, W - 1.2, h1, FACE, EDGE, .18, r=.55)
    rect(0.7, y1 + 0.1, W - 1.4, 2.9, ACC_DK, None, r=.45)
    step(s, 2.2, y1 + 1.55, 5, r=1.05)
    label(3.8, y1 + 1.55, '(a) Two-Stage Write Filtering & Shared Validation in $\\mathcal{H}$' if lang == 'en'
          else '(a) 两级写入筛选与共享验证表 $\\mathcal{H}$', 5.3, WHITE, 'bold')

    # Left box: Write Event & 2-Stage Filter
    wx, wy, ww, wh = 1.3, y1 + 3.5, 35.8, 16.3
    rect(wx, wy, ww, wh, WHITE, EDGE, .18, r=.45)
    rect(wx + 0.1, wy + 0.1, ww - 0.2, 2.5, ACC_PALE, None, r=.35)
    label(wx + 0.9, wy + 1.35, 'Write Event & 2-Stage Filter' if lang == 'en' else '写入事件与两级筛选', 4.9, ACC_DK, 'bold')

    label(wx + 0.9, wy + 4.1, 'Batch: $\\Delta\\mathrm{item}$, $V(\\mathrm{item}): 0\\rightarrow 1$' if lang == 'en'
          else '批次写入：$\\Delta\\mathrm{item}$，$V(\\mathrm{item}): 0\\rightarrow 1$', 4.7, INK, 'bold')
    s.line(wx + 0.7, wy + 5.5, wx + ww - 0.7, wy + 5.5, RULE, .14)

    # Stage 1
    rect(wx + 0.8, wy + 6.2, 10.8, 2.1, TEAL_PALE, LEARN, .15, r=.35)
    label(wx + 6.2, wy + 7.25, '1. Table stamp' if lang == 'en' else '1. 表版本筛选', 4.35, LEARN, 'bold', 'center')
    label(wx + 12.1, wy + 7.25, '`date_dim` ($V=0$) untouched' if lang == 'en' else '`date_dim` ($V=0$) 未变', 4.45, INK)
    label(wx + 1.0, wy + 9.7, '$\\rightarrow$ Skip checks; 3 defs reuse `Pass`' if lang == 'en'
          else '$\\rightarrow$ 免检，3 个定义直接复用通过结果', 4.5, LEARN, 'bold')

    # Stage 2
    rect(wx + 0.8, wy + 11.4, 10.8, 2.1, AMBER_PALE, OCHRE, .15, r=.35)
    label(wx + 6.2, wy + 12.45, '2. Batch $\\Delta T$' if lang == 'en' else '2. 批次增量 $\\Delta T$', 4.35, OCHRE, 'bold', 'center')
    label(wx + 12.1, wy + 12.45, 'Probe $\\Delta\\mathrm{item} \\bowtie \\mathrm{item}_{\\mathrm{old}}$' if lang == 'en'
          else '仅检验增量 $\\Delta\\mathrm{item} \\bowtie \\mathrm{item}_{\\mathrm{old}}$', 4.45, INK)
    label(wx + 1.0, wy + 14.9, '$\\rightarrow$ Dup `id=17` found (no full scan)' if lang == 'en'
          else '$\\rightarrow$ 免全表扫描定位重复键 `id=17`', 4.5, RED, 'bold')

    # Arrow from Filter to Shared Table H
    s.route([(wx + ww + 0.2, wy + 8.3), (wx + ww + 1.8, wy + 8.3)], ACC_DK, .22, heads='end')

    # Right box: Shared Outcomes Table H
    tx, ty, tw, th = 39.1, y1 + 3.5, 44.2, 16.3
    rect(tx, ty, tw, th, WHITE, ACC, .2, r=.45)
    rect(tx + 0.1, ty + 0.1, tw - 0.2, 2.5, ACC, None, r=.35)
    label(tx + 0.9, ty + 1.35, 'Shared Outcomes $\\mathcal{H}$' if lang == 'en' else '共享检查表 $\\mathcal{H}$', 4.9, WHITE, 'bold')
    label(tx + tw - 0.9, ty + 1.35, 'key: $(c, v(\\mathrm{dep}(c)))$' if lang == 'en' else '键：$(c, v(\\mathrm{dep}(c)))$', 4.3, WHITE, 'sans', 'right')

    # Columns in H
    c1, c2, c3 = tx + 0.9, tx + 18.8, tx + 26.2
    label(c1, ty + 3.9, 'Condition $c$' if lang == 'en' else '条件 $c$', 4.4, MUTED, 'bold')
    label(c2, ty + 3.9, 'Stamp' if lang == 'en' else '版本', 4.4, MUTED, 'bold')
    label(c3, ty + 3.9, 'Outcome & Scope' if lang == 'en' else '结果与影响范围', 4.4, MUTED, 'bold')
    s.line(tx + 0.6, ty + 5.0, tx + tw - 0.6, ty + 5.0, RULE, .14)

    # Row 1: date_dim key unique
    r1y = ty + 6.8
    rect(tx + 0.6, r1y - 1.25, tw - 1.2, 2.6, TEAL_PALE, None, r=.3)
    label(c1, r1y, '`date_dim` key unique' if lang == 'en' else '`date_dim` 键唯一', 4.5, INK)
    label(c2, r1y, '`d:0`', 4.5, INK)
    label(c3, r1y, 'Pass (reused by 3 defs)' if lang == 'en' else '通过（3个定义共享）', 4.5, LEARN, 'bold')

    # Row 2: date_dim contiguity P_R3
    r2y = ty + 10.3
    rect(tx + 0.6, r2y - 1.25, tw - 1.2, 2.6, LEARN_PALE, MAINT_C, .14, r=.3, dash=(.6, .35))
    label(c1, r2y, 'Premise $P_{\\mathrm{R3}}$ (contig.)' if lang == 'en' else '前提 $P_{\\mathrm{R3}}$（日期连续）', 4.5, INK)
    label(c2, r2y, '`d:1`', 4.5, INK)
    label(c3, r2y, 'Fail (hits C2 edge R3)' if lang == 'en' else '失败（触发 C2 边撤销）', 4.5, MAINT_C, 'bold')

    # Row 3: item key unique
    r3y = ty + 13.8
    rect(tx + 0.6, r3y - 1.25, tw - 1.2, 2.6, RED_PALE, RED, .14, r=.3, dash=(.6, .35))
    label(c1, r3y, '`item` key unique' if lang == 'en' else '`item` 键唯一', 4.5, INK)
    label(c2, r3y, '`i:1`', 4.5, INK)
    label(c3, r3y, 'Fail (`id=17` dup in $\\Delta$)' if lang == 'en' else '失败（$\\Delta$ 中 `id=17` 重复）', 4.5, RED, 'bold')

    # =========================================================================
    # Panel (b): Dual Maintenance — C2 Equivalence Premises & C3 Definitions
    # =========================================================================
    y2, h2 = y1 + h1 + 0.9, 18.8
    rect(0.6, y2, W - 1.2, h2, FACE, EDGE, .18, r=.55)
    rect(0.7, y2 + 0.1, W - 1.4, 2.9, ACC_PALE, None, r=.45)
    step(s, 2.2, y2 + 1.55, 6, r=1.05)
    label(3.8, y2 + 1.55, '(b) Dual Maintenance: Revoke Broken C2 Premises & Repair Definitions' if lang == 'en'
          else '(b) 双重维护：撤销失效的 C2 等价前提并修复定义版本', 5.3, INK, 'bold')

    # Left branch: C2 Equivalence Premise Maintenance
    bx1, by1, bw1, bh1 = 1.3, y2 + 3.5, 40.2, 14.5
    rect(bx1, by1, bw1, bh1, WHITE, MAINT_C, .2, r=.45)
    rect(bx1 + 0.1, by1 + 0.1, bw1 - 0.2, 2.5, LEARN_PALE, None, r=.35)
    label(bx1 + 0.9, by1 + 1.35, 'Branch 1: C2 Equivalence Premise $P_{\\mathrm{R3}}$ Fails' if lang == 'en'
          else '分支 1：C2 条件等价前提 $P_{\\mathrm{R3}}$ 失效', 4.8, MAINT_C, 'bold')

    label(bx1 + 0.9, by1 + 4.3, '1. Suspend edge $\\mathrm{ER} \\equiv_{\\mathrm{R3}}\\ \\mathrm{ER\\_r1}$ in graph $G$' if lang == 'en'
          else '1. 在关联图 $G$ 中挂起条件等价边 $\\mathrm{ER} \\equiv_{\\mathrm{R3}}\\ \\mathrm{ER\\_r1}$', 4.55, INK, 'bold')
    label(bx1 + 0.9, by1 + 6.9, '2. Roll back rewrite `ER_r1` $\\rightarrow$ `ER` (`date_dim` join)' if lang == 'en'
          else '2. 回滚改写版本 `ER_r1` $\\rightarrow$ `ER`（恢复 `date_dim` 连接）', 4.55, INK)
    label(bx1 + 0.9, by1 + 9.5, '3. Templates $\\Phi$ routed via edge revert to tentative' if lang == 'en'
          else '3. 经由该等价边绑定的请求模板 $\\Phi$ 退回待审计状态', 4.55, INK)
    rect(bx1 + 0.9, by1 + 11.2, bw1 - 1.8, 2.5, LEARN_PALE, None, r=.3)
    check_mark(bx1 + 2.1, by1 + 12.45, True, MAINT_C)
    label(bx1 + 3.2, by1 + 12.45, 'Prevents stale rewrite from serving wrong dates' if lang == 'en'
          else '防止因日期键断档导致改写查询漏算或错算', 4.45, MAINT_C, 'bold')

    # Right branch: C3 Definition Validity Maintenance
    bx2, by2, bw2, bh2 = 42.3, y2 + 3.5, 41.0, 14.5
    rect(bx2, by2, bw2, bh2, WHITE, LEARN, .2, r=.45)
    rect(bx2 + 0.1, by2 + 0.1, bw2 - 0.2, 2.5, TEAL_PALE, None, r=.35)
    label(bx2 + 0.9, by2 + 1.35, 'Branch 2: Definition Condition $C(\\mathrm{ER})$ Fails' if lang == 'en'
          else '分支 2：定义有效性条件 $C(\\mathrm{ER})$ 失效', 4.8, LEARN, 'bold')

    label(bx2 + 0.9, by2 + 4.3, '1. Single-edit repair: add filter `i_is_current=\'Y\'`' if lang == 'en'
          else '1. 单步修复：补充过滤条件 `i_is_current=\'Y\'`', 4.55, LEARN, 'bold')
    label(bx2 + 0.9, by2 + 6.9, '2. Re-check $C(\\mathrm{ER}^{r_2})$ at $v=1$ $\\rightarrow$ Pass $\\rightarrow$ publish $r_2$' if lang == 'en'
          else '2. 在 $v=1$ 上复核 $C(\\mathrm{ER}^{r_2})$ 通过 $\\rightarrow$ 发布版本 $r_2$', 4.55, INK)
    label(bx2 + 0.9, by2 + 9.5, '3. Probe domain shift / $>1$ edit $\\rightarrow$ `Pending` + diff' if lang == 'en'
          else '3. 若探针值域变化或需多步修改 $\\rightarrow$ 转 `Pending` 并附差异', 4.55, OCHRE, 'bold')
    rect(bx2 + 0.9, by2 + 11.2, bw2 - 1.8, 2.5, TEAL_PALE, None, r=.3)
    check_mark(bx2 + 2.1, by2 + 12.45, True, LEARN)
    label(bx2 + 3.2, by2 + 12.45, 'Preserves core grain/measure; blocks fan-out' if lang == 'en'
          else '保持核心粒度与度量不变，阻断静默连接扇出放大', 4.45, LEARN, 'bold')

    # =========================================================================
    # Panel (c): Snapshot-Bound Execution Timeline (H_tx)
    # =========================================================================
    y3, h3 = y2 + h2 + 0.9, 13.5
    rect(0.6, y3, W - 1.2, h3, FACE, EDGE, .18, r=.55)
    rect(0.7, y3 + 0.1, W - 1.4, 2.8, ACC_PALE, None, r=.45)
    step(s, 2.2, y3 + 1.5, 4, r=1.05)
    label(3.8, y3 + 1.5, '(c) Snapshot-Bound Execution: Check & Query Share Snapshot $D_s$' if lang == 'en'
          else '(c) 快照绑定执行：有效性检查与查询在同一事务快照 $D_s$ 内完成', 5.2, INK, 'bold')

    # Timeline boxes inside (c)
    ty_box = y3 + 3.5
    bh_t = 6.2
    # Step A
    s1x, s1w = 1.3, 24.4
    rect(s1x, ty_box, s1w, bh_t, WHITE, ACC, .18, r=.4)
    label(s1x + 0.8, ty_box + 1.8, '1. `REPEATABLE READ` $s$' if lang == 'en' else '1. 开启可重复读事务 $s$', 4.55, ACC_DK, 'bold')
    label(s1x + 0.8, ty_box + 4.3, 'Read stamp $v_s(\\mathrm{item})=1$' if lang == 'en' else '读取快照版本 $v_s(\\mathrm{item})=1$', 4.45, INK)

    s.route([(s1x + s1w + 0.2, ty_box + 3.1), (s1x + s1w + 1.9, ty_box + 3.1)], ACC_DK, .2, heads='end')

    # Step B
    s2x, s2w = s1x + s1w + 2.1, 27.6
    rect(s2x, ty_box, s2w, bh_t, WHITE, LEARN, .18, r=.4)
    label(s2x + 0.8, ty_box + 1.8, '2. Verify via $\\mathcal{H}_{\\mathrm{tx}}(c, v_s)$' if lang == 'en' else '2. 查验版本绑定缓存 $\\mathcal{H}_{\\mathrm{tx}}(c, v_s)$', 4.55, LEARN, 'bold')
    label(s2x + 0.8, ty_box + 4.3, '`ER` $r_2$ valid at $v_s=1$ (reuse)' if lang == 'en' else '`ER` $r_2$ 在 $v_s=1$ 有效（直接复用）', 4.45, INK)

    s.route([(s2x + s2w + 0.2, ty_box + 3.1), (s2x + s2w + 1.9, ty_box + 3.1)], LEARN, .2, heads='end')

    # Step C
    s3x, s3w = s2x + s2w + 2.1, 25.8
    rect(s3x, ty_box, s3w, bh_t, TEAL_PALE, LEARN, .2, r=.4)
    label(s3x + 0.8, ty_box + 1.8, '3. Run $q(\\mathrm{ER}^{r_2}, p)$ on $D_s$' if lang == 'en' else '3. 在同一快照 $D_s$ 执行 $q(\\mathrm{ER}^{r_2}, p)$', 4.55, LEARN, 'bold')
    label(s3x + 0.8, ty_box + 4.3, 'Return `$142.8k` & `COMMIT`' if lang == 'en' else '返回 `$142.8k` 并提交事务', 4.45, INK, 'bold')

    # Bottom note in (c) showing concurrent commit isolation
    check_mark(2.2, y3 + 11.4, True, ACC_DK)
    label(3.3, y3 + 11.4, 'Concurrent commit ($v=2$) during step 2/3 cannot cause $q$ to read unverified rows or stale $v=0$ verdicts.' if lang == 'en'
          else '执行期间即使并发写入提交 ($v=2$)，快照隔离与版本键 $v_s$ 保证查询绝不读取未验证的新行或过期的 $v=0$ 结论。', 4.5, ACC_DK, 'bold')
