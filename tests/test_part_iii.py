"""Tests on the real case: Arquitectura Limpia, Part III (SOLID).

They use the PDFs in ~/Documents/books and are skipped if those are missing.
"""

import re
from pathlib import Path

import pytest

from atril import bundle, mapping
from atril.project import Project

BOOKS = Path("~/Documents/books").expanduser()
REFERENCE = Path(__file__).parents[1] / "referencia" / "solid" / "en-p62-86.txt"


def _pdf(pattern):
    found = [p for p in BOOKS.glob(pattern) if "SOLID" not in p.name]
    return found[0] if found else None


EN = _pdf("Arquitectura Limpia - ingles.pdf")
ES = _pdf("Arquitectura Limpia - Espa*l.pdf")
pytestmark = pytest.mark.skipif(not (EN and ES), reason="faltan los PDFs del libro")


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    root = tmp_path_factory.mktemp("proyectos")
    return Project.create("al", "Arquitectura Limpia", EN, "en", ES, "es", root=root)


@pytest.fixture(scope="module")
def context(project):
    path = bundle.export(project, "parte-03", original=(62, 86), instructions="Traducir.")
    return path, path.read_text(encoding="utf-8")


def test_map_without_anchors_is_within_one_page(project):
    assert abs(project.map[77 - 1] - 62) <= 1
    assert abs(project.map[108 - 1] - 86) <= 1
    assert mapping.reference_range(project.map, 62, 86) == (77, 108)


def test_manual_anchors_pin_the_map(project):
    project.anchor(77, 62)
    project.anchor(108, 86)
    assert mapping.original_range(project.map, 77, 108) == (62, 86)


def test_all_20_figures_are_extracted(context):
    path, _ = context
    names = sorted(f.stem for f in (path.parent / "figuras").iterdir())
    assert len([n for n in names if n.startswith("fig-")]) == 14
    assert len([n for n in names if n.startswith("ilus-")]) == 6
    assert "fig-7.1" in names and "fig-11.1" in names


def test_no_formatting_leftovers(context):
    _, text = context
    assert "Machine Translated" not in text
    assert "Click here to view code image" not in text


def test_english_text_is_complete(context):
    """The original text covers what was used for SOLID (words of 5+ letters)."""
    _, text = context
    words = lambda t: set(re.findall(r"[a-z]{5,}", t.lower()))
    expected = words(REFERENCE.read_text(encoding="utf-8"))
    coverage = len(expected & words(text)) / len(expected)
    assert coverage > 0.98


def test_header_and_blocks(context):
    _, text = context
    assert 'paginas: "62-86"' in text and 'paginas: "77-108"' in text
    assert text.count("\n## Bloque ") == 25
    assert "## Bloque 1 · EN p.62 ↔ ES p.77" in text
    assert "![Figure 7.1 The `Employee` class](figuras/fig-7.1.jpeg)" in text


def test_code_in_a_single_block(context):
    _, text = context
    assert "Rectangle r = …\nr.setW(5);\nr.setH(2);\nassert(r.area() == 10);" in text
