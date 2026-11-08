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
