"""Shared look of the single-column technique figures in Section IV
(extraction, maintenance, snapshot).

Each figure draws what the system stores and how one operation walks through
it, with the running example's real keys, version stamps and statistics:
stored structures are tables with a title band (catalog entries pale blue,
the outcome stores H and H_tx solid blue, database tables grey), and the
access path carries tags L<n> for line n of Algorithm 1 or 2. They borrow
Fig. 2's visual vocabulary so a reader can map them back to the overview:
step badges in Fig. 2's path colours (learning 1-2 purple, execution 4
orange, data change and maintenance 5-6 teal), the LLM mark, JSON field names
in ochre. Outcomes carry two colours: red for a wrong or stale result, blue
for MAVRA's result, with a filled badge for the final verdict.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vecfig import PT, measure  # noqa: E402
from style import ACC, ACC_DK, ACC_PALE, EDGE, FIELD, MUTED, RED, WHITE  # noqa: E402

# Drawn 84.6 mm wide and scaled to the 88.8 mm IEEEtran column (x1.05).
LABEL, BODY, CODE, SMALL = 6.4, 6.0, 5.75, 5.7      # printed 6.7, 6.3, 6.0, 6.0 pt
LINE = .18
BLUE, BLUE_TXT, BLUE_PALE, BLUE_FIELD = ACC, ACC_DK, ACC_PALE, FIELD
RED_PALE = '#FBE9E5'
LEARN, LEARN_PALE = '#7A68B0', '#EFECF7'             # Fig. 2 path colours
EXEC_C, MAINT_C = '#C97A1E', '#13897B'
KEYC = '#8A5A00'                                     # JSON field names, as in Fig. 2
BAND = '#ECEAE5'
STEP_C = {1: LEARN, 2: LEARN, 3: ACC, 4: EXEC_C, 5: MAINT_C, 6: MAINT_C}


def baseline(y_center, size):
    """Baseline that centres capitals and digits on y_center."""
    return y_center + .34 * size * PT


def box(s, x, y, w, h, edge=EDGE, fill=WHITE, dash=None, sw=LINE):
    s.rect(x, y, w, h, fill, edge, sw, r=.5, dash=dash)


def card(s, x, y, w, h, band_h, band=BAND, edge=EDGE, fill=WHITE, sw=LINE):
    """A box with a tinted title band across its top."""
    s.rect(x, y, w, h, fill, edge, sw, r=.5)
    i = sw / 2 + .05
    s.rect(x + i, y + i, w - 2 * i, band_h, band, None, r=.4)
    s.rect(x + i, y + i + band_h / 2, w - 2 * i, band_h / 2, band, None)


def arrow(s, points, color=MUTED, sw=LINE):
    s.route(points, color, sw, length=.9, radius=.6)


def mark(s, x, yc, ok, k=.9):
    """A thin check (blue) or cross (red) centred on (x, yc), for an intermediate result."""
    if ok:
        s.poly([(x - .62 * k, yc), (x - .15 * k, yc + .5 * k), (x + .65 * k, yc - .55 * k)], None,
               BLUE, .26, closed=False)
    else:
        s.line(x - .5 * k, yc - .5 * k, x + .5 * k, yc + .5 * k, RED, .26)
        s.line(x - .5 * k, yc + .5 * k, x + .5 * k, yc - .5 * k, RED, .26)


def verdict(s, x, yc, ok, r=1.05):
    """The final verdict: a white check on a blue disc or a white cross on a red one."""
    s.circle(x, yc, r, BLUE if ok else RED)
    k = .5 * r
    if ok:
        s.poly([(x - 1.05 * k, yc + .05 * k), (x - .25 * k, yc + .8 * k), (x + 1.05 * k, yc - .8 * k)],
               None, WHITE, .3, closed=False)
    else:
        s.line(x - .75 * k, yc - .75 * k, x + .75 * k, yc + .75 * k, WHITE, .3)
        s.line(x - .75 * k, yc + .75 * k, x + .75 * k, yc - .75 * k, WHITE, .3)


def step(s, x, yc, n, r=1.25):
    """A step badge of Fig. 2, in the colour of that step's path."""
    s.circle(x, yc, r, STEP_C[n])
    s.text(x, baseline(yc, 5.6), str(n), 5.6, WHITE, 'bold', 'center')


def person(s, x, yc, color=EDGE):
    """Head and shoulders, about 2.2 x 2.9 mm, centred on (x, yc)."""
    s.circle(x, yc - .7, .72, color)
    s.rect(x - 1.1, yc + .18, 2.2, 1.25, color, None, r=.62)


