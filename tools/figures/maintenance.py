"""Dependency-aware maintenance and repair (Section IV-D), single column.

The item-history load of Fig. 2 (step 5) changes item's version. Check
outcomes are stored under their check and the versions of the tables the check
reads, so the item key check misses at item version 1 and runs once, while the
outcomes on unchanged tables are reused; definitions that read no item table
stay valid without any check. Repair then tests equality filters on item's
low-cardinality columns and adopts one only if exactly one restores one row
per key without losing keys, and regression on the learning snapshot
reproduces the verified answer (step 6).

Case and values follow Fig. 2 and the TPC-DS fixture: item history rows carry
i_is_current = 'N' and keep the category, the repair filter is
i_is_current = 'Y', the learning answer is 2,754,299.60. Which definitions use
which outcome is schematic, as in Fig. 2 (three definitions share the date_dim
key check).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402
from style import ACC, ACC_DK, ACC_PALE, AMBER_PALE, EDGE, INK, MUTED, RED, RULE, SIDE, WHITE  # noqa: E402
from smallparts import (CODE, MAINT_C, NOTE, OCHRE, SMALL, THICK, THIN, TITLE, USE,  # noqa: E402
                        Kit, baseline)

NAME = 'maintenance'
W, H = style.COLUMN, 51.2
VERIFIED = '2,754,299.60'

LABELS = {
    'en': {
        'etl': 'ETL job', 'etl_note': 'loads item history', 'batch': r'batch 0 $\rightarrow$ 1',
        'item_note': 'key 17 gets a history row', 'only': (('only checks that',), ('read', '`item`', 'run again')),
        'shared': 'Shared knowledge', 'shared_note': 'check outcomes are keyed by table versions',
        'defs': (('E', 'Electronics revenue', ('pending', 6)),
                 ('S', 'Store revenue', 'valid, no check'),
                 ('F', '`spend_90d`', 'valid, no check')),
        'cols': ('check', 'table versions', 'outcome', 'used by'),
        'checks': ('date key unique', 'sales grain unique', 'item key unique', 'item key unique'),
        'pass': 'pass', 'fail': 'fail', 'reused': 'reused', 'once': 'ran once', 'old': 'old version',
        'repair': 'Repair', 'failed': 'item key unique', 'repeats': 'fails: key 17 repeats',
        'search': 'one filter must restore one row per key',
        'cands': (("`i_is_current = 'Y'`", 'one row per key, no key lost', True),
                  ("`i_is_current = 'N'`", 'loses keys', False),
                  ("`i_category = 'Electronics'`", 'key 17 still repeats', False)),
        'result': ('exactly one passes', 'regression test', 'publish rev 1'),
        'else': 'else invalidate', 'rev1': 'rev 1',
    },
    'zh': {
        'etl': 'ETL 作业', 'etl_note': '载入 item 历史', 'batch': r'batch 0 $\rightarrow$ 1',
        'item_note': '键 17 多出一条历史行', 'only': (('只重跑读取',), ('`item`', '的检查')),
        'shared': '共享知识', 'shared_note': '检查结果按表版本存放',
        'defs': (('E', '电子品类营业额', ('待校验', 6)),
                 ('S', '门店营业额', '有效，无需检查'),
                 ('F', '`spend_90d`', '有效，无需检查')),
        'cols': ('检查', '表版本', '结果', '使用者'),
        'checks': ('日期键唯一', '销售粒度唯一', 'item 键唯一', 'item 键唯一'),
        'pass': '通过', 'fail': '失败', 'reused': '复用', 'once': '只跑一次', 'old': '旧版本',
        'repair': '自动修复', 'failed': 'item 键唯一', 'repeats': '不通过：键 17 重复',
        'search': '须恰有一个过滤使每键一行',
        'cands': (("`i_is_current = 'Y'`", '每键一行，不丢键', True),
                  ("`i_is_current = 'N'`", '丢失键', False),
                  ("`i_category = '电子'`", '键 17 仍重复', False)),
        'result': ('恰有一个通过', '回归测试', '发布修订 1'),
        'else': '否则置为失效', 'rev1': '修订 1',
    },
}

DEF_C = {'E': MAINT_C, 'S': USE, 'F': USE}
FLOOR, LETTER = 5.6, 5.6           # smallest label size (5.9 pt printed); letter pills


def draw(s, lang):
    L = LABELS[lang]
    k = Kit(s)
    text = s.text

    # Step 5: the ETL job changes item's version -----------------------------------
    tx, ty, tw, th = 1.0, 2.6, 21.0, 6.0
    k.stack(tx, ty, tw, th)
    text(tx + 1.2, ty + 2.6, L['etl'], SMALL + .2, INK, 'bold')
    text(tx + 1.2, ty + 5.0, L['etl_note'], NOTE - .3, OCHRE, width=tw - 2.4)
    ix, iw = 30.5, 27.0
    ay = ty + th / 2 + .6
    s.route([(tx + tw - 1.0, ay), (ix, ay)], MAINT_C, THIN, length=.9)
    k.step((tx + tw - 1.0 + ix) / 2, ay - 2.4, 5, r=1.3)
    k.box(ix, ty - .4, iw, th + .4, WHITE, OCHRE, .16, r=.4)
    s.rect(ix + .15, ty - .25, iw - .3, 2.5, AMBER_PALE, None, r=.3)
    text(ix + .9, ty + 1.5, '`item`', CODE, INK)
    k.rich(ix + iw - .9, ty + 1.0, L['batch'], NOTE - .3, OCHRE, 'bold', align='right')
    text(ix + .9, ty + 4.6, L['item_note'], NOTE - .3, OCHRE, width=iw - 1.8)
    ox = ix + iw + 2.4
    for j, line in enumerate(L['only']):
        k.rich(ox, ty + 1.4 + 2.8 * j, line, SMALL - .3, MAINT_C, 'bold', width=83.6 - ox)

    # Shared knowledge: definitions and check outcomes ---------------------------------
    fx, fy, fw, fh = 1.0, 11.4, 81.8, 20.6
    s.rect(fx + .8, fy + .8, fw, fh, SIDE, EDGE, .12, r=.6)
    k.box(fx, fy, fw, fh)
    k.header(fx, fy, fw, L['shared'], ACC, note=L['shared_note'], size=SMALL)

    # Definitions, each with the letter used in the "used by" column.
    cx, cw, ch, cg = fx + 1.0, 22.4, 4.9, .7
    for i, (letter, name, status) in enumerate(L['defs']):
        cy = fy + 3.8 + i * (ch + cg)
        hot = letter == 'E'
        k.box(cx, cy, cw, ch, ACC_PALE if hot else WHITE, MAINT_C if hot else EDGE, .16 if hot else .12, r=.4)
        k.pill(cx + .7, cy + 1.6, letter, DEF_C[letter], w=2.4, size=LETTER, h=2.0)
        text(cx + 3.7, baseline(cy + 1.6, SMALL - .5), name, SMALL - .5, INK, 'bold', width=cw - 4.2)
        k.rich(cx + 3.7, cy + 3.6, status, FLOOR, MAINT_C if hot else ACC_DK, width=cw - 4.2)

    # The outcome table: check, table versions, outcome (mark and tag), used by.
    tx0 = cx + cw + 1.8
    tw0 = fx + fw - 1.0 - tx0
    col = (tx0 + .8, tx0 + 17.6, tx0 + 31.6, fx + fw - 1.4 - 8.4)
    hy = fy + 4.7
    for x, label in zip(col, L['cols']):
        text(x, baseline(hy, FLOOR), label, FLOOR, MUTED)
    s.line(tx0, hy + 1.3, tx0 + tw0, hy + 1.3, RULE, .14)
    rows = (('`date_dim 0`', 'ok', 'reused', 'ESF'),
            ('`store_sales 0`', 'ok', 'reused', 'ES'),
            ('`item 0`', 'ok', 'old', ''),
            ('`item 1`', 'fail', 'once', 'E'))
    pitch = 3.35
    for i, (check, (versions, outcome, tag, users)) in enumerate(zip(L['checks'], rows)):
        yc = hy + 1.3 + pitch * i + pitch / 2
        old = tag == 'old'
        if tag == 'once':
            s.rect(tx0, yc - pitch / 2 + .2, tw0, pitch - .4, '#FBEDEB', None, r=.3)
        ink = MUTED if old else INK
        text(col[0], baseline(yc, SMALL - .5), check, SMALL - .5, ink, width=col[1] - col[0] - .6)
        text(col[1], baseline(yc, CODE - .1), versions, CODE - .1, OCHRE if tag == 'once' else ink,
             width=col[2] - col[1] - .6)
        k.mark(col[2] + 1.3, yc, outcome, MUTED if old else (RED if outcome == 'fail' else ACC), .9)
        if old:
            tgw = text(col[3] - 1.0, baseline(yc, FLOOR), L['old'], FLOOR, MUTED, align='right')
        else:
            tgw = k.tag(col[3] - 1.0, yc, L[tag], {'reused': ACC, 'once': MAINT_C}[tag], align='right',
                        size=FLOOR)
        assert col[2] + 2.0 < col[3] - 1.0 - tgw, (check, tgw)
        for j, letter in enumerate(users):
            k.pill(col[3] + j * 3.0, yc, letter, DEF_C[letter], w=2.4, size=LETTER, h=2.0)
    assert hy + 1.3 + pitch * len(rows) < fy + fh - .4

    # Step 6: repair the failed check -----------------------------------------------
    ry = fy + fh + 2.9
    rh = H - .8 - ry
    k.box(1.0, ry, 82.6, rh, WHITE, MAINT_C, .18, r=.5)
    lx = 2.2
    text(lx, ry + 3.4, L['repair'], TITLE - .2, INK, 'bold')
    k.step(lx + 17.6, ry + 2.5, 6, r=1.3)
    text(lx, ry + 6.4, L['failed'], SMALL - .4, INK)
    text(lx, ry + 8.9, L['repeats'], SMALL - .4, RED)
    text(lx, ry + rh - 1.6, L['else'], FLOOR, MUTED)
    vx = 22.6
    s.line(vx - 1.0, ry + 1.2, vx - 1.0, ry + rh - 1.2, RULE, .14)
    text(vx, ry + 2.9, L['search'], SMALL - .5, MAINT_C, 'bold')
    for i, (filt, result, ok) in enumerate(L['cands']):
        yy = ry + 5.7 + 2.45 * i
        fw_ = text(vx, yy, filt, CODE, ACC_DK if ok else INK)
        text(vx + 28.4, yy, result, SMALL - .6, ACC_DK if ok else MUTED, width=82.6 - vx - 28.4 - 2.6)
        k.mark(81.6, yy - .7, 'ok' if ok else 'fail', ACC if ok else RED, .85)
        assert fw_ < 28.0, filt
    ly = ry + 5.7 + 2.45 * 2 + 1.4
    s.line(vx, ly, 82.6, ly, RULE, .14)
    yy = ly + 2.6
    xx = vx
    for j, part in enumerate(L['result']):
        if j:
            xx += .9 + text(xx + .9, yy, r'$\rightarrow$', SMALL - .5, MUTED) + .9
        if j == 1:
            k.mark(xx + .6, yy - .7, 'ok', ACC, .85)
            xx += 1.6
        xx += text(xx, yy, part, SMALL - .5, ACC_DK if j == 2 else INK, 'bold' if j == 2 else 'sans')
    assert xx < 82.6, xx
    assert yy + .8 < ry + rh, (yy, ry + rh)
    # Repair publishes revision 1 of the metric (thick: writes shared state).
    ex = cx + 6.0
    s.route([(ex, ry), (ex, fy + fh)], MAINT_C, THICK, length=1.0)
    text(ex + 1.2, baseline((ry + fy + fh) / 2, FLOOR), L['rev1'], FLOOR, MAINT_C, 'bold')


if __name__ == '__main__':
    for path in style.build(sys.modules[__name__]):
        print(path)
