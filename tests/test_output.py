"""Phase 2 tests: SVG library, template and PDF build.

They don't need the book PDFs: they use the SOLID case in referencia/solid/.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

from atril import build
from atril.project import Project

SOLID = Path(__file__).parents[1] / "referencia" / "solid"


def test_solid_figs_identical_with_the_library(tmp_path):
    subprocess.run([sys.executable, SOLID / "figs.py", tmp_path], check=True,
                   capture_output=True)
    originals = sorted(SOLID.glob("*.svg"))
    assert len(originals) == 15
    for svg in originals:
        assert (tmp_path / svg.name).read_bytes() == svg.read_bytes(), svg.name


@pytest.fixture(scope="module")
def solid_pdf(tmp_path_factory):
    """SOLID built with template/libro.css instead of its own <style>."""
    d = tmp_path_factory.mktemp("solid")
    for f in [*SOLID.glob("*.svg"), *SOLID.glob("*.png")]:
        shutil.copy(f, d)
    shutil.copy(build.TEMPLATE / "libro.css", d)
    html = (SOLID / "solid.html").read_text(encoding="utf-8")
    html = re.sub(r"<style>.*?</style>", '<link rel="stylesheet" href="libro.css">', html,
                  flags=re.S)
    (d / "solid.html").write_text(html, encoding="utf-8")
    return build.html_to_pdf(d / "solid.html", d / "solid.pdf")


def test_template_reproduces_solid(solid_pdf):
    doc = pymupdf.open(solid_pdf)
    assert len(doc) == 32
    toc = doc[1].get_text()
    assert "7 · SRP" in toc and "\n6\n" in toc  # target-counter resolved


def test_two_up(solid_pdf, tmp_path):
    doc = pymupdf.open(build.two_up(solid_pdf, tmp_path / "2x1.pdf"))
    assert len(doc) == 16
    assert (doc[0].rect.width, doc[0].rect.height) == (792, 612)


def test_contact_sheets(solid_pdf, tmp_path):
    sheets = build.contact_sheets(solid_pdf, tmp_path)
    assert [h.name for h in sheets] == ["hoja-01.png", "hoja-02.png", "hoja-03.png"]


def test_init_and_build_a_part(tmp_path):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "Texto de prueba suficiente para tener capa de texto.")
    doc.save(tmp_path / "demo.pdf")
    p = Project.create("demo", "Libro Demo", tmp_path / "demo.pdf", root=tmp_path)
    folder = p.dir / "parte-01"
    folder.mkdir()
    (folder / "contexto.md").write_text("---\n---\n", encoding="utf-8")
    p.register_part({"id": "parte-01", "titulo": "I · Introducción", "original": "1-9",
                     "referencia": None, "idioma_destino": "es", "estado": "exportada"})

    html = build.init(folder)
    text = html.read_text(encoding="utf-8")
    assert "{{" not in text
    assert "Libro Demo · I · Introducción" in text and "págs. 1-9" in text
    assert (folder / "salida" / "libro.css").exists()

    html.write_text(text.replace("Título del capítulo<", "Capítulo de prueba<"),
                    encoding="utf-8")
    assert build.init(folder) == html  # does not overwrite an HTML already started
    assert "Capítulo de prueba" in html.read_text(encoding="utf-8")

    r = build.build(folder)
    assert r["pdf"].exists() and r["pdf_2up"].exists() and r["sheets"]
    part = Project("demo", root=tmp_path).data["partes"][0]
    assert part["estado"] == "construida" and part["paginas_pdf"] == r["pages"]
    assert [x.name for x in build.view(folder, [1, 2])] == ["p-001.png", "p-002.png"]
