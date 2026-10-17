"""Command line entry point; argparse texts are user-facing, so they stay in Spanish."""

import argparse
import re
import sys
from pathlib import Path

from . import build, bundle, mapping
from .project import ROOT, Project


def _range(text):
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", text)
    if not m:
        raise argparse.ArgumentTypeError(f"rango inválido: {text!r} (usa 62-86 o 64)")
    start, end = int(m[1]), int(m[2] or m[1])
    if end < start:
        raise argparse.ArgumentTypeError(f"rango al revés: {text!r}")
    return start, end


def _anchor(text):
    m = re.fullmatch(r"(\d+)=(\d+)", text)
    if not m:
        raise argparse.ArgumentTypeError(f"ancla inválida: {text!r} (usa REF=ORIG, p. ej. 77=62)")
    return int(m[1]), int(m[2])


def cmd_new(args):
    title = args.titulo or Path(args.original).stem
    try:
        p = Project.create(args.slug, title, args.original, args.idioma_original,
                           args.referencia, args.idioma_referencia)
    except ValueError as e:
        sys.exit(str(e))
    print(f"Proyecto creado: {p.file}")
    print(f"Original: {len(p.original)} págs · índice con {len(p.original.toc())} entradas")
    if p.reference:
        print(f"Referencia: {len(p.reference)} págs · mapa calculado")


def cmd_projects(args):
    for file in sorted(ROOT.glob("*/libro.json")):
        p = Project(file.parent.name)
        print(f"{p.slug:30} {p.title} · {len(p.data['partes'])} partes")


def cmd_toc(args):
    p = Project(args.slug)
    book = p.reference if args.referencia else p.original
    if book is None:
        sys.exit("Este proyecto no tiene PDF de referencia")
    if not book.has_toc:
        print("(el PDF no trae índice: títulos detectados por tamaño de letra)")
    for level, title, page in book.toc():
        if level <= args.nivel:
            print(f"{page:>5}  {'  ' * (level - 1)}{title}")


def cmd_map(args):
    p = Project(args.slug)
    if not p.reference:
        sys.exit("Este proyecto no tiene PDF de referencia")
    for ref, orig in args.ancla or []:
        p.data["mapa"]["anclas"][str(ref)] = orig
    if args.ancla or args.recalcular:
        p.recompute_map()
        print(f"Mapa recalculado con anclas {p.anchors}")
    if args.referencia:
        print("Original:", "-".join(map(str, mapping.original_range(p.map, *args.referencia))))
    if args.original:
        r = mapping.reference_range(p.map, *args.original)
        print("Referencia:", "-".join(map(str, r)) if r else "(sin páginas)")


def _extra_pdf(text):
    path, _, pages = text.rpartition(":")
    if not path:
        raise argparse.ArgumentTypeError(f"usa RUTA:RANGO, p. ej. apuntes.pdf:3-8 ({text!r})")
    return {"pdf": path, "paginas": _range(pages)}


def _read(path):
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8") if path else ""


def cmd_export(args):
    p = Project(args.slug)
    task = {"traducir": args.traducir, "mejorar_lectura": not args.sin_mejorar,
            "comentarios": args.comentarios, "contexto": args.contexto, "resumen": args.resumen}
    sources = {"notas": _read(args.notas), "enlaces": args.enlace or [], "pdfs": args.pdf or []}
    try:
        context = bundle.export(p, args.parte, args.original, args.referencia,
                                _read(args.instrucciones), args.titulo_parte,
                                task=task, sources=sources)
    except ValueError as e:
        sys.exit(str(e))
    print(f"Paquete listo: {context}")
    print(f"En Claude Code: /libro {context.parent}")


def _pages(text):
    pages = []
    for chunk in text.split(","):
        start, end = _range(chunk.strip())
        pages += range(start, end + 1)
    return pages


def cmd_init(args):
    html = build.init(args.carpeta)
    print(f"HTML de trabajo: {html}")


def cmd_build(args):
    r = build.build(args.carpeta)
    print(f"PDF: {r['pdf']} ({r['pages']} págs)")
    print(f"2 por hoja: {r['pdf_2up']}")
    print("Miniaturas:", *r["sheets"], sep="\n  ")


def cmd_view(args):
    for path in build.view(args.carpeta, args.paginas):
        print(path)


def cmd_print(args):
    from .printing import print_pdf

    out = build.Output(args.carpeta)
    pdf = out.pdf_2up if args.dos_por_hoja else out.pdf
    if not pdf.exists():
        sys.exit(f"Falta {pdf}: primero `atril construir {args.carpeta}`")
    cmd, message = print_pdf(pdf, args.impresora, args.copias, args.paginas, out.part,
                             args.simular)
    print(" ".join(cmd))
    print(message)


