"""Output chooser with directly editable, remembered PDF signature choices."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .dialogs import center_dialog, dialog_work_area_size, filedialog
from .export_signature_ui import ExportSignaturePicker
from .ui import FONT, PALETTE
from .ui_widgets import AutoHideScrollbar


def choose_export_directory(root, workbook, signature_store):
    dialog = tk.Toplevel(root)
    dialog.withdraw()
    dialog.title("导出验收单与领用单")
    dialog.resizable(True, True)
    dialog.transient(root)
    dialog.configure(bg=PALETTE["background"])
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(0, weight=1)
    directory = tk.StringVar(master=dialog, value=str(Path(workbook).parent / "导出PDF"))
    selected = []
    scroller = ttk.Frame(dialog)
    scroller.grid(row=0, column=0, sticky="nsew", padx=18, pady=(18, 0))
    scroller.columnconfigure(0, weight=1)
    scroller.rowconfigure(0, weight=1)
    canvas = tk.Canvas(scroller, background=PALETTE["background"], highlightthickness=0,
                       borderwidth=0, width=1, height=1)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar = AutoHideScrollbar(scroller, orient="vertical", command=canvas.yview,
                                  background=PALETTE["background"])
    scrollbar.attach(canvas, scroller)
    canvas.configure(yscrollcommand=scrollbar.set)
    body = ttk.Frame(canvas)
    body.columnconfigure(0, weight=1)
    window = canvas.create_window(0, 0, anchor="nw", window=body)
    ttk.Label(body, text="分别生成两份 PDF", font=(FONT, 12, "bold")).grid(
        row=0, column=0, sticky="w")
    ttk.Label(body, text="验收单.pdf  ·  领用单.pdf\nA4 横向，所有列在一页宽；明细较多时向下自动分页。",
              justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
    note = ttk.Label(body, text="导出本次执行处理并通过金额核对后保存的表格。更换输入或重新预览后，须再次执行成功才可导出；工作簿外部修改后也须重新处理。",
                     wraplength=700, justify="left", foreground="#946522")
    note.grid(row=2, column=0, sticky="ew", pady=(0, 14))
    ttk.Label(body, text="保存位置").grid(row=3, column=0, sticky="w")
    row = ttk.Frame(body)
    row.grid(row=4, column=0, sticky="ew", pady=(5, 16))
    row.columnconfigure(0, weight=1)
    ttk.Entry(row, textvariable=directory, state="readonly", width=1).grid(row=0, column=0, sticky="ew")

    def pick():
        initial = Path(directory.get())
        while not initial.exists() and initial.parent != initial:
            initial = initial.parent
        value = filedialog.askdirectory(title="选择 PDF 保存位置", initialdir=str(initial), parent=dialog)
        if value:
            directory.set(value)

    pick_button = ttk.Button(row, text="选择位置…", command=pick, style="ExportAction.TButton")
    pick_button.grid(row=0, column=1, padx=(8, 0))
    buttons = ttk.Frame(dialog)
    buttons.grid(row=1, column=0, sticky="ew", padx=18, pady=(12, 16))
    picker = None

    def close():
        if picker is None or not picker.saving:
            dialog.destroy()

    def accepted(snapshot):
        selected.append({"directory": directory.get(), "signatures": snapshot})
        dialog.destroy()

    def accept():
        picker.confirm(accepted)

    cancel = ttk.Button(buttons, text="取消", command=close, style="ExportAction.TButton")
    cancel.pack(side="right", padx=(8, 0))
    start = ttk.Button(buttons, text="开始导出", command=accept, style="ExecuteAction.TButton")
    start.pack(side="right")

    def controls():
        # Initial panel construction can notify before its assignment completes.
        if picker is not None:
            start.configure(state="normal" if picker.can_confirm else "disabled")
            state = "disabled" if picker.saving else "normal"
            cancel.configure(state=state)
            pick_button.configure(state=state)

    picker = ExportSignaturePicker(body, signature_store, controls)
    picker.frame.grid(row=5, column=0, sticky="ew")
    controls()

    def sync_scroll(event=None):
        width = max(1, canvas.winfo_width() - 16)
        canvas.itemconfigure(window, width=width)
        height = max(body.winfo_reqheight(), canvas.winfo_height())
        canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), height))
        if body.winfo_reqheight() <= canvas.winfo_height():
            canvas.yview_moveto(0)
        note.configure(wraplength=max(200, width - 8))
        picker.status.configure(wraplength=max(200, width - 8))

    def wheel(event):
        if body.winfo_reqheight() > canvas.winfo_height():
            number = getattr(event, "num", None)
            delta = getattr(event, "delta", 0)
            units = -1 if number == 4 or delta > 0 else 1 if number == 5 or delta < 0 else 0
            if units:
                canvas.yview_scroll(units, "units")
        return "break"

    def destroyed(event):
        if event.widget is dialog:
            picker.close()

    body.bind("<Configure>", sync_scroll)
    canvas.bind("<Configure>", sync_scroll)
    dialog.bind("<Destroy>", destroyed, add="+")
    dialog.bind("<Escape>", lambda event: close())
    dialog.protocol("WM_DELETE_WINDOW", close)
    for sequence in ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-4>", "<Button-5>"):
        dialog.bind(sequence, wheel)
    available_width, available_height = dialog_work_area_size(root)
    width, height_limit = min(800, max(1, available_width - 80)), max(1, available_height - 80)
    dialog.geometry(f"{width}x{min(540, height_limit)}")
    dialog.minsize(min(600, width), min(360, height_limit))
    dialog.update_idletasks()
    height = min(height_limit, body.winfo_reqheight() + buttons.winfo_reqheight() + 48)
    dialog.geometry(f"{width}x{height}")
    center_dialog(dialog, root)
    dialog.deiconify()
    dialog.wait_visibility()
    dialog.grab_set()
    start.focus_set()
    root.wait_window(dialog)
    return selected[0] if selected else None
