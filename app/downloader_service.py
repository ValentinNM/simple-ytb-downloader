from __future__ import annotations

"""Download service built around yt-dlp.

Contains the `DownloadContext`, format selection, and the `download_single`
function that emits progress dictionaries consumable by the UI.
"""

import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, Optional, Tuple

try:
    import importlib
    ytdlp = importlib.import_module("yt_dlp")
except Exception:
    ytdlp = None

from .config import SPEED_SMOOTH_WINDOW_SEC
from .utils import sanitize_filename, ensure_unique_path, human_readable_rate, format_eta


class CancelledDownloadError(Exception):
    pass


class DownloadContext:
    def __init__(self, target_dir: Path, merge_format: str, prefer_avc_for_mp4: bool, resolution_label: str,
                 ffmpeg_path: Optional[str] = None, limit_fragment_concurrency: bool = False,
                 audio_bitrate_kbps: Optional[int] = None):
        self.target_dir = target_dir
        self.merge_format = merge_format
        self.prefer_avc_for_mp4 = prefer_avc_for_mp4
        self.resolution_label = resolution_label
        self.ffmpeg_path = ffmpeg_path
        self.limit_fragment_concurrency = limit_fragment_concurrency
        self.audio_bitrate_kbps = audio_bitrate_kbps
        self.rate_samples: Deque[Tuple[float, int]] = deque()
        self.fallback_counter = 1


def select_format_string(ctx: DownloadContext) -> str:
    sel = ctx.resolution_label or ""
    merge_fmt = (ctx.merge_format or "mkv").lower()
    cap: Optional[int] = None
    # Extract leading number from labels like "2160 (4K)" or "1080 (FHD)"
    try:
        import re
        m = re.match(r"^(\d{3,4})", sel.strip())
        if m:
            cap = int(m.group(1))
    except Exception:
        cap = None
    # Auto defaults to 1080 (FHD)
    if cap is None and sel.lower().startswith("auto"):
        cap = 1080
    cap_clause = f"[height<={cap}]" if isinstance(cap, int) else ""
    if merge_fmt == "mp4" and ctx.prefer_avc_for_mp4:
        return f"bestvideo{cap_clause}[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best{cap_clause}[ext=mp4]"
    return f"bestvideo{cap_clause}+bestaudio/best{cap_clause}"


