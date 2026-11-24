"""Output chooser with directly editable, remembered PDF signature choices."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from .dialogs import center_dialog, dialog_work_area_size, filedialog
from .export_signature_ui import ExportSignaturePicker
from .ui import FONT, PALETTE, surface
from .ui_widgets import AutoHideScrollbar
from .ui_switches import configure_signature_toggle


def _pdf_card_icon(parent):
    scale = max(0.75, float(parent.tk.call("tk", "scaling")) / (4 / 3))
    unit = scale * 4
    image = Image.new("RGBA", (round(34 * unit), round(40 * unit)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    box = lambda values: tuple(round(value * unit) for value in values)
    draw.rounded_rectangle(box((0, 0, 34, 40)), radius=round(6 * unit), fill="#edf3ff")
    points = [box(point) for point in ((9, 7), (21, 7), (26, 12), (26, 33), (9, 33))]
    draw.polygon(points, fill="white", outline=PALETTE["blue"], width=max(1, round(unit)))
    draw.line([box(point) for point in ((21, 7), (21, 12), (26, 12))],
              fill=PALETTE["blue"], width=max(1, round(unit)))
    draw.rounded_rectangle(box((5, 20, 29, 31)), radius=round(2 * unit), fill=PALETTE["blue"])
    draw.text(box((17, 25.5)), "PDF", anchor="mm", fill="white",
              font=ImageFont.load_default(size=round(7 * unit)))
    return ImageTk.PhotoImage(image.resize((round(34 * scale), round(40 * scale)),
                                          Image.Resampling.LANCZOS), master=parent)


class ExportFileCards:
    """Read-only output previews, using the same surfaces as the main window."""
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.icon = _pdf_card_icon(parent)
        self.cards = []
        self.include_summary = True
        self.layout_key = None
        for name in ("验收单.pdf", "领用单.pdf", "发票汇总.pdf"):
            card = surface(self.frame, padding=10)
            ttk.Label(card, image=self.icon, style="Surface.TLabel").grid(row=0, column=0, sticky="w")
            ttk.Label(card, text=name, font=(FONT, 10, "bold"), foreground=PALETTE["heading"],
                      style="Surface.TLabel").grid(row=0, column=1, sticky="w", padx=(10, 0))
            card.columnconfigure(1, weight=1)
            self.cards.append(card)
        self.frame.bind("<Configure>", self._layout)
        self._layout()

    def set_summary(self, enabled):
        self.include_summary = bool(enabled)
        self._layout()

    def _layout(self, event=None):
        visible = self.cards if self.include_summary else self.cards[:2]
        width = event.width if event is not None else self.frame.winfo_width()
        minimum = max(card.winfo_reqwidth() for card in visible)
        columns = len(visible) if width <= 1 else min(len(visible), max(1, (width + 10) // (minimum + 10)))
        key = (self.include_summary, columns)
        if key == self.layout_key:
            return
        self.layout_key = key
        for column in range(3):
            self.frame.columnconfigure(column, weight=1 if column < columns else 0,
                                       uniform="export-file-cards" if column < columns else "")
        for card in self.cards:
            card.grid_forget()
        last_row = (len(visible) - 1) // columns
        for index, card in enumerate(visible):
            row, column = divmod(index, columns)
            card.grid(row=row, column=column, sticky="nsew",
                      padx=(0, 10 if column < columns - 1 else 0),
                      pady=(0, 8 if row < last_row else 0))


def _section_heading(parent, title, row, *, first=False):
    heading = ttk.Frame(parent)
    heading.grid(row=row, column=0, sticky="ew", pady=(0 if first else 16, 9))
    heading.columnconfigure(1, weight=1)
    ttk.Label(heading, text=title, font=(FONT, 11, "bold"),
              foreground=PALETTE["heading"]).grid(row=0, column=0, sticky="w")
    tk.Frame(heading, background=PALETTE["line"], height=1).grid(
        row=0, column=1, sticky="ew", padx=(12, 0))


def choose_export_directory(root, workbook, signature_store):
    dialog = tk.Toplevel(root)
    dialog.withdraw()
    dialog.title("导出 PDF")
    dialog.resizable(True, True)
    dialog.transient(root)
    dialog.configure(bg=PALETTE["background"])
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(0, weight=1)
    directory = tk.StringVar(master=dialog, value=str(Path(workbook).parent / "导出PDF"))
    include_summary = tk.BooleanVar(master=dialog, value=True)
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
    _section_heading(body, "导出位置", 0, first=True)
    row = ttk.Frame(body)
    row.grid(row=1, column=0, sticky="ew")
    row.columnconfigure(0, weight=1)
    ttk.Entry(row, textvariable=directory, state="readonly", width=1).grid(row=0, column=0, sticky="ew")

    _section_heading(body, "导出内容", 2)
    outputs = ExportFileCards(body)
    outputs.frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
    summary_switch = ttk.Checkbutton(body, text="同时生成发票汇总", variable=include_summary,
                                    command=lambda: outputs.set_summary(include_summary.get()), cursor="hand2", takefocus=True,
                                    style=configure_signature_toggle(body, font=FONT, palette=PALETTE))
    summary_switch.grid(row=3, column=0, sticky="w", pady=(0, 10))
    note = ttk.Label(body, text="导出本次执行处理并通过金额核对后保存的表格。更换输入或重新预览后，须再次执行成功才可导出；工作簿外部修改后也须重新处理。",
                     wraplength=700, justify="left", foreground="#946522")
    note.grid(row=5, column=0, sticky="ew")

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
        selected.append({"directory": directory.get(), "signatures": snapshot,
                         "include_invoice_summary": bool(include_summary.get())})
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
            summary_switch.configure(state=state)

    _section_heading(body, "签名", 6)
    picker = ExportSignaturePicker(body, signature_store, controls)
    picker.frame.grid(row=7, column=0, sticky="ew")
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
