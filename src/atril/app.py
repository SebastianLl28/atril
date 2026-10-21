"""Visual app: FastAPI backend serving projects, thumbnails, TOC, search, map and export.

The frontend (web/) is plain HTML + JS with no build step. Started with `uv run atril app`.
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

from . import bundle, thumbnails
from .build import Output
from .pdf import is_image_only
from .project import ROOT, Project

BOOKS = Path(os.environ.get("ATRIL_LIBROS", "~/Documents/books")).expanduser()
WEB = Path(__file__).parent / "web"
SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")
PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
SIDES = {"original": "original", "referencia": "reference"}  # API side → Project attribute


def _plain(text):
    """Lowercase and without accents, so search ignores them."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


class NewProject(BaseModel):
    slug: str
    titulo: str = ""
    original: str
    referencia: str | None = None
    idioma_original: str = "en"
    idioma_referencia: str = "es"


class Anchor(BaseModel):
    referencia: int
    original: int


class SourcePdf(BaseModel):
    pdf: str
    paginas: tuple[int, int]


class Sources(BaseModel):
    notas: str = ""
    enlaces: list[str] = []
    pdfs: list[SourcePdf] = []


class Task(BaseModel):
    traducir: str | None = None
    mejorar_lectura: bool = True
    comentarios: bool = False
    contexto: bool = False
    resumen: bool = False


class Export(BaseModel):
    parte: str
    original: tuple[int, int] | None = None
    referencia: tuple[int, int] | None = None
    instrucciones: str = ""
    titulo_parte: str | None = None
    tarea: Task = Task()
    fuentes: Sources = Sources()


