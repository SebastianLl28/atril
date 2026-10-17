"""Removes formatting leftovers and headers or footers repeated on every page."""

import re
from collections import Counter

# Marks that are never book content. Each book can add its own in libro.json.
MARKS = [
    r"^Machine Translated by Google$",
    r"^Click here to view code image$",
    r"^Haga clic aquí para ver la imagen del código\.?$",
]

# Top and bottom band (fraction of the height) where headers and page numbers live.
BAND = 0.08


def _key(text):
    return re.sub(r"\d+", "#", text.lower()).strip()


def _in_band(element, height):
    y0, y1 = element.bbox[1], element.bbox[3]
    return y1 <= height * BAND or y0 >= height * (1 - BAND)


def repeated(pages, minimum=0.5):
    """Header/footer band texts that appear on at least half of the pages."""
    if len(pages) < 4:
        return set()
    count = Counter()
    for p in pages:
        count.update({_key(e.text) for e in p.elements if e.text and _in_band(e, p.height)})
    return {c for c, n in count.items() if n >= minimum * len(pages)}


SENTENCE_END = re.compile(r"[.:!?»”\"')\]]$")


def _append(a, b, separator):
    x0, y0, x1, y1 = a.bbox
    bx0, by0, bx1, by1 = b.bbox
    a.text = a.text + separator + b.text
    a.bbox = (min(x0, bx0), min(y0, by0), max(x1, bx1), max(y1, by1))


def merge(page):
    """Rebuilds paragraphs split across lines and joins code line by line."""
    result = []
    for e in page.elements:
        prev = result[-1] if result else None
        if prev and prev.kind == e.kind == "code":
            _append(prev, e, "\n")
        elif (prev and prev.kind == e.kind == "paragraph"
              and not SENTENCE_END.search(prev.text)
              and not prev.text.isupper() and not e.text.isupper()):  # all-caps headings
            _append(prev, e, " ")
        else:
            result.append(e)
    page.elements = result


def clean(pages, extra_marks=()):
    """Filters out, in place, the elements that are not content."""
    patterns = [re.compile(m, re.I) for m in [*MARKS, *extra_marks]]
    drop = repeated(pages)
    for p in pages:
        p.elements = [
            e for e in p.elements
            if e.kind == "image" or not (
                any(r.search(e.text) for r in patterns)
                or (_in_band(e, p.height) and (_key(e.text) in drop or e.text.isdigit()))
            )
        ]
        merge(p)
    return pages
