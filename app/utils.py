"""Utility helpers for filename sanitization, URL checks, human formatting,
    and simple JSON settings persistence.
"""

import re
from pathlib import Path
from urllib.parse import urlparse
import json


INVALID_FS_CHARS = r"\\/:*?\"<>|"


def sanitize_filename(name: str) -> str:
    """Return a filesystem-safe filename (without extension)."""
    if not name:
        return ""
    name = re.sub(r"[\r\n\t]", " ", name)
    name = "".join((c if c not in INVALID_FS_CHARS else " ") for c in name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or ""


def ensure_unique_path(base_path: Path, ext: str) -> Path:
    """Return a unique path by appending (1), (2)... if needed."""
    candidate = base_path.with_suffix(f".{ext}")
    if not candidate.exists():
        return candidate
    i = 1
    while True:
        candidate = base_path.with_name(f"{base_path.name} ({i})").with_suffix(f".{ext}")
        if not candidate.exists():
            return candidate
        i += 1


def looks_like_url(s: str) -> bool:
    s = (s or "").strip()
    if not s:
        return False
    p = urlparse(s)
    return p.scheme in {"http", "https"} and bool(p.netloc)


def human_readable_rate(bps: float) -> str:
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    x = float(bps or 0)
    i = 0
    while x >= 1024 and i < len(units) - 1:
        x /= 1024
        i += 1
    return f"{x:.1f} {units[i]}"


def format_eta(seconds: int) -> str:
    try:
        if seconds < 0:
            seconds = 0
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"
    except Exception:
        return f"{int(seconds)}s"


def load_settings(path: Path) -> dict:
    try:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def save_settings(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data or {}, f, indent=2)
    except Exception:
        pass