def create_app(root=None, books=None, cache=None):
    root = Path(root or ROOT)
    books = Path(books or BOOKS)
    app = FastAPI(title="Atril")
    open_projects = {}  # slug → Project, with its PDFs and texts already loaded
    image_only = {}  # (path, mtime) → image-only?, so each PDF is measured once
    lock = threading.RLock()  # PyMuPDF is not thread-safe

    def project(slug):
        with lock:
            if slug not in open_projects:
                try:
                    open_projects[slug] = Project(slug, root=root)
                except FileNotFoundError as e:
                    raise HTTPException(404, str(e))
            return open_projects[slug]

    def book(slug, side):
        if side not in SIDES:
            raise HTTPException(404, f"Lado desconocido: {side}")
        with lock:  # opens the PDF the first time
            b = getattr(project(slug), SIDES[side])
        if b is None:
            raise HTTPException(404, "Este proyecto no tiene PDF de referencia")
        return b

    def side_summary(p, side):
        b = getattr(p, SIDES[side])
        if b is None:
            return None
        rect = b.doc[0].rect
        return {"pdf": str(b.path), "nombre": unicodedata.normalize("NFC", b.path.name),
                "idioma": p.data[side]["idioma"], "paginas": len(b),
                "proporcion": rect.height / rect.width, "indice": b.toc(),
                "indice_detectado": not b.has_toc}

    def part_pdf(p, part, kind):
        if not PART.fullmatch(part):
            raise HTTPException(422, "Id de parte inválido")
        try:
            out = Output(p.dir / part)
        except FileNotFoundError:
            return None
        return {"carta": out.pdf, "2x1": out.pdf_2up}.get(kind)

    def parts(p):
        """History: the parts in libro.json, with which built PDFs exist."""
        result = []
        for x in p.data["partes"]:
            pdfs = {k: bool((path := part_pdf(p, x["id"], k)) and path.exists())
                    for k in ("carta", "2x1")}
            result.append({**x, "pdfs": pdfs})
        return result

    def detail(p):
        return {"slug": p.slug, "titulo": p.title, "dir": str(p.dir),
                "original": side_summary(p, "original"),
                "referencia": side_summary(p, "referencia"),
                "mapa": p.map, "anclas": p.anchors, "partes": parts(p)}

    def page_count(path):
        try:
            with lock:
                return len(thumbnails.pymupdf.open(path))
        except Exception:
            return 0

    def lacks_text(path):
        key = (str(path), path.stat().st_mtime_ns)
        if key not in image_only:
            try:
                image_only[key] = is_image_only(path)
            except Exception:  # damaged or encrypted PDF: let opening it report the error
                image_only[key] = False
        return image_only[key]

    @app.get("/api/pdfs")
    def pdfs():
        """PDFs in the books folder, excluding those generated inside projects."""
        found = [f for f in books.rglob("*.pdf") if root not in f.parents]
        return [{"ruta": str(f),
                 "nombre": unicodedata.normalize("NFC", str(f.relative_to(books))),
                 "paginas": page_count(f), "solo_imagenes": lacks_text(f)}
                for f in sorted(found, key=lambda f: str(f).lower())]

    @app.get("/api/proyectos")
    def list_projects():
        result = []
        for file in sorted(root.glob("*/libro.json")):
            p = project(file.parent.name)
            result.append({"slug": p.slug, "titulo": p.title, "partes": len(p.data["partes"]),
                           "referencia": p.data.get("referencia") is not None})
        return result

    @app.post("/api/proyectos")
    def new_project(data: NewProject):
        if not SLUG.fullmatch(data.slug):
            raise HTTPException(422, "El nombre corto solo admite minúsculas, números y guiones")
        if (root / data.slug / "libro.json").exists():
            raise HTTPException(409, f"Ya existe el proyecto {data.slug!r}")
        for pdf in (data.original, data.referencia):
            if pdf and not Path(pdf).is_file():
                raise HTTPException(422, f"No existe el PDF {pdf}")
        with lock:
            try:
                p = Project.create(data.slug, data.titulo or Path(data.original).stem,
                                   data.original, data.idioma_original, data.referencia,
                                   data.idioma_referencia, root=root)
            except ValueError as e:  # image-only PDF
                raise HTTPException(422, str(e))
        open_projects[p.slug] = p
        return detail(p)

    @app.get("/api/proyectos/{slug}")
    def get_project(slug: str):
        p = project(slug)
        with lock:
            return detail(p)

    @app.get("/api/proyectos/{slug}/{lado}/pagina/{numero}")
    def page(slug: str, lado: str, numero: int, ancho: int = thumbnails.WIDTHS[0]):
        b = book(slug, lado)
        if not 1 <= numero <= len(b):
            raise HTTPException(404, f"No existe la página {numero}")
        if ancho not in thumbnails.WIDTHS:
            raise HTTPException(422, f"Ancho no permitido; usa {thumbnails.WIDTHS}")
        with lock:
            data = thumbnails.image(b.doc, b.path, numero, ancho, cache)
        return Response(data, media_type="image/jpeg",
                        headers={"Cache-Control": "max-age=86400"})

    @app.get("/api/proyectos/{slug}/{lado}/palabras")
    def words(slug: str, lado: str):
        """Words per page, for the selection counter."""
        b = book(slug, lado)
        with lock:
            return [len(re.findall(r"\w+", t)) for t in b.texts]

    @app.get("/api/proyectos/{slug}/{lado}/buscar")
    def search(slug: str, lado: str, q: str = Query(min_length=2)):
        b = book(slug, lado)
        term = _plain(q.strip())
        with lock:
            return [n for n, t in enumerate(b.texts, start=1) if term in _plain(t)]

    @app.post("/api/proyectos/{slug}/anclas")
    def add_anchor(slug: str, anchor: Anchor):
        p = project(slug)
        if p.reference is None:
            raise HTTPException(422, "Este proyecto no tiene PDF de referencia")
        if not (1 <= anchor.referencia <= len(p.reference)
                and 1 <= anchor.original <= len(p.original)):
            raise HTTPException(422, "Página fuera de rango")
        with lock:
            p.anchor(anchor.referencia, anchor.original)
        return {"mapa": p.map, "anclas": p.anchors}

    @app.delete("/api/proyectos/{slug}/anclas/{referencia}")
    def remove_anchor(slug: str, referencia: int):
        p = project(slug)
        with lock:
            p.unanchor(referencia)
        return {"mapa": p.map, "anclas": p.anchors}

    @app.post("/api/proyectos/{slug}/exportar")
    def export(slug: str, data: Export):
        p = project(slug)
        if not PART.fullmatch(data.parte):
            raise HTTPException(422, "El id de la parte solo admite letras, números, . _ y -")
        if data.original is None and data.referencia is None:
            raise HTTPException(422, "Elige páginas en al menos uno de los dos PDFs")
        for f in data.fuentes.pdfs:
            if books not in Path(f.pdf).expanduser().resolve().parents:
                raise HTTPException(422, f"Los PDFs de apoyo tienen que estar en {books}")
        with lock:
            try:
                context = bundle.export(p, data.parte, data.original, data.referencia,
                                        data.instrucciones, data.titulo_parte,
                                        task=data.tarea.model_dump(),
                                        sources=data.fuentes.model_dump())
            except ValueError as e:
                raise HTTPException(422, str(e))
        text = context.read_text(encoding="utf-8")
        figures = len(list((context.parent / "figuras").iterdir()))
        return {"contexto": str(context), "carpeta": str(context.parent),
                "comando": f"/libro {context.parent}", "figuras": figures,
                "caracteres": len(text), "partes": parts(p)}

    @app.get("/api/proyectos/{slug}/partes/{parte}/pdf")
    def get_pdf(slug: str, parte: str, tipo: str = "carta"):
        path = part_pdf(project(slug), parte, tipo)
        if not path or not path.exists():
            raise HTTPException(404, "Esa parte todavía no tiene ese PDF construido")
        return FileResponse(path, media_type="application/pdf",
                            content_disposition_type="inline")

    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
    return app


def serve(port=8765, open_browser=True, host=None):
    import webbrowser

    import uvicorn

    host = host or os.environ.get("ATRIL_HOST", "127.0.0.1")
    url = f"http://{host}:{port}"
    print(f"Atril en {url} (Ctrl+C para salir)")
    if open_browser:
        threading.Timer(1.0, webbrowser.open, [url]).start()
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")
