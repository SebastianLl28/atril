"""Línea de comandos de Atril: nuevo, mapa, exportar, construir, app, imprimir… (ver --help)."""

import argparse
import re
import sys
from pathlib import Path

from . import construir as salida
from . import paquete
from .proyecto import RAIZ, Proyecto


def _rango(texto):
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", texto)
    if not m:
        raise argparse.ArgumentTypeError(f"rango inválido: {texto!r} (usa 62-86 o 64)")
    desde, hasta = int(m[1]), int(m[2] or m[1])
    if hasta < desde:
        raise argparse.ArgumentTypeError(f"rango al revés: {texto!r}")
    return desde, hasta


def _ancla(texto):
    m = re.fullmatch(r"(\d+)=(\d+)", texto)
    if not m:
        raise argparse.ArgumentTypeError(f"ancla inválida: {texto!r} (usa REF=ORIG, p. ej. 77=62)")
    return int(m[1]), int(m[2])


def nuevo(args):
    titulo = args.titulo or Path(args.original).stem
    try:
        p = Proyecto.crear(args.slug, titulo, args.original, args.idioma_original,
                           args.referencia, args.idioma_referencia)
    except ValueError as e:
        sys.exit(str(e))
    print(f"Proyecto creado: {p.archivo}")
    print(f"Original: {len(p.original)} págs · índice con {len(p.original.indice())} entradas")
    if p.referencia:
        print(f"Referencia: {len(p.referencia)} págs · mapa calculado")


def proyectos(args):
    for archivo in sorted(RAIZ.glob("*/libro.json")):
        p = Proyecto(archivo.parent.name)
        print(f"{p.slug:30} {p.titulo} · {len(p.datos['partes'])} partes")


def indice(args):
    p = Proyecto(args.slug)
    libro = p.referencia if args.referencia else p.original
    if libro is None:
        sys.exit("Este proyecto no tiene PDF de referencia")
    if not libro.tiene_indice:
        print("(el PDF no trae índice: títulos detectados por tamaño de letra)")
    for nivel, titulo, pagina in libro.indice():
        if nivel <= args.nivel:
            print(f"{pagina:>5}  {'  ' * (nivel - 1)}{titulo}")


def mapa(args):
    p = Proyecto(args.slug)
    if not p.referencia:
        sys.exit("Este proyecto no tiene PDF de referencia")
    for ref, orig in args.ancla or []:
        p.datos["mapa"]["anclas"][str(ref)] = orig
    if args.ancla or args.recalcular:
        p.recalcular_mapa()
        print(f"Mapa recalculado con anclas {p.anclas}")
    if args.referencia:
        print("Original:", "-".join(map(str, paquete.rango_original(p.mapa, *args.referencia))))
    if args.original:
        r = paquete.rango_referencia(p.mapa, *args.original)
        print("Referencia:", "-".join(map(str, r)) if r else "(sin páginas)")


def _pdf_extra(texto):
    ruta, _, rango = texto.rpartition(":")
    if not ruta:
        raise argparse.ArgumentTypeError(f"usa RUTA:RANGO, p. ej. apuntes.pdf:3-8 ({texto!r})")
    return {"pdf": ruta, "paginas": _rango(rango)}


def _leer(ruta):
    if ruta == "-":
        return sys.stdin.read()
    return Path(ruta).read_text(encoding="utf-8") if ruta else ""


def exportar(args):
    p = Proyecto(args.slug)
    tarea = {"traducir": args.traducir, "mejorar_lectura": not args.sin_mejorar,
             "comentarios": args.comentarios, "contexto": args.contexto, "resumen": args.resumen}
    fuentes = {"notas": _leer(args.notas), "enlaces": args.enlace or [], "pdfs": args.pdf or []}
    try:
        contexto = paquete.exportar(p, args.parte, args.original, args.referencia,
                                    _leer(args.instrucciones), args.titulo_parte,
                                    tarea=tarea, fuentes=fuentes)
    except ValueError as e:
        sys.exit(str(e))
    print(f"Paquete listo: {contexto}")
    print(f"En Claude Code: /libro {contexto.parent}")


def _paginas(texto):
    paginas = []
    for trozo in texto.split(","):
        desde, hasta = _rango(trozo.strip())
        paginas += range(desde, hasta + 1)
    return paginas


