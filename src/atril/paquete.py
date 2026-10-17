"""Escribe el paquete de una parte: contexto.md con el texto ya fusionado + figuras/.

Además del texto, el paquete dice qué hacer con él (`tarea`: traducir o no, mejorar la
lectura, comentarios, contexto, resumen) y suma las fuentes adicionales de la parte: notas
pegadas, enlaces y páginas de otros PDFs.
"""

import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from . import limpieza
from .mapa import rango_original, rango_referencia
from .pdf import PIE_FIGURA, Libro, solo_imagenes

# Distancia máxima (pt) entre el borde inferior de una imagen y su pie de figura.
DISTANCIA_PIE = 60

TAREA = {
    "traducir": None,         # código del idioma de salida, o None para mantener el del documento
    "mejorar_lectura": True,  # maquetación limpia, diagramas redibujados, notas en su sitio
    "comentarios": False,     # recuadros de estudio que explican el texto
    "contexto": False,        # recuadros con antecedentes, a partir de las fuentes adicionales
    "resumen": False,         # resumen final de repaso
}

DESCRIPCION_TAREA = {
    "mejorar_lectura": "Mejorar la lectura: maquetación limpia, diagramas redibujados en "
                       "vectores, notas al pie en su sitio y errores de extracción corregidos.",
    "comentarios": "Comentarios de estudio: recuadros que explican lo difícil (figuras, "
                   "términos, razonamientos).",
    "contexto": "Contexto: recuadros con antecedentes y relaciones con otras ideas, apoyados "
                "en las fuentes adicionales.",
    "resumen": "Resumen final: una página de repaso al terminar.",
}


def normalizar_tarea(tarea=None):
    t = {**TAREA, **(tarea or {})}
    desconocidas = set(t) - set(TAREA)
    if desconocidas:
        raise ValueError(f"Tarea desconocida: {', '.join(sorted(desconocidas))}")
    t["traducir"] = (t["traducir"] or "").strip().lower() or None
    return t


def describir_tarea(tarea, idioma_documento):
    lineas = []
    if tarea["traducir"] and tarea["traducir"] != idioma_documento:
        lineas.append(f"Traducir del {idioma_documento} al {tarea['traducir']}, fiel al documento.")
    else:
        lineas.append(f"Mantener el idioma del documento ({idioma_documento}): transcribir fiel, "
                      "sin traducir ni resumir.")
    lineas += [DESCRIPCION_TAREA[k] for k in DESCRIPCION_TAREA if tarea[k]]
    return lineas


def _yaml(valor):
    """Escalares y dicts en YAML de flujo; json.dumps produce cadenas YAML válidas."""
    if isinstance(valor, dict):
        return "{ " + ", ".join(f"{k}: {_yaml(v)}" for k, v in valor.items()) + " }"
    if isinstance(valor, list):
        return "[" + ", ".join(_yaml(v) for v in valor) + "]"
    if isinstance(valor, str):
        return json.dumps(valor, ensure_ascii=False)
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if valor is None:
        return "null"
    return str(valor)


def _rango(desde, hasta):
    return f"{desde}" if desde == hasta else f"{desde}-{hasta}"


def _nombrar_figuras(paginas, prefijo):
    """Asigna nombre de archivo a cada imagen: fig-7.1 si tiene pie de figura, si no ilus-p064-1."""
    nombres, pies = {}, {}
    for p in paginas:
        n = 0
        for i, e in enumerate(p.elementos):
            if e.tipo != "imagen" or e.xref in nombres:
                continue
            n += 1
            pie = next((s for s in p.elementos[i + 1:]
                        if s.tipo == "pie_figura" and 0 <= s.bbox[1] - e.bbox[3] < DISTANCIA_PIE),
                       None)
            if pie:
                numero = PIE_FIGURA.match(pie.texto).group(0).split()[-1]
                nombres[e.xref] = f"{prefijo}fig-{numero}"
                pies[e.xref] = pie.texto
            else:
                nombres[e.xref] = f"{prefijo}ilus-p{p.numero:03d}-{n}"
    return nombres, pies


