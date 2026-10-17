"""Genera los diagramas del capítulo SOLID como SVG vectoriales."""
import math
import os
import sys

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

SANS = "Noto Sans, DejaVu Sans, sans-serif"
MONO = "DejaVu Sans Mono, monospace"
STROKE = "#111"


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.parts = w, h, []

    def add(self, s):
        self.parts.append(s)

    def save(self, name):
        body = "\n".join(self.parts)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
               f'viewBox="0 0 {self.w} {self.h}" font-family="{SANS}">\n'
               f'<rect width="{self.w}" height="{self.h}" fill="white"/>\n{body}\n</svg>\n')
        with open(os.path.join(OUT, name), "w") as f:
            f.write(svg)

    # ---- primitivas -------------------------------------------------------
    def text(self, x, y, s, size=12, weight="normal", anchor="middle", family=None,
             fill=STROKE, style="normal"):
        fam = family or SANS
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
                 f'font-style="{style}" text-anchor="{anchor}" font-family="{fam}" '
                 f'fill="{fill}">{s}</text>')

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
        if kind == "tri":
            # acorta la línea para que no atraviese el triángulo
            (x1, y1), (x2, y2) = pts[-2], pts[-1]
            a = math.atan2(y2 - y1, x2 - x1)
            short = pts[:-1] + [(x2 - 13 * math.cos(a), y2 - 13 * math.sin(a))]
            self.line(short, dash=dash, stroke=stroke, sw=sw)
        else:
            self.line(pts, dash=dash, stroke=stroke, sw=sw)
        self.head(pts[-2], pts[-1], kind, stroke=stroke)

    def cls(self, x, y, w, title, members=(), stereo=None, h=None, title_size=12.5,
            member_family=None):
        """Caja de clase UML. title puede tener varias líneas separadas por \\n."""
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
        self.rect(x, y, w, h, sw=1.1, fill="none")
        self.rect(x + 3.5, y + 3.5, w - 7, h - 7, sw=1.1, fill="none")
        tw = len(label) * 6.6 + 8
        self.add(f'<rect x="{x + 12}" y="{y - 6}" width="{tw}" height="13" fill="white"/>')
        self.text(x + 16, y + 4, label, size=11, anchor="start", fill="#333")

    def uml_comp(self, x, y, w, h, title):
        self.rect(x, y, w, h)
        for dy in (0.25, 0.6):
            self.rect(x - 7, y + h * dy, 14, 9, sw=1.1)
        lines = title.split("\n")
        ty = y + h / 2 - 8 * (len(lines) - 1) + 4
        for i, ln in enumerate(lines):
            self.text(x + w / 2 + 4, ty + i * 16, ln, size=12, weight="bold")

    def actor(self, cx, cy, label, sub=None):
        self.add(f'<circle cx="{cx}" cy="{cy}" r="9" fill="white" stroke="{STROKE}" stroke-width="1.3"/>')
        self.line([(cx, cy + 9), (cx, cy + 34)])
        self.line([(cx - 15, cy + 18), (cx + 15, cy + 18)])
        self.line([(cx - 11, cy + 54), (cx, cy + 34), (cx + 11, cy + 54)])
        self.text(cx, cy + 69, label, size=12, weight="bold")
        if sub:
            self.text(cx, cy + 83, sub, size=10, fill="#444")


# ---------------------------------------------------------------- Figura 7.1
s = Svg(470, 300)
s.cls(270, 95, 170, "Employee", ["+ calculatePay", "+ reportHours", "+ save"])
s.actor(110, 12, "CFO", "Contabilidad")
s.actor(45, 112, "COO", "Recursos Humanos")
s.actor(110, 205, "CTO", "DBAs")
s.arrow([(128, 32), (268, 130)], dash="5,4")
s.arrow([(65, 132), (268, 148)], dash="5,4")
s.arrow([(128, 225), (268, 166)], dash="5,4")
s.save("fig7-1.svg")

# ---------------------------------------------------------------- Figura 7.2
s = Svg(420, 150)
s.cls(20, 15, 140, "calculatePay", title_size=13, h=34)
s.cls(260, 15, 140, "reportHours", title_size=13, h=34)
s.cls(140, 100, 140, "regularHours", title_size=13, h=34)
s.arrow([(160, 32), (185, 32), (185, 100)])
s.arrow([(260, 32), (235, 32), (235, 100)])
s.save("fig7-2.svg")

