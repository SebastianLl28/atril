"""App visual: backend FastAPI que sirve proyectos, miniaturas, índice, búsqueda, mapa y exportación.

El frontend (web/) es HTML + JS sin paso de build. Se abre con `uv run atril app`.
"""

import os
import re
import threading
import unicodedata
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import imprimir, miniaturas, ocr, paquete
from .construir import Salida
from .proyecto import RAIZ, Proyecto

LIBROS = Path(os.environ.get("ATRIL_LIBROS", "~/Documents/books")).expanduser()
WEB = Path(__file__).parent / "web"
SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")
PARTE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
LADOS = ("original", "referencia")


def _plano(texto):
    """Minúsculas y sin tildes, para buscar sin que importen los acentos."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


class NuevoProyecto(BaseModel):
    slug: str
    titulo: str = ""
    original: str
    referencia: str | None = None
    idioma_original: str = "en"
    idioma_referencia: str = "es"


class Ancla(BaseModel):
    referencia: int
    original: int


class Ocr(BaseModel):
    pdf: str
    idiomas: str = "spa+eng"


class Impresion(BaseModel):
    tipo: str = "carta"  # carta | 2x1
    copias: int = 1
    paginas: str | None = None
    simular: bool = False


class Exportacion(BaseModel):
    parte: str
    original: tuple[int, int] | None = None
    referencia: tuple[int, int] | None = None
    instrucciones: str = ""
    titulo_parte: str | None = None
    idioma_destino: str = "es"


def crear_app(raiz=None, libros=None, cache=None):
    raiz = Path(raiz or RAIZ)
    libros = Path(libros or LIBROS)
    app = FastAPI(title="Atril")
    abiertos = {}  # slug → Proyecto, con sus PDFs y textos ya cargados
    sin_texto = {}  # (ruta, mtime) → bool, para no volver a medir cada PDF
    candado = threading.RLock()  # PyMuPDF no es seguro entre hilos

    def proyecto(slug):
        with candado:
            if slug not in abiertos:
                try:
                    abiertos[slug] = Proyecto(slug, raiz=raiz)
                except FileNotFoundError as e:
                    raise HTTPException(404, str(e))
            return abiertos[slug]

    def libro(slug, lado):
        if lado not in LADOS:
            raise HTTPException(404, f"Lado desconocido: {lado}")
        with candado:  # abre el PDF la primera vez
            lib = getattr(proyecto(slug), lado)
        if lib is None:
            raise HTTPException(404, "Este proyecto no tiene PDF de referencia")
        return lib

    def resumen_lado(p, lado):
        lib = getattr(p, lado)
        if lib is None:
            return None
        rect = lib.doc[0].rect
        return {"pdf": str(lib.ruta), "nombre": unicodedata.normalize("NFC", lib.ruta.name),
                "idioma": p.datos[lado]["idioma"], "paginas": len(lib),
                "proporcion": rect.height / rect.width, "indice": lib.indice(),
                "indice_detectado": not lib.tiene_indice}

    def pdf_de_parte(p, parte, tipo):
        if not PARTE.fullmatch(parte):
            raise HTTPException(422, "Id de parte inválido")
        try:
            s = Salida(p.dir / parte)
        except FileNotFoundError:
            return None
        return {"carta": s.pdf, "2x1": s.pdf_2x1}.get(tipo)

    def partes(p):
        """Historial: las partes de libro.json, con qué PDFs construidos existen."""
        lista = []
        for x in p.datos["partes"]:
            pdfs = {t: bool((r := pdf_de_parte(p, x["id"], t)) and r.exists())
                    for t in ("carta", "2x1")}
            lista.append({**x, "pdfs": pdfs})
        return lista

    def detalle(p):
        return {"slug": p.slug, "titulo": p.titulo, "dir": str(p.dir),
                "original": resumen_lado(p, "original"),
                "referencia": resumen_lado(p, "referencia"),
                "mapa": p.mapa, "anclas": p.anclas, "partes": partes(p)}

    def falta_texto(ruta):
        clave = (str(ruta), ruta.stat().st_mtime_ns)
        if clave not in sin_texto:
            try:
                sin_texto[clave] = ocr.necesita_ocr(ruta)
            except Exception:  # PDF dañado o cifrado: que lo diga al abrirlo
                sin_texto[clave] = False
        return sin_texto[clave]

    @app.get("/api/pdfs")
    def pdfs():
        """PDFs disponibles en la carpeta de libros (sin los generados en los proyectos)."""
        encontrados = [f for f in libros.rglob("*.pdf") if raiz not in f.parents]
        return [{"ruta": str(f),
                 "nombre": unicodedata.normalize("NFC", str(f.relative_to(libros))),
                 "sin_texto": falta_texto(f)}
                for f in sorted(encontrados, key=lambda f: str(f).lower())]

    @app.post("/api/ocr")
    def pasar_ocr(datos: Ocr):
        """Copia con capa de texto, «<nombre> (OCR).pdf». Tarda: va fuera del candado."""
        ruta = Path(datos.pdf)
        if not ruta.is_file() or libros not in ruta.resolve().parents:
            raise HTTPException(422, f"El PDF tiene que estar en {libros}")
        try:
            destino = ocr.ocr(ruta, datos.idiomas)
        except RuntimeError as e:
            raise HTTPException(500, str(e))
        return {"ruta": str(destino)}

    @app.get("/api/impresoras")
    def ver_impresoras():
        nombres, predeterminada = imprimir.impresoras()
        return {"impresoras": nombres,
                "predeterminada": os.environ.get("ATRIL_IMPRESORA") or predeterminada}

    @app.get("/api/proyectos")
    def proyectos():
        lista = []
        for archivo in sorted(raiz.glob("*/libro.json")):
            p = proyecto(archivo.parent.name)
            lista.append({"slug": p.slug, "titulo": p.titulo, "partes": len(p.datos["partes"]),
                          "referencia": p.datos.get("referencia") is not None})
        return lista

    @app.post("/api/proyectos")
    def nuevo(datos: NuevoProyecto):
        if not SLUG.fullmatch(datos.slug):
            raise HTTPException(422, "El nombre corto solo admite minúsculas, números y guiones")
        if (raiz / datos.slug / "libro.json").exists():
            raise HTTPException(409, f"Ya existe el proyecto {datos.slug!r}")
        for pdf in (datos.original, datos.referencia):
            if pdf and not Path(pdf).is_file():
                raise HTTPException(422, f"No existe el PDF {pdf}")
        with candado:
            p = Proyecto.crear(datos.slug, datos.titulo or Path(datos.original).stem,
                               datos.original, datos.idioma_original, datos.referencia,
                               datos.idioma_referencia, raiz=raiz)
        abiertos[p.slug] = p
        return detalle(p)

    @app.get("/api/proyectos/{slug}")
    def ver(slug: str):
        p = proyecto(slug)
        with candado:
            return detalle(p)

    @app.get("/api/proyectos/{slug}/{lado}/pagina/{numero}")
    def pagina(slug: str, lado: str, numero: int, ancho: int = miniaturas.ANCHOS[0]):
        lib = libro(slug, lado)
        if not 1 <= numero <= len(lib):
            raise HTTPException(404, f"No existe la página {numero}")
        if ancho not in miniaturas.ANCHOS:
            raise HTTPException(422, f"Ancho no permitido; usa {miniaturas.ANCHOS}")
        with candado:
            datos = miniaturas.imagen(lib.doc, lib.ruta, numero, ancho, cache)
        return Response(datos, media_type="image/jpeg",
                        headers={"Cache-Control": "max-age=86400"})

    @app.get("/api/proyectos/{slug}/{lado}/palabras")
    def palabras(slug: str, lado: str):
        """Palabras por página, para el contador de la selección."""
        lib = libro(slug, lado)
        with candado:
            return [len(re.findall(r"\w+", t)) for t in lib.textos]

    @app.get("/api/proyectos/{slug}/{lado}/buscar")
    def buscar(slug: str, lado: str, q: str = Query(min_length=2)):
        lib = libro(slug, lado)
        termino = _plano(q.strip())
        with candado:
            return [n for n, t in enumerate(lib.textos, start=1) if termino in _plano(t)]

    @app.post("/api/proyectos/{slug}/anclas")
    def anclar(slug: str, ancla: Ancla):
        p = proyecto(slug)
        if p.referencia is None:
            raise HTTPException(422, "Este proyecto no tiene PDF de referencia")
        if not (1 <= ancla.referencia <= len(p.referencia)
                and 1 <= ancla.original <= len(p.original)):
            raise HTTPException(422, "Página fuera de rango")
        with candado:
            p.anclar(ancla.referencia, ancla.original)
        return {"mapa": p.mapa, "anclas": p.anclas}

    @app.delete("/api/proyectos/{slug}/anclas/{referencia}")
    def desanclar(slug: str, referencia: int):
        p = proyecto(slug)
        with candado:
            p.desanclar(referencia)
        return {"mapa": p.mapa, "anclas": p.anclas}

    @app.post("/api/proyectos/{slug}/exportar")
    def exportar(slug: str, datos: Exportacion):
        p = proyecto(slug)
        if not PARTE.fullmatch(datos.parte):
            raise HTTPException(422, "El id de la parte solo admite letras, números, . _ y -")
        if datos.original is None and datos.referencia is None:
            raise HTTPException(422, "Elige páginas en al menos uno de los dos PDFs")
        with candado:
            try:
                contexto = paquete.exportar(p, datos.parte, datos.original, datos.referencia,
                                            datos.instrucciones, datos.titulo_parte,
                                            idioma_destino=datos.idioma_destino)
            except ValueError as e:
                raise HTTPException(422, str(e))
        texto = contexto.read_text(encoding="utf-8")
        figuras = len(list((contexto.parent / "figuras").iterdir()))
        return {"contexto": str(contexto), "carpeta": str(contexto.parent),
                "comando": f"/libro {contexto.parent}", "figuras": figuras,
                "caracteres": len(texto), "partes": partes(p)}

    @app.get("/api/proyectos/{slug}/partes/{parte}/pdf")
    def ver_pdf(slug: str, parte: str, tipo: str = "carta"):
        ruta = pdf_de_parte(proyecto(slug), parte, tipo)
        if not ruta or not ruta.exists():
            raise HTTPException(404, "Esa parte todavía no tiene ese PDF construido")
        return FileResponse(ruta, media_type="application/pdf",
                            content_disposition_type="inline")

    @app.post("/api/proyectos/{slug}/partes/{parte}/imprimir")
    def mandar_a_imprimir(slug: str, parte: str, datos: Impresion):
        ruta = pdf_de_parte(proyecto(slug), parte, datos.tipo)
        if not ruta or not ruta.exists():
            raise HTTPException(404, "Esa parte todavía no tiene ese PDF construido")
        try:
            cmd, mensaje = imprimir.imprimir(ruta, copias=datos.copias, paginas=datos.paginas,
                                             titulo=parte, simular=datos.simular)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(422, str(e))
        return {"comando": cmd, "mensaje": mensaje}

    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
    return app


def servir(puerto=8765, abrir=True):
    import webbrowser

    import uvicorn

    url = f"http://127.0.0.1:{puerto}"
    print(f"Atril en {url} (Ctrl+C para salir)")
    if abrir:
        threading.Timer(1.0, webbrowser.open, [url]).start()
    uvicorn.run(crear_app(), host="127.0.0.1", port=puerto, log_level="warning")
