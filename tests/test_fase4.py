"""Pruebas de la Fase 4: índice detectado, OCR, impresión e historial de partes en la app.

La impresión nunca llega a la impresora: o se simula o se usa un `lp` falso en el PATH.
"""

import os
import shutil
import stat

import pymupdf
import pytest
from fastapi.testclient import TestClient

from atril import cli, imprimir, ocr
from atril.app import crear_app
from atril.pdf import Libro
from atril.proyecto import Proyecto

from test_parte_iii import EN


def _libro_sin_indice(ruta):
    doc = pymupdf.open()
    cuerpo = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod."
    for titulo, seccion in [("Capítulo uno", "Primera sección"), (None, "Otra sección"),
                            ("Capítulo dos", None)]:
        page = doc.new_page()
        y = 80
        if titulo:
            page.insert_text((72, y), titulo, fontsize=24)
            y += 50
        if seccion:
            page.insert_text((72, y), seccion, fontsize=15, fontname="hebo")  # negrita
            y += 30
        for _ in range(20):
            page.insert_text((72, y), cuerpo, fontsize=11)
            y += 16
    doc.save(ruta)


def test_indice_detectado_sin_toc(tmp_path):
    _libro_sin_indice(tmp_path / "libro.pdf")
    lib = Libro(tmp_path / "libro.pdf")
    assert not lib.tiene_indice
    assert lib.indice() == [(1, "Capítulo uno", 1), (2, "Primera sección", 1),
                            (2, "Otra sección", 2), (1, "Capítulo dos", 3)]


@pytest.mark.skipif(not EN, reason="faltan los PDFs del libro")
def test_indice_detectado_coincide_con_el_real():
    lib = Libro(EN)
    detectados = {(t, p) for n, t, p in lib.indice_detectado if n == 1}
    assert ("7 SRP: THE SINGLE RESPONSIBILITY PRINCIPLE", 64) in detectados
    assert ("12 COMPONENTS", 88) in detectados
    capitulos = [p for n, t, p in lib.indice() if n == 2 and t.startswith("Chapter")]
    acertados = {p for _, p in detectados}
    assert sum(p in acertados for p in capitulos) / len(capitulos) > 0.95


def _escaneado(ruta):
    """PDF de una página que es solo una imagen con texto (como un escaneo)."""
    origen = pymupdf.open()
    origen.new_page().insert_text((72, 120), "Arquitectura limpia componentes", fontsize=28)
    pix = origen[0].get_pixmap(dpi=200)
    doc = pymupdf.open()
    doc.new_page().insert_image(doc[0].rect, pixmap=pix)
    doc.save(ruta)


def test_detecta_pdf_sin_texto(tmp_path):
    _escaneado(tmp_path / "escaneo.pdf")
    _libro_sin_indice(tmp_path / "texto.pdf")
    assert ocr.necesita_ocr(tmp_path / "escaneo.pdf")
    assert not ocr.necesita_ocr(tmp_path / "texto.pdf")


@pytest.mark.skipif(not (shutil.which("ocrmypdf") or os.path.exists(
    os.path.expanduser("~/.local/bin/ocrmypdf"))), reason="falta ocrmypdf")
def test_ocr_agrega_capa_de_texto(tmp_path):
    _escaneado(tmp_path / "escaneo.pdf")
    destino = ocr.ocr(tmp_path / "escaneo.pdf")
    assert destino.name == "escaneo (OCR).pdf"
    texto = pymupdf.open(destino)[0].get_text().lower()
    assert "arquitectura" in texto and "componentes" in texto
    assert not ocr.necesita_ocr(destino)


