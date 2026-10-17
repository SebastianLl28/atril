"""Imágenes de página (miniaturas y vistas grandes) con caché en disco.

La caché vive en ~/.cache/atril/paginas/ (se cambia con ATRIL_CACHE). La clave incluye la
ruta, el tamaño y la fecha del PDF: si el archivo cambia, las imágenes se regeneran solas.
"""

import hashlib
import os
from pathlib import Path

import pymupdf

CACHE = Path(os.environ.get("ATRIL_CACHE",
                            Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")) / "atril"))
CACHE = CACHE.expanduser() / "paginas"

ANCHOS = (240, 1100)  # miniatura y vista grande, en px
CALIDAD = 82


def _clave(ruta):
    ruta = Path(ruta)
    st = ruta.stat()
    return hashlib.sha1(f"{ruta.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:16]


def imagen(doc, ruta, numero, ancho, cache=None):
    """JPEG de la página `numero` (1-based) con `ancho` px. Devuelve los bytes.

    `doc` es el pymupdf.Document ya abierto de `ruta`; solo se usa si no está en caché.
    """
    archivo = (cache or CACHE) / _clave(ruta) / str(ancho) / f"p-{numero:04d}.jpg"
    if archivo.exists():
        return archivo.read_bytes()
    pagina = doc[numero - 1]
    escala = ancho / pagina.rect.width
    pix = pagina.get_pixmap(matrix=pymupdf.Matrix(escala, escala), alpha=False)
    datos = pix.tobytes("jpg", jpg_quality=CALIDAD)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_bytes(datos)
    return datos
