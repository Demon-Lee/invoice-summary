"""Output chooser with a synchronized portable signature-library summary."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .signature_ui import open_signature_manager
from .signatures import SLOTS
from .dialogs import center_dialog, filedialog, messagebox


def choose_export_directory(root, workbook, signature_store):
    dialog = tk.Toplevel(root)
    dialog.withdraw()
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
            attention = state.get("attention", {})
            available = bool(assigned or attention)
            was_disabled = checkbox.instate(("disabled",))
            if initial or (was_disabled and available):
                include.set(available)
            # A refresh must not turn a requested signed export into unsigned.
            checkbox.configure(state="normal" if available or include.get() else "disabled")
            summary = [f"{sheet} · {role}：{label}" for sheet, role, label in assigned]
            if attention:
                affected = [f"{sheet} · {role}" for key, sheet, role in SLOTS if key in attention]
                summary.append("需要重新确认：" + "、".join(affected) + "。请打开签名管理，重新选择标签或明确选择不使用签名。")
            issues = state.get("issues", [])
            summary.extend(issues[:3])
            if len(issues) > 3:
                summary.append(f"另有 {len(issues) - 3} 项，请在签名管理中查看。")
            if not available and not attention:
                summary.insert(0, "请放入签名图片，并在签名管理中为签字位置选择标签。")
            signature_summary.configure(text="\n".join(summary), foreground="#946522" if attention or issues else "#273d5d")
        except (OSError, ValueError) as exc:
            displayed_revision = None
            if initial:
                include.set(True)
            checkbox.configure(state="normal")
            signature_summary.configure(text="签名设置暂不可用：" + str(exc)
                                        + "\n请重试或进入签名管理；如需无签名导出，请明确取消勾选。", foreground="#946522")
    def manage():
        open_signature_manager(dialog, signature_store)
        refresh_signatures()
    ttk.Button(signing, text="签名管理…", command=manage).grid(row=0, column=1, sticky="e", padx=(10, 0))
    refresh_signatures(initial=True)
    buttons = ttk.Frame(dialog)
    buttons.grid(row=6, column=0, sticky="e")
    def accept():
        try:
            if include.get() and displayed_revision is None:
                raise ValueError("签名设置尚未读取完成，请刷新并核对标签后再导出。")
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
    center_dialog(dialog, root)
    dialog.deiconify()
    dialog.wait_visibility()
    dialog.grab_set()
    start.focus_set()
    root.wait_window(dialog)
    return selected[0] if selected else None