# ---------------------------------------------------------------- Figura 7.3
s = Svg(400, 200)
for i, (t, m) in enumerate([("PayCalculator", "+ calculatePay"),
                            ("HourReporter", "+ reportHours"),
                            ("EmployeeSaver", "+ saveEmployee")]):
    s.cls(15, 12 + i * 62, 150, t, [m])
    s.line([(165, 32 + i * 62), (205, 32 + i * 62)])
s.line([(205, 32), (205, 156)])
s.arrow([(205, 94), (255, 94)])
s.cls(255, 70, 125, "EmployeeData", title_size=12.5, h=48)
s.save("fig7-3.svg")

# ---------------------------------------------------------------- Figura 7.4
s = Svg(600, 200)
s.cls(10, 50, 150, "EmployeeFacade", ["+ calculatePay", "+ reportHours", "+ save"])
for i, (t, m) in enumerate([("PayCalculator", "+ calculatePay"),
                            ("HourReporter", "+ reportHours"),
                            ("EmployeeSaver", "+ saveEmployee")]):
    y = 12 + i * 62
    s.cls(225, y, 150, t, [m])
    s.arrow([(195, y + 20), (223, y + 20)])
    s.line([(375, y + 20), (415, y + 20)])
s.line([(160, 94), (195, 94)])
s.line([(195, 32), (195, 156)])
s.line([(415, 32), (415, 156)])
s.arrow([(415, 94), (455, 94)])
s.cls(455, 70, 125, "EmployeeData", h=48)
s.save("fig7-4.svg")

# ---------------------------------------------------------------- Figura 7.5
s = Svg(470, 175)
s.cls(10, 20, 165, "Employee", ["- employeeData", "+ calculatePay", "+ reportHours", "+ save"])
s.cls(290, 15, 155, "HourReporter", ["+ reportHours"])
s.cls(290, 110, 155, "EmployeeSaver", ["+ saveEmployee"])
s.line([(175, 80), (230, 80)])
s.arrow([(230, 80), (230, 35), (288, 35)])
s.arrow([(230, 80), (230, 130), (288, 130)])
s.save("fig7-5.svg")