def iniciar(args):
    html = salida.iniciar(args.carpeta)
    print(f"HTML de trabajo: {html}")


def construir(args):
    r = salida.construir(args.carpeta)
    print(f"PDF: {r['pdf']} ({r['paginas']} págs)")
    print(f"2 por hoja: {r['pdf_2x1']}")
    print("Miniaturas:", *r["miniaturas"], sep="\n  ")


def ver(args):
    for ruta in salida.ver(args.carpeta, args.paginas):
        print(ruta)


def imprimir(args):
    from .imprimir import imprimir as mandar

    s = salida.Salida(args.carpeta)
    pdf = s.pdf_2x1 if args.dos_por_hoja else s.pdf
    if not pdf.exists():
        sys.exit(f"Falta {pdf}: primero `atril construir {args.carpeta}`")
    cmd, mensaje = mandar(pdf, args.impresora, args.copias, args.paginas, s.parte, args.simular)
    print(" ".join(cmd))
    print(mensaje)


def app(args):
    from .app import servir  # FastAPI solo se importa para la app

    servir(args.puerto, abrir=not args.no_abrir)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="atril", description=__doc__)
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
    s.set_defaults(fn=nuevo)

    s = sub.add_parser("proyectos", help="listar proyectos")
    s.set_defaults(fn=proyectos)

    s = sub.add_parser("indice", help="índice del PDF original (o detectado si no trae)")
    s.add_argument("slug")
    s.add_argument("--nivel", type=int, default=2)
    s.add_argument("--referencia", action="store_true", help="índice de la referencia")
    s.set_defaults(fn=indice)

    s = sub.add_parser("mapa", help="consultar o corregir el mapa de páginas")
    s.add_argument("slug")
    s.add_argument("--ancla", type=_ancla, action="append", help="REF=ORIG, se puede repetir")
    s.add_argument("--recalcular", action="store_true")
    s.add_argument("--referencia", type=_rango, help="rango de la referencia a traducir")
    s.add_argument("--original", type=_rango, help="rango del original a traducir")
    s.set_defaults(fn=mapa)

    s = sub.add_parser("exportar", help="generar el paquete de una parte y decir qué hacer")
    s.add_argument("slug")
    s.add_argument("parte", help="id de la parte, p. ej. parte-03-solid")
    s.add_argument("--original", type=_rango, help="páginas del documento")
    s.add_argument("--referencia", type=_rango, help="páginas de la otra versión")
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
    g.add_argument("--pdf", type=_pdf_extra, action="append", metavar="RUTA:RANGO",
                   help="páginas de otro PDF como apoyo, p. ej. apuntes.pdf:3-8; se repite")
    s.set_defaults(fn=exportar)

    s = sub.add_parser("iniciar", help="crear salida/ con la plantilla HTML de una parte")
    s.add_argument("carpeta", help="carpeta de la parte (la que tiene contexto.md)")
    s.set_defaults(fn=iniciar)

    s = sub.add_parser("construir", help="HTML → PDF, 2 por hoja y miniaturas de revisión")
    s.add_argument("carpeta", help="carpeta de la parte (la que tiene contexto.md)")
    s.set_defaults(fn=construir)

    s = sub.add_parser("ver", help="renderizar páginas del PDF construido para revisarlas")
    s.add_argument("carpeta")
    s.add_argument("paginas", type=_paginas, help="p. ej. 5 o 3,7-9")
    s.set_defaults(fn=ver)

    s = sub.add_parser("imprimir", help="mandar el PDF de una parte a la impresora (lp)")
    s.add_argument("carpeta", help="carpeta de la parte")
    s.add_argument("--2-por-hoja", dest="dos_por_hoja", action="store_true")
    s.add_argument("--copias", type=int, default=1)
    s.add_argument("--paginas", help="p. ej. 1-4,7")
    s.add_argument("--impresora", help="por defecto, la predeterminada de CUPS o ATRIL_IMPRESORA")
    s.add_argument("--simular", action="store_true", help="mostrar el comando sin imprimir")
    s.set_defaults(fn=imprimir)

    s = sub.add_parser("app", help="abrir la app visual en el navegador")
    s.add_argument("--puerto", type=int, default=8765)
    s.add_argument("--no-abrir", action="store_true", help="no abrir el navegador")
    s.set_defaults(fn=app)

    args = ap.parse_args(argv)
    args.fn(args)