def _markdown(pagina, archivos, pies):
    partes = []
    for e in pagina.elementos:
        if e.tipo == "titulo":
            partes.append(f"#### {e.texto}")
        elif e.tipo == "subtitulo":
            partes.append(f"##### {e.texto}")
        elif e.tipo == "cita":
            partes.append(f"> {e.texto}")
        elif e.tipo == "codigo":
            partes.append(f"```\n{e.texto}\n```")
        elif e.tipo == "vineta":
            partes.append("\n".join(f"- {item}" for item in e.texto.split("\n")))
        elif e.tipo == "pie_figura":
            if e.texto not in pies.values():  # el de una figura ya va como texto alternativo
                partes.append(f"*{e.texto}*")
        elif e.tipo == "imagen":
            alt = pies.get(e.xref) or "Ilustración"
            partes.append(f"![{alt}](figuras/{archivos[e.xref]})")
        else:
            partes.append(e.texto)
    return "\n\n".join(partes)


def _guardar_figuras(libro, paginas, prefijo, carpeta):
    nombres, pies = _nombrar_figuras(paginas, prefijo)
    archivos = {}
    for xref, nombre in nombres.items():
        datos, ext = libro.imagen(xref)
        archivos[xref] = f"{nombre}.{ext}"
        (carpeta / archivos[xref]).write_bytes(datos)
    return archivos, pies


def _palabras(texto):
    return len(re.findall(r"\w+", texto))


def _fuentes_pdf(pdfs, figuras, marcas):
    """Texto limpio de las páginas elegidas de otros PDFs. Devuelve (markdown, palabras, resumen)."""
    partes, palabras, resumen = [], 0, []
    for i, f in enumerate(pdfs, start=1):
        ruta = Path(f["pdf"]).expanduser()
        if not ruta.is_file():
            raise ValueError(f"No existe el PDF de apoyo {ruta}")
        if solo_imagenes(ruta):
            raise ValueError(f"{ruta.name} es solo imágenes (sin texto): no se acepta")
        libro = Libro(ruta)
        desde, hasta = f["paginas"]
        if not 1 <= desde <= hasta <= len(libro):
            raise ValueError(f"{ruta.name} tiene {len(libro)} páginas; rango {desde}-{hasta} inválido")
        pags = limpieza.limpiar([libro.pagina(n) for n in range(desde, hasta + 1)], marcas)
        archivos, pies = _guardar_figuras(libro, pags, f"fuente{i}-", figuras)
        nombre = unicodedata.normalize("NFC", ruta.name)
        partes += [f"## PDF · {nombre} · p.{_rango(desde, hasta)}", f"Ruta: `{ruta}`"]
        for p in pags:
            texto = _markdown(p, archivos, pies)
            palabras += _palabras(texto)
            partes += [f"### {nombre} · p.{p.numero}", texto or "_(página sin texto)_"]
        resumen.append({"pdf": str(ruta), "paginas": _rango(desde, hasta)})
    return partes, palabras, resumen


