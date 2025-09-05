"""Tkinter UI for the YouTube Downloader.

Handles user input, progress display, and delegates work to background
download operations. Uses a queue for thread-safe communication.
"""

from __future__ import annotations

import queue
import threading
from typing import Any, cast
from pathlib import Path

from tkinter import Tk, Text, StringVar, BooleanVar, ttk, filedialog, messagebox, TclError

from .dnd_support import DND_TEXT

from .config import DEFAULT_CONTAINER, DEFAULT_RESOLUTION_LABEL, PROGRESS_POLL_MS, SETTINGS_FILE_NAME, DEFAULT_LIMIT_FRAGMENT_CONCURRENCY
from .ffmpeg_check import check_ffmpeg
from .utils import looks_like_url, load_settings, save_settings
from .downloader_service import DownloadContext, download_single, CancelledDownloadError
from .planner import plan_downloads
from .theme import apply_theme
from .log_window import show_log_window
from .quality import configure_quality_widgets_for_format, parse_bitrate_kbps
from .progress_ui import process_progress_queue


class DownloaderApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("YouTube Downloader")
        self.root.geometry("720x420")

        self.fallback_counter = 1
        self.target_dir = None
        self.downloading = False
        self.cancel_event = threading.Event()
        self.log_lines: list[str] = []
        self.last_error_details: str | None = None

        self.settings_path = Path.home() / SETTINGS_FILE_NAME
        _settings = load_settings(self.settings_path)
        self.container_var = StringVar(self.root, value=_settings.get("container", DEFAULT_CONTAINER))
        self.resolution_var = StringVar(self.root, value=_settings.get("resolution", DEFAULT_RESOLUTION_LABEL))
        self.expand_playlist_var = BooleanVar(self.root, value=bool(_settings.get("expand_playlist", False)))
        self.limit_fragments_var = BooleanVar(self.root, value=bool(_settings.get("limit_fragments", DEFAULT_LIMIT_FRAGMENT_CONCURRENCY)))
        self.prefer_avc_var = BooleanVar(self.root, value=bool(_settings.get("prefer_avc", True)))
        # Theme preference: Auto / Light / Dark
        try:
            _pref = str(_settings.get("theme", "Auto"))
            if _pref.lower() not in {"auto", "light", "dark"}:
                _pref = "Auto"
        except Exception:
            _pref = "Auto"
        self.theme_var = StringVar(self.root, value=_pref)

        self.progress_q: "queue.Queue[dict]" = queue.Queue()

        self.ffmpeg_ok = False
        self.ffmpeg_path: str | None = None
        self.ffprobe_path: str | None = None
        # UI packing flags
        self._item_widgets_packed = False
        self._dynamic_packed = False
        # Predefine attributes referenced later
        self._saved_to_full_path: str | None = None
        self.warn_var: StringVar | None = None

        self._build_ui()
        self.root.after(PROGRESS_POLL_MS, lambda: process_progress_queue(self))
        self._start_ffmpeg_check()
        # initial theme application
        try:
            apply_theme(self.root, self.url_text, self.theme_var.get())
        except Exception:
            pass
        # restore last folder if exists
        try:
            last_folder = _settings.get("last_folder")
            if last_folder:
                p = Path(last_folder)
                if p.exists():
                    self.target_dir = p
                    self.dir_label_var.set(str(p))
        except Exception:
            pass

    def _build_ui(self):
        pad = {"padx": 12, "pady": 8}
        ttk.Label(self.root, text="Drop YouTube URL(s) here or paste below:", font=("", 11, "bold")).pack(**pad, anchor="w")

        self.url_text = Text(self.root, height=6, wrap="word", background="#1f1f1f", foreground="#e0e0e0", insertbackground="#e0e0e0", highlightthickness=0)
        self.url_text.pack(fill="x", padx=12)
        if DND_TEXT is not None:
            url_text_any = cast(Any, self.url_text)
            register = getattr(url_text_any, "drop_target_register", None)
            binder = getattr(url_text_any, "dnd_bind", None)
            if register is not None:
                try:
                    cast(Any, register)(DND_TEXT)  # type: ignore[attr-defined]
                except (AttributeError, TypeError, TclError):
                    pass
            if binder is not None:
                try:
                    cast(Any, binder)("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]
                except (AttributeError, TypeError, TclError):
                    pass

        row = ttk.Frame(self.root)
        row.pack(fill="x", **pad)
        self.dir_label_var = StringVar(value="No folder selected")
        ttk.Button(row, text="Choose Save Folder", command=self._choose_folder).pack(side="left")
        dir_lbl = ttk.Label(row, textvariable=self.dir_label_var, foreground="#8ab4f8", cursor="hand2")
        dir_lbl.pack(side="left", padx=10)
        try:
            dir_lbl.bind("<Button-1>", self._on_open_folder)
        except Exception:
            pass

        # Overall progress bar and label at the top
        # Start with a placeholder until calculation begins
        self.overall_label_var = StringVar(value="Total items will be calculated when the download starts.")
        self.overall_label = ttk.Label(self.root, textvariable=self.overall_label_var)
        self.overall_label.pack(padx=12, pady=(6, 2), anchor="w")
        self.overall_progress = ttk.Progressbar(self.root, orient="horizontal", mode="determinate", maximum=100)
        self.overall_progress.pack(fill="x", padx=12)
        # Dynamic area between overall bar and FFmpeg status
        self.dynamic_area = ttk.Frame(self.root)
        self.dynamic_area.pack(fill="x")
        # Current item label above item progress (hidden until download starts)
        self.current_item_var = StringVar(value="")
        self.current_item_label = ttk.Label(self.dynamic_area, textvariable=self.current_item_var)
        # Per-item progress (hidden until download starts)
        self.item_progress = ttk.Progressbar(self.dynamic_area, orient="horizontal", mode="determinate", maximum=100)
        # Status row with colored segmented stats (hidden until download starts)
        self.status_var = StringVar(value="Preparing...")
        self.status_row = ttk.Frame(self.dynamic_area)
        self.stat_prefix = ttk.Label(self.status_row, textvariable=self.status_var)
        self.stat_prefix.pack(side="left")
        self.stat_pct_var = StringVar(value="")
        self.stat_pct_lbl = ttk.Label(self.status_row, textvariable=self.stat_pct_var, foreground="#ffd166")
        self.stat_pct_lbl.pack(side="left", padx=(6, 0))
        self.stat_speed_var = StringVar(value="")
        self.stat_speed_lbl = ttk.Label(self.status_row, textvariable=self.stat_speed_var, foreground="#4aa3df")
        self.stat_speed_lbl.pack(side="left", padx=(6, 0))
        self.stat_eta_var = StringVar(value="")
        self.stat_eta_lbl = ttk.Label(self.status_row, textvariable=self.stat_eta_var, foreground="#6aa84f")
        self.stat_eta_lbl.pack(side="left", padx=(6, 0))
        # Warning/error label (separate from status)
        self.warn_var = StringVar(self.root, value="")
        self.warn_label = ttk.Label(self.dynamic_area, textvariable=self.warn_var, foreground="#e67e22")
        # Clickable Saved-to label (hidden until we have a file)
        self._saved_to_full_path = None
        self.saved_to_var = StringVar(value="")
        self.saved_to_label = ttk.Label(self.dynamic_area, textvariable=self.saved_to_var, foreground="#8ab4f8", cursor="hand2")
        try:
            self.saved_to_label.bind("<Button-1>", self._on_open_saved)
        except Exception:
            pass
        # Keep legacy variables for compatibility (not displayed)
        self.batch_var = StringVar(value="")
        self.file_identifier_var = StringVar(value="")
        self.ffmpeg_status_var = StringVar(value="FFmpeg: checking…")
        ttk.Label(self.root, textvariable=self.ffmpeg_status_var).pack(**pad, anchor="w")

        btn_row = ttk.Frame(self.root)
        btn_row.pack(**pad)
        self.download_btn = ttk.Button(btn_row, text="Download", command=self._start_download)
        self.download_btn.pack(side="left", padx=(0, 10))
        self.cancel_btn = ttk.Button(btn_row, text="Cancel", command=self._cancel_download, state="disabled")
        self.cancel_btn.pack(side="left", padx=(0, 10))
        self.clear_btn = ttk.Button(btn_row, text="Clear URLs", command=lambda: self.url_text.delete("1.0", "end"))
        self.clear_btn.pack(side="left")

        opt_row = ttk.Frame(self.root)
        opt_row.pack(**pad, anchor="center")
        ttk.Label(opt_row, text="Format:").pack(side="left")
        self.container_menu = ttk.OptionMenu(opt_row, self.container_var, self.container_var.get(), "mkv", "mp4", "mp3", command=lambda _=None: self._on_container_change())
        self.container_menu.pack(side="left", padx=(6, 14))
        self.res_or_br_lbl = ttk.Label(opt_row, text="Resolution:")
        self.res_or_br_lbl.pack(side="left")
        self.resolution_menu = ttk.OptionMenu(opt_row, self.resolution_var, self.resolution_var.get(), "Auto (Best)", "2160 (4K)", "1440 (2K)", "1080 (FHD)", "720 (HD)", "480 (SD)", command=lambda _=None: self._on_resolution_change())
        self.resolution_menu.pack(side="left", padx=(6, 14))
        # Second row for option checkboxes
        opt_row2 = ttk.Frame(self.root)
        opt_row2.pack(**pad, anchor="center")
        self.playlist_chk = ttk.Checkbutton(opt_row2, text="Expand playlist", variable=self.expand_playlist_var)
        self.playlist_chk.pack(side="left")
        self.prefer_avc_chk = ttk.Checkbutton(opt_row2, text="Prefer AVC for MP4", variable=self.prefer_avc_var)
        self.prefer_avc_chk.pack(side="left", padx=(14, 0))
        # Advanced smoother UI toggle
        ttk.Checkbutton(opt_row2, text="Smoother UI (limit fragment concurrency)", variable=self.limit_fragments_var).pack(side="left", padx=(14, 0))
        self._on_container_change()
        self._attach_var_traces()

        log_row = ttk.Frame(self.root)
        log_row.pack(**pad, anchor="center")
        ttk.Button(log_row, text="Show Log", command=self._show_log_window).pack(side="left")
        ttk.Button(log_row, text="Re-check FFmpeg", command=self._start_ffmpeg_check).pack(side="left", padx=(8, 0))
        # Theme preference selector
        ttk.Label(log_row, text="Theme:").pack(side="left", padx=(8, 4))
        ttk.OptionMenu(log_row, self.theme_var, self.theme_var.get(), "Auto", "Light", "Dark", command=lambda _=None: apply_theme(self.root, self.url_text, self.theme_var.get())).pack(side="left")

    def _start_ffmpeg_check(self):
        try:
            threading.Thread(target=self._ffmpeg_check_worker, daemon=True).start()
        except Exception:
            pass

    def _ffmpeg_check_worker(self):
        ok, ffmpeg, ffprobe, version = check_ffmpeg()
        self.ffmpeg_ok = ok
        self.ffmpeg_path = ffmpeg
        self.ffprobe_path = ffprobe
        if ok:
            # Extract short version like v6.1
            short_v = ""
            try:
                import re
                m = re.search(r"ffmpeg version\s+([\w\.-]+)", version or "")
                if m:
                    ver = m.group(1)
                    # keep major.minor if possible
                    parts = ver.split(".")
                    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                        short_v = f"v{parts[0]}.{parts[1]}"
                    else:
                        short_v = f"v{ver}"
            except Exception:
                short_v = ""
            label = f"FFmpeg OK — {short_v}" if short_v else "FFmpeg OK"
            self.ffmpeg_status_var.set(label)
        else:
            # Basic categorization
            emoji = "⚠️" if (ffmpeg or ffprobe) else "❌"
            self.ffmpeg_status_var.set(f"FFmpeg check {emoji} - Click 'Re-check FFmpeg'.")

    def _on_drop(self, event):
        data = event.data.strip().replace("{", "").replace("}", "")
        self.url_text.insert("end", ("\n" if self.url_text.get("1.0", "end").strip() else "") + data)

    def _choose_folder(self):
        folder = filedialog.askdirectory(title="Choose download folder")
        if folder:
            self.target_dir = Path(folder)
            self.dir_label_var.set(str(self.target_dir))
            try:
                # persist folder
                self._persist_settings()
            except Exception:
                pass

    def _collect_urls(self):
        raw = self.url_text.get("1.0", "end").strip()
        import re
        items = re.split(r"\s+", raw)
        urls = [s for s in items if looks_like_url(s)]
        return urls

    def _start_download(self):
        if self.downloading:
            return
        urls = self._collect_urls()
        if not urls:
            messagebox.showerror("Missing URLs", "Please paste or drop at least one valid URL.")
            return
        if not self.target_dir:
            messagebox.showerror("Choose Folder", "Please choose a target folder first.")
            return
        try:
            if not self.expand_playlist_var.get():
                from .planner import looks_like_playlist_url
                if any(looks_like_playlist_url(u) for u in urls):
                    if messagebox.askyesno("Playlist detected", "One or more URLs look like playlists. Download all items?"):
                        self.expand_playlist_var.set(True)
        except Exception:
            pass
        self.downloading = True
        self.download_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.item_progress.configure(value=0)
        self.overall_progress.configure(value=0)
        if not self.ffmpeg_ok:
            try:
                messagebox.showerror("FFmpeg Required", "FFmpeg is missing or not working. Install it (e.g., 'brew install ffmpeg') or bundle it with the app, then click 'Re-check FFmpeg'.")
            except Exception:
                pass
            self.downloading = False
            self.download_btn.config(state="normal")
            self.cancel_btn.config(state="disabled")
            return
        # Make dynamic widgets visible and set placeholders
        try:
            if not getattr(self, "_dynamic_packed", False):
                # overall label/progress already at top; show only the Preparing… status initially
                self.status_row.pack(padx=12, pady=(6, 0), anchor="w")
                self._dynamic_packed = True
            # ensure item widgets remain hidden until title is known
            self._item_widgets_packed = False
            # Saved-to and warning labels will be packed after item widgets are shown
            try:
                self.saved_to_label.pack_forget()
            except Exception:
                pass
            try:
                self.warn_label.pack_forget()
            except Exception:
                pass
        except Exception:
            pass
        self.status_var.set("Preparing...")
        self.cancel_event.clear()
        threading.Thread(target=self._download_worker, args=(urls,), daemon=True).start()

    def _cancel_download(self):
        if not self.downloading:
            return
        self.cancel_event.set()
        self.status_var.set("Cancelling…")

    # legacy batch label method removed

    def _download_worker(self, urls):
        try:
            planned = plan_downloads(urls, self.expand_playlist_var.get())
            total = len(planned)
            # As soon as totals are known, surface the overall label with unknown current index
            if total:
                self.progress_q.put({"type": "label", "which": "overall", "text": f"Total items ? / {total}"})
            for idx, task in enumerate(planned, start=1):
                if self.cancel_event.is_set():
                    self.progress_q.put({"type": "status", "text": "Cancelled"})
                    break
                # Update overall items label (displayed as "Total items X / Y")
                self.progress_q.put({"type": "label", "which": "overall", "text": f"Total items {idx} / {total}"})
                try:
                    pl_index = task.get("pl_index") if isinstance(task, dict) else None
                    pl_count = task.get("pl_count") if isinstance(task, dict) else None
                    entry_title = task.get("entry_title") if isinstance(task, dict) else None
                    is_playlist = isinstance(pl_index, int) and isinstance(pl_count, int) and pl_count > 0
                except Exception:
                    pl_index = pl_count = None
                    entry_title = None
                    is_playlist = False

                # Probe title for individual links when not provided
                title = entry_title
                private_detected = False
                if not title:
                    try:
                        import importlib as _il
                        _ytdlp = _il.import_module("yt_dlp")
                        _opts = {"quiet": True, "skip_download": True, "noplaylist": True}
                        with _ytdlp.YoutubeDL(_opts) as _ydl:
                            _info = _ydl.extract_info(task.get("url"), download=False)
                        if isinstance(_info, dict):
                            title = _info.get("title") or title
                    except Exception as _e:
                        if "Private video" in str(_e):
                            private_detected = True
                        # otherwise ignore; title stays None

                # Determine if entry is private based on known markers
                title_str = str(title or "").strip()
                if (title_str.lower().startswith("[private video]") or title_str.lower() == "private video"):
                    private_detected = True

                # Build context-aware label text
                if is_playlist:
                    pl_title = task.get('pl_title') or 'Playlist'
                    file_label = f"Playlist [{pl_title}] - Item {int(pl_index)} of {int(pl_count)}: {title or ''}"
                else:
                    file_label = f"YouTube Video {idx} of {total}: {title or ''}"
                self.progress_q.put({"type": "label", "which": "file", "text": file_label})
                self.progress_q.put({"type": "label", "which": "current_item", "text": file_label})

                # If private, skip this item
                if private_detected:
                    self._log(f"Skipping private video: {title or task.get('url')}")
                    # More verbose skip message with item index and total
                    self.progress_q.put({
                        "type": "status",
                        "text": f"Skipping item {idx} / {total} - private video: {title or 'Unknown'}",
                    })
                    # Advance overall progress as if this item completed
                    try:
                        overall_after_skip = (float(idx) / max(1, float(total))) * 100.0
                    except Exception:
                        overall_after_skip = 0.0
                    self.progress_q.put({"type": "progress", "value": overall_after_skip, "text": ""})
                    continue

                # Derive audio bitrate when mp3 is selected
                br_kbps = None
                try:
                    if (self.container_var.get() or "").lower() == "mp3":
                        br_kbps = parse_bitrate_kbps(self.resolution_var.get()) or 320
                except Exception:
                    br_kbps = None

                dl_ctx = DownloadContext(
                    target_dir=self.target_dir,
                    merge_format=self.container_var.get(),
                    prefer_avc_for_mp4=self.prefer_avc_var.get(),
                    resolution_label=self.resolution_var.get(),
                    ffmpeg_path=self.ffmpeg_path,
                    limit_fragment_concurrency=bool(self.limit_fragments_var.get()),
                    audio_bitrate_kbps=br_kbps,
                )
                current_index = idx
                current_total = total
                def post_progress(ev: dict):
                    if ev.get("type") == "progress":
                        # Map item progress to overall progress across all items
                        try:
                            item_pct = float(ev.get("value", 0) or 0)
                        except Exception:
                            item_pct = 0.0
                        overall = (((current_index - 1) + (item_pct / 100.0)) / max(1, current_total)) * 100.0
                        ev = dict(ev)
                        ev["value"] = overall
                        self.progress_q.put(ev)
                    elif ev.get("type") == "status":
                        # also capture saved-to path
                        text = ev.get("text") or ""
                        if text.startswith("Saved to:"):
                            self.progress_q.put({"type": "label", "which": "saved_to", "text": text})
                        self.progress_q.put(ev)

                download_single(task.get("url"), dl_ctx, post_progress, ctx_entry=task, is_cancelled=self.cancel_event.is_set)
            self.progress_q.put({"type": "status", "text": "All done"})
        except CancelledDownloadError:
            self.progress_q.put({"type": "status", "text": "Cancelled"})
        except Exception as e:
            import traceback
            self.last_error_details = traceback.format_exc()
            self._log(f"Error: {e}")
            self.progress_q.put({"type": "status", "text": f"Error: {e}"})
        finally:
            self.progress_q.put({"type": "done"})

    def _rebuild_quality_menu_for_format(self, merge_fmt: str):
        try:
            configure_quality_widgets_for_format(merge_fmt, self.res_or_br_lbl, self.resolution_menu, self.resolution_var)
        except Exception:
            pass

    def _on_container_change(self):
        try:
            sel = (self.container_var.get() or "").lower()
            is_mp4 = sel == "mp4"
            is_mkv = sel == "mkv"
            # Rebuild the quality dropdown according to format
            self._rebuild_quality_menu_for_format(sel)
            if is_mp4:
                self.prefer_avc_var.set(True)
                try:
                    self.prefer_avc_chk.state(["!disabled"])  # enable
                except Exception:
                    pass
            elif is_mkv:
                self.prefer_avc_var.set(False)
                try:
                    self.prefer_avc_chk.state(["disabled"])  # disable
                except Exception:
                    pass
            else:
                # mp3 - audio only, AVC preference irrelevant
                self.prefer_avc_var.set(False)
                try:
                    self.prefer_avc_chk.state(["disabled"])  # disable
                except Exception:
                    pass
            self._persist_settings()
        except Exception:
            pass

    def _on_resolution_change(self):
        try:
            self._persist_settings()
        except Exception:
            pass

    def _attach_var_traces(self):
        try:
            self.container_var.trace_add('write', lambda *_: self._persist_settings())
            self.resolution_var.trace_add('write', lambda *_: self._persist_settings())
            self.expand_playlist_var.trace_add('write', lambda *_: self._persist_settings())
            self.prefer_avc_var.trace_add('write', lambda *_: self._persist_settings())
            self.limit_fragments_var.trace_add('write', lambda *_: self._persist_settings())
        except Exception:
            pass

    def _persist_settings(self):
        try:
            data = {
                "container": (self.container_var.get() or "mkv"),
                "resolution": (self.resolution_var.get() or DEFAULT_RESOLUTION_LABEL),
                "expand_playlist": bool(self.expand_playlist_var.get()),
                "prefer_avc": bool(self.prefer_avc_var.get()),
                "limit_fragments": bool(self.limit_fragments_var.get()),
                "last_folder": str(self.target_dir) if self.target_dir else None,
                "theme": (self.theme_var.get() if hasattr(self, 'theme_var') else "Auto"),
            }
            save_settings(self.settings_path, data)
        except Exception:
            pass

    def _on_open_saved(self, _event=None):
        try:
            text = self.saved_to_var.get() or ""
            if text.startswith("Saved to:"):
                path = text.split("Saved to:", 1)[1].strip()
                p = Path(path)
                if p.exists():
                    import subprocess as _sp
                    _sp.Popen(["open", "-R", str(p)])
        except Exception:
            pass

    def _on_open_folder(self, _event=None):
        try:
            if self.target_dir:
                import subprocess as _sp
                _sp.Popen(["open", str(self.target_dir)])
        except Exception:
            pass

    def _apply_theme(self):
        try:
            apply_theme(self.root, self.url_text, self.theme_var.get())
            self._persist_settings()
        except Exception:
            pass

    def _log(self, line: str):
        try:
            self.log_lines.append(line)
            if len(self.log_lines) > 1000:
                del self.log_lines[: len(self.log_lines) - 1000]
        except Exception:
            pass

    def _show_log_window(self):
        show_log_window(self.root, self.log_lines, self.last_error_details)


def create_root():
    """Deprecated: moved to app.ui_root.create_root."""
    from .ui_root import create_root as _mk
    return _mk()


