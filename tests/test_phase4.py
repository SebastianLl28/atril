"""Phase 4 tests: detected TOC, image-only PDFs, printing and history in the app.

Printing never reaches the printer: it is either a dry run or a fake `lp` on the PATH.
"""

import os
import shutil
import stat

import pymupdf
import pytest
from fastapi.testclient import TestClient

from atril import cli, printing
from atril.app import create_app
from atril.pdf import Book, is_image_only
from atril.project import Project

from test_part_iii import EN


def _book_without_toc(path):
    doc = pymupdf.open()
    body = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod."
    for title, section in [("Capítulo uno", "Primera sección"), (None, "Otra sección"),
                           ("Capítulo dos", None)]:
        page = doc.new_page()
        y = 80
        if title:
            page.insert_text((72, y), title, fontsize=24)
            y += 50
        if section:
            page.insert_text((72, y), section, fontsize=15, fontname="hebo")  # bold
            y += 30
        for _ in range(20):
            page.insert_text((72, y), body, fontsize=11)
            y += 16
    doc.save(path)


def test_detected_toc_without_outline(tmp_path):
    _book_without_toc(tmp_path / "libro.pdf")
    book = Book(tmp_path / "libro.pdf")
    assert not book.has_toc
    assert book.toc() == [(1, "Capítulo uno", 1), (2, "Primera sección", 1),
                          (2, "Otra sección", 2), (1, "Capítulo dos", 3)]


@pytest.mark.skipif(not EN, reason="faltan los PDFs del libro")
def test_detected_toc_matches_the_real_one():
    book = Book(EN)
    detected = {(t, p) for n, t, p in book.detected_toc if n == 1}
    assert ("7 SRP: THE SINGLE RESPONSIBILITY PRINCIPLE", 64) in detected
    assert ("12 COMPONENTS", 88) in detected
    chapters = [p for n, t, p in book.toc() if n == 2 and t.startswith("Chapter")]
    hits = {p for _, p in detected}
    assert sum(p in hits for p in chapters) / len(chapters) > 0.95


def _scanned(path):
    """One-page PDF that is just an image of text (like a scan)."""
    source = pymupdf.open()
    source.new_page().insert_text((72, 120), "Arquitectura limpia componentes", fontsize=28)
    pix = source[0].get_pixmap(dpi=200)
    doc = pymupdf.open()
    doc.new_page().insert_image(doc[0].rect, pixmap=pix)
    doc.save(path)


def test_rejects_image_only_pdfs(tmp_path):
    _scanned(tmp_path / "escaneo.pdf")
    _book_without_toc(tmp_path / "texto.pdf")
    assert is_image_only(tmp_path / "escaneo.pdf")
    assert not is_image_only(tmp_path / "texto.pdf")
    with pytest.raises(ValueError, match="solo imágenes"):
        Project.create("x", "X", tmp_path / "escaneo.pdf", root=tmp_path / "proyectos")
    with pytest.raises(ValueError, match="solo imágenes"):
        Project.create("x", "X", tmp_path / "texto.pdf", reference=tmp_path / "escaneo.pdf",
                       root=tmp_path / "proyectos")
    assert not (tmp_path / "proyectos" / "x").exists()


@pytest.fixture
def fake_lp(tmp_path, monkeypatch):
    """An `lp` that only logs its arguments; first on the PATH."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    log = tmp_path / "lp.log"
    lp = bin_ / "lp"
    lp.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{log}"\n'
                  'echo "request id is Falsa-1 (1 file(s))"\n')
    lp.chmod(lp.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.delenv("ATRIL_IMPRESORA", raising=False)
    assert shutil.which("lp") == str(lp)
    return log


def test_print_command():
    assert printing.command("x.pdf", "Epson", 2, "1-3", "parte") == [
        "lp", "-d", "Epson", "-n", "2", "-o", "media=Letter", "-o", "fit-to-page",
        "-P", "1-3", "-t", "parte", "x.pdf"]
    cmd, message = printing.print_pdf("x.pdf", dry_run=True)
    assert cmd[0] == "lp" and "simulado" in message
    with pytest.raises(ValueError):
        printing.print_pdf("x.pdf", pages="1; rm -rf /", dry_run=True)
    with pytest.raises(ValueError):
        printing.print_pdf("x.pdf", copies=0, dry_run=True)


@pytest.fixture
def built_part(tmp_path):
    """Project with a part that already has its PDFs in salida/ (skipping WeasyPrint)."""
    _book_without_toc(tmp_path / "orig.pdf")
    root = tmp_path / "proyectos"
    p = Project.create("demo", "Demo", tmp_path / "orig.pdf", root=root)
    folder = p.dir / "cap-1"
    (folder / "salida").mkdir(parents=True)
    (folder / "contexto.md").write_text("---\n---\n", encoding="utf-8")
    for name in ("cap-1.pdf", "cap-1-2-por-hoja.pdf"):
        shutil.copy(tmp_path / "orig.pdf", folder / "salida" / name)
    p.register_part({"id": "cap-1", "titulo": "Capítulo 1", "original": "1-3",
                     "referencia": None, "estado": "construida"})
    return root, folder


def test_cli_print(built_part, fake_lp, capsys):
    _, folder = built_part
    cli.main(["imprimir", str(folder), "--simular"])
    assert "simulado" in capsys.readouterr().out and not fake_lp.exists()
    cli.main(["imprimir", str(folder), "--2-por-hoja", "--copias", "2"])
    args = fake_lp.read_text()
    assert "-n 2" in args and args.strip().endswith("cap-1-2-por-hoja.pdf")


def test_app_history_pdf_and_printing(built_part, fake_lp, tmp_path):
    root, _ = built_part
    c = TestClient(create_app(root=root, books=tmp_path, cache=tmp_path / "cache"))
    d = c.get("/api/proyectos/demo").json()
    assert d["partes"][0]["pdfs"] == {"carta": True, "2x1": True}
    assert d["original"]["indice_detectado"] is True
    assert d["original"]["indice"][0] == [1, "Capítulo uno", 1]

    r = c.get("/api/proyectos/demo/partes/cap-1/pdf?tipo=2x1")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert c.get("/api/proyectos/demo/partes/nada/pdf").status_code == 404

    url = "/api/proyectos/demo/partes/cap-1/imprimir"
    r = c.post(url, json={"tipo": "carta", "copias": 1, "simular": True}).json()
    assert "simulado" in r["mensaje"] and not fake_lp.exists()
    r = c.post(url, json={"tipo": "carta", "copias": 3, "paginas": "1-2"}).json()
    assert "Falsa-1" in r["mensaje"]
    assert "-n 3" in fake_lp.read_text() and "-P 1-2" in fake_lp.read_text()
    assert c.post(url, json={"paginas": "1;x"}).status_code == 422


def test_app_flags_and_rejects_image_only_pdfs(tmp_path):
    _scanned(tmp_path / "escaneo.pdf")
    _book_without_toc(tmp_path / "texto.pdf")
    c = TestClient(create_app(root=tmp_path / "proyectos", books=tmp_path,
                              cache=tmp_path / "cache"))
    flags = {f["nombre"]: f["solo_imagenes"] for f in c.get("/api/pdfs").json()}
    assert flags == {"escaneo.pdf": True, "texto.pdf": False}
    r = c.post("/api/proyectos", json={"slug": "x", "original": str(tmp_path / "escaneo.pdf")})
    assert r.status_code == 422 and "solo imágenes" in r.json()["detail"]
