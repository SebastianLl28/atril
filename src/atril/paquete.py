"""Escribe el paquete de una parte: contexto.md con el texto ya fusionado + figuras/."""

import json
import re
from datetime import date

from . import limpieza
from .mapa import rango_original, rango_referencia
from .pdf import PIE_FIGURA

# Distancia máxima (pt) entre el borde inferior de una imagen y su pie de figura.
DISTANCIA_PIE = 60


def _yaml(valor):
    """Escalares y dicts en YAML de flujo; json.dumps produce cadenas YAML válidas."""
    if isinstance(valor, dict):
        return "{ " + ", ".join(f"{k}: {_yaml(v)}" for k, v in valor.items()) + " }"
    if isinstance(valor, list):
        return "[" + ", ".join(_yaml(v) for v in valor) + "]"
    if isinstance(valor, str):
        return json.dumps(valor, ensure_ascii=False)
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


def exportar(proyecto, parte, original=None, referencia=None, instrucciones="",
             titulo_parte=None, salida=("carta", "2-por-hoja"), idioma_destino="es"):
    """Genera <proyecto>/<parte>/contexto.md y figuras/. Devuelve la ruta de contexto.md.

    Basta con indicar uno de los dos rangos (tuplas 1-based, inclusivas): el otro sale del mapa.
    """
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
        cuerpo += [titulo, f"### {io} · original · p.{p.numero}", texto or "_(página sin texto)_"]
        for r in refs:
            texto_ref = _markdown(r, a_ref, pies_ref)
            palabras += _palabras(texto_ref)
            cuerpo += [f"### {ir} · referencia · p.{r.numero}", texto_ref or "_(página sin texto)_"]

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
            "nota": "versión de apoyo; puede tener errores de traducción",
        }
    cabecera["idioma_destino"] = idioma_destino
    cabecera["salida"] = list(salida)
    cabecera["estadisticas"] = {
        "paginas_original": original[1] - original[0] + 1,
        "paginas_referencia": len(pags_ref),
        "palabras": palabras,
        "figuras": len(list(figuras.iterdir())),
    }

    md = ["---", *(f"{k}: {_yaml(v)}" for k, v in cabecera.items()), "---", "",
          "# Instrucciones", "", instrucciones.strip() or "_(sin instrucciones adicionales)_", "",
          "# Glosario del libro", "", glosario, ""]
    if indice:
        md += ["# Índice de la parte", "", *indice, ""]
    md += ["# Contenido", "", "\n\n".join(cuerpo), ""]

    contexto = carpeta / "contexto.md"
    contexto.write_text("\n".join(md), encoding="utf-8")
    proyecto.registrar_parte({
        "id": parte,
        "titulo": titulo_parte or parte,
        "original": _rango(*original),
        "referencia": _rango(*referencia) if referencia else None,
        "idioma_destino": idioma_destino,
        "estado": "exportada",
        "fecha": date.today().isoformat(),
    })
    return contexto
