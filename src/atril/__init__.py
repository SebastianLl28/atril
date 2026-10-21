"""Atril: builds context bundles to translate and improve books part by part."""

from . import env  # noqa: F401  (loads .env before the other modules read it)
from .cli import main

__all__ = ["main"]
