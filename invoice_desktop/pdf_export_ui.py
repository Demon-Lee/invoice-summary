"""Native output-directory chooser; no files are created by this dialog."""
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk


def choose_export_directory(root, workbook):
    dialog = tk.Toplevel(root)
    dialog.title("导出验收单与领用单")
    dialog.resizable(True, False)
    dialog.transient(root)
    dialog.configure(padx=20, pady=18)
    dialog.columnconfigure(0, weight=1)
    directory = tk.StringVar(value=str(Path(workbook).parent / "导出PDF"))
    selected = []
    ttk.Label(dialog, text="分别生成两份 PDF", font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(dialog, text="验收单.pdf  ·  领用单.pdf\nA4 横向，所有列在一页宽；明细较多时向下自动分页。",
              justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
    note = ttk.Label(dialog, text="导出工作簿已保存的内容。若本次只做了预览或人工校正，请先完成“执行处理”，再导出更新后的表格。",
                     wraplength=520, justify="left", foreground="#946522")
    note.grid(row=2, column=0, sticky="ew", pady=(0, 14))
    ttk.Label(dialog, text="保存位置").grid(row=3, column=0, sticky="w")
    row = ttk.Frame(dialog)
    row.grid(row=4, column=0, sticky="ew", pady=(5, 16))
    row.columnconfigure(0, weight=1)
    ttk.Entry(row, textvariable=directory, state="readonly", width=58).grid(row=0, column=0, sticky="ew")
    def pick():
        initial = Path(directory.get())
        while not initial.exists() and initial.parent != initial:
            initial = initial.parent
        value = filedialog.askdirectory(title="选择 PDF 保存位置", initialdir=str(initial), parent=dialog)
        if value:
            directory.set(value)
    ttk.Button(row, text="选择位置…", command=pick).grid(row=0, column=1, padx=(8, 0))
    buttons = ttk.Frame(dialog)
    buttons.grid(row=5, column=0, sticky="e")
    def accept():
        selected.append(directory.get())
        dialog.destroy()
    ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right", padx=(8, 0))
    start = ttk.Button(buttons, text="开始导出", command=accept, style="Primary.TButton")
    start.pack(side="right")
    dialog.bind("<Escape>", lambda event: dialog.destroy())
    dialog.bind("<Configure>", lambda event: note.configure(wraplength=max(240, dialog.winfo_width() - 40)) if event.widget is dialog else None)
    dialog.update_idletasks()
    x = root.winfo_rootx() + max(0, (root.winfo_width() - dialog.winfo_width()) // 2)
    y = root.winfo_rooty() + max(0, (root.winfo_height() - dialog.winfo_height()) // 2)
    dialog.geometry(f"+{x}+{y}")
    dialog.grab_set()
    start.focus_set()
    root.wait_window(dialog)
    return selected[0] if selected else None
