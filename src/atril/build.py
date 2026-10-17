"""A part's output: HTML → letter PDF, 2-up PDF and contact sheets for review.

Everything lives in <part>/salida/: <part>.html (written by the /libro skill), libro.css (a
copy of the template), the redrawn SVGs and what this module generates.
"""

import shutil
from importlib import resources
from pathlib import Path

import pymupdf
from pypdf import PageObject, PdfReader, PdfWriter, Transformation

from .project import Project

TEMPLATE = resources.files("atril") / "template"

# 2-up: margins and gap between the two pages (pt), as in the SOLID PDF.
MARGIN_2UP = 18
# Contact sheets: columns × rows, thumbnail width (px) and gap.
COLUMNS, ROWS, THUMB_WIDTH, GAP = 4, 3, 306, 12


class Output:
    """Paths of a part's output, from its folder in the project."""

    def __init__(self, folder):
        self.folder = Path(folder).expanduser().resolve()
        if not (self.folder / "contexto.md").exists():
            raise FileNotFoundError(f"No hay contexto.md en {self.folder}")
        self.part = self.folder.name
        self.dir = self.folder / "salida"
        self.html = self.dir / f"{self.part}.html"
        self.pdf = self.dir / f"{self.part}.pdf"
        self.pdf_2up = self.dir / f"{self.part}-2-por-hoja.pdf"
        self.review = self.dir / "revision"

    def project(self):
        """The project owning the part, or None if the folder is not inside one."""
        if not (self.folder.parent / "libro.json").exists():
            return None
        return Project(self.folder.parent.name, root=self.folder.parent.parent)


def _copy_css(output):
    output.dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMPLATE / "libro.css", output.dir / "libro.css")


def _cover_texts(project, part):
    """Cover language and wording according to the part's task (see bundle.TASK)."""
    task = part.get("tarea") or {}
    lang = project.data["original"]["idioma"]
    target = task.get("traducir") or part.get("idioma_destino")  # idioma_destino: older parts
    translates = bool(target) and target != lang
    if translates:
        version = (f"traducción revisada directamente del documento original ({lang}), "
                   "para estudio personal.")
        fidelity = "traducción fiel del original"
    else:
        version = ("transcripción fiel del documento original, con una maquetación pensada "
                   "para leer y estudiar.")
        fidelity = "transcripción fiel del original"
    ref = project.data.get("referencia")
    if translates and ref and part.get("referencia"):
        version += (f" Sustituye a la otra versión (págs. {part['referencia']} del PDF en "
                    f"{ref['idioma']}). COMPLETAR: errores típicos que corrige.")
    extras = []
    if task.get("mejorar_lectura", True):
        extras.append("los diagramas se han redibujado en vectores para que se impriman nítidos")
    if task.get("comentarios") or task.get("contexto"):
        extras.append("se han añadido recuadros de comentario y contexto")
    if extras:
        version += " " + "; ".join(extras).capitalize() + "."
    return {"idioma_salida": target if translates else lang, "descripcion_version": version,
            "fidelidad": fidelity}


def init(folder):
    """Creates salida/ with libro.css and, if missing, <part>.html from the base template.

    Fills in what is known without AI (book, part, pages, languages); the rest is marked
    COMPLETAR. Returns the HTML path.
    """
    output = Output(folder)
    _copy_css(output)
    if output.html.exists():
        return output.html

    project = output.project()
    # Keys are the {{placeholders}} in base.html.
    values = {"libro": "", "parte": output.part, "paginas_original": "?", "idioma_salida": "es",
              "descripcion_version": "", "fidelidad": "fiel al documento original"}
    if project:
        part = next((p for p in project.data["partes"] if p["id"] == output.part), {})
        values.update(libro=project.title, parte=part.get("titulo", output.part),
                      paginas_original=part.get("original", "?"))
        values.update(_cover_texts(project, part))

    html = (TEMPLATE / "base.html").read_text(encoding="utf-8")
    for key, value in values.items():
        html = html.replace("{{" + key + "}}", str(value))
    output.html.write_text(html, encoding="utf-8")
    return output.html


