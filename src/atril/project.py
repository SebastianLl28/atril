"""A book project: its PDFs, the page map and the exported parts (libro.json)."""

import json
import os
from functools import cached_property
from pathlib import Path

from . import mapping
from .pdf import Book, is_image_only

ROOT = Path(os.environ.get("ATRIL_PROYECTOS", "~/Documents/books/proyectos")).expanduser()


class Project:
    def __init__(self, slug, root=None):
        self.slug = slug
        self.dir = (root or ROOT) / slug
        self.file = self.dir / "libro.json"
        if not self.file.exists():
            raise FileNotFoundError(f"No existe el proyecto {slug!r} ({self.file})")
        self.data = json.loads(self.file.read_text(encoding="utf-8"))

    @classmethod
    def create(cls, slug, title, original, original_lang="en",
               reference=None, reference_lang="es", root=None):
        for pdf in filter(None, (original, reference)):
            if is_image_only(pdf):
                raise ValueError(f"{Path(pdf).name} es solo imágenes (sin capa de texto): "
                                 "Atril solo acepta PDFs con texto")
        directory = (root or ROOT) / slug
        directory.mkdir(parents=True, exist_ok=True)
        data = {
            "titulo": title,
            "original": {"pdf": str(Path(original).resolve()), "idioma": original_lang},
            "referencia": ({"pdf": str(Path(reference).resolve()), "idioma": reference_lang}
                           if reference else None),
            "limpieza": {"marcas": []},
            "mapa": {"anclas": {}, "ref_a_orig": []},
            "partes": [],
        }
        (directory / "libro.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        project = cls(slug, root)
        if reference:
            project.recompute_map()
        return project

    def save(self):
        self.file.write_text(json.dumps(self.data, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    @property
    def title(self):
        return self.data["titulo"]

    @cached_property
    def original(self):
        return Book(self.data["original"]["pdf"])

    @cached_property
    def reference(self):
        ref = self.data.get("referencia")
        return Book(ref["pdf"]) if ref else None

    @property
    def glossary(self):
        return self.dir / "glosario.md"

    @property
    def map(self):
        return self.data["mapa"]["ref_a_orig"]

    @property
    def anchors(self):
        return {int(r): o for r, o in self.data["mapa"]["anclas"].items()}

    def anchor(self, ref_page, orig_page):
        """Manual fix: this reference page corresponds to that original page."""
        self.data["mapa"]["anclas"][str(ref_page)] = orig_page
        self.recompute_map()

    def unanchor(self, ref_page):
        self.data["mapa"]["anclas"].pop(str(ref_page), None)
        self.recompute_map()

    def recompute_map(self):
        self.data["mapa"]["ref_a_orig"] = mapping.compute(self.reference.texts,
                                                          self.original.texts, self.anchors)
        self.save()

    def register_part(self, part):
        parts = [p for p in self.data["partes"] if p["id"] != part["id"]]
        self.data["partes"] = [*parts, part]
        self.save()