def sparkle(s, x, y, r, color):
    """Four-pointed star, the usual mark for an LLM."""
    k = .28 * r
    s.poly([(x, y - r), (x + k, y - k), (x + r, y), (x + k, y + k), (x, y + r),
            (x - k, y + k), (x - r, y), (x - k, y - k)], color, None)


def parts(s, x, y, items, size):
    """Draw (text, colour) pieces one after another on a baseline; returns the end x."""
    for item in items:
        label, color = item[:2]
        x += s.text(x, y, label, size, color, item[2] if len(item) > 2 else 'sans')
    return x


# Storage structures (Figs. 3-5 draw what the store holds, as tables with real keys and values).
CODE_T, HEAD_T, TAG = 5.4, 5.3, 5.0                  # printed 5.7, 5.6, 5.3 pt
MAINT_PALE = '#E2F1EE'                               # teal tint: a changed version, the maintenance path


def stamp(fp, dml, batch):
    """A version stamp V(T) = <schema fingerprint, DML counter, ETL batch>, as a label.

    dml may be a $...$ math label (e.g. $10^6$); the other parts are code.
    """
    d = dml if dml.startswith('$') else f'`{dml}`'
    return rf'$\langle$`{fp},`{d}`,{batch}`$\rangle$'


def structure(s, x, y, w, h, band_h, title, note=None, band=BLUE, ink=WHITE, edge=EDGE, size=SMALL, inset=0.0):
    """A stored structure: a frame with a filled title band, title pieces left and a note right.

    title is a list of (text, style) pieces, starting inset mm further right (room for a badge);
    returns the y of the band's bottom.
    """
    s.rect(x, y, w, h, WHITE, edge, LINE, r=.5)
    i = LINE / 2 + .05
    s.rect(x + i, y + i, w - 2 * i, band_h, band, None, r=.4)
    s.rect(x + i, y + i + band_h / 2, w - 2 * i, band_h / 2, band, None)
    yb = baseline(y + i + band_h / 2, size)
    end = parts(s, x + 1.0 + inset, yb, [(t, ink, st) for t, st in title], size)
    if note:
        s.text(x + w - 1.0, yb, note, size, ink, align='right', width=x + w - 2.0 - end - 1.5)
    return y + i + band_h


def tag(s, x, yc, label, color, size=TAG, align='left'):
    """An algorithm-line tag such as L7: a white bold label on a small rounded box; returns its width."""
    w = measure(label, size, 'bold') + 1.1
    x0 = {'left': x, 'center': x - w / 2, 'right': x - w}[align]
    s.rect(x0, yc - 1.1, w, 2.2, color, None, r=.55)
    s.text(x0 + .55, baseline(yc, size), label, size, WHITE, 'bold')
    return w


# Glyphs shared by Figs. 3-5 (round 3): each stands for something the store or the check holds.
GAUGE_BAND = '#B9D3F3'                               # tolerance above a baseline (pale MAVRA blue)


def key_icon(s, x, yc, color, k=1.0, sw=.17):
    """A small key with its bow at the left, starting at x and centred on yc (key columns, KeyUnique); returns its width."""
    r = .4 * k
    s.circle(x + r, yc, r, None, color, sw)
    x1 = x + 2 * r
    s.line(x1, yc, x1 + 1.3 * k, yc, color, sw)
    for t in (.75, 1.15):
        s.line(x1 + t * k, yc, x1 + t * k, yc + .42 * k, color, sw)
    return 2 * r + 1.3 * k


def gauge(s, x, yc, w, value, tol, vmax, h=1.15, color=BLUE):
    """An unmatched-fraction gauge from 0 to vmax: the measured loss filled, the tolerance band above it, the
    bound as a red tick, and the region past the bound (a failure) tinted red."""
    sc = w / vmax
    y0 = yc - h / 2
    bound = min(value + tol, vmax)
    s.rect(x, y0, w, h, WHITE, None)
    s.rect(x + bound * sc, y0, w - bound * sc, h, RED_PALE, None)
    if value > 0:
        s.rect(x, y0, value * sc, h, color, None)
    s.rect(x + value * sc, y0, tol * sc, h, GAUGE_BAND, None)
    s.rect(x, y0, w, h, None, EDGE, .12)
    s.line(x + bound * sc, y0 - .3, x + bound * sc, y0 + h + .3, RED, .2)


