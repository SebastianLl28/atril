"""Salida de una parte: HTML → PDF carta, PDF 2 por hoja y hojas de miniaturas para revisar.

Todo vive en <parte>/salida/: <parte>.html (lo escribe la skill /libro), libro.css (copia de la
plantilla), los SVG redibujados y lo que genera este módulo.
"""

import shutil
from importlib import resources
from pathlib import Path

import pymupdf
from pypdf import PageObject, PdfReader, PdfWriter, Transformation

from .proyecto import Proyecto

PLANTILLA = resources.files("atril") / "plantilla"

# 2 por hoja: márgenes y separación entre las dos páginas (pt), como el PDF del SOLID.
MARGEN_2X1 = 18
# Hojas de miniaturas: columnas × filas, ancho de cada miniatura (px) y separación.
COLUMNAS, FILAS, ANCHO_MINI, HUECO = 4, 3, 306, 12


class Salida:
    """Rutas de la salida de una parte, a partir de su carpeta en el proyecto."""

    def __init__(self, carpeta):
        self.carpeta = Path(carpeta).expanduser().resolve()
        if not (self.carpeta / "contexto.md").exists():
            raise FileNotFoundError(f"No hay contexto.md en {self.carpeta}")
        self.parte = self.carpeta.name
        self.dir = self.carpeta / "salida"
        self.html = self.dir / f"{self.parte}.html"
        self.pdf = self.dir / f"{self.parte}.pdf"
        self.pdf_2x1 = self.dir / f"{self.parte}-2-por-hoja.pdf"
        self.revision = self.dir / "revision"

    def proyecto(self):
        """El proyecto dueño de la parte, o None si la carpeta no está dentro de uno."""
        if not (self.carpeta.parent / "libro.json").exists():
            return None
        return Proyecto(self.carpeta.parent.name, raiz=self.carpeta.parent.parent)


def _copiar_css(salida):
    salida.dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PLANTILLA / "libro.css", salida.dir / "libro.css")


def iniciar(carpeta):
    """Crea salida/ con libro.css y, si no existe, <parte>.html desde la plantilla base.

    Rellena lo que se sabe sin IA (libro, parte, páginas, idiomas); lo demás queda marcado
    con COMPLETAR. Devuelve la ruta del HTML.
    """
    salida = Salida(carpeta)
    _copiar_css(salida)
    if salida.html.exists():
        return salida.html

    proyecto = salida.proyecto()
    datos = {"libro": "", "parte": salida.parte, "paginas_original": "?",
             "idioma_destino": "es", "descripcion_version": ""}
    if proyecto:
        parte = next((p for p in proyecto.datos["partes"] if p["id"] == salida.parte), {})
        ref = proyecto.datos.get("referencia")
        datos.update(libro=proyecto.titulo, parte=parte.get("titulo", salida.parte),
                     paginas_original=parte.get("original", "?"),
                     idioma_destino=parte.get("idioma_destino", "es"))
        version = (f"traducción revisada directamente del original "
                   f"({proyecto.datos['original']['idioma']}), para estudio personal.")
        if ref and parte.get("referencia"):
            version += (f" Sustituye a la versión de referencia (págs. {parte['referencia']} "
                        f"del PDF en {ref['idioma']}). COMPLETAR: errores típicos que corrige.")
        version += " Los diagramas se han redibujado en vectores para que se impriman nítidos."
        datos["descripcion_version"] = version

    html = (PLANTILLA / "base.html").read_text(encoding="utf-8")
    for clave, valor in datos.items():
        html = html.replace("{{" + clave + "}}", str(valor))
    salida.html.write_text(html, encoding="utf-8")
    return salida.html


def html_a_pdf(html, pdf):
    from weasyprint import HTML  # tarda en importar; solo hace falta aquí

    HTML(filename=str(html)).write_pdf(str(pdf))
    return pdf


