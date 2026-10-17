"""Pruebas de la tarea de cada parte (traducir o no, comentarios, contexto…) y de las fuentes
adicionales (notas, enlaces, páginas de otros PDFs). Usan PDFs sintéticos.
"""

import json

import pymupdf
import pytest
from fastapi.testclient import TestClient

from atril import cli, construir, paquete
from atril.app import crear_app
from atril.proyecto import Proyecto


def _pdf(ruta, paginas):
    doc = pymupdf.open()
    for texto in paginas:
        page = doc.new_page()
        for i, linea in enumerate(texto.split("\n")):
            page.insert_text((72, 100 + 16 * i), linea, fontsize=11)
    doc.save(ruta)


def _escaneado(ruta):
    origen = pymupdf.open()
    origen.new_page().insert_text((72, 120), "Texto escaneado", fontsize=28)
    doc = pymupdf.open()
    doc.new_page().insert_image(doc[0].rect, pixmap=origen[0].get_pixmap(dpi=100))
    doc.save(ruta)


@pytest.fixture
def entorno(tmp_path):
    libros = tmp_path / "books"
    libros.mkdir()
    _pdf(libros / "informe.pdf", [f"Quarterly report section {n}.\nRevenue grew steadily."
                                  for n in range(1, 5)])
    _pdf(libros / "apuntes.pdf", [f"Apunte {n}: el contexto histórico importa." for n in range(1, 4)])
    _escaneado(libros / "escaneo.pdf")
    p = Proyecto.crear("informe", "Informe trimestral", libros / "informe.pdf", "en",
                       raiz=libros / "proyectos")
    return p, libros


def test_por_defecto_mantiene_el_idioma(entorno):
    p, _ = entorno
    texto = paquete.exportar(p, "sec-1", original=(1, 2)).read_text(encoding="utf-8")
    assert "tarea: { traducir: null, mejorar_lectura: true, comentarios: false" in texto
    assert 'idioma_salida: "en"' in texto
    assert "- Mantener el idioma del documento (en)" in texto
    assert "Traducir" not in texto.split("# Instrucciones")[0]
    assert "# Fuentes adicionales" not in texto


def test_traducir_y_enriquecer_con_fuentes(entorno):
    p, libros = entorno
    tarea = {"traducir": "ES", "comentarios": True, "contexto": True, "resumen": True}
    fuentes = {"notas": "El autor escribió esto en 2019.",
               "enlaces": ["https://example.com/contexto", "  "],
               "pdfs": [{"pdf": str(libros / "apuntes.pdf"), "paginas": (2, 3)}]}
    texto = paquete.exportar(p, "sec-2", original=(3, 4), tarea=tarea,
                             fuentes=fuentes).read_text(encoding="utf-8")
    assert 'idioma_salida: "es"' in texto
    assert "- Traducir del en al es, fiel al documento." in texto
    assert "- Comentarios de estudio" in texto and "- Contexto" in texto and "- Resumen final" in texto
    fuentes_md = texto.split("# Fuentes adicionales")[1].split("# Contenido")[0]
    assert "## Notas\n\nEl autor escribió esto en 2019." in fuentes_md
    assert "- https://example.com/contexto" in fuentes_md and "- \n" not in fuentes_md
    assert "## PDF · apuntes.pdf · p.2-3" in fuentes_md
    assert "Apunte 2" in fuentes_md and "Apunte 3" in fuentes_md and "Apunte 1" not in fuentes_md
    parte = json.loads(p.archivo.read_text(encoding="utf-8"))["partes"][-1]
    assert parte["tarea"]["traducir"] == "es" and parte["tarea"]["resumen"] is True
    assert parte["fuentes"]["enlaces"] == ["https://example.com/contexto"]
    assert parte["fuentes"]["pdfs"] == [{"pdf": str(libros / "apuntes.pdf"), "paginas": "2-3"}]


def test_fuentes_invalidas(entorno):
    p, libros = entorno
    with pytest.raises(ValueError, match="solo imágenes"):
        paquete.exportar(p, "x", original=(1, 1),
                         fuentes={"pdfs": [{"pdf": str(libros / "escaneo.pdf"), "paginas": (1, 1)}]})
    with pytest.raises(ValueError, match="rango"):
        paquete.exportar(p, "x", original=(1, 1),
                         fuentes={"pdfs": [{"pdf": str(libros / "apuntes.pdf"), "paginas": (2, 9)}]})
    with pytest.raises(ValueError, match="desconocida"):
        paquete.exportar(p, "x", original=(1, 1), tarea={"resumir": True})


def test_portada_segun_la_tarea(entorno):
    p, _ = entorno
    carpeta = paquete.exportar(p, "sin-traducir", original=(1, 1)).parent
    html = construir.iniciar(carpeta).read_text(encoding="utf-8")
    assert '<html lang="en">' in html and "transcripción fiel del original" in html
    assert "traducción" not in html

    carpeta = paquete.exportar(p, "traducida", original=(1, 1),
                               tarea={"traducir": "es", "comentarios": True}).parent
    html = construir.iniciar(carpeta).read_text(encoding="utf-8")
    assert '<html lang="es">' in html and "traducción fiel del original" in html
    assert "recuadros de comentario" in html


def test_cli_exportar_con_tarea_y_fuentes(entorno, tmp_path, monkeypatch):
    p, libros = entorno
    monkeypatch.setattr("atril.proyecto.RAIZ", libros / "proyectos")
    notas = tmp_path / "notas.md"
    notas.write_text("Contexto pegado.", encoding="utf-8")
    cli.main(["exportar", "informe", "cli", "--original", "1-2", "--traducir", "es",
              "--comentarios", "--notas", str(notas), "--enlace", "https://a.org",
              "--pdf", f"{libros / 'apuntes.pdf'}:1-2"])
    texto = (p.dir / "cli" / "contexto.md").read_text(encoding="utf-8")
    assert "traducir: \"es\"" in texto and "comentarios: true" in texto
    assert "Contexto pegado." in texto and "https://a.org" in texto and "Apunte 1" in texto


def test_app_exporta_tarea_y_fuentes(entorno, tmp_path):
    p, libros = entorno
    c = TestClient(crear_app(raiz=libros / "proyectos", libros=libros, cache=tmp_path / "c"))
    pdfs = {f["nombre"]: f for f in c.get("/api/pdfs").json()}
    assert pdfs["apuntes.pdf"]["paginas"] == 3 and pdfs["escaneo.pdf"]["solo_imagenes"]
    cuerpo = {"parte": "app", "original": [1, 2],
              "tarea": {"traducir": "es", "contexto": True},
              "fuentes": {"notas": "nota", "enlaces": ["https://b.org"],
                          "pdfs": [{"pdf": str(libros / "apuntes.pdf"), "paginas": [1, 1]}]}}
    r = c.post("/api/proyectos/informe/exportar", json=cuerpo)
    assert r.status_code == 200, r.text
    parte = r.json()["partes"][-1]
    assert parte["tarea"]["contexto"] is True and parte["fuentes"]["enlaces"] == ["https://b.org"]
    cuerpo["fuentes"]["pdfs"] = [{"pdf": "/etc/hosts.pdf", "paginas": [1, 1]}]
    assert c.post("/api/proyectos/informe/exportar", json=cuerpo).status_code == 422
