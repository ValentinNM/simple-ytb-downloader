from __future__ import annotations

"""Planner utilities.

Detects playlist URLs and optionally expands them into individual tasks
using yt-dlp in extract-only mode.
"""

from typing import Dict, List


def looks_like_playlist_url(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        return "list=" in (p.query or "") or "/playlist" in (p.path or "")
    except Exception:
        return False


def plan_downloads(urls: List[str], expand_playlist: bool) -> List[Dict]:
    try:
        import importlib
        ytdlp = importlib.import_module("yt_dlp")
    except Exception:
        ytdlp = None

    tasks: List[Dict] = []
    if ytdlp is None:
        return [{"url": u} for u in urls]
    playlist_batch_index = 0
    for u in urls:
        if not expand_playlist:
            tasks.append({"url": u})
            continue
        try:
            opts = {"quiet": True, "skip_download": True, "noplaylist": False, "extract_flat": "in_playlist"}
            with ytdlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(u, download=False)
            if isinstance(info, dict) and info.get("_type") == "playlist" and info.get("entries"):
                playlist_batch_index += 1
                entries = [e for e in (info.get("entries") or []) if isinstance(e, dict) and e.get("url")]
                from .utils import sanitize_filename
                pl_title = sanitize_filename(info.get("title") or "Playlist")
                pl_count = len(entries)
                for i, e in enumerate(entries, start=1):
                    tasks.append({
                        "url": e.get("url"),
                        "pl_title": pl_title,
                        "pl_index": i,
                        "pl_count": pl_count,
                        "entry_title": e.get("title"),
                        "pl_batch_index": playlist_batch_index,
                    })
            else:
                tasks.append({"url": u})
        except Exception:
            tasks.append({"url": u})
    return tasks


