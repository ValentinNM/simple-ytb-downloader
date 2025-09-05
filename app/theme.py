"""Theme utilities for the Tkinter UI.

Provides helpers to detect system theme preferences on macOS and to apply
light/dark styling to the application widgets in a consistent way.
"""

from __future__ import annotations

from tkinter import Tk, ttk, Text


def detect_system_dark() -> bool:
    """Return True if the macOS system appearance is Dark.

    Falls back to False (Light) if detection fails or on non-macOS systems.
    """
    try:
        import subprocess
        out = subprocess.check_output(["defaults", "read", "-g", "AppleInterfaceStyle"], stderr=subprocess.STDOUT)
        return b"Dark" in out
    except Exception:
        return False


def apply_theme(root: Tk, text_widget: Text | None, preference: str) -> bool:
    """Apply a light/dark theme to the given Tk root and optional Text widget.

    Args:
        root: The Tk root window.
        text_widget: Optional Text widget to restyle according to theme.
        preference: One of "Auto", "Light", or "Dark" (case-insensitive).

    Returns:
        True if dark theme was applied, False if light.
    """
    pref = (preference or "Auto").lower()
    if pref == "auto":
        dark = detect_system_dark()
    elif pref == "dark":
        dark = True
    else:
        dark = False

    style = ttk.Style(root)
    if dark:
        bg = "#2b2b2b"; fg = "#e0e0e0"; btn = "#3a3a3a"; trough = "#3a3a3a"; pb = "#6aa84f"
        root.configure(background=bg)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=btn, foreground=fg)
        style.configure("TCheckbutton", background=bg, foreground=fg)
        style.configure("TProgressbar", troughcolor=trough, background=pb)
        try:
            if text_widget is not None:
                text_widget.configure(background="#1f1f1f", foreground=fg, insertbackground=fg, highlightthickness=0)
        except Exception:
            pass
    else:
        bg = "#f5f5f5"; fg = "#222"; btn = "#e6e6e6"; trough = "#ddd"; pb = "#4a90e2"
        root.configure(background=bg)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=btn, foreground=fg)
        style.configure("TCheckbutton", background=bg, foreground=fg)
        style.configure("TProgressbar", troughcolor=trough, background=pb)
        try:
            if text_widget is not None:
                text_widget.configure(background="#ffffff", foreground=fg, insertbackground="#000000")
        except Exception:
            pass

    return dark


