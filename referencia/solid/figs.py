"""Generates the SOLID chapter diagrams as vector SVGs.

Usage: uv run python referencia/solid/figs.py <output-folder>
"""
import sys
from pathlib import Path

from atril.svg import Svg

OUT = Path(sys.argv[1])

# ---------------------------------------------------------------- Figure 7.1
s = Svg(470, 300)
s.cls(270, 95, 170, "Employee", ["+ calculatePay", "+ reportHours", "+ save"])
s.actor(110, 12, "CFO", "Contabilidad")
s.actor(45, 112, "COO", "Recursos Humanos")
s.actor(110, 205, "CTO", "DBAs")
s.arrow([(128, 32), (268, 130)], dash="5,4")
s.arrow([(65, 132), (268, 148)], dash="5,4")
s.arrow([(128, 225), (268, 166)], dash="5,4")
s.save(OUT / "fig7-1.svg")

# ---------------------------------------------------------------- Figure 7.2
s = Svg(420, 150)
s.cls(20, 15, 140, "calculatePay", title_size=13, h=34)
s.cls(260, 15, 140, "reportHours", title_size=13, h=34)
s.cls(140, 100, 140, "regularHours", title_size=13, h=34)
s.arrow([(160, 32), (185, 32), (185, 100)])
s.arrow([(260, 32), (235, 32), (235, 100)])
s.save(OUT / "fig7-2.svg")

# ---------------------------------------------------------------- Figure 7.3
s = Svg(400, 200)
for i, (t, m) in enumerate([("PayCalculator", "+ calculatePay"),
                            ("HourReporter", "+ reportHours"),
                            ("EmployeeSaver", "+ saveEmployee")]):
    s.cls(15, 12 + i * 62, 150, t, [m])
    s.line([(165, 32 + i * 62), (205, 32 + i * 62)])
s.line([(205, 32), (205, 156)])
s.arrow([(205, 94), (255, 94)])
s.cls(255, 70, 125, "EmployeeData", title_size=12.5, h=48)
s.save(OUT / "fig7-3.svg")

# ---------------------------------------------------------------- Figure 7.4
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
s.save(OUT / "fig7-4.svg")

# ---------------------------------------------------------------- Figure 7.5
s = Svg(470, 175)
s.cls(10, 20, 165, "Employee", ["- employeeData", "+ calculatePay", "+ reportHours", "+ save"])
s.cls(290, 15, 155, "HourReporter", ["+ reportHours"])
s.cls(290, 110, 155, "EmployeeSaver", ["+ saveEmployee"])
s.line([(175, 80), (230, 80)])
s.arrow([(230, 80), (230, 35), (288, 35)])
s.arrow([(230, 80), (230, 130), (288, 130)])
s.save(OUT / "fig7-5.svg")

# ---------------------------------------------------------------- Figure 8.1
s = Svg(620, 220)
s.store(10, 95, 120, "Datos\nfinancieros")
s.ellipse(205, 50, 70, 32, "Analizador\nfinanciero")
s.store(240, 135, 160, "Datos del informe\nfinanciero")
s.ellipse(520, 40, 85, 30, "Generador de\ninforme web")
s.ellipse(520, 178, 85, 30, "Generador de\ninforme impreso")
s.arrow([(80, 93), (100, 70), (133, 55)])
s.arrow([(268, 65), (300, 80), (315, 133)])
s.arrow([(350, 133), (390, 70), (433, 45)])
s.arrow([(385, 181), (433, 180)])
s.save(OUT / "fig8-1.svg")

# ---------------------------------------------------------------- Figure 8.2
s = Svg(820, 690)
s.component(10, 10, 232, 232, "Controller")
s.component(258, 10, 552, 232, "Interactor")
s.component(10, 270, 180, 302, "Screen Presenter")
s.component(205, 270, 180, 302, "Print Presenter")
s.component(10, 590, 180, 85, "Web View")
s.component(205, 590, 180, 85, "PDF View")
s.component(490, 380, 320, 130, "Database")
# classes
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
# relations: Controller
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
s.save(OUT / "fig8-2.svg")

# ---------------------------------------------------------------- Figure 8.3
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
s.save(OUT / "fig8-3.svg")

# ---------------------------------------------------------------- Figure 9.1
s = Svg(460, 230)
s.cls(15, 22, 120, "Billing", h=38)
s.cls(245, 15, 160, "License", ["+ calcFee()"], stereo="I")
s.arrow([(135, 41), (244, 41)])
s.cls(140, 150, 130, "Personal\nLicense", h=50)
s.cls(310, 150, 130, "Business\nLicense", ["- users"])
s.line([(205, 150), (205, 120), (375, 120), (375, 150)])
s.arrow([(325, 120), (325, 77)], kind="tri")
s.save(OUT / "fig9-1.svg")

# ---------------------------------------------------------------- Figure 9.2
s = Svg(420, 210)
s.cls(15, 22, 120, "User", h=38)
s.cls(240, 15, 150, "Rectangle", ["+ setH, + setW"])
s.arrow([(135, 41), (239, 41)])
s.cls(240, 140, 150, "Square", ["+ setSide"])
s.arrow([(315, 140), (315, 77)], kind="tri")
s.save(OUT / "fig9-2.svg")

# ---------------------------------------------------------------- Figure 10.1
s = Svg(440, 210)
for i, u in enumerate(["User1", "User2", "User3"]):
    s.cls(15 + i * 145, 12, 120, u, h=38)
s.cls(150, 140, 140, "OPS", ["+op1 +op2 +op3"])
s.arrow([(75, 50), (75, 160), (149, 160)])
s.arrow([(220, 50), (220, 139)])
s.arrow([(365, 50), (365, 160), (291, 160)])
s.save(OUT / "fig10-1.svg")

# ---------------------------------------------------------------- Figure 10.2
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
s.save(OUT / "fig10-2.svg")

# ---------------------------------------------------------------- Figure 10.3
s = Svg(520, 70)
s.cls(10, 12, 130, "Sistema S", h=40)
s.cls(195, 12, 130, "Framework F", h=40)
s.cls(380, 12, 130, "Base de datos D", h=40)
s.arrow([(140, 32), (194, 32)])
s.arrow([(325, 32), (379, 32)])
s.save(OUT / "fig10-3.svg")

# ---------------------------------------------------------------- Figure 11.1
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
s.save(OUT / "fig11-1.svg")

# ------------------------------------------- Commentary figure (DIP)
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
s.save(OUT / "fig-com-dip.svg")

print("ok")
