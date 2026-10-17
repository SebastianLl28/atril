"""Proyecto de un libro: sus PDFs, el mapa de páginas y las partes exportadas (libro.json)."""

import json
import os
from functools import cached_property
from pathlib import Path

from . import mapa
from .pdf import Libro, solo_imagenes

RAIZ = Path(os.environ.get("ATRIL_PROYECTOS", "~/Documents/books/proyectos")).expanduser()


class Proyecto:
    def __init__(self, slug, raiz=None):
        self.slug = slug
        self.dir = (raiz or RAIZ) / slug
        self.archivo = self.dir / "libro.json"
        if not self.archivo.exists():
            raise FileNotFoundError(f"No existe el proyecto {slug!r} ({self.archivo})")
        self.datos = json.loads(self.archivo.read_text(encoding="utf-8"))

    @classmethod
    def crear(cls, slug, titulo, original, idioma_original="en",
              referencia=None, idioma_referencia="es", raiz=None):
        for pdf in filter(None, (original, referencia)):
            if solo_imagenes(pdf):
                raise ValueError(f"{Path(pdf).name} es solo imágenes (sin capa de texto): "
                                 "Atril solo acepta PDFs con texto")
        directorio = (raiz or RAIZ) / slug
        directorio.mkdir(parents=True, exist_ok=True)
        datos = {
            "titulo": titulo,
            "original": {"pdf": str(Path(original).resolve()), "idioma": idioma_original},
            "referencia": ({"pdf": str(Path(referencia).resolve()), "idioma": idioma_referencia}
                           if referencia else None),
            "limpieza": {"marcas": []},
            "mapa": {"anclas": {}, "ref_a_orig": []},
            "partes": [],
        }
        (directorio / "libro.json").write_text(
            json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        proyecto = cls(slug, raiz)
        if referencia:
            proyecto.recalcular_mapa()
        return proyecto

    def guardar(self):
        self.archivo.write_text(json.dumps(self.datos, ensure_ascii=False, indent=2),
                                encoding="utf-8")

    @property
    def titulo(self):
        return self.datos["titulo"]

    @cached_property
    def original(self):
        return Libro(self.datos["original"]["pdf"])

    @cached_property
    def referencia(self):
        ref = self.datos.get("referencia")
        return Libro(ref["pdf"]) if ref else None

    @property
    def glosario(self):
        return self.dir / "glosario.md"

    @property
    def mapa(self):
        return self.datos["mapa"]["ref_a_orig"]

    @property
    def anclas(self):
        return {int(r): o for r, o in self.datos["mapa"]["anclas"].items()}

    def anclar(self, pagina_ref, pagina_orig):
        """Corrección manual: esta página de la referencia corresponde a esa del original."""
        self.datos["mapa"]["anclas"][str(pagina_ref)] = pagina_orig
        self.recalcular_mapa()

    def desanclar(self, pagina_ref):
        self.datos["mapa"]["anclas"].pop(str(pagina_ref), None)
        self.recalcular_mapa()

    def recalcular_mapa(self):
        self.datos["mapa"]["ref_a_orig"] = mapa.calcular(self.referencia.textos,
                                                         self.original.textos, self.anclas)
        self.guardar()

    def registrar_parte(self, parte):
        partes = [p for p in self.datos["partes"] if p["id"] != parte["id"]]
        self.datos["partes"] = [*partes, parte]
        self.guardar()