def cmd_app(args):
    from .app import serve  # FastAPI is only imported for the app

    serve(args.puerto, open_browser=not args.no_abrir)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="atril", description="Línea de comandos de Atril: nuevo, mapa, exportar, construir, app, imprimir… (ver --help).")
    sub = ap.add_subparsers(required=True)

    s = sub.add_parser("nuevo", help="crear el proyecto de un documento (libro, informe…)")
    s.add_argument("slug", help="nombre corto, p. ej. arquitectura-limpia")
    s.add_argument("--original", "--documento", dest="original", required=True,
                   help="PDF del documento (con texto; no se aceptan escaneos sin texto)")
    s.add_argument("--referencia", "--otra-version", dest="referencia",
                   help="el mismo documento en otro idioma, para compararlo (opcional)")
    s.add_argument("--titulo")
    s.add_argument("--idioma-original", "--idioma", dest="idioma_original", default="en")
    s.add_argument("--idioma-referencia", default="es")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("proyectos", help="listar proyectos")
    s.set_defaults(fn=cmd_projects)

    s = sub.add_parser("indice", help="índice del PDF original (o detectado si no trae)")
    s.add_argument("slug")
    s.add_argument("--nivel", type=int, default=2)
    s.add_argument("--referencia", action="store_true", help="índice de la referencia")
    s.set_defaults(fn=cmd_toc)

    s = sub.add_parser("mapa", help="consultar o corregir el mapa de páginas")
    s.add_argument("slug")
    s.add_argument("--ancla", type=_anchor, action="append", help="REF=ORIG, se puede repetir")
    s.add_argument("--recalcular", action="store_true")
    s.add_argument("--referencia", type=_range, help="rango de la referencia a traducir")
    s.add_argument("--original", type=_range, help="rango del original a traducir")
    s.set_defaults(fn=cmd_map)

    s = sub.add_parser("exportar", help="generar el paquete de una parte y decir qué hacer")
    s.add_argument("slug")
    s.add_argument("parte", help="id de la parte, p. ej. parte-03-solid")
    s.add_argument("--original", type=_range, help="páginas del documento")
    s.add_argument("--referencia", type=_range, help="páginas de la otra versión")
    s.add_argument("--titulo-parte")
    g = s.add_argument_group("tarea (por defecto: mantener el idioma y mejorar la lectura)")
    g.add_argument("--traducir", metavar="IDIOMA", help="traducir a este idioma, p. ej. es")
    g.add_argument("--comentarios", action="store_true", help="recuadros de estudio")
    g.add_argument("--contexto", action="store_true", help="recuadros de contexto y antecedentes")
    g.add_argument("--resumen", action="store_true", help="resumen final de repaso")
    g.add_argument("--sin-mejorar", action="store_true",
                   help="no redibujar ni rehacer la maquetación: solo el texto")
    g = s.add_argument_group("fuentes adicionales")
    g.add_argument("--instrucciones", help="archivo de texto, o - para leer de stdin")
    g.add_argument("--notas", help="archivo con notas o contexto pegado")
    g.add_argument("--enlace", action="append", help="URL de apoyo; se puede repetir")
    g.add_argument("--pdf", type=_extra_pdf, action="append", metavar="RUTA:RANGO",
                   help="páginas de otro PDF como apoyo, p. ej. apuntes.pdf:3-8; se repite")
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("iniciar", help="crear salida/ con la plantilla HTML de una parte")
    s.add_argument("carpeta", help="carpeta de la parte (la que tiene contexto.md)")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("construir", help="HTML → PDF, 2 por hoja y miniaturas de revisión")
    s.add_argument("carpeta", help="carpeta de la parte (la que tiene contexto.md)")
    s.set_defaults(fn=cmd_build)

    s = sub.add_parser("ver", help="renderizar páginas del PDF construido para revisarlas")
    s.add_argument("carpeta")
    s.add_argument("paginas", type=_pages, help="p. ej. 5 o 3,7-9")
    s.set_defaults(fn=cmd_view)

    s = sub.add_parser("imprimir", help="mandar el PDF de una parte a la impresora (lp)")
    s.add_argument("carpeta", help="carpeta de la parte")
    s.add_argument("--2-por-hoja", dest="dos_por_hoja", action="store_true")
    s.add_argument("--copias", type=int, default=1)
    s.add_argument("--paginas", help="p. ej. 1-4,7")
    s.add_argument("--impresora", help="por defecto, la predeterminada de CUPS o ATRIL_IMPRESORA")
    s.add_argument("--simular", action="store_true", help="mostrar el comando sin imprimir")
    s.set_defaults(fn=cmd_print)

    s = sub.add_parser("app", help="abrir la app visual en el navegador")
    s.add_argument("--puerto", type=int, default=8765)
    s.add_argument("--no-abrir", action="store_true", help="no abrir el navegador")
    s.set_defaults(fn=cmd_app)

    args = ap.parse_args(argv)
    args.fn(args)
