"""Pruebas de la app visual (Fase 3): API con PDFs sintéticos y, si están los PDFs del libro,
la verificación del plan: exportar la Parte III desde la app da el mismo paquete que la CLI.
"""

import filecmp

import pymupdf
import pytest
from fastapi.testclient import TestClient

from atril import cli
from atril.app import crear_app

from test_parte_iii import EN, ES


def _pdf(ruta, paginas, toc=()):
    doc = pymupdf.open()
    for texto in paginas:
        doc.new_page().insert_text((72, 100), texto, fontsize=12)
    if toc:
        doc.set_toc(list(toc))
    doc.save(ruta)


@pytest.fixture
def cliente(tmp_path):
    libros = tmp_path / "books"
    libros.mkdir()
    _pdf(libros / "orig.pdf", [f"Chapter {n} Introduction PageObject{n} Liskov" for n in range(1, 7)],
         toc=[(1, "Part I", 1), (2, "Chapter 1", 2), (2, "Chapter 2", 4)])
    _pdf(libros / "ref.pdf", [f"Capítulo PageObject{n} Lískov" for n in (1, 2, 2, 3, 4, 5, 6)])
    app = crear_app(raiz=libros / "proyectos", libros=libros, cache=tmp_path / "cache")
    return TestClient(app), libros, tmp_path


def _crear(c, libros, **extra):
    datos = {"slug": "demo", "titulo": "Demo", "original": str(libros / "orig.pdf"),
             "referencia": str(libros / "ref.pdf"), **extra}
    r = c.post("/api/proyectos", json=datos)
    assert r.status_code == 200, r.text
    return r.json()


def test_frontend_se_sirve(cliente):
    c, _, _ = cliente
    r = c.get("/")
    assert r.status_code == 200 and "<title>Atril</title>" in r.text
    assert c.get("/app.js").status_code == 200


def test_crear_proyecto_y_detalle(cliente):
    c, libros, _ = cliente
    assert {f["nombre"] for f in c.get("/api/pdfs").json()} == {"orig.pdf", "ref.pdf"}
    p = _crear(c, libros)
    assert p["original"]["paginas"] == 6 and p["referencia"]["paginas"] == 7
    assert p["original"]["indice"][1] == [2, "Chapter 1", 2]
    assert p["mapa"] == [1, 2, 2, 3, 4, 5, 6]
    assert c.get("/api/proyectos").json()[0]["slug"] == "demo"
    assert c.post("/api/proyectos", json={"slug": "demo", "original": str(libros / "orig.pdf")}
                  ).status_code == 409
    assert c.post("/api/proyectos", json={"slug": "Mal Nombre", "original": "x"}).status_code == 422


def test_miniaturas_con_cache(cliente):
    c, libros, tmp = cliente
    _crear(c, libros)
    r = c.get("/api/proyectos/demo/original/pagina/2")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == b"\xff\xd8"
    assert len(list((tmp / "cache").rglob("p-0002.jpg"))) == 1
    assert c.get("/api/proyectos/demo/original/pagina/2").content == r.content
    assert c.get("/api/proyectos/demo/original/pagina/99").status_code == 404
    assert c.get("/api/proyectos/demo/original/pagina/1?ancho=333").status_code == 422


def test_buscar_sin_tildes_y_palabras(cliente):
    c, libros, _ = cliente
    _crear(c, libros)
    assert c.get("/api/proyectos/demo/referencia/buscar?q=liskov").json() == list(range(1, 8))
    assert c.get("/api/proyectos/demo/original/buscar?q=pageobject3").json() == [3]
    assert c.get("/api/proyectos/demo/original/palabras").json() == [5] * 6


def test_anclas(cliente):
    c, libros, _ = cliente
    _crear(c, libros)
    r = c.post("/api/proyectos/demo/anclas", json={"referencia": 3, "original": 3}).json()
    assert r["anclas"] == {"3": 3} and r["mapa"][2] == 3
    r = c.delete("/api/proyectos/demo/anclas/3").json()
    assert r["anclas"] == {} and r["mapa"][2] == 2


def test_exportar(cliente):
    c, libros, _ = cliente
    _crear(c, libros)
    r = c.post("/api/proyectos/demo/exportar", json={
        "parte": "cap-1", "original": [2, 3], "referencia": [2, 4],
        "instrucciones": "Traducir.", "titulo_parte": "Capítulo 1"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["comando"] == f"/libro {d['carpeta']}"
    texto = open(d["contexto"], encoding="utf-8").read()
    assert 'paginas: "2-3"' in texto and 'paginas: "2-4"' in texto and "Traducir." in texto
    assert d["partes"][0]["id"] == "cap-1"
    assert c.post("/api/proyectos/demo/exportar", json={"parte": "../fuera", "original": [1, 1]}
                  ).status_code == 422


@pytest.mark.skipif(not (EN and ES), reason="faltan los PDFs del libro")
def test_parte_iii_app_igual_que_cli(tmp_path, monkeypatch):
    raiz = tmp_path / "proyectos"
    c = TestClient(crear_app(raiz=raiz, libros=EN.parent, cache=tmp_path / "cache"))
    _crear(c, EN.parent, slug="al", titulo="Arquitectura Limpia", original=str(EN),
           referencia=str(ES))
    notas = tmp_path / "notas.txt"
    notas.write_text("Traducir y revisar.", encoding="utf-8")

    monkeypatch.setattr("atril.proyecto.RAIZ", raiz)
    cli.main(["exportar", "al", "p3-cli", "--original", "62-86", "--instrucciones", str(notas),
              "--titulo-parte", "III · Principios de diseño"])
    r = c.post("/api/proyectos/al/exportar", json={
        "parte": "p3-app", "original": [62, 86], "referencia": [77, 108],
        "instrucciones": "Traducir y revisar.", "titulo_parte": "III · Principios de diseño"})
    assert r.status_code == 200, r.text

    a, b = raiz / "al" / "p3-cli", raiz / "al" / "p3-app"
    texto_a = (a / "contexto.md").read_text(encoding="utf-8").replace(str(a), "PARTE")
    texto_b = (b / "contexto.md").read_text(encoding="utf-8").replace(str(b), "PARTE")
    assert texto_a == texto_b
    comparacion = filecmp.dircmp(a / "figuras", b / "figuras")
    assert not comparacion.diff_files and not comparacion.left_only and not comparacion.right_only
    assert len(comparacion.same_files) == len(list((a / "figuras").iterdir())) >= 20
