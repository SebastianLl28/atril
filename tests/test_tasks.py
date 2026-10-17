"""Tests for each part's task (translate or not, comments, context…) and for the extra
sources (notes, links, pages from other PDFs). They use synthetic PDFs.
"""

import json

import pymupdf
import pytest
from fastapi.testclient import TestClient

from atril import build, bundle, cli
from atril.app import create_app
from atril.project import Project


def _pdf(path, pages):
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        for i, line in enumerate(text.split("\n")):
            page.insert_text((72, 100 + 16 * i), line, fontsize=11)
    doc.save(path)


def _scanned(path):
    source = pymupdf.open()
    source.new_page().insert_text((72, 120), "Texto escaneado", fontsize=28)
    doc = pymupdf.open()
    doc.new_page().insert_image(doc[0].rect, pixmap=source[0].get_pixmap(dpi=100))
    doc.save(path)


@pytest.fixture
def env(tmp_path):
    books = tmp_path / "books"
    books.mkdir()
    _pdf(books / "informe.pdf", [f"Quarterly report section {n}.\nRevenue grew steadily."
                                 for n in range(1, 5)])
    _pdf(books / "apuntes.pdf", [f"Apunte {n}: el contexto histórico importa." for n in range(1, 4)])
    _scanned(books / "escaneo.pdf")
    p = Project.create("informe", "Informe trimestral", books / "informe.pdf", "en",
                       root=books / "proyectos")
    return p, books


def test_keeps_language_by_default(env):
    p, _ = env
    text = bundle.export(p, "sec-1", original=(1, 2)).read_text(encoding="utf-8")
    assert "tarea: { traducir: null, mejorar_lectura: true, comentarios: false" in text
    assert 'idioma_salida: "en"' in text
    assert "- Mantener el idioma del documento (en)" in text
    assert "Traducir" not in text.split("# Instrucciones")[0]
    assert "# Fuentes adicionales" not in text


def test_translate_and_enrich_with_sources(env):
    p, books = env
    task = {"traducir": "ES", "comentarios": True, "contexto": True, "resumen": True}
    sources = {"notas": "El autor escribió esto en 2019.",
               "enlaces": ["https://example.com/contexto", "  "],
               "pdfs": [{"pdf": str(books / "apuntes.pdf"), "paginas": (2, 3)}]}
    text = bundle.export(p, "sec-2", original=(3, 4), task=task,
                         sources=sources).read_text(encoding="utf-8")
    assert 'idioma_salida: "es"' in text
    assert "- Traducir del en al es, fiel al documento." in text
    assert "- Comentarios de estudio" in text and "- Contexto" in text and "- Resumen final" in text
    sources_md = text.split("# Fuentes adicionales")[1].split("# Contenido")[0]
    assert "## Notas\n\nEl autor escribió esto en 2019." in sources_md
    assert "- https://example.com/contexto" in sources_md and "- \n" not in sources_md
    assert "## PDF · apuntes.pdf · p.2-3" in sources_md
    assert "Apunte 2" in sources_md and "Apunte 3" in sources_md and "Apunte 1" not in sources_md
    part = json.loads(p.file.read_text(encoding="utf-8"))["partes"][-1]
    assert part["tarea"]["traducir"] == "es" and part["tarea"]["resumen"] is True
    assert part["fuentes"]["enlaces"] == ["https://example.com/contexto"]
    assert part["fuentes"]["pdfs"] == [{"pdf": str(books / "apuntes.pdf"), "paginas": "2-3"}]


def test_invalid_sources(env):
    p, books = env
    with pytest.raises(ValueError, match="solo imágenes"):
        bundle.export(p, "x", original=(1, 1),
                      sources={"pdfs": [{"pdf": str(books / "escaneo.pdf"), "paginas": (1, 1)}]})
    with pytest.raises(ValueError, match="rango"):
        bundle.export(p, "x", original=(1, 1),
                      sources={"pdfs": [{"pdf": str(books / "apuntes.pdf"), "paginas": (2, 9)}]})
    with pytest.raises(ValueError, match="desconocida"):
        bundle.export(p, "x", original=(1, 1), task={"resumir": True})


def test_cover_follows_the_task(env):
    p, _ = env
    folder = bundle.export(p, "sin-traducir", original=(1, 1)).parent
    html = build.init(folder).read_text(encoding="utf-8")
    assert '<html lang="en">' in html and "transcripción fiel del original" in html
    assert "traducción" not in html

    folder = bundle.export(p, "traducida", original=(1, 1),
                           task={"traducir": "es", "comentarios": True}).parent
    html = build.init(folder).read_text(encoding="utf-8")
    assert '<html lang="es">' in html and "traducción fiel del original" in html
    assert "recuadros de comentario" in html


def test_cli_export_with_task_and_sources(env, tmp_path, monkeypatch):
    p, books = env
    monkeypatch.setattr("atril.project.ROOT", books / "proyectos")
    notes = tmp_path / "notas.md"
    notes.write_text("Contexto pegado.", encoding="utf-8")
    cli.main(["exportar", "informe", "cli", "--original", "1-2", "--traducir", "es",
              "--comentarios", "--notas", str(notes), "--enlace", "https://a.org",
              "--pdf", f"{books / 'apuntes.pdf'}:1-2"])
    text = (p.dir / "cli" / "contexto.md").read_text(encoding="utf-8")
    assert "traducir: \"es\"" in text and "comentarios: true" in text
    assert "Contexto pegado." in text and "https://a.org" in text and "Apunte 1" in text


def test_app_exports_task_and_sources(env, tmp_path):
    p, books = env
    c = TestClient(create_app(root=books / "proyectos", books=books, cache=tmp_path / "c"))
    pdfs = {f["nombre"]: f for f in c.get("/api/pdfs").json()}
    assert pdfs["apuntes.pdf"]["paginas"] == 3 and pdfs["escaneo.pdf"]["solo_imagenes"]
    body = {"parte": "app", "original": [1, 2],
            "tarea": {"traducir": "es", "contexto": True},
            "fuentes": {"notas": "nota", "enlaces": ["https://b.org"],
                        "pdfs": [{"pdf": str(books / "apuntes.pdf"), "paginas": [1, 1]}]}}
    r = c.post("/api/proyectos/informe/exportar", json=body)
    assert r.status_code == 200, r.text
    part = r.json()["partes"][-1]
    assert part["tarea"]["contexto"] is True and part["fuentes"]["enlaces"] == ["https://b.org"]
    body["fuentes"]["pdfs"] = [{"pdf": "/etc/hosts.pdf", "paginas": [1, 1]}]
    assert c.post("/api/proyectos/informe/exportar", json=body).status_code == 422
