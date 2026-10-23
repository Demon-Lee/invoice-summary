"""Compact modal results; technical diagnostics are copied only on request."""

import math
import tkinter as tk
from tkinter import font as tkfont, ttk

from .ui import FONT, PALETTE, STAGES, surface, text_widget


def show_result_dialog(parent, title, message, *, diagnostics=None, tone="error"):
    snapshot = None if diagnostics is None else str(diagnostics)
    previous_grab = parent.grab_current()
    previous_status = previous_grab.grab_status() if previous_grab else None
    previous_focus = parent.focus_get()
    dialog = tk.Toplevel(parent)
    dialog.withdraw()
    dialog.title(title)
    dialog.transient(parent.winfo_toplevel())
    dialog.configure(bg=PALETTE["background"])
    def close(event=None):
        dialog.destroy()
        return "break"
    dialog.protocol("WM_DELETE_WINDOW", close)
    dialog.bind("<Escape>", close)
    try:
        width = min(640, max(320, dialog.winfo_screenwidth() - 80))
        font = tkfont.Font(dialog, font=(FONT, 10))
        lines = sum(max(1, math.ceil(font.measure(line) / max(160, width - 90)))
                    for line in str(message).splitlines())
        height = min(max(200, dialog.winfo_screenheight() - 100),
                     max(220, min(520, (lines + 2) * font.metrics("linespace") + 90)))
        dialog.geometry(f"{width}x{height}")
        dialog.minsize(min(360, width), min(200, height))
        frame = ttk.Frame(dialog, padding=14)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        panel = surface(frame)
        border = STAGES.get(tone, STAGES["error"])[2]
        panel.configure(highlightbackground=border, highlightcolor=border)
        panel.grid(row=0, column=0, sticky="nsew")
        text = text_widget(panel, height=5)
        text.configure(state="normal", font=(FONT, 10))
        text.insert("1.0", str(message))
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)
        footer = ttk.Frame(frame)
        footer.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(0, weight=1)
        if snapshot is not None:
            def copy_error(event=None):
                try:
                    dialog.clipboard_clear()
                    dialog.clipboard_append(snapshot)
                except tk.TclError:
                    copy_button.configure(text="复制失败，请重试")
                else:
                    copy_button.configure(text="已复制")
                return "break"
            copy_button = ttk.Button(footer, text="复制错误信息", command=copy_error,
                                     style="ExportAction.TButton", cursor="hand2")
            copy_button.grid(row=0, column=0, sticky="w", padx=(0, 12))
            copy_button.bind("<Return>", copy_error)
        confirm = ttk.Button(footer, text="确定", command=close,
                             style="ExecuteAction.TButton", cursor="hand2")
        confirm.grid(row=0, column=1, sticky="e")
        confirm.bind("<Return>", close)
        dialog.deiconify()
        dialog.wait_visibility()
        dialog.grab_set()
        confirm.focus_set()
        parent.wait_window(dialog)
    finally:
        try:
            if dialog.winfo_exists():
                dialog.destroy()
            if previous_grab is not None and previous_grab.winfo_exists():
                if previous_status == "global":
                    previous_grab.grab_set_global()
                else:
                    previous_grab.grab_set()
            if previous_focus is not None and previous_focus.winfo_exists():
                previous_focus.focus_set()
        except tk.TclError:
            pass
