"""Printing through CUPS (`lp`). Defaults to the system default printer (the Epson L3250).

`ATRIL_IMPRESORA` picks another one; `dry_run=True` returns the command without printing.
"""

import os
import shutil
import subprocess


def printers():
    """(printer names, default) from `lpstat`; empty if CUPS is missing."""
    if not shutil.which("lpstat"):
        return [], None
    listing = subprocess.run(["lpstat", "-p"], capture_output=True, text=True).stdout
    names = [l.split()[1] for l in listing.splitlines() if l.startswith("printer ")]
    out = subprocess.run(["lpstat", "-d"], capture_output=True, text=True).stdout
    default = out.split(":", 1)[1].strip() if ":" in out else None
    return names, default


def command(pdf, printer=None, copies=1, pages=None, title=None):
    printer = printer or os.environ.get("ATRIL_IMPRESORA")
    cmd = ["lp"]
    if printer:
        cmd += ["-d", printer]
    cmd += ["-n", str(copies), "-o", "media=Letter", "-o", "fit-to-page"]
    if pages:
        cmd += ["-P", pages]
    if title:
        cmd += ["-t", title]
    return cmd + [str(pdf)]


def print_pdf(pdf, printer=None, copies=1, pages=None, title=None, dry_run=False):
    """Send the PDF to the print queue. Returns (command, lp message)."""
    if not 1 <= copies <= 20:
        raise ValueError("Copias entre 1 y 20")
    # Whitelist: `pages` comes from the user and ends up as an lp argument.
    if pages and not all(c.isdigit() or c in ",-" for c in pages):
        raise ValueError(f"Páginas inválidas: {pages!r} (usa 1-4,7)")
    cmd = command(pdf, printer, copies, pages, title)
    if dry_run:
        return cmd, "(simulado: no se imprimió nada)"
    if not shutil.which("lp"):
        raise RuntimeError("No está `lp` (CUPS)")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"lp falló: {r.stderr.strip()}")
    return cmd, r.stdout.strip()