def download_single(url: str, ctx: DownloadContext, post_progress, ctx_entry: Optional[dict] = None, is_cancelled=None) -> str:
    if ytdlp is None:
        raise RuntimeError("yt-dlp is not installed. Install with: pip install yt-dlp")

    def hook(d):
        if d.get('status') == 'downloading':
            if callable(is_cancelled) and is_cancelled():
                raise CancelledDownloadError("Cancelled by user")
            downloaded = d.get('downloaded_bytes', 0) or 0
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            percent = (downloaded / total * 100) if total else 0

            now = time.time()
            ctx.rate_samples.append((now, int(downloaded)))
            while ctx.rate_samples and (now - ctx.rate_samples[0][0]) > SPEED_SMOOTH_WINDOW_SEC:
                ctx.rate_samples.popleft()

            avg_speed_bps = 0.0
            if len(ctx.rate_samples) >= 2:
                first_t, first_b = ctx.rate_samples[0]
                last_t, last_b = ctx.rate_samples[-1]
                dt = max(0.001, last_t - first_t)
                db = max(0, last_b - first_b)
                avg_speed_bps = db / dt

            raw_speed = d.get('speed') or 0
            speed_bps = avg_speed_bps or float(raw_speed or 0)
            eta = None
            if total and speed_bps > 0:
                remaining = max(0, total - downloaded)
                eta = int(remaining / speed_bps)
            # Human friendly strings
            speed_human = human_readable_rate(speed_bps) if speed_bps else ""
            eta_str = format_eta(int(eta)) if eta is not None else ""
            msg = (
                f"Downloading {percent:0.1f}%"
                + (f" @ {speed_human}" if speed_human else "")
                + (f" in ETA {eta_str}" if eta_str else "")
            )
            # Single-line console style for logs
            total_mib = (total / (1024 * 1024)) if total else None
            log_line = f"[download] {percent:0.1f}%" + (
                f" of {total_mib:.2f}MiB" if isinstance(total_mib, float) else ""
            ) + (f" at {speed_human}" if speed_human else "") + (
                f" in ETA {eta_str}" if eta_str else ""
            )
            post_progress({
                "type": "progress",
                "value": percent,
                "text": msg,
                "percent": percent,
                "speed_bps": speed_bps,
                "speed_human": speed_human,
                "eta_seconds": eta if eta is not None else None,
                "eta_human": eta_str,
                "log_line": log_line,
            })
        elif d.get('status') == 'finished':
            post_progress({"type": "progress", "value": 100, "text": "Downloaded. Merging…", "percent": 100.0})

    # Probe title first
    ydl_info_opts = {"quiet": True, "skip_download": True, "noplaylist": True}
    with ytdlp.YoutubeDL(ydl_info_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    title = None
    if ctx_entry and isinstance(ctx_entry, dict):
        title = ctx_entry.get('entry_title') or None
    if not title:
        title = info.get('title') if isinstance(info, dict) else None
    safe_title = sanitize_filename(title) if title else ""
    if not safe_title:
        safe_title = f"YouTube_Download_{ctx.fallback_counter}"
        ctx.fallback_counter += 1

    merge_fmt = (ctx.merge_format or "mkv").lower()
    if merge_fmt not in {"mkv", "mp4", "mp3"}:
        merge_fmt = "mkv"

    # playlist-aware naming when context provided: resolve to the actual title
    if ctx_entry and isinstance(ctx_entry, dict) and isinstance(ctx_entry.get("pl_index"), int) and isinstance(ctx_entry.get("pl_count"), int) and ctx_entry.get("pl_count"):
        pl_title = sanitize_filename(str(ctx_entry.get("pl_title") or "Playlist"))
        index_num = int(ctx_entry.get("pl_index"))
        base = ctx.target_dir / f"{pl_title} - {index_num:02d} - {safe_title}"
        out_path = ensure_unique_path(base, merge_fmt)
        outtmpl_value = str(out_path)
    else:
        base = ctx.target_dir / safe_title
        out_path = ensure_unique_path(base, merge_fmt)
        outtmpl_value = str(out_path)

    ydl_opts_base: Dict[str, Any] = {
        'outtmpl': outtmpl_value,
        'noplaylist': True,
        'progress_hooks': [hook],
    }
    # Optionally limit fragment concurrency for steadier UI updates
    if getattr(ctx, "limit_fragment_concurrency", False):
        try:
            ydl_opts_base['concurrent_fragment_downloads'] = 1
        except Exception:
            pass
    # For container formats that support merging, set merge_output_format
    if merge_fmt in {"mkv", "mp4"}:
        ydl_opts_base['merge_output_format'] = merge_fmt
    if ctx.ffmpeg_path:
        try:
            ydl_opts_base['ffmpeg_location'] = str(Path(ctx.ffmpeg_path).parent)
        except Exception:
            pass

    selected_format = select_format_string(ctx)
    try:
        ydl_opts = dict(ydl_opts_base)
        if merge_fmt == 'mp3':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '0',
                }
            ]
            # Enforce CBR bitrate via ffmpeg when selected
            if getattr(ctx, 'audio_bitrate_kbps', None):
                try:
                    kbps = int(ctx.audio_bitrate_kbps)
                    ydl_opts['postprocessor_args'] = [
                        '-c:a', 'libmp3lame',
                        '-b:a', f'{kbps}k',
                    ]
                except Exception:
                    pass
        else:
            ydl_opts['format'] = selected_format
        with ytdlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception:
        ydl_opts = dict(ydl_opts_base)
        ydl_opts['format'] = 'best'
        with ytdlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    post_progress({"type": "status", "text": f"Saved to: {outtmpl_value}"})
    return outtmpl_value


