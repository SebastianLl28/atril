"""Quita restos de formato y encabezados o pies que se repiten en cada página."""

import re
from collections import Counter

# Marcas que nunca son contenido del libro. Cada libro puede sumar las suyas en libro.json.
MARCAS = [
    r"^Machine Translated by Google$",
    r"^Click here to view code image$",
    r"^Haga clic aquí para ver la imagen del código\.?$",
]

# Franja superior e inferior (fracción del alto) donde viven encabezados y números de página.
FRANJA = 0.08


def _clave(texto):
    return re.sub(r"\d+", "#", texto.lower()).strip()


def _en_franja(elemento, alto):
    y0, y1 = elemento.bbox[1], elemento.bbox[3]
    return y1 <= alto * FRANJA or y0 >= alto * (1 - FRANJA)


def repetidos(paginas, minimo=0.5):
    """Textos en la franja de encabezado o pie que aparecen en al menos la mitad de las páginas."""
    if len(paginas) < 4:
        return set()
    conteo = Counter()
    for p in paginas:
        conteo.update({_clave(e.texto) for e in p.elementos if e.texto and _en_franja(e, p.alto)})
    return {c for c, n in conteo.items() if n >= minimo * len(paginas)}


FIN_DE_FRASE = re.compile(r"[.:!?»”\"')\]]$")


def _juntar(a, b, separador):
    x0, y0, x1, y1 = a.bbox
    bx0, by0, bx1, by1 = b.bbox
    a.texto = a.texto + separador + b.texto
    a.bbox = (min(x0, bx0), min(y0, by0), max(x1, bx1), max(y1, by1))


def fusionar(pagina):
    """Reconstruye párrafos partidos en varias líneas y une el código línea a línea."""
    resultado = []
    for e in pagina.elementos:
        previo = resultado[-1] if resultado else None
        if previo and previo.tipo == e.tipo == "codigo":
            _juntar(previo, e, "\n")
        elif (previo and previo.tipo == e.tipo == "parrafo"
              and not FIN_DE_FRASE.search(previo.texto)
              and not previo.texto.isupper() and not e.texto.isupper()):  # títulos en mayúsculas
            _juntar(previo, e, " ")
        else:
            resultado.append(e)
    pagina.elementos = resultado


def limpiar(paginas, marcas_extra=()):
    """Filtra in situ los elementos que no son contenido."""
    patrones = [re.compile(m, re.I) for m in [*MARCAS, *marcas_extra]]
    quitar = repetidos(paginas)
    for p in paginas:
        p.elementos = [
            e for e in p.elementos
            if e.tipo == "imagen" or not (
                any(r.search(e.texto) for r in patrones)
                or (_en_franja(e, p.alto) and (_clave(e.texto) in quitar or e.texto.isdigit()))
            )
        ]
        fusionar(p)
    return paginas
