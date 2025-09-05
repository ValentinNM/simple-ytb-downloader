"""Log window UI component.

Provides a simple Toplevel window to display log lines and optional error
details, with a Copy button and lightweight categorization summary.
"""

from __future__ import annotations

from typing import Iterable, Optional
from tkinter import Toplevel, StringVar, Text, ttk


def show_log_window(parent, log_lines: Iterable[str], error_details: Optional[str] = None) -> None:
    """Display a modal-like log window with contents and a Copy button.

    Args:
        parent: The parent Tk widget (typically the root).
        log_lines: Lines to display.
        error_details: Optional traceback or details to append.
    """
    win = Toplevel(parent)
    win.title("Log")
    win.geometry("720x360")

    ctrl = ttk.Frame(win)
    ctrl.pack(fill="x", padx=8, pady=6)
    summary_var = StringVar(value="")
    ttk.Label(ctrl, textvariable=summary_var, foreground="#888").pack(side="left")

    def copy_all():
        try:
            data = "\n".join(list(log_lines))
            if error_details:
                data += "\n\n" + error_details
            win.clipboard_clear()
            win.clipboard_append(data)
        except Exception:
            pass

    ttk.Button(ctrl, text="Copy", command=copy_all).pack(side="right")

    text = Text(win, wrap="word")
    text.pack(fill="both", expand=True)
    try:
        payload = "\n".join(list(log_lines))
        if error_details:
            payload += "\n\n" + error_details
        text.insert("1.0", payload)
    except Exception:
        text.insert("1.0", "(No log)")

    # Simple categorization
    try:
        data = text.get("1.0", "end")
        cat = None
        if "HTTP Error 4" in data or "403" in data:
            cat = "Network/auth error (4xx)"
        elif "HTTP Error 5" in data:
            cat = "YouTube server error (5xx)"
        elif "ffmpeg" in data.lower() and "not found" in data.lower():
            cat = "FFmpeg missing"
        elif "age-restricted" in data.lower():
            cat = "Age-restricted content"
        elif "blocked" in data.lower() or "geo" in data.lower():
            cat = "Region-blocked content"
        if cat:
            summary_var.set(f"Category: {cat}")
    except Exception:
        pass