# ---------------------------------------------------------------- Figura 8.1
s = Svg(620, 220)
def ellipse(cx, cy, rx, ry, label):
    s.add(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="white" stroke="{STROKE}" stroke-width="1.3"/>')
    for i, ln in enumerate(label.split("\n")):
        s.text(cx, cy - 3 + i * 15 - 7 * (len(label.split(chr(10))) - 2), ln, size=12, weight="bold")
def store(x, y, w, label):
    s.line([(x, y), (x + w, y)])
    s.line([(x, y + 44), (x + w, y + 44)])
    for i, ln in enumerate(label.split("\n")):
        s.text(x + w / 2, y + 19 + i * 15, ln, size=12, weight="bold")
store(10, 95, 120, "Datos\nfinancieros")
ellipse(205, 50, 70, 32, "Analizador\nfinanciero")
store(240, 135, 160, "Datos del informe\nfinanciero")
ellipse(520, 40, 85, 30, "Generador de\ninforme web")
ellipse(520, 178, 85, 30, "Generador de\ninforme impreso")
s.arrow([(80, 93), (100, 70), (133, 55)])
s.arrow([(268, 65), (300, 80), (315, 133)])
s.arrow([(350, 133), (390, 70), (433, 45)])
s.arrow([(385, 181), (433, 180)])
s.save("fig8-1.svg")

# ---------------------------------------------------------------- Figura 8.2
s = Svg(820, 690)
s.component(10, 10, 232, 232, "Controller")
s.component(258, 10, 552, 232, "Interactor")
s.component(10, 270, 180, 302, "Screen Presenter")
s.component(205, 270, 180, 302, "Print Presenter")
s.component(10, 590, 180, 85, "Web View")
s.component(205, 590, 180, 85, "PDF View")
s.component(490, 380, 320, 130, "Database")
# clases
s.cls(40, 45, 150, "Financial\nReport\nController", h=60)
s.cls(40, 160, 150, "Financial\nReport\nPresenter", stereo="I", h=60)
s.cls(290, 25, 140, "Financial\nReport\nRequest", stereo="DS", h=58)
s.cls(290, 95, 140, "Financial\nReport\nRequester", stereo="I", h=58)
s.cls(290, 165, 140, "Financial\nReport\nResponse", stereo="DS", h=58)
s.cls(480, 52, 140, "Financial\nReport\nGenerator", h=58)
s.cls(510, 160, 130, "Financial\nData\nGateway", stereo="I", h=58)
s.cls(670, 95, 125, "Financial\nentities", h=50)
s.cls(30, 300, 120, "Screen\nPresenter", h=45)
s.cls(30, 385, 120, "Screen\nView\nModel", stereo="DS", h=58)
s.cls(30, 480, 120, "Screen\nView", stereo="I", h=45)
s.cls(225, 300, 120, "Print\nPresenter", h=45)
s.cls(225, 385, 120, "Print\nView\nModel", stereo="DS", h=58)
s.cls(225, 480, 120, "Print\nView", stereo="I", h=45)
s.cls(30, 607, 120, "Web\nView", h=45)
s.cls(225, 607, 120, "PDF\nView", h=45)
s.cls(510, 418, 130, "Financial\nData\nMapper", h=58)
s.cls(665, 425, 125, "Financial\nDatabase", h=46)
# relaciones: Controller
s.arrow([(115, 108), (115, 159)])
s.line([(190, 75), (250, 75)])
s.line([(250, 54), (250, 180)])
s.arrow([(250, 54), (289, 54)])
s.arrow([(250, 124), (289, 124)])
s.arrow([(250, 180), (289, 180)])
s.arrow([(190, 205), (289, 205)])
# Interactor
s.arrow([(520, 52), (520, 42), (431, 42)])
s.arrow([(480, 88), (455, 88), (455, 124), (431, 124)], kind="tri")
s.arrow([(495, 112), (495, 200), (431, 200)])
s.arrow([(575, 112), (575, 158)])
s.arrow([(620, 70), (732, 70), (732, 94)])
# Database
s.arrow([(575, 418), (575, 220)], kind="tri")
s.arrow([(625, 418), (625, 365), (732, 365), (732, 147)])
s.arrow([(640, 448), (664, 448)])
# Presenters
s.line([(140, 300), (140, 252), (335, 252), (335, 300)])
s.arrow([(165, 252), (165, 222)], kind="tri")
for dx in (0, 195):
    s.arrow([(90 + dx, 347), (90 + dx, 384)])
    s.arrow([(90 + dx, 480), (90 + dx, 446)])
    s.arrow([(150 + dx, 322), (170 + dx, 322), (170 + dx, 502), (151 + dx, 502)])
    s.arrow([(115 + dx, 607), (115 + dx, 527)], kind="tri")
s.save("fig8-2.svg")

# ---------------------------------------------------------------- Figura 8.3
s = Svg(480, 320)
s.uml_comp(80, 15, 140, 60, "Financial\nReport\nController")
s.uml_comp(320, 15, 140, 60, "Financial\nReport\nInteractor")
s.uml_comp(20, 130, 130, 55, "Screen\nPresenter")
s.uml_comp(175, 130, 130, 55, "Print\nPresenter")
s.uml_comp(320, 130, 140, 55, "Financial\nDatabase")
s.uml_comp(20, 250, 130, 55, "Web\nView")
s.uml_comp(175, 250, 130, 55, "PDF\nView")
s.arrow([(220, 45), (312, 45)])
s.line([(88, 130), (88, 105), (240, 105), (240, 130)])
s.arrow([(150, 105), (150, 76)])
s.arrow([(390, 130), (390, 76)])
s.arrow([(88, 250), (88, 186)])
s.arrow([(240, 250), (240, 186)])
s.save("fig8-3.svg")

# ---------------------------------------------------------------- Figura 9.1
s = Svg(460, 230)
s.cls(15, 22, 120, "Billing", h=38)
s.cls(245, 15, 160, "License", ["+ calcFee()"], stereo="I")
s.arrow([(135, 41), (244, 41)])
s.cls(140, 150, 130, "Personal\nLicense", h=50)
s.cls(310, 150, 130, "Business\nLicense", ["- users"])
s.line([(205, 150), (205, 120), (375, 120), (375, 150)])
s.arrow([(325, 120), (325, 77)], kind="tri")
s.save("fig9-1.svg")

# ---------------------------------------------------------------- Figura 9.2
s = Svg(420, 210)
s.cls(15, 22, 120, "User", h=38)
s.cls(240, 15, 150, "Rectangle", ["+ setH, + setW"])
s.arrow([(135, 41), (239, 41)])
s.cls(240, 140, 150, "Square", ["+ setSide"])
s.arrow([(315, 140), (315, 77)], kind="tri")
s.save("fig9-2.svg")

# ---------------------------------------------------------------- Figura 10.1
s = Svg(440, 210)
for i, u in enumerate(["User1", "User2", "User3"]):
    s.cls(15 + i * 145, 12, 120, u, h=38)
s.cls(150, 140, 140, "OPS", ["+op1 +op2 +op3"])
s.arrow([(75, 50), (75, 160), (149, 160)])
s.arrow([(220, 50), (220, 139)])
s.arrow([(365, 50), (365, 160), (291, 160)])
s.save("fig10-1.svg")

# ---------------------------------------------------------------- Figura 10.2
s = Svg(440, 290)
for i, u in enumerate(["User1", "User2", "User3"]):
    x = 15 + i * 145
    s.cls(x, 12, 120, u, h=38)
    s.cls(x, 92, 120, f"U{i + 1}Ops", [f"+ op{i + 1}"], stereo="I")
    s.arrow([(x + 60, 50), (x + 60, 91)])
s.cls(150, 220, 140, "OPS", ["+op1 +op2 +op3"])
s.line([(75, 190), (365, 190)])
s.line([(220, 220), (220, 190)])
for x in (75, 220, 365):
    s.arrow([(x, 190), (x, 142)], kind="tri")
s.save("fig10-2.svg")

# ---------------------------------------------------------------- Figura 10.3
s = Svg(520, 70)
s.cls(10, 12, 130, "Sistema S", h=40)
s.cls(195, 12, 130, "Framework F", h=40)
s.cls(380, 12, 130, "Base de datos D", h=40)
s.arrow([(140, 32), (194, 32)])
s.arrow([(325, 32), (379, 32)])
s.save("fig10-3.svg")

# ---------------------------------------------------------------- Figura 11.1
s = Svg(500, 320)
s.add('<path d="M0,224 C110,238 195,230 240,165 S330,95 500,90" fill="none" '
      'stroke="#9a9a9a" stroke-width="9" stroke-linecap="round" opacity="0.75"/>')
s.text(16, 40, "LADO ABSTRACTO", size=10, weight="bold", anchor="start", fill="#666")
s.text(490, 300, "LADO CONCRETO", size=10, weight="bold", anchor="end", fill="#666")
s.cls(40, 55, 150, "Application", h=40)
s.cls(300, 20, 150, "Service", stereo="I", h=40)
s.cls(40, 125, 150, "Service\nFactory", ["+ makeSvc"], stereo="I")
s.cls(300, 125, 150, "Concrete\nImpl", h=50)
s.cls(40, 255, 150, "Service\nFactory Impl", ["+ makeSvc"])
s.arrow([(190, 70), (240, 70), (240, 45), (299, 45)])
s.arrow([(115, 95), (115, 124)])
s.arrow([(190, 140), (320, 62)], dash="5,4")
s.arrow([(375, 125), (375, 61)], kind="tri")
s.arrow([(115, 255), (115, 192)], kind="tri")
s.arrow([(190, 285), (375, 285), (375, 176)])
s.text(285, 278, "«crea»", size=11)
s.save("fig11-1.svg")

# ------------------------------------------- Figura de comentario (DIP)
s = Svg(560, 150)
s.cls(15, 70, 140, "Application", h=40)
s.cls(210, 70, 140, "Service", stereo="I", h=40)
s.cls(405, 70, 140, "ConcreteImpl", h=40)
s.arrow([(155, 90), (209, 90)])
s.arrow([(405, 90), (351, 90)], kind="tri")
s.text(280, 136, "dependencias de código fuente: ambas flechas apuntan hacia la abstracción",
       size=11, fill="#222")
s.arrow([(85, 62), (85, 30), (475, 30), (475, 62)], dash="6,4", stroke="#666")
s.text(280, 22, "flujo de control en ejecución: Application termina ejecutando código de ConcreteImpl",
       size=11, fill="#444", style="italic")
s.save("fig-com-dip.svg")

print("ok")
