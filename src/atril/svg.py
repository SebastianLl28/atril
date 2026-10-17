"""Black-and-white SVG diagram library, for crisp printing.

Extracted from `referencia/solid/figs.py`. Typical use in a part's `figs.py`:

    from atril.svg import Svg

    s = Svg(470, 300)
    s.cls(270, 95, 170, "Employee", ["+ calculatePay", "+ reportHours"])
    s.actor(110, 12, "CFO", "Contabilidad")
    s.arrow([(128, 32), (268, 130)], dash="5,4")
    s.save("salida/fig7-1.svg")

Coordinates in px with the origin at the top left. Arrows: `kind="open"` (uses / knows),
`kind="tri"` (inherits / implements); `dash` for dependencies or flows.
"""

import math
from pathlib import Path

SANS = "Noto Sans, DejaVu Sans, sans-serif"
MONO = "DejaVu Sans Mono, monospace"
STROKE = "#111"


def _escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.parts = w, h, []

    def add(self, s):
        self.parts.append(s)

    def render(self):
        body = "\n".join(self.parts)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" font-family="{SANS}">\n'
                f'<rect width="{self.w}" height="{self.h}" fill="white"/>\n{body}\n</svg>\n')

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(), encoding="utf-8")
        return path

    # ---- primitives ------------------------------------------------------
    def text(self, x, y, s, size=12, weight="normal", anchor="middle", family=None,
             fill=STROKE, style="normal"):
        fam = family or SANS
        self.add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
                 f'font-style="{style}" text-anchor="{anchor}" font-family="{fam}" '
                 f'fill="{fill}">{_escape(s)}</text>')

    def rect(self, x, y, w, h, sw=1.3, fill="white", dash=None, stroke=STROKE):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def line(self, pts, sw=1.3, dash=None, stroke=STROKE):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        p = " ".join(f"{x},{y}" for x, y in pts)
        self.add(f'<polyline points="{p}" fill="none" stroke="{stroke}" '
                 f'stroke-width="{sw}"{d} stroke-linejoin="round"/>')

    def head(self, p_from, p_to, kind, stroke=STROKE):
        (x1, y1), (x2, y2) = p_from, p_to
        a = math.atan2(y2 - y1, x2 - x1)
        if kind == "open":
            L, sp = 11, math.radians(24)
            pts = [(x2 - L * math.cos(a - sp), y2 - L * math.sin(a - sp)), (x2, y2),
                   (x2 - L * math.cos(a + sp), y2 - L * math.sin(a + sp))]
            self.line(pts, stroke=stroke)
        elif kind == "tri":
            L, W = 13, 6.5
            bx, by = x2 - L * math.cos(a), y2 - L * math.sin(a)
            px, py = -math.sin(a) * W, math.cos(a) * W
            pts = [(x2, y2), (bx + px, by + py), (bx - px, by - py)]
            p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            self.add(f'<polygon points="{p}" fill="white" stroke="{stroke}" stroke-width="1.3"/>')

    def arrow(self, pts, kind="open", dash=None, stroke=STROKE, sw=1.3):
        """Polyline with a head at the last point: "open" = uses, "tri" = inherits/implements."""
        if kind == "tri":
            # shorten the line so it doesn't cross the triangle
            (x1, y1), (x2, y2) = pts[-2], pts[-1]
            a = math.atan2(y2 - y1, x2 - x1)
            short = pts[:-1] + [(x2 - 13 * math.cos(a), y2 - 13 * math.sin(a))]
            self.line(short, dash=dash, stroke=stroke, sw=sw)
        else:
            self.line(pts, dash=dash, stroke=stroke, sw=sw)
        self.head(pts[-2], pts[-1], kind, stroke=stroke)

    # ---- composite shapes ------------------------------------------------
    def cls(self, x, y, w, title, members=(), stereo=None, h=None, title_size=12.5,
            member_family=None):
        """UML class box. title may have several lines separated by \\n.

        stereo="I" (interface) or "DS" (data structure) goes in the top right corner.
        Returns the box's total height.
        """
        lines = title.split("\n")
        th = max(h or 0, 16 * len(lines) + 14) if not members else 16 * len(lines) + 12
        mh = 17 * len(members) + 6 if members else 0
        total = th + mh
        self.rect(x, y, w, total)
        ty = y + (th - 16 * len(lines)) / 2 + 12.5
        for i, ln in enumerate(lines):
            self.text(x + w / 2, ty + i * 16, ln, size=title_size, weight="bold")
        if members:
            self.line([(x, y + th), (x + w, y + th)])
            for i, m in enumerate(members):
                self.text(x + 8, y + th + 16 + i * 17, m, size=11.5, anchor="start",
                          family=member_family)
        if stereo:
            self.add(f'<rect x="{x + w - 34}" y="{y - 7}" width="34" height="13" fill="white"/>')
            self.text(x + w - 17, y + 4, f"<{stereo}>", size=10.5, weight="bold", family=MONO)
        return total

    def component(self, x, y, w, h, label):
        """Component frame (double border) with the label over the top border."""
        self.rect(x, y, w, h, sw=1.1, fill="none")
        self.rect(x + 3.5, y + 3.5, w - 7, h - 7, sw=1.1, fill="none")
        tw = len(label) * 6.6 + 8
        self.add(f'<rect x="{x + 12}" y="{y - 6}" width="{tw}" height="13" fill="white"/>')
        self.text(x + 16, y + 4, label, size=11, anchor="start", fill="#333")

    def uml_comp(self, x, y, w, h, title):
        """UML component: box with the two tabs on the left."""
        self.rect(x, y, w, h)
        for dy in (0.25, 0.6):
            self.rect(x - 7, y + h * dy, 14, 9, sw=1.1)
        lines = title.split("\n")
        ty = y + h / 2 - 8 * (len(lines) - 1) + 4
        for i, ln in enumerate(lines):
            self.text(x + w / 2 + 4, ty + i * 16, ln, size=12, weight="bold")

    def actor(self, cx, cy, label, sub=None):
        """UML stick figure; (cx, cy) is the head's center. About 85 px tall."""
        self.add(f'<circle cx="{cx}" cy="{cy}" r="9" fill="white" stroke="{STROKE}" '
                 f'stroke-width="1.3"/>')
        self.line([(cx, cy + 9), (cx, cy + 34)])
        self.line([(cx - 15, cy + 18), (cx + 15, cy + 18)])
        self.line([(cx - 11, cy + 54), (cx, cy + 34), (cx + 11, cy + 54)])
        self.text(cx, cy + 69, label, size=12, weight="bold")
        if sub:
            self.text(cx, cy + 83, sub, size=10, fill="#444")

    def ellipse(self, cx, cy, rx, ry, label):
        """Process of a data flow diagram."""
        self.add(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="white" '
                 f'stroke="{STROKE}" stroke-width="1.3"/>')
        lines = label.split("\n")
        for i, ln in enumerate(lines):
            self.text(cx, cy - 3 + i * 15 - 7 * (len(lines) - 2), ln, size=12, weight="bold")

    def store(self, x, y, w, label):
        """Data store: two horizontal lines with the name in between (44 px tall)."""
        self.line([(x, y), (x + w, y)])
        self.line([(x, y + 44), (x + w, y + 44)])
        for i, ln in enumerate(label.split("\n")):
            self.text(x + w / 2, y + 19 + i * 15, ln, size=12, weight="bold")
