"""Thin wrapper around tkinterdnd2 imports.

Exposes `TkinterDnD` and `DND_TEXT` if available, else sets them to None.
This isolates optional dependency handling from UI code.
"""

from __future__ import annotations

try:
    import importlib
    _tkdnd_mod = importlib.import_module("tkinterdnd2")
    TkinterDnD = getattr(_tkdnd_mod, "TkinterDnD", None)
    DND_TEXT = getattr(_tkdnd_mod, "DND_TEXT", None)
except Exception:
    TkinterDnD, DND_TEXT = None, None


__all__ = ["TkinterDnD", "DND_TEXT"]