@pytest.fixture
def lp_falso(tmp_path, monkeypatch):
    """Un `lp` que solo anota sus argumentos; va primero en el PATH."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    registro = tmp_path / "lp.log"
    lp = bin_ / "lp"
    lp.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{registro}"\n'
                  'echo "request id is Falsa-1 (1 file(s))"\n')
    lp.chmod(lp.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.delenv("ATRIL_IMPRESORA", raising=False)
    assert shutil.which("lp") == str(lp)
    return registro


def test_comando_de_impresion():
    assert imprimir.comando("x.pdf", "Epson", 2, "1-3", "parte") == [
        "lp", "-d", "Epson", "-n", "2", "-o", "media=Letter", "-o", "fit-to-page",
        "-P", "1-3", "-t", "parte", "x.pdf"]
    cmd, mensaje = imprimir.imprimir("x.pdf", simular=True)
    assert cmd[0] == "lp" and "simulado" in mensaje
    with pytest.raises(ValueError):
        imprimir.imprimir("x.pdf", paginas="1; rm -rf /", simular=True)
    with pytest.raises(ValueError):
        imprimir.imprimir("x.pdf", copias=0, simular=True)


@pytest.fixture
def parte_construida(tmp_path):
    """Proyecto con una parte que ya tiene sus PDFs en salida/ (sin pasar por WeasyPrint)."""
    _libro_sin_indice(tmp_path / "orig.pdf")
    raiz = tmp_path / "proyectos"
    p = Proyecto.crear("demo", "Demo", tmp_path / "orig.pdf", raiz=raiz)
    carpeta = p.dir / "cap-1"
    (carpeta / "salida").mkdir(parents=True)
    (carpeta / "contexto.md").write_text("---\n---\n", encoding="utf-8")
    for nombre in ("cap-1.pdf", "cap-1-2-por-hoja.pdf"):
        shutil.copy(tmp_path / "orig.pdf", carpeta / "salida" / nombre)
    p.registrar_parte({"id": "cap-1", "titulo": "Capítulo 1", "original": "1-3",
                       "referencia": None, "estado": "construida"})
    return raiz, carpeta


def test_cli_imprimir(parte_construida, lp_falso, capsys):
    _, carpeta = parte_construida
    cli.main(["imprimir", str(carpeta), "--simular"])
    assert "simulado" in capsys.readouterr().out and not lp_falso.exists()
    cli.main(["imprimir", str(carpeta), "--2-por-hoja", "--copias", "2"])
    args = lp_falso.read_text()
    assert "-n 2" in args and args.strip().endswith("cap-1-2-por-hoja.pdf")


def test_app_historial_pdf_e_impresion(parte_construida, lp_falso, tmp_path):
    raiz, _ = parte_construida
    c = TestClient(crear_app(raiz=raiz, libros=tmp_path, cache=tmp_path / "cache"))
    d = c.get("/api/proyectos/demo").json()
    assert d["partes"][0]["pdfs"] == {"carta": True, "2x1": True}
    assert d["original"]["indice_detectado"] is True
    assert d["original"]["indice"][0] == [1, "Capítulo uno", 1]

    r = c.get("/api/proyectos/demo/partes/cap-1/pdf?tipo=2x1")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert c.get("/api/proyectos/demo/partes/nada/pdf").status_code == 404

    url = "/api/proyectos/demo/partes/cap-1/imprimir"
    r = c.post(url, json={"tipo": "carta", "copias": 1, "simular": True}).json()
    assert "simulado" in r["mensaje"] and not lp_falso.exists()
    r = c.post(url, json={"tipo": "carta", "copias": 3, "paginas": "1-2"}).json()
    assert "Falsa-1" in r["mensaje"]
    assert "-n 3" in lp_falso.read_text() and "-P 1-2" in lp_falso.read_text()
    assert c.post(url, json={"paginas": "1;x"}).status_code == 422


def test_app_marca_pdfs_sin_texto(tmp_path):
    _escaneado(tmp_path / "escaneo.pdf")
    _libro_sin_indice(tmp_path / "texto.pdf")
    c = TestClient(crear_app(raiz=tmp_path / "proyectos", libros=tmp_path,
                             cache=tmp_path / "cache"))
    marcas = {f["nombre"]: f["sin_texto"] for f in c.get("/api/pdfs").json()}
    assert marcas == {"escaneo.pdf": True, "texto.pdf": False}
    assert c.post("/api/ocr", json={"pdf": "/etc/passwd"}).status_code == 422