def exportar(proyecto, parte, original=None, referencia=None, instrucciones="",
             titulo_parte=None, salida=("carta", "2-por-hoja"), tarea=None, fuentes=None):
    """Genera <proyecto>/<parte>/contexto.md y figuras/. Devuelve la ruta de contexto.md.

    Basta con indicar uno de los dos rangos (tuplas 1-based, inclusivas): el otro sale del mapa.
    `tarea` sigue el formato de TAREA. `fuentes` admite {"notas": str, "enlaces": [url],
    "pdfs": [{"pdf": ruta, "paginas": (desde, hasta)}]}.
    """
    tarea = normalizar_tarea(tarea)
    fuentes = fuentes or {}
    notas = (fuentes.get("notas") or "").strip()
    enlaces = [e.strip() for e in fuentes.get("enlaces") or [] if e.strip()]
    hay_ref = proyecto.referencia is not None
    if original is None:
        if not (hay_ref and referencia):
            raise ValueError("Indica el rango del original o el de la referencia")
        original = rango_original(proyecto.mapa, *referencia)
    if hay_ref and referencia is None:
        referencia = rango_referencia(proyecto.mapa, *original)

    datos_orig = proyecto.datos["original"]
    datos_ref = proyecto.datos.get("referencia")
    marcas = proyecto.datos.get("limpieza", {}).get("marcas", [])

    carpeta = proyecto.dir / parte
    figuras = carpeta / "figuras"
    figuras.mkdir(parents=True, exist_ok=True)
    for viejo in figuras.iterdir():
        viejo.unlink()

    pags_orig = limpieza.limpiar(
        [proyecto.original.pagina(n) for n in range(original[0], original[1] + 1)], marcas)
    archivos, pies = _guardar_figuras(proyecto.original, pags_orig, "", figuras)

    pags_ref, a_ref, pies_ref = [], {}, {}
    grupos = {n: [] for n in range(original[0], original[1] + 1)}
    if hay_ref and referencia:
        pags_ref = limpieza.limpiar(
            [proyecto.referencia.pagina(n) for n in range(referencia[0], referencia[1] + 1)],
            marcas)
        a_ref, pies_ref = _guardar_figuras(proyecto.referencia, pags_ref, "ref-", figuras)
        for p in pags_ref:
            destino = min(max(proyecto.mapa[p.numero - 1], original[0]), original[1])
            grupos[destino].append(p)

    md_fuentes, palabras_fuentes, pdfs_fuente = _fuentes_pdf(fuentes.get("pdfs") or [], figuras,
                                                              marcas)

    io = datos_orig["idioma"].upper()
    ir = datos_ref["idioma"].upper() if datos_ref else ""
    cuerpo, palabras = [], 0
    for i, p in enumerate(pags_orig, start=1):
        refs = grupos[p.numero]
        titulo = f"## Bloque {i} · {io} p.{p.numero}"
        if refs:
            titulo += f" ↔ {ir} p.{_rango(refs[0].numero, refs[-1].numero)}"
        texto = _markdown(p, archivos, pies)
        palabras += _palabras(texto)
        cuerpo += [titulo, f"### {io} · documento · p.{p.numero}", texto or "_(página sin texto)_"]
        for r in refs:
            texto_ref = _markdown(r, a_ref, pies_ref)
            palabras += _palabras(texto_ref)
            cuerpo += [f"### {ir} · otra versión · p.{r.numero}",
                       texto_ref or "_(página sin texto)_"]

    indice = [f"{'  ' * (nivel - 1)}- p.{pag} · {t}" for nivel, t, pag in proyecto.original.indice()
              if original[0] <= pag <= original[1]]
    glosario = (proyecto.glosario.read_text(encoding="utf-8").strip()
                if proyecto.glosario.exists() else "_(vacío: se completa al terminar cada parte)_")

    cabecera = {
        "libro": proyecto.titulo,
        "parte": titulo_parte or parte,
        "paquete": str(carpeta),
        "glosario": str(proyecto.glosario),
        "original": {"pdf": datos_orig["pdf"], "idioma": datos_orig["idioma"],
                     "paginas": _rango(*original)},
    }
    if datos_ref and referencia:
        cabecera["referencia"] = {
            "pdf": datos_ref["pdf"], "idioma": datos_ref["idioma"],
            "paginas": _rango(*referencia),
            "nota": "otra versión del documento (p. ej. una traducción); solo de apoyo, "
                    "puede tener errores",
        }
    cabecera["tarea"] = tarea
    cabecera["idioma_salida"] = tarea["traducir"] or datos_orig["idioma"]
    if enlaces or pdfs_fuente or notas:
        cabecera["fuentes"] = {"notas": bool(notas), "enlaces": len(enlaces),
                               "pdfs": [f"{f['pdf']} p.{f['paginas']}" for f in pdfs_fuente]}
    cabecera["salida"] = list(salida)
    cabecera["estadisticas"] = {
        "paginas_original": original[1] - original[0] + 1,
        "paginas_referencia": len(pags_ref),
        "palabras": palabras + palabras_fuentes,
        "figuras": len(list(figuras.iterdir())),
    }

    md = ["---", *(f"{k}: {_yaml(v)}" for k, v in cabecera.items()), "---", "",
          "# Tarea", "", *(f"- {l}" for l in describir_tarea(tarea, datos_orig["idioma"])), "",
          "# Instrucciones", "", instrucciones.strip() or "_(sin instrucciones adicionales)_", "",
          "# Glosario", "", glosario, ""]
    if indice:
        md += ["# Índice de la parte", "", *indice, ""]
    if notas or enlaces or md_fuentes:
        md += ["# Fuentes adicionales", ""]
        if notas:
            md += ["## Notas", "", notas, ""]
        if enlaces:
            md += ["## Enlaces", "", *(f"- {e}" for e in enlaces), ""]
        if md_fuentes:
            md += ["\n\n".join(md_fuentes), ""]
    md += ["# Contenido", "", "\n\n".join(cuerpo), ""]

    contexto = carpeta / "contexto.md"
    contexto.write_text("\n".join(md), encoding="utf-8")
    proyecto.registrar_parte({
        "id": parte,
        "titulo": titulo_parte or parte,
        "original": _rango(*original),
        "referencia": _rango(*referencia) if referencia else None,
        "tarea": tarea,
        "fuentes": {"notas": bool(notas), "enlaces": enlaces, "pdfs": pdfs_fuente},
        "estado": "exportada",
        "fecha": date.today().isoformat(),
    })
    return contexto
