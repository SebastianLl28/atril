"""Lectura de PDFs con PyMuPDF: índice, texto plano y elementos estructurados por página."""

import re
from collections import Counter
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import pymupdf

MONO = re.compile(r"courier|mono|consol|menlo|code", re.I)
PIE_FIGURA = re.compile(r"^(Figure|Figura|Fig\.|Table|Tabla)\s+\d+(\.\d+)*\b", re.I)
VINETA = re.compile(r"^\s*[•◦▪●‣–]\s*")
ESPACIOS = re.compile(r"[ \t   ]+")

# Una imagen que cubre casi toda la página es un escaneo, no una figura.
AREA_ESCANEO = 0.8

# Un PDF con más de la mitad de páginas casi sin texto es solo imágenes y no se acepta.
MINIMO_CARACTERES, MUESTRA = 25, 30

# Detección de títulos en PDFs sin índice, en múltiplos del tamaño del cuerpo.
TITULO, SUBTITULO, NUMERO_CAPITULO = 1.75, 1.25, 2.3
SOLO_NUMERO = re.compile(r"^(\d+|[IVXLC]+)$")


def solo_imagenes(ruta, muestra=MUESTRA):
    """True si el PDF es un escaneo sin capa de texto (mirando una muestra de páginas)."""
    doc = pymupdf.open(ruta)
    paso = max(1, len(doc) // muestra)
    paginas = range(0, len(doc), paso)
    vacias = sum(len(doc[i].get_text().strip()) < MINIMO_CARACTERES for i in paginas)
    return bool(len(paginas)) and vacias / len(paginas) > 0.5


@dataclass
class Elemento:
    tipo: str  # titulo, subtitulo, parrafo, cita, codigo, vineta, pie_figura, imagen
    texto: str = ""
    bbox: tuple = ()
    xref: int = 0  # solo imágenes


@dataclass
class Pagina:
    numero: int  # 1-based, como lo muestra un visor de PDF
    alto: float
    elementos: list[Elemento] = field(default_factory=list)


def _normalizar(texto):
    return ESPACIOS.sub(" ", texto).strip()


def _es_italica(span):
    return bool(span["flags"] & 2) or "ital" in span["font"].lower()


def _es_negrita(span):
    return bool(span["flags"] & 16) or "bold" in span["font"].lower()


def _unir(lineas):
    """Une líneas de un párrafo, quitando el guion de las palabras partidas."""
    texto = ""
    for linea in lineas:
        if not texto:
            texto = linea
        elif re.search(r"[a-záéíóúñ]-$", texto) and linea[:1].islower():
            texto = texto[:-1] + linea
        else:
            texto += " " + linea
    return texto


class Libro:
    def __init__(self, ruta):
        self.ruta = Path(ruta)
        self.doc = pymupdf.open(self.ruta)

    def __len__(self):
        return self.doc.page_count

    def indice(self):
        """Entradas del índice del PDF como (nivel, título, página).

        Si el PDF no trae índice, se usa el detectado por tamaño de letra.
        """
        toc = [(nivel, titulo, pagina) for nivel, titulo, pagina, *_ in self.doc.get_toc()]
        return toc or self.indice_detectado

    @property
    def tiene_indice(self):
        return bool(self.doc.get_toc())

    @cached_property
    def indice_detectado(self):
        """Títulos por tamaño de letra relativo al cuerpo.

        Si el libro marca los capítulos con un número muy grande (como los escaneos con OCR,
        donde las secciones son casi tan grandes como los títulos), las páginas con ese número
        son capítulos y el resto de títulos, secciones. Si no, los títulos son capítulos y los
        subtítulos en negrita, secciones.
        """
        cuerpo = self.tamano_cuerpo
        paginas = []  # (página, [(tamaño, negrita, y, texto)])
        for n, page in enumerate(self.doc, start=1):
            bloques = []
            for b in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
                spans = [s for l in b["lines"] for s in l["spans"] if s["text"].strip()]
                if not spans:
                    continue
                tamano = max(s["size"] for s in spans) / cuerpo
                if tamano < SUBTITULO:
                    continue
                # Los fragmentos de una línea van pegados: las versalitas («C» + «ONTENTS»)
                # son fragmentos distintos de la misma palabra.
                texto = _normalizar(" ".join("".join(s["text"] for s in l["spans"])
                                             for l in b["lines"]))
                if len(texto) <= 120:
                    bloques.append((tamano, all(_es_negrita(s) for s in spans), b["bbox"][1], texto))
            paginas.append((n, sorted(bloques, key=lambda b: b[2])))

        con_numero = any(t >= NUMERO_CAPITULO for _, bs in paginas for t, *_ in bs)
        entradas = []
        for n, bloques in paginas:
            titulos = [b for b in bloques if b[0] >= TITULO]
            if con_numero:
                if any(t >= NUMERO_CAPITULO for t, *_ in titulos):
                    texto = " ".join(b[3] for b in titulos)
                    if SOLO_NUMERO.match(texto):  # el título quedó por debajo del umbral
                        texto += " " + " ".join(b[3] for b in bloques if b not in titulos)[:100]
                    entradas.append((1, texto.strip(), n))
                else:
                    entradas += [(2, b[3], n) for b in titulos]
            else:
                entradas += [(1, b[3], n) for b in titulos]
                entradas += [(2, b[3], n) for b in bloques if b[0] < TITULO and b[1]]
        # Sin letras son números de página o fechas sueltas, no títulos.
        return [e for e in entradas if any(c.isalpha() for c in e[1])]

    def texto_plano(self, numero):
        return self.textos[numero - 1]

    @cached_property
    def textos(self):
        """Texto plano de todas las páginas; lo usan el mapa, la búsqueda y el contador."""
        return [pagina.get_text() for pagina in self.doc]

    @cached_property
    def tamano_cuerpo(self):
        """Tamaño de letra más usado, medido en una muestra repartida por el libro."""
        conteo = Counter()
        paso = max(1, len(self) // 40)
        for i in range(0, len(self), paso):
            for b in self.doc[i].get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
                for l in b["lines"]:
                    for s in l["spans"]:
                        conteo[round(s["size"], 1)] += len(s["text"].strip())
        return conteo.most_common(1)[0][0] if conteo else 10.0

    def pagina(self, numero):
        page = self.doc[numero - 1]
        pag = Pagina(numero, page.rect.height)
        for b in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
            elemento = self._clasificar(b)
            if elemento:
                pag.elementos.append(elemento)
        area_pagina = page.rect.width * page.rect.height
        for info in page.get_image_info(xrefs=True):
            x0, y0, x1, y1 = info["bbox"]
            if info["xref"] and (x1 - x0) * (y1 - y0) < AREA_ESCANEO * area_pagina:
                pag.elementos.append(Elemento("imagen", bbox=info["bbox"], xref=info["xref"]))
        pag.elementos.sort(key=lambda e: (round(e.bbox[1]), e.bbox[0]))
        return pag

    def imagen(self, xref):
        """Bytes originales de una imagen y su extensión."""
        datos = self.doc.extract_image(xref)
        return datos["image"], datos["ext"]

    def _clasificar(self, bloque):
        lineas, spans = [], []
        for l in bloque["lines"]:
            partes = []
            for s in l["spans"]:
                spans.append(s)
                partes.append((s["text"], bool(MONO.search(s["font"]))))
            lineas.append(partes)
        con_texto = [s for s in spans if s["text"].strip()]
        if not con_texto:
            return None
        bbox = tuple(bloque["bbox"])
        todo_mono = all(MONO.search(s["font"]) for s in con_texto)
        if todo_mono:
            codigo = "\n".join("".join(t for t, _ in l).rstrip() for l in lineas)
            return Elemento("codigo", codigo.replace(" ", " "), bbox)

        # Fragmentos en fuente monoespaciada dentro de prosa → `código`
        textos = []
        for partes in lineas:
            linea = "".join(f"`{t.strip()}`" + (" " if t.endswith(" ") else "")
                            if mono and t.strip() else t for t, mono in partes)
            linea = _normalizar(linea)
            if linea:
                textos.append(linea)
        if not textos:
            return None

        cuerpo = self.tamano_cuerpo
        tamano = max(s["size"] for s in con_texto)
        if tamano >= cuerpo * 1.75:
            return Elemento("titulo", " ".join(textos), bbox)
        if tamano >= cuerpo * 1.25 and all(_es_negrita(s) for s in con_texto):
            return Elemento("subtitulo", " ".join(textos), bbox)
        if PIE_FIGURA.match(textos[0]):
            return Elemento("pie_figura", " ".join(textos), bbox)
        if VINETA.match(textos[0]):
            items, actual = [], []
            for t in textos:
                if VINETA.match(t) and actual:
                    items.append(_unir(actual))
                    actual = []
                actual.append(VINETA.sub("", t) if VINETA.match(t) else t)
            items.append(_unir(actual))
            return Elemento("vineta", "\n".join(items), bbox)
        if all(_es_italica(s) for s in con_texto) and tamano < cuerpo:
            return Elemento("cita", _unir(textos), bbox)
        return Elemento("parrafo", _unir(textos), bbox)
