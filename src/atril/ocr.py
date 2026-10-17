"""OCR para PDFs sin capa de texto, con ocrmypdf (`uv tool install ocrmypdf`) y tesseract."""

import os
import shutil
import subprocess
from pathlib import Path

import pymupdf

# Una página con menos caracteres que esto se considera sin texto.
MINIMO_CARACTERES = 25
MUESTRA = 30


def proporcion_sin_texto(ruta, muestra=MUESTRA):
    """Fracción de páginas sin texto, medida en una muestra repartida por el PDF."""
    doc = pymupdf.open(ruta)
    paso = max(1, len(doc) // muestra)
    paginas = range(0, len(doc), paso)
    vacias = sum(len(doc[i].get_text().strip()) < MINIMO_CARACTERES for i in paginas)
    return vacias / len(paginas) if len(paginas) else 0.0


def necesita_ocr(ruta):
    return proporcion_sin_texto(ruta) > 0.5


def _ejecutable():
    encontrado = shutil.which("ocrmypdf")
    if encontrado:
        return encontrado
    local = Path("~/.local/bin/ocrmypdf").expanduser()  # donde lo deja `uv tool install`
    if local.exists():
        return str(local)
    raise RuntimeError("Falta ocrmypdf: instálalo con `uv tool install ocrmypdf`")


def destino_por_defecto(ruta):
    ruta = Path(ruta)
    return ruta.with_name(f"{ruta.stem} (OCR).pdf")


def ocr(ruta, idiomas="spa+eng", destino=None, forzar=False):
    """Crea una copia del PDF con capa de texto. Devuelve la ruta de la copia.

    Las páginas que ya tienen texto se dejan como están (--skip-text), salvo con `forzar`,
    que rehace el OCR de todas (--redo-ocr).
    """
    ruta = Path(ruta)
    destino = Path(destino) if destino else destino_por_defecto(ruta)
    comando = [_ejecutable(), "-l", idiomas, "--jobs", str(os.cpu_count() or 2),
               "--redo-ocr" if forzar else "--skip-text", "--output-type", "pdf",
               str(ruta), str(destino)]
    r = subprocess.run(comando, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ocrmypdf falló ({r.returncode}):\n{r.stderr.strip()[-2000:]}")
    return destino