def html_to_pdf(html, pdf):
    from weasyprint import HTML  # slow to import; only needed here

    HTML(filename=str(html)).write_pdf(str(pdf))
    return pdf


def two_up(pdf, dest, margin=MARGIN_2UP):
    """Two pages per landscape sheet, the same size as the original rotated."""
    reader = PdfReader(pdf)
    writer = PdfWriter()
    pages = reader.pages
    w, h = float(pages[0].mediabox.width), float(pages[0].mediabox.height)
    width, height = h, w
    scale = min((width - 3 * margin) / 2 / w, (height - 2 * margin) / h)
    dy = (height - h * scale) / 2
    xs = (margin, width - margin - w * scale)
    for i in range(0, len(pages), 2):
        sheet = PageObject.create_blank_page(width=width, height=height)
        for x, page in zip(xs, pages[i:i + 2]):
            t = Transformation().scale(scale).translate(x, dy)
            sheet.merge_transformed_page(page, t)
        writer.add_page(sheet)
    with open(dest, "wb") as f:
        writer.write(f)
    return dest


def contact_sheets(pdf, folder, columns=COLUMNS, rows=ROWS, width=THUMB_WIDTH):
    """PNG sheets of numbered thumbnails (hoja-01.png…) to review the layout at a glance."""
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("hoja-*.png"):
        old.unlink()
    doc = pymupdf.open(pdf)
    scale = width / doc[0].rect.width
    height = doc[0].rect.height * scale
    label = 14
    sheets, per_sheet = [], columns * rows
    for first in range(0, len(doc), per_sheet):
        batch = range(first, min(first + per_sheet, len(doc)))
        n_rows = -(-len(batch) // columns)
        canvas = pymupdf.open()
        sheet = canvas.new_page(width=columns * (width + GAP) + GAP,
                                height=n_rows * (height + label + GAP) + GAP)
        sheet.draw_rect(sheet.rect, color=None, fill=(0.82, 0.82, 0.82))
        for k, n in enumerate(batch):
            x = GAP + (k % columns) * (width + GAP)
            y = GAP + (k // columns) * (height + label + GAP)
            box = pymupdf.Rect(x, y, x + width, y + height)
            sheet.draw_rect(box, color=None, fill=(1, 1, 1))
            sheet.show_pdf_page(box, doc, n)
            sheet.insert_text((x, y + height + 11), f"p. {n + 1}", fontsize=10)
        path = folder / f"hoja-{len(sheets) + 1:02d}.png"
        sheet.get_pixmap().save(path)
        sheets.append(path)
    return sheets


def view(folder, pages, dpi=110):
    """Renders single pages of the built PDF (revision/p-005.png) to inspect them closely."""
    output = Output(folder)
    doc = pymupdf.open(output.pdf)
    output.review.mkdir(parents=True, exist_ok=True)
    paths = []
    for n in pages:
        if not 1 <= n <= len(doc):
            raise ValueError(f"El PDF tiene {len(doc)} páginas; no existe la {n}")
        path = output.review / f"p-{n:03d}.png"
        doc[n - 1].get_pixmap(dpi=dpi).save(path)
        paths.append(path)
    return paths


def build(folder):
    """HTML → PDF, 2-up and contact sheets. Marks the part as built in libro.json."""
    output = Output(folder)
    if not output.html.exists():
        raise FileNotFoundError(f"Falta {output.html} (créalo con `atril iniciar`)")
    _copy_css(output)
    html_to_pdf(output.html, output.pdf)
    two_up(output.pdf, output.pdf_2up)
    sheets = contact_sheets(output.pdf, output.review)
    pages = len(pymupdf.open(output.pdf))

    project = output.project()
    if project:
        for part in project.data["partes"]:
            if part["id"] == output.part:
                part.update(estado="construida", pdf=str(output.pdf), paginas_pdf=pages)
        project.save()
    return {"pdf": output.pdf, "pdf_2up": output.pdf_2up, "sheets": sheets,
            "pages": pages}
