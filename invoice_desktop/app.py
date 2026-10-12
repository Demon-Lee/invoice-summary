"""Native offline UI; background work reports through a main-thread queue."""
import json
import os
import queue
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .controller import Controller, resource_root
from .updates import EngineStore, export_update, read_manifest

HELP = """1. 选择包含完整批次发票的文件夹，以及需要更新的 .xlsx 工作簿。
2. 点击“只读预览”。此步骤不会重命名 PDF，也不会保存工作簿。
3. 查看文件命名、明细金额、异常和表格映射。异常解决后重新预览。
4. 预览通过后点击“执行处理”。软件会重命名发票、更新工作簿、设置字体、调用 Excel 重算，并逐票复核金额。
5. 查看实际结果和临时文件清理状态。

工作簿须包含“验收”“领用”两张表，且各有完整表头、唯一三行页脚（合计、签字、说明）和日期标签。请选择 .xlsx，执行前关闭 Excel 中的目标工作簿。

软件原位更新所选工作簿，不自动创建备份。出现重名、字段不确定、金额不一致或模板结构异常时停止，不提供强制覆盖。

识别依据与 skill 相同：从 PDF 内容读取字段，合并规定的折扣与运费，保留重复明细，空数量按 1，金额逐分核对。当前不支持扫描图片 OCR。

规则更新：在“规则与更新”中绑定可信的 summarize-invoice-pdfs 文件夹，点击“同步本机 skill”。其他电脑可导入离线 ZIP 更新包。处理时固定使用界面显示的识别版本。

只修改 SKILL.md 文字不会自动改进算法：需要同时更新对应脚本和测试。写表原则变化或新增依赖可能要求升级主程序。更新前请由 skill 维护者运行其测试。
"""


