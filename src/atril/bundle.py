"""Writes a part's bundle: contexto.md with the already merged text, plus figuras/.

Besides the text, the bundle says what to do with it (`tarea`: translate or not, improve
readability, comments, context, summary) and adds the part's extra sources: pasted notes,
links and pages from other PDFs.
"""

import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from . import cleaning
from .mapping import original_range, reference_range
from .pdf import CAPTION, Book, is_image_only

# Max distance (pt) between an image's bottom edge and its caption.
CAPTION_DISTANCE = 60

TASK = {
    "traducir": None,         # output language code, or None to keep the document's
    "mejorar_lectura": True,  # clean layout, redrawn diagrams, footnotes in place
    "comentarios": False,     # study boxes explaining the text
    "contexto": False,        # background boxes, built from the extra sources
    "resumen": False,         # closing review summary
}

TASK_DESCRIPTIONS = {
    "mejorar_lectura": "Mejorar la lectura: maquetación limpia, diagramas redibujados en "
                       "vectores, notas al pie en su sitio y errores de extracción corregidos.",
    "comentarios": "Comentarios de estudio: recuadros que explican lo difícil (figuras, "
                   "términos, razonamientos).",
    "contexto": "Contexto: recuadros con antecedentes y relaciones con otras ideas, apoyados "
                "en las fuentes adicionales.",
    "resumen": "Resumen final: una página de repaso al terminar.",
}


def normalize_task(task=None):
    t = {**TASK, **(task or {})}
    unknown = set(t) - set(TASK)
    if unknown:
        raise ValueError(f"Tarea desconocida: {', '.join(sorted(unknown))}")
    t["traducir"] = (t["traducir"] or "").strip().lower() or None
    return t


def describe_task(task, document_lang):
    lines = []
    if task["traducir"] and task["traducir"] != document_lang:
        lines.append(f"Traducir del {document_lang} al {task['traducir']}, fiel al documento.")
    else:
        lines.append(f"Mantener el idioma del documento ({document_lang}): transcribir fiel, "
                     "sin traducir ni resumir.")
    lines += [TASK_DESCRIPTIONS[k] for k in TASK_DESCRIPTIONS if task[k]]
    return lines


def _yaml(value):
    """Scalars and dicts as flow-style YAML; json.dumps yields valid YAML strings."""
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{k}: {_yaml(v)}" for k, v in value.items()) + " }"
    if isinstance(value, list):
        return "[" + ", ".join(_yaml(v) for v in value) + "]"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _range(start, end):
    return f"{start}" if start == end else f"{start}-{end}"


def _name_figures(pages, prefix):
    """File name for each image: fig-7.1 if it has a caption, otherwise ilus-p064-1."""
    names, captions = {}, {}
    for p in pages:
        n = 0
        for i, e in enumerate(p.elements):
            if e.kind != "image" or e.xref in names:
                continue
            n += 1
            caption = next((s for s in p.elements[i + 1:]
                            if s.kind == "caption"
                            and 0 <= s.bbox[1] - e.bbox[3] < CAPTION_DISTANCE),
                           None)
            if caption:
                number = CAPTION.match(caption.text).group(0).split()[-1]
                names[e.xref] = f"{prefix}fig-{number}"
                captions[e.xref] = caption.text
            else:
                names[e.xref] = f"{prefix}ilus-p{p.number:03d}-{n}"
    return names, captions


def _markdown(page, files, captions):
    parts = []
    for e in page.elements:
        if e.kind == "title":
            parts.append(f"#### {e.text}")
        elif e.kind == "subtitle":
            parts.append(f"##### {e.text}")
        elif e.kind == "quote":
            parts.append(f"> {e.text}")
        elif e.kind == "code":
            parts.append(f"```\n{e.text}\n```")
        elif e.kind == "bullet":
            parts.append("\n".join(f"- {item}" for item in e.text.split("\n")))
        elif e.kind == "caption":
            if e.text not in captions.values():  # a figure's caption already goes as alt text
                parts.append(f"*{e.text}*")
        elif e.kind == "image":
            alt = captions.get(e.xref) or "Ilustración"
            parts.append(f"![{alt}](figuras/{files[e.xref]})")
        else:
            parts.append(e.text)
    return "\n\n".join(parts)


def _save_figures(book, pages, prefix, folder):
    names, captions = _name_figures(pages, prefix)
    files = {}
    for xref, name in names.items():
        data, ext = book.image(xref)
        files[xref] = f"{name}.{ext}"
        (folder / files[xref]).write_bytes(data)
    return files, captions


def _words(text):
    return len(re.findall(r"\w+", text))


def _pdf_sources(pdfs, figures, marks):
    """Clean text of the chosen pages of other PDFs. Returns (markdown, words, summary)."""
    parts, words, summary = [], 0, []
    for i, f in enumerate(pdfs, start=1):
        path = Path(f["pdf"]).expanduser()
        if not path.is_file():
            raise ValueError(f"No existe el PDF de apoyo {path}")
        if is_image_only(path):
            raise ValueError(f"{path.name} es solo imágenes (sin texto): no se acepta")
        book = Book(path)
        start, end = f["paginas"]
        if not 1 <= start <= end <= len(book):
            raise ValueError(f"{path.name} tiene {len(book)} páginas; rango {start}-{end} inválido")
        pages = cleaning.clean([book.page(n) for n in range(start, end + 1)], marks)
        files, captions = _save_figures(book, pages, f"fuente{i}-", figures)
        name = unicodedata.normalize("NFC", path.name)
        parts += [f"## PDF · {name} · p.{_range(start, end)}", f"Ruta: `{path}`"]
        for p in pages:
            text = _markdown(p, files, captions)
            words += _words(text)
            parts += [f"### {name} · p.{p.number}", text or "_(página sin texto)_"]
        summary.append({"pdf": str(path), "paginas": _range(start, end)})
    return parts, words, summary


