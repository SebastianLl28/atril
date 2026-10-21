# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What it is

Atril prepares documents (books, reports, notes) so they can be read and studied better, part by
part. You pick a page range from a PDF with text (the **documento**, i.e. the document;
`original` in the code) and, optionally, from an **otra versión** (another version) in another
language (`reference` in the code, `referencia` in `libro.json`). For each part you choose the
**tarea** (task):
- translate or keep the language;
- improve readability;
- comments, context, summary.

You can add **fuentes adicionales** (additional sources): notes, links and pages from other PDFs.
Atril exports a `contexto.md` with the text already cleaned and merged, plus its figures. **Not
translating is not a rare case**: the default output language is the document's. Image-only PDFs
are rejected (`pdf.is_image_only`); there is no OCR.

Claude Code then processes that bundle with the `/libro` skill to produce the final PDF.
`PLAN.md` lists the phases and their status: read it before starting new work.

**Design constraint:** nothing may call the Anthropic API. The AI part happens inside Claude
Code (the `/libro` skill, on the user's subscription). Everything mechanical is deterministic
code, to use less of the plan.

## Commands

```fish
uv sync                                        # install dependencies
uv run pytest                                  # all tests
uv run pytest tests/test_part_iii.py::test_all_20_figures_are_extracted   # one test
uv run atril --help                            # CLI: nuevo | proyectos | indice | mapa | exportar
                                               #      iniciar | construir | ver (output to PDF) | app
```

`tests/test_part_iii.py` uses the real PDFs from `~/Documents/books` (Arquitectura Limpia) and
is skipped if they are missing (same as the app = CLI test in `tests/test_app.py`);
`tests/test_output.py` and the rest of `test_app.py` do not need the PDFs. The Spanish PDF's
name uses a decomposed «ñ» (NFD): find it with a glob (`Espa*l.pdf`), not the literal name.

## Architecture

Flow: `pdf.Book` → `cleaning.clean` → `bundle.export` → `contexto.md`, with
`mapping` and `project` around it.

- **`pdf.py`**: turns each page into a list of `Element` (kind: title, subtitle,
  paragraph, quote, code, bullet, caption, image), sorted by vertical position.
  - Classification is **relative to the body font size** (`body_size`, the most common size in
    a sample of the book), not to absolute sizes.
  - Monospaced fonts mark code: if the whole block is mono, it is a code block; if they are
    fragments inside prose, they become `` `code` ``.
  - Images covering more than 80 % of the page are discarded: they are scans, like every page
    of the Spanish PDF, not figures.
- **`cleaning.py`**: removes fixed marks (`MARKS`, plus `limpieza.marcas` from libro.json),
  headers and footers repeated in the top or bottom band of the page, and page numbers. Then
  `merge` rebuilds paragraphs split line by line (the scanned PDF has one block per line) and
  joins consecutive code.
- **`mapping.py`**: pairs each reference page with an original page, without AI.
  - Anchors are words identical in both languages, weighted by idf, and figure numbers.
  - A monotonic dynamic program picks the path: the original page advances 0–2 for each
    reference page.
  - Manual anchors (`atril mapa --ancla REF=ORIG`) force the path. They are saved in
    `libro.json` and the whole map is recomputed.
- **`project.py`**: each book's folder lives **outside the repo**, in
  `~/Documents/books/proyectos/<slug>/` (override with `ATRIL_PROYECTOS`). It contains:
  - `libro.json`: PDF paths, languages, map, anchors and exported parts;
  - `glosario.md`: updated by the skill and copied into each new export;
  - one folder per part.
- **`bundle.py`**: one range is enough; the other is derived from the map. It writes:
  - `<parte>/contexto.md`: YAML header with absolute paths to the original PDFs as a
    fallback, `tarea` and `idioma_salida`. Then the sections `# Tarea` (in words),
    `# Instrucciones`, `# Glosario`, `# Índice de la parte`, `# Fuentes adicionales` (notes,
    links and the cleaned text of other PDFs) and `# Contenido`, with one `## Bloque` per
    document page and its other-version pages grouped under it;
  - `<parte>/figuras/`: images in their original format, named `fig-7.1` if they have a
    caption or `ilus-pNNN-k` if not. Those from the other version get the `ref-` prefix and
    those from supporting PDFs, `fuenteN-`.

  `bundle.TASK` defines the task fields; the app (`app.Task`), the CLI and the cover page
  (`build._cover_texts`) follow it.

  The `/libro` skill consumes this format: if it changes, update both.
- **`build.py`** + **`template/`** (`libro.css`, `base.html`): everything goes in
  `<parte>/salida/`. `init` (`atril iniciar`) creates `<parte>.html` from the template. `build`
  (`atril construir`) copies `libro.css`, generates the PDF (WeasyPrint), the 2-up version
  (pypdf) and the thumbnails `revision/hoja-NN.png` (PyMuPDF), and marks the part `construida`.
  Per-part tweaks go in a `<style>` in its HTML, not in `libro.css`.
- **`svg.py`**: diagram library (`Svg` with `cls`, `arrow`, `actor`, `component`…). Each
  part uses it from its `salida/figs.py`.
- **`app.py`** + **`web/`** + **`thumbnails.py`**: the visual app (`atril app`).
  `create_app(root, books, cache)` builds the FastAPI app. It keeps one open `Project` per slug
  in memory and guards PyMuPDF with a lock, because it is not thread-safe. The frontend is
  HTML + JS with no build step. `web/app.js` duplicates in JS `original_range` and
  `reference_range` from `mapping.py` (`originalRange`, `referenceRange`): if they change,
  change both. Page texts are cached in `Book.texts`.
- **Detected table of contents** (`Book.detected_toc`): if the PDF has no TOC, titles are
  found by size relative to the body. Pages with a very large chapter number (≥ 2.3×) are
  chapters.
- **`.claude/skills/libro/SKILL.md`**: the `/libro` skill, with the steps and the style rules
  taken from the SOLID case.

`referencia/solid/` is the hand-made case (Part III, SOLID principles): `solid.html` and
`figs.py`, which uses `atril.svg`. It is the skill's style model and the template's regression
test: compiled with `libro.css` it must produce the same 32 pages. If `libro.css` or `svg.py`
is touched, `tests/test_output.py` checks it. `en-p62-86.txt` is the reference the tests use to
check that the extracted text is complete.

## Conventions

- Internal code is in English: module, function, class and variable names, comments and
  docstrings. Comments only when they explain something the code does not say.
- These stay in Spanish: everything the user sees (CLI and app text, error messages), CLI
  command names and their flags, and on-disk or shared formats: `libro.json` keys, the content
  of `contexto.md`, names of written files and folders, API routes and JSON fields, and
  environment variables.
- Commit messages are in English, with no `Co-Authored-By` or `Claude-Session` trailers.
- Conversation with the user is in Spanish.
