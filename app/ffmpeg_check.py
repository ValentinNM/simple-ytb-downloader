from __future__ import annotations

"""FFmpeg preflight utilities.

Resolves bundled tools when running from a PyInstaller bundle and checks
availability and version of FFmpeg/FFprobe.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from .config import FFMPEG_CHECK_TIMEOUT_SEC


def resolve_bundled_tool(name: str) -> Optional[str]:
    try:
        base = getattr(sys, "_MEIPASS", None)
        if base:
            candidate = Path(base) / name
            if candidate.exists():
                return str(candidate)
    except Exception:
        pass
    return None


def check_ffmpeg() -> Tuple[bool, Optional[str], Optional[str], str]:
    """
    Returns (ok, ffmpeg_path, ffprobe_path, version_or_error)
    """
    ffmpeg = resolve_bundled_tool("ffmpeg") or shutil.which("ffmpeg")
    ffprobe = resolve_bundled_tool("ffprobe") or shutil.which("ffprobe")
    ok = False
    version = ""
    if ffmpeg:
        try:
            out = subprocess.check_output([ffmpeg, "-version"], stderr=subprocess.STDOUT, timeout=FFMPEG_CHECK_TIMEOUT_SEC)
            version = out.decode(errors="ignore").splitlines()[0].strip()
            ok = True
        except Exception as e:
            version = f"error: {e}"
            ok = False
    return ok, ffmpeg, ffprobe, version