def export(project, part, original=None, reference=None, instructions="",
           part_title=None, output=("carta", "2-por-hoja"), task=None, sources=None):
    """Writes <project>/<part>/contexto.md and figuras/. Returns the path of contexto.md.

    One of the two ranges (1-based, inclusive tuples) is enough: the other comes from the map.
    `task` follows TASK. `sources` accepts {"notas": str, "enlaces": [url],
    "pdfs": [{"pdf": path, "paginas": (start, end)}]}.
    """
    task = normalize_task(task)
    sources = sources or {}
    notes = (sources.get("notas") or "").strip()
    links = [e.strip() for e in sources.get("enlaces") or [] if e.strip()]
    has_ref = project.reference is not None
    if original is None:
        if not (has_ref and reference):
            raise ValueError("Indica el rango del original o el de la referencia")
        original = original_range(project.map, *reference)
    if has_ref and reference is None:
        reference = reference_range(project.map, *original)

    orig_data = project.data["original"]
    ref_data = project.data.get("referencia")
    marks = project.data.get("limpieza", {}).get("marcas", [])

    folder = project.dir / part
    figures = folder / "figuras"
    figures.mkdir(parents=True, exist_ok=True)
    for old in figures.iterdir():
        old.unlink()

    orig_pages = cleaning.clean(
        [project.original.page(n) for n in range(original[0], original[1] + 1)], marks)
    files, captions = _save_figures(project.original, orig_pages, "", figures)

    ref_pages, ref_files, ref_captions = [], {}, {}
    groups = {n: [] for n in range(original[0], original[1] + 1)}
    if has_ref and reference:
        ref_pages = cleaning.clean(
            [project.reference.page(n) for n in range(reference[0], reference[1] + 1)],
            marks)
        ref_files, ref_captions = _save_figures(project.reference, ref_pages, "ref-", figures)
        for p in ref_pages:
            target = min(max(project.map[p.number - 1], original[0]), original[1])
            groups[target].append(p)

    sources_md, sources_words, source_pdfs = _pdf_sources(sources.get("pdfs") or [], figures,
                                                          marks)

    lo = orig_data["idioma"].upper()
    lr = ref_data["idioma"].upper() if ref_data else ""
    body, words = [], 0
    for i, p in enumerate(orig_pages, start=1):
        refs = groups[p.number]
        heading = f"## Bloque {i} · {lo} p.{p.number}"
        if refs:
            heading += f" ↔ {lr} p.{_range(refs[0].number, refs[-1].number)}"
        text = _markdown(p, files, captions)
        words += _words(text)
        body += [heading, f"### {lo} · documento · p.{p.number}", text or "_(página sin texto)_"]
        for r in refs:
            ref_text = _markdown(r, ref_files, ref_captions)
            words += _words(ref_text)
            body += [f"### {lr} · otra versión · p.{r.number}",
                     ref_text or "_(página sin texto)_"]

    toc = [f"{'  ' * (level - 1)}- p.{pg} · {t}" for level, t, pg in project.original.toc()
           if original[0] <= pg <= original[1]]
    glossary = (project.glossary.read_text(encoding="utf-8").strip()
                if project.glossary.exists() else "_(vacío: se completa al terminar cada parte)_")

    header = {
        "libro": project.title,
        "parte": part_title or part,
        "paquete": str(folder),
        "glosario": str(project.glossary),
        "original": {"pdf": orig_data["pdf"], "idioma": orig_data["idioma"],
                     "paginas": _range(*original)},
    }
    if ref_data and reference:
        header["referencia"] = {
            "pdf": ref_data["pdf"], "idioma": ref_data["idioma"],
            "paginas": _range(*reference),
            "nota": "otra versión del documento (p. ej. una traducción); solo de apoyo, "
                    "puede tener errores",
        }
    header["tarea"] = task
    header["idioma_salida"] = task["traducir"] or orig_data["idioma"]
    if links or source_pdfs or notes:
        header["fuentes"] = {"notas": bool(notes), "enlaces": len(links),
                             "pdfs": [f"{f['pdf']} p.{f['paginas']}" for f in source_pdfs]}
    header["salida"] = list(output)
    header["estadisticas"] = {
        "paginas_original": original[1] - original[0] + 1,
        "paginas_referencia": len(ref_pages),
        "palabras": words + sources_words,
        "figuras": len(list(figures.iterdir())),
    }

    md = ["---", *(f"{k}: {_yaml(v)}" for k, v in header.items()), "---", "",
          "# Tarea", "", *(f"- {l}" for l in describe_task(task, orig_data["idioma"])), "",
          "# Instrucciones", "", instructions.strip() or "_(sin instrucciones adicionales)_", "",
          "# Glosario", "", glossary, ""]
    if toc:
        md += ["# Índice de la parte", "", *toc, ""]
    if notes or links or sources_md:
        md += ["# Fuentes adicionales", ""]
        if notes:
            md += ["## Notas", "", notes, ""]
        if links:
            md += ["## Enlaces", "", *(f"- {e}" for e in links), ""]
        if sources_md:
            md += ["\n\n".join(sources_md), ""]
    md += ["# Contenido", "", "\n\n".join(body), ""]

    context = folder / "contexto.md"
    context.write_text("\n".join(md), encoding="utf-8")
    project.register_part({
        "id": part,
        "titulo": part_title or part,
        "original": _range(*original),
        "referencia": _range(*reference) if reference else None,
        "tarea": task,
        "fuentes": {"notas": bool(notes), "enlaces": links, "pdfs": source_pdfs},
        "estado": "exportada",
        "fecha": date.today().isoformat(),
    })
    return context
