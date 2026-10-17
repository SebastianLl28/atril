"""Impresión con CUPS (`lp`). Por defecto, la impresora predeterminada (la Epson L3250).

`ATRIL_IMPRESORA` elige otra; `simular=True` devuelve el comando sin imprimir nada.
"""

import os
import shutil
import subprocess


def impresoras():
    """(lista de impresoras, predeterminada) según `lpstat`; vacía si CUPS no está."""
    if not shutil.which("lpstat"):
        return [], None
    lista = subprocess.run(["lpstat", "-p"], capture_output=True, text=True).stdout
    nombres = [l.split()[1] for l in lista.splitlines() if l.startswith("printer ")]
    pred = subprocess.run(["lpstat", "-d"], capture_output=True, text=True).stdout
    predeterminada = pred.split(":", 1)[1].strip() if ":" in pred else None
    return nombres, predeterminada


def comando(pdf, impresora=None, copias=1, paginas=None, titulo=None):
    impresora = impresora or os.environ.get("ATRIL_IMPRESORA")
    cmd = ["lp"]
    if impresora:
        cmd += ["-d", impresora]
    cmd += ["-n", str(copias), "-o", "media=Letter", "-o", "fit-to-page"]
    if paginas:
        cmd += ["-P", paginas]
    if titulo:
        cmd += ["-t", titulo]
    return cmd + [str(pdf)]


def imprimir(pdf, impresora=None, copias=1, paginas=None, titulo=None, simular=False):
    """Manda el PDF a la cola de impresión. Devuelve (comando, mensaje de lp)."""
    if not 1 <= copias <= 20:
        raise ValueError("Copias entre 1 y 20")
    if paginas and not all(c.isdigit() or c in ",-" for c in paginas):
        raise ValueError(f"Páginas inválidas: {paginas!r} (usa 1-4,7)")
    cmd = comando(pdf, impresora, copias, paginas, titulo)
    if simular:
        return cmd, "(simulado: no se imprimió nada)"
    if not shutil.which("lp"):
        raise RuntimeError("No está `lp` (CUPS)")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"lp falló: {r.stderr.strip()}")
    return cmd, r.stdout.strip()