class App:
    def __init__(self, root, state_dir=None):
        self.root = root
        self.state_dir = Path(state_dir or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "InvoiceSummary")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.store = EngineStore(self.state_dir / "recognition", resource_root() / "engine")
        self.events = queue.Queue()
        self.busy = False
        self.preview_result = None
        self.controller = None
        self.last_result = None
        self.interactive = []
        self.pdf = tk.StringVar()
        self.book = tk.StringVar()
        self.status = tk.StringVar(value="选择文件，然后进行只读预览")
        self.summary = tk.StringVar(value="文件在本机处理 · Microsoft Excel 桌面版必需")
        self.version = tk.StringVar()
        self.source_status = tk.StringVar()
        settings = self.state_dir / "settings.json"
        default = Path.home() / ".agents/skills/summarize-invoice-pdfs"
        try:
            source = json.loads(settings.read_text(encoding="utf-8")).get("skill_source", "")
        except (OSError, ValueError):
            source = str(default) if default.is_dir() else ""
        self.source = tk.StringVar(value=source)
        self._build()
        self.pdf.trace_add("write", self._invalidate)
        self.book.trace_add("write", self._invalidate)
        self.source.trace_add("write", self._source_changed)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._refresh_version()
        self.root.after(100, self._poll)
        self.root.after(3000, self._periodic_source)

    def _button(self, parent, label, action):
        widget = ttk.Button(parent, text=label, command=action)
        self.interactive.append(widget)
        return widget

    def _build(self):
        self.root.title("发票汇总助手")
        icon = resource_root() / "resources/app.ico"
        if icon.exists():
            self.root.iconbitmap(str(icon))
        self.root.geometry("1140x820")
        self.root.minsize(900, 650)
        self.root.configure(bg="#f4f7fb")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("TFrame", background="#f4f7fb")
        style.configure("TLabel", background="#f4f7fb", foreground="#18304e")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 22, "bold"))
        style.configure("TButton", padding=(12, 8))
        style.configure("Treeview", rowheight=32, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"), padding=8)
        style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", "#12385c")])
        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="发票汇总助手", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="离线处理 · 先预览，再执行 · 逐分复核金额").pack(anchor="w", pady=(4, 16))
        tabs = ttk.Notebook(outer)
        tabs.pack(fill="both", expand=True)
        process = ttk.Frame(tabs, padding=16)
        rules = ttk.Frame(tabs, padding=16)
        help_tab = ttk.Frame(tabs, padding=16)
        tabs.add(process, text="处理发票")
        tabs.add(rules, text="规则与更新")
        tabs.add(help_tab, text="使用说明")
        process.columnconfigure(1, weight=1)
        process.rowconfigure(5, weight=1)
        for row, label, variable, action in ((0, "PDF 文件夹", self.pdf, self._pick_pdf), (1, "目标工作簿", self.book, self._pick_book)):
            ttk.Label(process, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
            entry = ttk.Entry(process, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            self.interactive.append(entry)
            self._button(process, "选择", action).grid(row=row, column=2, padx=(10, 0))
        buttons = ttk.Frame(process)
        buttons.grid(row=2, column=0, columnspan=3, sticky="w", pady=(12, 8))
        self._button(buttons, "只读预览", self._preview).pack(side="left", padx=(0, 8))
        self.execute = self._button(buttons, "执行处理", self._apply)
        self.execute.pack(side="left", padx=(0, 8))
        self.execute.configure(state="disabled")
        self._button(buttons, "打开发票目录", lambda: self._open(self.pdf.get())).pack(side="left", padx=(0, 8))
        self._button(buttons, "打开工作簿", lambda: self._open(self.book.get())).pack(side="left")
        ttk.Label(process, textvariable=self.summary, wraplength=950).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 4))
        ttk.Label(process, text="完整批次明细（已有发票也会显示）").grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 4))
        table = ttk.Frame(process)
        table.grid(row=5, column=0, columnspan=3, sticky="nsew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        columns = ("sequence", "filename", "spec", "unit", "quantity", "amount")
        self.tree = ttk.Treeview(table, columns=columns, show="headings")
        for name, label, width in zip(columns, ("序号", "PDF → 新文件名", "规格型号", "单位", "数量", "含税金额"), (55, 460, 140, 65, 70, 105)):
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, minwidth=40, anchor="w" if name in ("filename", "spec") else "center", stretch=name == "filename")
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        scroll = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        scroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=scroll.set)
        ttk.Label(process, text="检查、异常与实际结果").grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 4))
        self.report = self._text(process, height=7)
        self.report.grid(row=7, column=0, columnspan=3, sticky="ew")
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(12, 5))
        self.progress_bar = ttk.Progressbar(outer, mode="indeterminate")
        self.progress_bar.pack(fill="x")
        ttk.Label(rules, textvariable=self.version, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(0, 10))
        ttk.Label(rules, text="绑定本机 skill 后，预览前会检查更新。同步只影响后续处理，正在运行的任务固定使用原版本。", wraplength=950).pack(anchor="w")
        source_row = ttk.Frame(rules)
        source_row.pack(fill="x", pady=10)
        entry = ttk.Entry(source_row, textvariable=self.source)
        entry.pack(side="left", fill="x", expand=True)
        self.interactive.append(entry)
        self._button(source_row, "选择 skill", self._pick_source).pack(side="left", padx=(8, 0))
        source_buttons = ttk.Frame(rules)
        source_buttons.pack(anchor="w", pady=5)
        for label, action in (("同步本机 skill", self._sync), ("导出离线更新包", self._export), ("导入更新包", self._import), ("回退版本", self._rollback), ("解除绑定", self._unbind)):
            self._button(source_buttons, label, action).pack(side="left", padx=(0, 6))
        ttk.Label(rules, textvariable=self.source_status, wraplength=950).pack(anchor="w", pady=10)
        ttk.Label(rules, text="当前识别版本的 skill 规则").pack(anchor="w", pady=(6, 5))
        self.rule_text = self._text(rules)
        self.rule_text.pack(fill="both", expand=True)
        text_widget = self._text(help_tab)
        text_widget.pack(fill="both", expand=True)
        self._set_text(text_widget, HELP)

    def _text(self, parent, height=15):
        return tk.Text(parent, height=height, wrap="word", bg="white", fg="#243d55", relief="flat", padx=10, pady=8, font=("Microsoft YaHei UI", 10), state="disabled")

    def _set_text(self, widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _pick_pdf(self):
        value = filedialog.askdirectory(title="选择完整批次的发票 PDF 文件夹")
        if value:
            self.pdf.set(value)

    def _pick_book(self):
        value = filedialog.askopenfilename(title="选择要原位更新的工作簿", filetypes=[("Excel 工作簿", "*.xlsx")])
        if value:
            self.book.set(value)

    def _pick_source(self):
        value = filedialog.askdirectory(title="选择包含 SKILL.md 和 scripts 的 skill 文件夹")
        if value:
            self.source.set(value)

    def _invalidate(self, *_):
        self.preview_result = None
        self.execute.configure(state="disabled")

    def _source_changed(self, *_):
        self._invalidate()
        (self.state_dir / "settings.json").write_text(json.dumps({"skill_source": self.source.get()}, ensure_ascii=False), encoding="utf-8")
        self._check_source()

    def _check_source(self):
        source = self.source.get().strip()
        if not source:
            self.source_status.set("使用当前版本的离线快照，可绑定本机 skill 或导入更新包。")
            return None
        try:
            status = self.store.source_status(source)
            if status["error"]:
                self.source_status.set(status["error"])
                return status["error"]
            if status["changed"]:
                value = "发现 skill 更新，请先同步：" + "、".join(status["changed"])
                self.source_status.set(value)
                return value
            self.source_status.set("已与本机 skill 同步 · 来源：" + source)
            return None
        except Exception as exc:
            value = "绑定来源不可用：" + str(exc)
            self.source_status.set(value)
            return value

    def _periodic_source(self):
        if not self.busy and self._check_source():
            self._invalidate()
        self.root.after(3000, self._periodic_source)

    def _refresh_version(self):
        self.version.set(f"软件 {__version__}  ·  识别版本 {self.store.version()}")
        self._set_text(self.rule_text, (self.store.active() / "SKILL.md").read_text(encoding="utf-8"))
        self._check_source()

    def _run(self, work, done):
        if self.busy:
            return
        self.busy = True
        self.execute.configure(state="disabled")
        for widget in self.interactive:
            widget.configure(state="disabled")
        self.progress_bar.start(12)
        def worker():
            try:
                self.events.put(("done", done, work()))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "progress":
                    self.status.set(event[1])
                    continue
                self.busy = False
                self.progress_bar.stop()
                for widget in self.interactive:
                    widget.configure(state="normal")
                self.execute.configure(state="disabled")
                if event[0] == "done":
                    event[1](event[2])
                else:
                    self._invalidate()
                    self.status.set("未完成，请查看原因")
                    self._set_text(self.report, event[1])
                    messagebox.showerror("处理未完成", event[1])
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _preview(self):
        error = self._check_source()
        if error:
            messagebox.showinfo("规则需要同步", error)
            return
        self._invalidate()
        directory, book = self.pdf.get(), self.book.get()
        self.controller = Controller(self.store.active(), lambda msg: self.events.put(("progress", msg)), state_dir=self.state_dir / "runs")
        self._run(lambda: self.controller.preview(directory, book), self._render_preview)

    def _render_preview(self, preview):
        self.preview_result = preview
        self._render_table(preview.payload)
        invoices = len(preview.payload.get("records", []))
        rows = sum(len(r.get("rows", [])) for r in preview.payload.get("records", []))
        self.summary.set(f"{invoices} 张发票 · {rows} 条明细 · 本批合计 ¥{preview.total} · 新增明细 {preview.rows_to_add} 条")
        parts = [f"目标工作簿：{preview.workbook}（原位更新，不自动创建备份）", f"识别版本：{preview.engine_version}"]
        for name, details in preview.sheet_details.items():
            parts.append(f"{name}：表头、字段映射、页脚与日期检查通过；待移除末尾空行 {details['blankRowsToRemove']} 行")
        parts.append("异常：\n" + "\n".join(preview.issues) if preview.issues else "异常：无；只读预览通过，尚未改动文件。")
        if preview.resume_pending:
            parts.append("检测到上次处理未完成；本次将继续字体、重算和金额验证，缺失的改名或明细也会补齐。")
        if preview.clean and not preview.has_changes:
            parts.append("没有新增、改名或多余末尾空行，无需处理。")
        self._set_text(self.report, "\n".join(parts))
        if preview.clean and preview.has_changes:
            self.execute.configure(state="normal")

    def _render_table(self, payload, renamed=None):
        self.tree.delete(*self.tree.get_children())
        plans = {p["source"]: p for p in (renamed or payload.get("rename_plan", []))}
        for record in payload.get("records", []):
            source = record["pdf"]
            destination = plans.get(source, {}).get("destination", source)
            mapping = Path(source).name if source == destination else f"{Path(source).name} → {Path(destination).name}"
            for row in record.get("rows", []):
                self.tree.insert("", "end", values=(record["sequence"], mapping, row.get("spec") or "—", row.get("unit") or "—", row.get("quantity") or "1", "¥"+row["amount"]))

    def _apply(self):
        preview = self.preview_result
        if preview is None:
            return
        error = self._check_source()
        if error:
            self._invalidate()
            messagebox.showinfo("规则需要同步", error)
            return
        self._run(lambda: self.controller.apply(preview), self._render_result)

    def _render_result(self, result):
        self.last_result = result
        self.preview_result = None
        self._render_table(result["payload"], result.get("rename_plan"))
        parts = ["处理完成，逐分金额验证通过。" if result["status"] == "completed" else "处理未完成。", "已执行：" + "、".join(result.get("completed", []))]
        if result.get("error"):
            parts.append(result["error"])
        if result.get("rename_plan"):
            actual = result["rename_plan"]
            parts.append(f"实际改名：{sum(p['status']=='renamed' for p in actual)} 个；未完成：{sum(p['status']=='not_completed' for p in actual)} 个")
        totals = result.get("totals", {})
        if result.get("blank_rows_removed"):
            parts.append("实际移除末尾空行：" + "；".join(f"{name} {count} 行" for name, count in result["blank_rows_removed"].items()))
        if totals:
            parts.append(f"PDF 合计 ¥{result['total']} · 验收合计 ¥{totals.get('acceptance_footer_total')} · 领用合计 ¥{totals.get('issue_footer_total')}")
        if result.get("verification", {}).get("exceptions"):
            parts.append("异常：" + json.dumps(result["verification"]["exceptions"], ensure_ascii=False))
        parts.append("临时文件清理：" + result["cleanup"])
        parts.append("继续处理前请重新进行只读预览。")
        self._set_text(self.report, "\n".join(parts))

    def _sync(self):
        source = self.source.get().strip()
        if not source:
            messagebox.showinfo("选择来源", "请先选择本机 skill 文件夹")
            return
        self._run(lambda: self.store.sync(source), self._updated)

    def _updated(self, result):
        self._invalidate()
        self._refresh_version()
        self.status.set("识别版本已更新：" + result["version"])
        messagebox.showinfo("更新完成", "已更新识别版本：" + result["version"] + "\n修改文件：" + "、".join(result.get("changed", [])))

    def _export(self):
        source = self.source.get().strip()
        if not source:
            messagebox.showinfo("选择来源", "请先绑定已完成脚本适配和测试的本机 skill")
            return
        output = filedialog.asksaveasfilename(title="导出离线 skill 更新包", defaultextension=".zip", initialfile="invoice-skill-update.zip", filetypes=[("更新包", "*.zip")])
        if output:
            self._run(lambda: export_update(source, output, read_manifest(self.store.active())), lambda result: messagebox.showinfo("导出完成", "更新包已保存：" + output))

    def _import(self):
        path = filedialog.askopenfilename(title="选择可信的离线 skill 更新包", filetypes=[("更新包", "*.zip")])
        if path:
            self._run(lambda: self.store.install(path), self._updated)

    def _rollback(self):
        def done(_):
            self.source.set("")
            self._invalidate()
            self._refresh_version()
            self.status.set("已回退识别版本，并解除来源绑定；可重新绑定改进后的 skill。")
        self._run(self.store.rollback, done)

    def _unbind(self):
        self.source.set("")
        self._refresh_version()

    def _open(self, value):
        try:
            if not value or not Path(value).exists():
                raise ValueError("请先选择有效文件或目录")
            os.startfile(str(Path(value).resolve()))
        except Exception as exc:
            messagebox.showinfo("无法打开", str(exc))

    def _close(self):
        if self.busy:
            messagebox.showinfo("正在运行", "当前操作结束后再关闭软件，结果会显示在窗口中。")
            return
        self.root.destroy()
