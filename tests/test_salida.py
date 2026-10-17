"""Pruebas de la Fase 2: librería SVG, plantilla y construcción del PDF.

No necesitan los PDFs del libro: usan el caso SOLID de referencia/solid/.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

from atril import construir
from atril.proyecto import Proyecto

SOLID = Path(__file__).parents[1] / "referencia" / "solid"


def test_figs_solid_identicos_con_la_libreria(tmp_path):
    subprocess.run([sys.executable, SOLID / "figs.py", tmp_path], check=True,
                   capture_output=True)
    originales = sorted(SOLID.glob("*.svg"))
    assert len(originales) == 15
    for svg in originales:
        assert (tmp_path / svg.name).read_bytes() == svg.read_bytes(), svg.name


@pytest.fixture(scope="module")
def solid_pdf(tmp_path_factory):
    """El SOLID compilado con plantilla/libro.css en lugar de su <style> propio."""
    d = tmp_path_factory.mktemp("solid")
    for f in [*SOLID.glob("*.svg"), *SOLID.glob("*.png")]:
        shutil.copy(f, d)
    shutil.copy(construir.PLANTILLA / "libro.css", d)
    html = (SOLID / "solid.html").read_text(encoding="utf-8")
    html = re.sub(r"<style>.*?</style>", '<link rel="stylesheet" href="libro.css">', html,
                  flags=re.S)
    (d / "solid.html").write_text(html, encoding="utf-8")
    return construir.html_a_pdf(d / "solid.html", d / "solid.pdf")


def test_plantilla_reproduce_el_solid(solid_pdf):
    doc = pymupdf.open(solid_pdf)
    assert len(doc) == 32
    indice = doc[1].get_text()
    assert "7 · SRP" in indice and "\n6\n" in indice  # target-counter resuelto


def test_dos_por_hoja(solid_pdf, tmp_path):
    doc = pymupdf.open(construir.dos_por_hoja(solid_pdf, tmp_path / "2x1.pdf"))
    assert len(doc) == 16
    assert (doc[0].rect.width, doc[0].rect.height) == (792, 612)


def test_miniaturas(solid_pdf, tmp_path):
    hojas = construir.miniaturas(solid_pdf, tmp_path)
    assert [h.name for h in hojas] == ["hoja-01.png", "hoja-02.png", "hoja-03.png"]


def test_iniciar_y_construir_una_parte(tmp_path):
    p = Proyecto.crear("demo", "Libro Demo", tmp_path / "demo.pdf", raiz=tmp_path)
    carpeta = p.dir / "parte-01"
    carpeta.mkdir()
    (carpeta / "contexto.md").write_text("---\n---\n", encoding="utf-8")
    p.registrar_parte({"id": "parte-01", "titulo": "I · Introducción", "original": "1-9",
                       "referencia": None, "idioma_destino": "es", "estado": "exportada"})

    html = construir.iniciar(carpeta)
    texto = html.read_text(encoding="utf-8")
    assert "{{" not in texto
    assert "Libro Demo · I · Introducción" in texto and "págs. 1-9" in texto
    assert (carpeta / "salida" / "libro.css").exists()

    html.write_text(texto.replace("Título del capítulo<", "Capítulo de prueba<"),
                    encoding="utf-8")
    assert construir.iniciar(carpeta) == html  # no pisa el HTML ya empezado
    assert "Capítulo de prueba" in html.read_text(encoding="utf-8")

    r = construir.construir(carpeta)
    assert r["pdf"].exists() and r["pdf_2x1"].exists() and r["miniaturas"]
    parte = Proyecto("demo", raiz=tmp_path).datos["partes"][0]
    assert parte["estado"] == "construida" and parte["paginas_pdf"] == r["paginas"]
    assert [x.name for x in construir.ver(carpeta, [1, 2])] == ["p-001.png", "p-002.png"]
