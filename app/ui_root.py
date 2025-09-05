"""Root window creation for the TkinterDnD-enabled application."""

from __future__ import annotations

from tkinter import ttk, TclError

from .dnd_support import TkinterDnD


def create_root():
    """Create and return the Tk root using TkinterDnD.

    Raises:
        RuntimeError: if tkinterdnd2 is not installed.
    """
    if TkinterDnD is None:
        raise RuntimeError("tkinterdnd2 is not installed. Install with: pip install tkinterdnd2-universal")
    root = TkinterDnD.Tk()
    try:
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except TclError:
        pass
    return root


