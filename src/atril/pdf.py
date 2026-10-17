"""PDF reading with PyMuPDF: table of contents, plain text and structured elements per page."""

import re
from collections import Counter
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import pymupdf

MONO = re.compile(r"courier|mono|consol|menlo|code", re.I)
CAPTION = re.compile(r"^(Figure|Figura|Fig\.|Table|Tabla)\s+\d+(\.\d+)*\b", re.I)
BULLET = re.compile(r"^\s*[•◦▪●‣–]\s*")
SPACES = re.compile(r"[ \t   ]+")

# An image covering almost the whole page is a scan, not a figure.
SCAN_AREA = 0.8

# A PDF where more than half the pages have almost no text is image-only and is rejected.
MIN_CHARS, SAMPLE = 25, 30

# Heading detection for PDFs without a TOC, as multiples of the body font size.
TITLE, SUBTITLE, CHAPTER_NUMBER = 1.75, 1.25, 2.3
ONLY_NUMBER = re.compile(r"^(\d+|[IVXLC]+)$")


def is_image_only(path, sample=SAMPLE):
    """True if the PDF is a scan with no text layer (checking a sample of pages)."""
    doc = pymupdf.open(path)
    step = max(1, len(doc) // sample)
    pages = range(0, len(doc), step)
    empty = sum(len(doc[i].get_text().strip()) < MIN_CHARS for i in pages)
    return bool(len(pages)) and empty / len(pages) > 0.5


@dataclass
class Element:
    kind: str  # title, subtitle, paragraph, quote, code, bullet, caption, image
    text: str = ""
    bbox: tuple = ()
    xref: int = 0  # images only


@dataclass
class Page:
    number: int  # 1-based, as a PDF viewer shows it
    height: float
    elements: list[Element] = field(default_factory=list)


def _normalize(text):
    return SPACES.sub(" ", text).strip()


def _is_italic(span):
    return bool(span["flags"] & 2) or "ital" in span["font"].lower()


def _is_bold(span):
    return bool(span["flags"] & 16) or "bold" in span["font"].lower()


def _join(lines):
    """Joins the lines of a paragraph, removing the hyphen from split words."""
    text = ""
    for line in lines:
        if not text:
            text = line
        elif re.search(r"[a-záéíóúñ]-$", text) and line[:1].islower():
            text = text[:-1] + line
        else:
            text += " " + line
    return text


class Book:
    def __init__(self, path):
        self.path = Path(path)
        self.doc = pymupdf.open(self.path)

    def __len__(self):
        return self.doc.page_count

    def toc(self):
        """TOC entries as (level, title, page); falls back to the one detected by font size."""
        toc = [(level, title, page) for level, title, page, *_ in self.doc.get_toc()]
        return toc or self.detected_toc

    @property
    def has_toc(self):
        return bool(self.doc.get_toc())

    @cached_property
    def detected_toc(self):
        """Headings by font size relative to the body.

        If the book marks chapters with a very large number (like OCR'd scans, where sections
        are almost as large as titles), pages with that number are chapters and the other
        titles are sections. Otherwise titles are chapters and bold subtitles are sections.
        """
        body = self.body_size
        pages = []  # (page, [(size, bold, y, text)])
        for n, page in enumerate(self.doc, start=1):
            blocks = []
            for b in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
                spans = [s for l in b["lines"] for s in l["spans"] if s["text"].strip()]
                if not spans:
                    continue
                size = max(s["size"] for s in spans) / body
                if size < SUBTITLE:
                    continue
                # Spans on one line are glued together: small caps («C» + «ONTENTS») are
                # separate spans of the same word.
                text = _normalize(" ".join("".join(s["text"] for s in l["spans"])
                                           for l in b["lines"]))
                if len(text) <= 120:
                    blocks.append((size, all(_is_bold(s) for s in spans), b["bbox"][1], text))
            pages.append((n, sorted(blocks, key=lambda b: b[2])))

        with_number = any(t >= CHAPTER_NUMBER for _, bs in pages for t, *_ in bs)
        entries = []
        for n, blocks in pages:
            titles = [b for b in blocks if b[0] >= TITLE]
            if with_number:
                if any(t >= CHAPTER_NUMBER for t, *_ in titles):
                    text = " ".join(b[3] for b in titles)
                    if ONLY_NUMBER.match(text):  # the title itself fell below the threshold
                        text += " " + " ".join(b[3] for b in blocks if b not in titles)[:100]
                    entries.append((1, text.strip(), n))
                else:
                    entries += [(2, b[3], n) for b in titles]
            else:
                entries += [(1, b[3], n) for b in titles]
                entries += [(2, b[3], n) for b in blocks if b[0] < TITLE and b[1]]
        # Without letters they are page numbers or stray dates, not headings.
        return [e for e in entries if any(c.isalpha() for c in e[1])]

    def plain_text(self, number):
        return self.texts[number - 1]

    @cached_property
    def texts(self):
        """Plain text of every page; used by the map, the search and the counter."""
        return [page.get_text() for page in self.doc]

    @cached_property
    def body_size(self):
        """Most used font size, measured on a sample spread across the book."""
        count = Counter()
        step = max(1, len(self) // 40)
        for i in range(0, len(self), step):
            for b in self.doc[i].get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
                for l in b["lines"]:
                    for s in l["spans"]:
                        count[round(s["size"], 1)] += len(s["text"].strip())
        return count.most_common(1)[0][0] if count else 10.0

    def page(self, number):
        page = self.doc[number - 1]
        result = Page(number, page.rect.height)
        for b in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
            element = self._classify(b)
            if element:
                result.elements.append(element)
        page_area = page.rect.width * page.rect.height
        for info in page.get_image_info(xrefs=True):
            x0, y0, x1, y1 = info["bbox"]
            if info["xref"] and (x1 - x0) * (y1 - y0) < SCAN_AREA * page_area:
                result.elements.append(Element("image", bbox=info["bbox"], xref=info["xref"]))
        result.elements.sort(key=lambda e: (round(e.bbox[1]), e.bbox[0]))
        return result

    def image(self, xref):
        """Original bytes of an image and its extension."""
        data = self.doc.extract_image(xref)
        return data["image"], data["ext"]

    def _classify(self, block):
        lines, spans = [], []
        for l in block["lines"]:
            parts = []
            for s in l["spans"]:
                spans.append(s)
                parts.append((s["text"], bool(MONO.search(s["font"]))))
            lines.append(parts)
        with_text = [s for s in spans if s["text"].strip()]
        if not with_text:
            return None
        bbox = tuple(block["bbox"])
        if all(MONO.search(s["font"]) for s in with_text):
            code = "\n".join("".join(t for t, _ in l).rstrip() for l in lines)
            return Element("code", code.replace(" ", " "), bbox)

        # Monospaced fragments inside prose → `code`
        texts = []
        for parts in lines:
            line = "".join(f"`{t.strip()}`" + (" " if t.endswith(" ") else "")
                           if mono and t.strip() else t for t, mono in parts)
            line = _normalize(line)
            if line:
                texts.append(line)
        if not texts:
            return None

        body = self.body_size
        size = max(s["size"] for s in with_text)
        if size >= body * 1.75:
            return Element("title", " ".join(texts), bbox)
        if size >= body * 1.25 and all(_is_bold(s) for s in with_text):
            return Element("subtitle", " ".join(texts), bbox)
        if CAPTION.match(texts[0]):
            return Element("caption", " ".join(texts), bbox)
        if BULLET.match(texts[0]):
            items, current = [], []
            for t in texts:
                if BULLET.match(t) and current:
                    items.append(_join(current))
                    current = []
                current.append(BULLET.sub("", t) if BULLET.match(t) else t)
            items.append(_join(current))
            return Element("bullet", "\n".join(items), bbox)
        if all(_is_italic(s) for s in with_text) and size < body:
            return Element("quote", _join(texts), bbox)
        return Element("paragraph", _join(texts), bbox)
