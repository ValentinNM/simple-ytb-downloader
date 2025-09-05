"""Progress queue handling logic extracted from the main UI class.

This module centralizes the draining of the background progress queue and
the updates of Tkinter widgets. The main UI calls `process_progress_queue(self)`
periodically via `root.after`.
"""

from __future__ import annotations

import queue
from typing import Any

from .config import PROGRESS_POLL_MS


def process_progress_queue(app: Any) -> None:
    try:
        while True:
            item = app.progress_q.get_nowait()
            if item.get("type") == "progress":
                try:
                    overall_val = float(item.get("value", 0) or 0)
                except Exception:
                    overall_val = 0.0
                app.overall_progress.configure(value=overall_val)
                item_pct = item.get("percent")
                if item_pct is not None:
                    try:
                        app.item_progress.configure(value=float(item_pct))
                    except Exception:
                        pass
                pct = item.get("percent")
                speed = item.get("speed_human")
                eta = item.get("eta_human")
                if pct is None and "value" in item:
                    try:
                        pct = float(item.get("value") or 0)
                    except Exception:
                        pct = 0
                if pct is not None:
                    pct_text = f"{pct:.1f}%"
                    app.stat_pct_var.set(pct_text)
                    try:
                        c = "#6aa84f" if float(pct) >= 100.0 else "#ffd166"
                        app.stat_pct_lbl.configure(foreground=c)
                    except Exception:
                        pass
                else:
                    app.stat_pct_var.set("")
                app.stat_speed_var.set((f"@ {speed}" if speed else ""))
                app.stat_eta_var.set((f"in ETA {eta}" if eta else ""))
                app.status_var.set("Downloading")
                log_line = item.get("log_line")
                if log_line:
                    app._log(log_line)
            elif item.get("type") == "status":
                app.stat_pct_var.set("")
                app.stat_speed_var.set("")
                app.stat_eta_var.set("")
                text = item.get("text", "")
                if str(text).startswith("Saved to:"):
                    pass
                else:
                    t = str(text)
                    if t.lower().startswith("error") or t.startswith("❌"):
                        try:
                            app.warn_var.set(f"❌ {t.replace('Error:', '').strip()}")
                        except Exception:
                            app.warn_var.set(f"❌ {t}")
                        app.status_var.set(f"❌ {t}")
                    elif t.lower().startswith("skipping") or t.startswith("⚠️"):
                        app.warn_var.set(f"⚠️ {t}")
                    else:
                        app.status_var.set(t)
            elif item.get("type") == "label":
                if item.get("which") == "overall":
                    txt = item.get("text", "")
                    try:
                        app.overall_label_var.set(txt)
                    except Exception:
                        pass
                elif item.get("which") == "file":
                    try:
                        app.current_item_var.set(item.get("text", ""))
                    except Exception:
                        pass
                elif item.get("which") == "current_item":
                    try:
                        app.current_item_var.set(item.get("text", ""))
                        if not getattr(app, "_item_widgets_packed", False):
                            try:
                                app.status_row.pack_forget()
                            except Exception:
                                pass
                            try:
                                app.current_item_label.pack(padx=12, pady=(6, 2), anchor="w")
                            except Exception:
                                pass
                            try:
                                app.item_progress.pack(fill="x", padx=12)
                            except Exception:
                                pass
                            try:
                                app.status_var.set("")
                                app.status_row.pack(padx=12, pady=(6, 0), anchor="w")
                            except Exception:
                                pass
                            try:
                                app.saved_to_label.pack(padx=12, pady=(6, 0), anchor="w")
                            except Exception:
                                pass
                            try:
                                app.warn_label.pack(padx=12, pady=(4, 0), anchor="w")
                            except Exception:
                                pass
                            app._item_widgets_packed = True
                    except Exception:
                        pass
                elif item.get("which") == "saved_to":
                    text = item.get("text", "")
                    try:
                        app._saved_to_full_path = text.split("Saved to:", 1)[1].strip()
                    except Exception:
                        app._saved_to_full_path = None
                    app.saved_to_var.set(text)
                elif item.get("which") == "clear_warn":
                    app.warn_var.set("")
            elif item.get("type") == "done":
                app.downloading = False
                app.download_btn.config(state="normal")
                if hasattr(app, 'cancel_btn'):
                    app.cancel_btn.config(state="disabled")
    except queue.Empty:
        pass
    finally:
        app.root.after(PROGRESS_POLL_MS, lambda: process_progress_queue(app))