def dos_por_hoja(pdf, destino, margen=MARGEN_2X1):
    """Dos páginas por hoja apaisada, del mismo tamaño que el original girado."""
    lector = PdfReader(pdf)
    escritor = PdfWriter()
    paginas = lector.pages
    w, h = float(paginas[0].mediabox.width), float(paginas[0].mediabox.height)
    ancho, alto = h, w  # hoja apaisada
    escala = min((ancho - 3 * margen) / 2 / w, (alto - 2 * margen) / h)
    dy = (alto - h * escala) / 2
    xs = (margen, ancho - margen - w * escala)
    for i in range(0, len(paginas), 2):
        hoja = PageObject.create_blank_page(width=ancho, height=alto)
        for x, pagina in zip(xs, paginas[i:i + 2]):
            t = Transformation().scale(escala).translate(x, dy)
            hoja.merge_transformed_page(pagina, t)
        escritor.add_page(hoja)
    with open(destino, "wb") as f:
        escritor.write(f)
    return destino


def miniaturas(pdf, carpeta, columnas=COLUMNAS, filas=FILAS, ancho=ANCHO_MINI):
    """Hojas PNG con miniaturas numeradas (hoja-01.png…) para revisar la maqueta de un vistazo."""
    carpeta.mkdir(parents=True, exist_ok=True)
    for viejo in carpeta.glob("hoja-*.png"):
        viejo.unlink()
    doc = pymupdf.open(pdf)
    escala = ancho / doc[0].rect.width
    alto = doc[0].rect.height * escala
    etiqueta = 14
    hojas, por_hoja = [], columnas * filas
    for inicio in range(0, len(doc), por_hoja):
        lote = range(inicio, min(inicio + por_hoja, len(doc)))
        n_filas = -(-len(lote) // columnas)
        lienzo = pymupdf.open()
        hoja = lienzo.new_page(width=columnas * (ancho + HUECO) + HUECO,
                               height=n_filas * (alto + etiqueta + HUECO) + HUECO)
        hoja.draw_rect(hoja.rect, color=None, fill=(0.82, 0.82, 0.82))
        for k, n in enumerate(lote):
            x = HUECO + (k % columnas) * (ancho + HUECO)
            y = HUECO + (k // columnas) * (alto + etiqueta + HUECO)
            caja = pymupdf.Rect(x, y, x + ancho, y + alto)
            hoja.draw_rect(caja, color=None, fill=(1, 1, 1))
            hoja.show_pdf_page(caja, doc, n)
            hoja.insert_text((x, y + alto + 11), f"p. {n + 1}", fontsize=10)
        ruta = carpeta / f"hoja-{len(hojas) + 1:02d}.png"
        hoja.get_pixmap().save(ruta)
        hojas.append(ruta)
    return hojas


def ver(carpeta, paginas, dpi=110):
    """Renderiza páginas sueltas del PDF construido (revision/p-005.png) para mirarlas en detalle."""
    salida = Salida(carpeta)
    doc = pymupdf.open(salida.pdf)
    salida.revision.mkdir(parents=True, exist_ok=True)
    rutas = []
    for n in paginas:
        if not 1 <= n <= len(doc):
            raise ValueError(f"El PDF tiene {len(doc)} páginas; no existe la {n}")
        ruta = salida.revision / f"p-{n:03d}.png"
        doc[n - 1].get_pixmap(dpi=dpi).save(ruta)
        rutas.append(ruta)
    return rutas


def construir(carpeta):
    """HTML → PDF, 2 por hoja y miniaturas. Marca la parte como construida en libro.json."""
    salida = Salida(carpeta)
    if not salida.html.exists():
        raise FileNotFoundError(f"Falta {salida.html} (créalo con `atril iniciar`)")
    _copiar_css(salida)
    html_a_pdf(salida.html, salida.pdf)
    dos_por_hoja(salida.pdf, salida.pdf_2x1)
    hojas = miniaturas(salida.pdf, salida.revision)
    paginas = len(pymupdf.open(salida.pdf))

    proyecto = salida.proyecto()
    if proyecto:
        for parte in proyecto.datos["partes"]:
            if parte["id"] == salida.parte:
                parte.update(estado="construida", pdf=str(salida.pdf), paginas_pdf=paginas)
        proyecto.guardar()
    return {"pdf": salida.pdf, "pdf_2x1": salida.pdf_2x1, "miniaturas": hojas,
            "paginas": paginas}
