"""Quality selection helpers (resolution/bitrate)."""

from __future__ import annotations

import re
from tkinter import ttk, StringVar


RESOLUTION_OPTIONS = [
    "Auto (Best)",
    "2160 (4K)",
    "1440 (2K)",
    "1080 (FHD)",
    "720 (HD)",
    "480 (SD)",
]

BITRATE_OPTIONS = [
    "320 kbps",
    "256 kbps",
    "192 kbps",
    "160 kbps",
    "128 kbps",
    "96 kbps",
    "64 kbps",
]


def parse_bitrate_kbps(label: str | None) -> int | None:
    try:
        if not label:
            return None
        m = re.search(r"(\d+)\s*kbps", str(label))
        if m:
            return int(m.group(1))
        return None
    except Exception:
        return None


def set_menu_options(option_menu: ttk.OptionMenu, var: StringVar, options: list[str]) -> None:
    try:
        setter = getattr(option_menu, "set_menu", None)
        if callable(setter):
            setter(var.get(), *options)
    except Exception:
        pass


def configure_quality_widgets_for_format(merge_fmt: str, label_widget: ttk.Label, option_menu: ttk.OptionMenu, var: StringVar) -> None:
    """Switch resolution/bitrate UI based on selected merge format."""
    try:
        if (merge_fmt or "").lower() == "mp3":
            label_widget.configure(text="Bitrate:")
            if not any((var.get() or "").startswith(x.split()[0]) for x in BITRATE_OPTIONS):
                var.set("320 kbps")
            set_menu_options(option_menu, var, BITRATE_OPTIONS)
        else:
            label_widget.configure(text="Resolution:")
            if (var.get() or "Auto (Best)") not in RESOLUTION_OPTIONS:
                var.set("Auto (Best)")
            set_menu_options(option_menu, var, RESOLUTION_OPTIONS)
    except Exception:
        pass

