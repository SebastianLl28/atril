"""Visual app tests: the API with synthetic PDFs and, when the book PDFs are present,
the plan's check that exporting Part III from the app gives the same bundle as the CLI.
"""

import filecmp

import pymupdf
import pytest
from fastapi.testclient import TestClient

from atril import cli
from atril.app import create_app

from test_part_iii import EN, ES


def _pdf(path, pages, toc=()):
    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 100), text, fontsize=12)
    if toc:
        doc.set_toc(list(toc))
    doc.save(path)


@pytest.fixture
def client(tmp_path):
    books = tmp_path / "books"
    books.mkdir()
    _pdf(books / "orig.pdf", [f"Chapter {n} Introduction PageObject{n} Liskov" for n in range(1, 7)],
         toc=[(1, "Part I", 1), (2, "Chapter 1", 2), (2, "Chapter 2", 4)])
    _pdf(books / "ref.pdf", [f"Capítulo PageObject{n} Lískov" for n in (1, 2, 2, 3, 4, 5, 6)])
    app = create_app(root=books / "proyectos", books=books, cache=tmp_path / "cache")
    return TestClient(app), books, tmp_path


def _create(c, books, **extra):
    data = {"slug": "demo", "titulo": "Demo", "original": str(books / "orig.pdf"),
             "referencia": str(books / "ref.pdf"), **extra}
    r = c.post("/api/proyectos", json=data)
    assert r.status_code == 200, r.text
    return r.json()


def test_frontend_is_served(client):
    c, _, _ = client
    r = c.get("/")
    assert r.status_code == 200 and "<title>Atril</title>" in r.text
    assert c.get("/app.js").status_code == 200


def test_create_project_and_detail(client):
    c, books, _ = client
    assert {f["nombre"] for f in c.get("/api/pdfs").json()} == {"orig.pdf", "ref.pdf"}
    p = _create(c, books)
    assert p["original"]["paginas"] == 6 and p["referencia"]["paginas"] == 7
    assert p["original"]["indice"][1] == [2, "Chapter 1", 2]
    assert p["mapa"] == [1, 2, 2, 3, 4, 5, 6]
    assert c.get("/api/proyectos").json()[0]["slug"] == "demo"
    assert c.post("/api/proyectos", json={"slug": "demo", "original": str(books / "orig.pdf")}
                  ).status_code == 409
    assert c.post("/api/proyectos", json={"slug": "Mal Nombre", "original": "x"}).status_code == 422


def test_thumbnails_with_cache(client):
    c, books, tmp = client
    _create(c, books)
    r = c.get("/api/proyectos/demo/original/pagina/2")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == b"\xff\xd8"
    assert len(list((tmp / "cache").rglob("p-0002.jpg"))) == 1
    assert c.get("/api/proyectos/demo/original/pagina/2").content == r.content
    assert c.get("/api/proyectos/demo/original/pagina/99").status_code == 404
    assert c.get("/api/proyectos/demo/original/pagina/1?ancho=333").status_code == 422


def test_accent_insensitive_search_and_words(client):
    c, books, _ = client
    _create(c, books)
    assert c.get("/api/proyectos/demo/referencia/buscar?q=liskov").json() == list(range(1, 8))
    assert c.get("/api/proyectos/demo/original/buscar?q=pageobject3").json() == [3]
    assert c.get("/api/proyectos/demo/original/palabras").json() == [5] * 6


def test_anchors(client):
    c, books, _ = client
    _create(c, books)
    r = c.post("/api/proyectos/demo/anclas", json={"referencia": 3, "original": 3}).json()
    assert r["anclas"] == {"3": 3} and r["mapa"][2] == 3
    r = c.delete("/api/proyectos/demo/anclas/3").json()
    assert r["anclas"] == {} and r["mapa"][2] == 2


def test_export(client):
    c, books, _ = client
    _create(c, books)
    r = c.post("/api/proyectos/demo/exportar", json={
        "parte": "cap-1", "original": [2, 3], "referencia": [2, 4],
        "instrucciones": "Traducir.", "titulo_parte": "Capítulo 1"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["comando"] == f"/libro {d['carpeta']}"
    text = open(d["contexto"], encoding="utf-8").read()
    assert 'paginas: "2-3"' in text and 'paginas: "2-4"' in text and "Traducir." in text
    assert d["partes"][0]["id"] == "cap-1"
    assert c.post("/api/proyectos/demo/exportar", json={"parte": "../fuera", "original": [1, 1]}
                  ).status_code == 422


@pytest.mark.skipif(not (EN and ES), reason="faltan los PDFs del libro")
def test_part_iii_app_same_as_cli(tmp_path, monkeypatch):
    root = tmp_path / "proyectos"
    c = TestClient(create_app(root=root, books=EN.parent, cache=tmp_path / "cache"))
    _create(c, EN.parent, slug="al", titulo="Arquitectura Limpia", original=str(EN),
           referencia=str(ES))
    notes = tmp_path / "notas.txt"
    notes.write_text("Traducir y revisar.", encoding="utf-8")

    monkeypatch.setattr("atril.project.ROOT", root)
    cli.main(["exportar", "al", "p3-cli", "--original", "62-86", "--instrucciones", str(notes),
              "--titulo-parte", "III · Principios de diseño"])
    r = c.post("/api/proyectos/al/exportar", json={
        "parte": "p3-app", "original": [62, 86], "referencia": [77, 108],
        "instrucciones": "Traducir y revisar.", "titulo_parte": "III · Principios de diseño"})
    assert r.status_code == 200, r.text

    a, b = root / "al" / "p3-cli", root / "al" / "p3-app"
    text_a = (a / "contexto.md").read_text(encoding="utf-8").replace(str(a), "PARTE")
    text_b = (b / "contexto.md").read_text(encoding="utf-8").replace(str(b), "PARTE")
    assert text_a == text_b
    comparison = filecmp.dircmp(a / "figuras", b / "figuras")
    assert not comparison.diff_files and not comparison.left_only and not comparison.right_only
    assert len(comparison.same_files) == len(list((a / "figuras").iterdir())) >= 20
