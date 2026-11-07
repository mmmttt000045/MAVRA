"""Drawing parts for the single-column figures of Section IV (extraction, maintenance, snapshot).

They reuse Fig. 2's inks, path colours and glyphs so the four schematics read
as one set: publication violet, reuse blue, execution amber, data change and
maintenance teal; thin arrows are calls, thick arrows write shared state,
dashed arrows read the database, and a circled number is the step of Fig. 2
that the part belongs to.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vecfig import PT, measure  # noqa: E402
from style import ACC, EDGE, RED, WHITE  # noqa: E402
from architecture import (EXEC_C, KEYC, LEARN, LEARN_PALE, MAINT_C, OCHRE, REF,  # noqa: E402
                          STEP_C, USE)

# Path colours and inks the figures take from here, so all three match Fig. 2.
__all__ = ['EXEC_C', 'KEYC', 'LEARN', 'LEARN_PALE', 'MAINT_C', 'OCHRE', 'REF', 'USE', 'TITLE', 'BODY', 'SMALL',
           'CODE', 'STEP', 'NOTE', 'THIN', 'THICK', 'MAINT_PALE', 'EXEC_PALE', 'Kit', 'baseline']

# Drawn 84.6 mm wide and scaled to the 88.8 mm IEEEtran column (x1.05), these
# sizes print at Fig. 2's sizes (Fig. 2 is scaled x1.02).
TITLE, BODY, SMALL, CODE, STEP, NOTE = 7.2, 6.8, 6.2, 5.75, 6.3, 5.9
THIN, THICK = .22, .5
MINI = .95                      # radius of an inline step reference
MAINT_PALE = '#E3F2EF'
EXEC_PALE = '#FBEFD9'
SOFT = '#BDB9B2'                # 3D node edges, as in Fig. 2


def baseline(y_center, size):
    """Baseline that centres capitals and digits on y_center."""
    return y_center + .34 * size * PT


class Kit:
    """Fig. 2's glyphs on a vecfig sheet."""

    def __init__(self, s):
        self.s = s

    def box(self, x, y, w, h, fill=WHITE, edge=EDGE, sw=.16, r=.6, dash=None):
        self.s.rect(x, y, w, h, fill, edge, sw, r=r, dash=dash)

    def node(self, x, y, w, h, d=1.2):
        """A 3D box (agents and outside actors), depth d to the upper right."""
        s = self.s
        s.poly([(x, y), (x + d, y - d), (x + w + d, y - d), (x + w, y)], '#F2F0EC', SOFT, .12)
        s.poly([(x + w, y), (x + w + d, y - d), (x + w + d, y + h - d), (x + w, y + h)],
               '#E7E4DF', SOFT, .12)
        s.rect(x, y, w, h, WHITE, SOFT, .16, r=.4)

    def stack(self, x, y, w, h):
        """A job: three stacked cards, as Fig. 2's ETL job."""
        for off in (1.0, .5, 0):
            self.s.rect(x + off, y - off, w - 1.0, h, WHITE, EDGE, .13, r=.4)

    def person(self, x, y, c='#8E8B85'):
        self.s.circle(x, y, .72, c)
        self.s.rect(x - 1.1, y + .88, 2.2, 1.25, c, None, r=.62)

    def mark(self, x, y, kind, c=None, k=1.0):
        s = self.s
        if kind == 'ok':
            s.poly([(x - .62 * k, y), (x - .15 * k, y + .5 * k), (x + .65 * k, y - .55 * k)], None,
                   c or ACC, .26, closed=False)
        else:
            s.line(x - .5 * k, y - .5 * k, x + .5 * k, y + .5 * k, c or RED, .26)
            s.line(x - .5 * k, y + .5 * k, x + .5 * k, y - .5 * k, c or RED, .26)

    def pill(self, x, yc, label, color, w=None, size=5.6, fg=WHITE, h=2.3):
        w = w or measure(label, size, 'bold') + 1.6
        self.s.rect(x, yc - h / 2, w, h, color, None, r=.6)
        self.s.text(x + w / 2, baseline(yc, size), label, size, fg, 'bold', 'center')
        return w

    def step(self, x, y, n, r=1.45):
        self.s.circle(x, y, r, STEP_C[n])
        self.s.text(x, baseline(y, STEP), str(n), STEP, WHITE, 'bold', 'center')

    def rich(self, x, yc, tokens, size, color, style='sans', align='left', width=None):
        """A label whose integer tokens are inline step references (small
        circled numbers in that step's colour); yc is the line's visual centre."""
        tokens = tokens if isinstance(tokens, tuple) else (tokens,)
        gap = .4

        def size_of(t):
            return 2 * MINI if isinstance(t, int) else measure(t, size, style)
        def gap_before(j):
            t = tokens[j]
            return 0 if j == 0 or (isinstance(t, str) and t[:1] in ',:;.)，：；。） ') else gap
        total = sum(size_of(t) for t in tokens) + sum(gap_before(j) for j in range(len(tokens)))
        if width is not None:
            assert total <= width + 1e-6, f'{tokens!r} is {total:.1f} mm wide; {width:.1f} mm available'
        xx = x - total if align == 'right' else x - total / 2 if align == 'center' else x
        for j, t in enumerate(tokens):
            xx += gap_before(j)
            if isinstance(t, int):
                self.s.circle(xx + MINI, yc, MINI, STEP_C[t])
                self.s.text(xx + MINI, baseline(yc, 4.9), str(t), 4.9, WHITE, 'bold', 'center')
            else:
                self.s.text(xx, baseline(yc, size), t, size, color, style)
            xx += size_of(t)
        return total

    def sparkle(self, x, y, r, c):
        k = .28 * r
        self.s.poly([(x, y - r), (x + k, y - k), (x + r, y), (x + k, y + k), (x, y + r),
                     (x - k, y + k), (x - r, y), (x - k, y - k)], c, None)

    def header(self, x, y, w, title, fill, fg=WHITE, note=None, note_c=None, h=3.0, size=SMALL + .2):
        """A coloured title band on top of a box drawn at (x, y, w, ...)."""
        self.s.rect(x, y, w, h, fill, None, r=.6)
        self.s.rect(x, y + h / 2, w, h / 2, fill, None)
        tw = self.s.text(x + 1.2, baseline(y + h / 2, size), title, size, fg, 'bold')
        if note:
            self.s.text(x + w - 1.2, baseline(y + h / 2, NOTE - .3), note, NOTE - .3, note_c or fg,
                        align='right', width=w - tw - 3.4)

    def tag(self, x, yc, label, color, align='left', size=NOTE - .4):
        """A small rounded outline tag such as 'reused' or 'run once'."""
        w = measure(label, size, 'bold') + 1.4
        x0 = x - w if align == 'right' else x
        self.s.rect(x0, yc - 1.05, w, 2.1, WHITE, color, .16, r=.9)
        self.s.text(x0 + w / 2, baseline(yc, size), label, size, color, 'bold', 'center')
        return w
