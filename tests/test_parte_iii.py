"""Pruebas con el caso real: Arquitectura Limpia, Parte III (SOLID).

Usan los PDFs de ~/Documents/books; si no están, se saltan.
"""

import re
from pathlib import Path

import pytest

from atril import mapa, paquete
from atril.proyecto import Proyecto

LIBROS = Path("~/Documents/books").expanduser()
REFERENCIA = Path(__file__).parents[1] / "referencia" / "solid" / "en-p62-86.txt"


def _pdf(patron):
    encontrados = [p for p in LIBROS.glob(patron) if "SOLID" not in p.name]
    return encontrados[0] if encontrados else None


EN = _pdf("Arquitectura Limpia - ingles.pdf")
ES = _pdf("Arquitectura Limpia - Espa*l.pdf")
pytestmark = pytest.mark.skipif(not (EN and ES), reason="faltan los PDFs del libro")


@pytest.fixture(scope="module")
def proyecto(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("proyectos")
    return Proyecto.crear("al", "Arquitectura Limpia", EN, "en", ES, "es", raiz=raiz)


@pytest.fixture(scope="module")
def contexto(proyecto):
    ruta = paquete.exportar(proyecto, "parte-03", original=(62, 86), instrucciones="Traducir.")
    return ruta, ruta.read_text(encoding="utf-8")


def test_mapa_sin_anclas_acierta_a_una_pagina(proyecto):
    assert abs(proyecto.mapa[77 - 1] - 62) <= 1
    assert abs(proyecto.mapa[108 - 1] - 86) <= 1
    assert mapa.rango_referencia(proyecto.mapa, 62, 86) == (77, 108)


def test_anclas_manuales_fijan_el_mapa(proyecto):
    proyecto.anclar(77, 62)
    proyecto.anclar(108, 86)
    assert mapa.rango_original(proyecto.mapa, 77, 108) == (62, 86)


def test_salen_las_20_figuras(contexto):
    ruta, _ = contexto
    nombres = sorted(f.stem for f in (ruta.parent / "figuras").iterdir())
    assert len([n for n in nombres if n.startswith("fig-")]) == 14
    assert len([n for n in nombres if n.startswith("ilus-")]) == 6
    assert "fig-7.1" in nombres and "fig-11.1" in nombres


def test_sin_restos_de_formato(contexto):
    _, texto = contexto
    assert "Machine Translated" not in texto
    assert "Click here to view code image" not in texto


def test_texto_ingles_completo(contexto):
    """El texto del original cubre lo que se usó para el SOLID (palabras de 5+ letras)."""
    _, texto = contexto
    palabras = lambda t: set(re.findall(r"[a-z]{5,}", t.lower()))
    esperado = palabras(REFERENCIA.read_text(encoding="utf-8"))
    cobertura = len(esperado & palabras(texto)) / len(esperado)
    assert cobertura > 0.98


def test_cabecera_y_bloques(contexto):
    _, texto = contexto
    assert 'paginas: "62-86"' in texto and 'paginas: "77-108"' in texto
    assert texto.count("\n## Bloque ") == 25
    assert "## Bloque 1 · EN p.62 ↔ ES p.77" in texto
    assert "![Figure 7.1 The `Employee` class](figuras/fig-7.1.jpeg)" in texto


def test_codigo_en_un_solo_bloque(contexto):
    _, texto = contexto
    assert "Rectangle r = …\nr.setW(5);\nr.setH(2);\nassert(r.area() == 10);" in texto
