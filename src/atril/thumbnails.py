"""Page images (thumbnails and large views) with a disk cache.

The cache lives in ~/.cache/atril/paginas/ (override with ATRIL_CACHE). The key includes the
PDF's path, size and mtime: if the file changes, the images are regenerated.
"""

import hashlib
import os
from pathlib import Path

import pymupdf

CACHE = Path(os.environ.get("ATRIL_CACHE",
                            Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")) / "atril"))
CACHE = CACHE.expanduser() / "paginas"

WIDTHS = (240, 1100)  # thumbnail and large view, in px
QUALITY = 82


def _key(path):
    path = Path(path)
    st = path.stat()
    return hashlib.sha1(f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:16]


def image(doc, path, number, width, cache=None):
    """JPEG bytes of page `number` (1-based) at `width` px.

    `doc` is the already open pymupdf.Document of `path`; only used on a cache miss.
    """
    file = (cache or CACHE) / _key(path) / str(width) / f"p-{number:04d}.jpg"
    if file.exists():
        return file.read_bytes()
    page = doc[number - 1]
    scale = width / page.rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    data = pix.tobytes("jpg", jpg_quality=QUALITY)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(data)
    return data
