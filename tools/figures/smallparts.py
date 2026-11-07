"""Shared look of the single-column technique figures in Section IV
(extraction, maintenance, snapshot).

They follow the common practice of SIGMOD/VLDB technique figures: one point
per figure, told with the running example's real values; flat boxes with thin
grey lines; monospace for SQL and stored data; black and grey text plus two
colours that only carry meaning (red: a wrong or stale result, blue: MAVRA's
result). Fonts and line weights are those of Fig. 2; the captions name the
matching steps of Fig. 2 instead of drawing step badges.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vecfig import PT  # noqa: E402
from style import ACC, ACC_DK, EDGE, MUTED, RED, WHITE  # noqa: E402

# Drawn 84.6 mm wide and scaled to the 88.8 mm IEEEtran column (x1.05).
LABEL, BODY, CODE, SMALL = 6.4, 6.0, 5.75, 5.7      # printed 6.7, 6.3, 6.0, 6.0 pt
LINE = .18
BLUE, BLUE_TXT = ACC, ACC_DK
LIGHT = '#E9E6E0'                                    # highlight behind a literal


def baseline(y_center, size):
    """Baseline that centres capitals and digits on y_center."""
    return y_center + .34 * size * PT


def box(s, x, y, w, h, edge=EDGE, fill=WHITE, dash=None, sw=LINE):
    s.rect(x, y, w, h, fill, edge, sw, r=.5, dash=dash)


def arrow(s, points, color=MUTED, sw=LINE):
    s.route(points, color, sw, length=.9, radius=.6)


def mark(s, x, yc, ok, k=.9):
    """A check (blue) or a cross (red) centred on (x, yc)."""
    if ok:
        s.poly([(x - .62 * k, yc), (x - .15 * k, yc + .5 * k), (x + .65 * k, yc - .55 * k)], None,
               BLUE, .26, closed=False)
    else:
        s.line(x - .5 * k, yc - .5 * k, x + .5 * k, yc + .5 * k, RED, .26)
        s.line(x - .5 * k, yc + .5 * k, x + .5 * k, yc - .5 * k, RED, .26)