def gauge_icon(s, x, yc, color=BLUE):
    """The gauge in miniature, the mark of an Unmatched condition; returns its width."""
    gauge(s, x, yc, 2.6, .9, .45, 2.6, h=.95, color=color)
    return 2.6


def units(s, x, yc, n, filled, color, cell=.8, gap=.22, per_row=None):
    """n check runs as small squares: the first `filled` solid (run once by MAVRA), the rest outlined (run only by a
    full recheck per definition); returns the width."""
    per_row = per_row or n
    rows = -(-n // per_row)
    top = yc - (rows * cell + (rows - 1) * gap) / 2
    for i in range(n):
        r, c = divmod(i, per_row)
        cx, cy = x + c * (cell + gap), top + r * (cell + gap)
        if i < filled:
            s.rect(cx, cy, cell, cell, color, None, r=.1)
        else:
            s.rect(cx + .07, cy + .07, cell - .14, cell - .14, WHITE, color, .13, r=.1)
    return min(n, per_row) * (cell + gap) - gap


def bolt(s, x, yc, h, color):
    """A lightning bolt (a write to a table), h mm tall, centred on (x, yc)."""
    k = h / 2
    s.poly([(x + .32 * k, yc - k), (x - .44 * k, yc + .14 * k), (x - .02 * k, yc + .14 * k),
            (x - .32 * k, yc + k), (x + .44 * k, yc - .14 * k), (x + .02 * k, yc - .14 * k)], color, None)


def rerun(s, x, yc, r, color, sw=.2):
    """A circular arrow (the check runs again), radius r, centred on (x, yc)."""
    import math
    t0, t1 = math.radians(70), math.radians(345)
    ts = [t0 + (t1 - t0) * i / 23 for i in range(24)]
    s.poly([(x + r * math.cos(t), yc - r * math.sin(t)) for t in ts], None, color, sw, closed=False)
    t = t1
    ang = math.atan2(-math.cos(t), -math.sin(t))
    ex, ey = x + r * math.cos(t), yc - r * math.sin(t)
    s.head(ex + .25 * math.cos(ang), ey + .25 * math.sin(ang), ang, color, length=.85 * r + .2)


def crow(s, x, yc, d, color, sw=.16, spread=.75, length=1.5):
    """Crow's foot of a join's many side, touching a box edge at x; d = +1 when the line leaves to the right."""
    for dy in (-spread, 0, spread):
        s.line(x + d * length, yc, x, yc + dy, color, sw)


def one_bar(s, x, yc, d, color, sw=.16, at=.8, half=.75):
    """The bar of a join's one side, at mm from a box edge at x; d = +1 when the line leaves to the right."""
    s.line(x + d * at, yc - half, x + d * at, yc + half, color, sw)


def db_table(s, x, y, w, name, n, head=2.5, row=2.25, note=None, size=CODE_T):
    """A database table: a grey header with its name, then n column lines; returns the lines' centre ys."""
    from style import RULE as _RULE, INK as _INK
    s.rect(x, y, w, head + n * row, WHITE, EDGE, LINE, r=.5)
    i = LINE / 2 + .05
    s.rect(x + i, y + i, w - 2 * i, head - i, BAND, None, r=.4)
    s.rect(x + i, y + head / 2, w - 2 * i, head / 2 - .02, BAND, None)
    s.line(x, y + head, x + w, y + head, EDGE, .12)
    s.text(x + .8, baseline(y + head / 2, size), name, size, _INK)
    if note:
        s.text(x + w - .8, baseline(y + head / 2, size), note, size, MUTED, align='right')
    ys = []
    for k in range(n):
        if k:
            s.line(x + .35, y + head + row * k, x + w - .35, y + head + row * k, _RULE, .1)
        ys.append(y + head + row * (k + .5))
    return ys


def swatch(s, x, yc, color, w=1.6, h=1.0, edge=None):
    s.rect(x, yc - h / 2, w, h, color, edge, .12)
    return w


def gate(s, x, yc, label, color=LEARN, fill=LEARN_PALE, size=4.7, align='left'):
    """A publication gate such as G3: an outlined tag, lighter than the L<n> algorithm tags; returns its width."""
    w = measure(label, size, 'bold') + .9
    x0 = {'left': x, 'center': x - w / 2, 'right': x - w}[align]
    s.rect(x0, yc - .92, w, 1.84, fill, color, .14, r=.45)
    s.text(x0 + .45, baseline(yc, size), label, size, color, 'bold')
    return w
