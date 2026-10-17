"""Empareja las páginas de la referencia (p. ej. la traducción) con las del original, sin IA.

Anclas: palabras idénticas en ambos idiomas (identificadores de código, siglas, apellidos)
y referencias a figuras normalizadas. Cada ancla pesa según qué tan rara es (idf). Luego una
programación dinámica monótona elige el camino de mayor puntaje: la página del original
avanza 0, 1 o 2 por cada página de la referencia. Las anclas manuales fijan el camino.
"""

import math
import re
from collections import Counter

PALABRA = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
FIGURA = re.compile(r"\b(?:Figure|Figura|Fig\.)\s+(\d+\.\d+)")
SALTOS = (0, 1, 2)


def anclas(texto):
    tokens = {w.lower() for w in PALABRA.findall(texto)}
    tokens |= {"fig:" + n for n in FIGURA.findall(texto)}
    return tokens


def calcular(textos_ref, textos_orig, fijas=None):
    """Devuelve, para cada página de la referencia, la página del original (ambas 1-based).

    `fijas` es {pagina_ref: pagina_orig} con correcciones manuales que el camino debe respetar.
    """
    fijas = fijas or {}
    ref = [anclas(t) for t in textos_ref]
    orig = [anclas(t) for t in textos_orig]

    # Solo cuenta lo que existe en ambos libros: lo que no se traduce.
    comunes = set().union(*ref) & set().union(*orig)
    ref = [a & comunes for a in ref]
    orig = [a & comunes for a in orig]
    df = Counter(t for a in ref + orig for t in a)
    total = len(ref) + len(orig)
    idf = {t: math.log(total / c) for t, c in df.items()}

    R, O = len(ref), len(orig)
    nada = float("-inf")
    puntaje = [[nada] * O for _ in range(R)]
    atras = [[0] * O for _ in range(R)]
    for i in range(R):
        fija = fijas.get(i + 1)
        columnas = [fija - 1] if fija and 0 < fija <= O else range(O)
        for j in columnas:
            ganancia = sum(idf[t] for t in ref[i] & orig[j])
            if i == 0:
                puntaje[i][j] = ganancia
                continue
            mejor, previo = nada, j
            for k in SALTOS:
                if j - k >= 0 and puntaje[i - 1][j - k] > mejor:
                    mejor, previo = puntaje[i - 1][j - k], j - k
            if mejor == nada and fija:
                # Un ancla manual puede exigir un salto mayor: se permite desde cualquier
                # columna anterior para no dejar el camino cortado.
                for k in range(j + 1):
                    if puntaje[i - 1][k] > mejor:
                        mejor, previo = puntaje[i - 1][k], k
            if mejor > nada:
                puntaje[i][j] = mejor + ganancia
                atras[i][j] = previo

    j = max(range(O), key=lambda c: puntaje[R - 1][c])
    camino = [0] * R
    for i in range(R - 1, -1, -1):
        camino[i] = j + 1
        j = atras[i][j]
    return camino


def rango_original(mapa, desde, hasta):
    """Páginas del original que cubren un rango de la referencia."""
    paginas = mapa[desde - 1:hasta]
    return min(paginas), max(paginas)


def rango_referencia(mapa, desde, hasta):
    """Páginas de la referencia que caen dentro de un rango del original."""
    paginas = [i + 1 for i, p in enumerate(mapa) if desde <= p <= hasta]
    return (min(paginas), max(paginas)) if paginas else None
