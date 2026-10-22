"""Native output-directory chooser; no files are created by this dialog."""
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .signature_ui import open_signature_manager
from .signatures import SLOTS


def choose_export_directory(root, workbook, signature_store):
    dialog = tk.Toplevel(root)
    dialog.title("导出验收单与领用单")
    dialog.resizable(True, False)
    dialog.transient(root)
    dialog.configure(padx=20, pady=18)
    dialog.columnconfigure(0, weight=1)
    directory = tk.StringVar(value=str(Path(workbook).parent / "导出PDF"))
    selected = []
    displayed_revision = None
    ttk.Label(dialog, text="分别生成两份 PDF", font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(dialog, text="验收单.pdf  ·  领用单.pdf\nA4 横向，所有列在一页宽；明细较多时向下自动分页。",
              justify="left").grid(row=1, column=0, sticky="w", pady=(8, 12))
    note = ttk.Label(dialog, text="导出本次执行处理并通过金额核对后保存的表格。更换输入或重新预览后，须再次执行成功才可导出；工作簿外部修改后也须重新处理。",
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
    signing = ttk.LabelFrame(dialog, text="签名", padding=10)
    signing.grid(row=5, column=0, sticky="ew", pady=(0, 14))
    signing.columnconfigure(0, weight=1)
    include = tk.BooleanVar(value=False)
    checkbox = ttk.Checkbutton(signing, text="添加已保存签名", variable=include)
    checkbox.grid(row=0, column=0, sticky="w")
    signature_summary = ttk.Label(signing, justify="left", wraplength=490)
    signature_summary.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(7, 0))
    def refresh_signatures(initial=False):
        nonlocal displayed_revision
        try:
            state = signature_store.read()
            displayed_revision = signature_store.revision(state)
            labels = {item["id"]: item["label"] for item in state["items"]}
            assigned = [(sheet, label, labels[state["bindings"][key]]) for key, sheet, label in SLOTS
                        if state["bindings"].get(key)]
            available = bool(assigned)
            was_disabled = checkbox.instate(("disabled",))
            checkbox.configure(state="normal" if available else "disabled")
            if initial or not available or was_disabled:
                include.set(available)
            signature_summary.configure(text="\n".join(f"{sheet} · {role}：{label}" for sheet, role, label in assigned)
                                        if available else "请在签名管理中导入图片，并为签字位置选择标签。")
        except (OSError, ValueError) as exc:
            displayed_revision = None
            include.set(False)
            checkbox.configure(state="disabled")
            signature_summary.configure(text="签名设置不可用：" + str(exc))
    def manage():
        open_signature_manager(dialog, signature_store)
        refresh_signatures()
    ttk.Button(signing, text="签名管理…", command=manage).grid(row=0, column=1, sticky="e", padx=(10, 0))
    refresh_signatures(initial=True)
    buttons = ttk.Frame(dialog)
    buttons.grid(row=6, column=0, sticky="e")
    def accept():
        try:
            snapshot = signature_store.snapshot(expected_revision=displayed_revision) if include.get() else None
            if snapshot is not None and not any(snapshot["bindings"].values()):
                raise ValueError("签字位置已变化，请在签名管理中重新选择标签。")
        except (OSError, ValueError) as exc:
            messagebox.showwarning("签名暂不可用", str(exc), parent=dialog)
            refresh_signatures()
            return
        selected.append({"directory": directory.get(), "signatures": snapshot})
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
