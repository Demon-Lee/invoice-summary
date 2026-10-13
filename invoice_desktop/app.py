"""Native offline UI; background work reports through a main-thread queue."""
import json
import hashlib
import os
import queue
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from decimal import Decimal, InvalidOperation
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .controller import Controller, resource_root, application_root
from .updates import EngineStore, export_update, read_manifest
from .corrections import FIELDS, LABELS, field_value, normalize
from .policy import BOUNDARY_GUIDE, RETAINED_FEATURES, describe_changes

EXECUTION_STEPS = (
    "1. 选择完整批次的 PDF 文件夹和目标 .xlsx 工作簿。",
    "2. 点击“只读预览”；字段有误可双击明细人工校正。",
    "3. 预览通过后点击“执行处理”，清空旧明细并整批重填。",
    "4. 等待完成提示，查看金额复核与临时文件清理结果。",
)
NECESSARY_CONDITIONS = (
    "Windows 10/11，已安装 Microsoft Excel 桌面版。",
    "有文本层的电子 PDF；每次选择完整批次，旧明细全部替换。",
    "约定格式的 .xlsx，含“验收”“领用”、表头、日期与三行页脚。",
    "执行前关闭目标工作簿；软件和输入文件所在目录须可写。",
)
PROCESS_NOTICE = "执行会重命名 PDF，清空两表主表旧明细（含品牌、备注）后整批重填；保留右侧模板文字；原位更新，不自动备份。"
HELP_HEADINGS = ("执行步骤", "必要条件", "阶段提示", "人工校正", "工作簿详细要求", "处理与恢复", "识别原则", "规则更新与分发", "功能归属与更新边界", "一、与 skill 保持一致：共享规则", "二、软件独有功能：随软件版本更新", "三、双方共同遵守：数据与模板约定", "软件执行流程", "原始 skill 说明的适用范围", "以后更新与分发")
HELP = "\n".join(("执行步骤", *EXECUTION_STEPS, "", PROCESS_NOTICE, "", "必要条件", *NECESSARY_CONDITIONS)) + """

阶段提示
操作按钮下方显示当前阶段与下一步。蓝色表示处理中，绿色表示通过，黄色表示预览异常或清理提醒，红色表示操作未完成。只读预览和执行结束时会弹出结果提示，关闭提示后仍可查看页面上的阶段结果与详细报告。

预览完成只表示检查结束；只有“预览通过”才可以执行。人工校正后的检查只更新页面提示。更换输入或更新规则后，须重新预览。

人工校正
选中一条预览明细，点击“人工校正”或双击该行。对照原 PDF 校正产品名称、规格型号、单位、数量、含税金额和生产厂家，单价自动计算。保存后重新检查金额、文件名和工作簿映射；通过后才可执行。“恢复识别值”可撤销该行校正。

校正只对本次预览有效，保存时不会改动 PDF、工作簿或 skill。重新发起普通预览会重新识别，需要再次校正。未完成执行的校正会随恢复记录保留，恢复期间固定使用该次校正。

不支持增删预览明细或修改票面总额。漏项、多项、整票无法解析等结构问题仍需改进 skill。金额始终逐分核对，正式填表使用本次预览及人工校正后的结果。

工作簿详细要求
工作簿须包含“验收”“领用”两张表，且各有完整表头、明细格式行、唯一三行页脚（合计、签字、说明）和日期标签。

每次按完整批次重填：清空表头与合计之间的主表明细内容，包括品牌、备注、其他手填内容、批注和超链接。列范围按完整表头（包括合并表头）界定；主表右侧“第二联：财务报销”等模板内容保留原位置和样式。保留表头、格式、签字和说明页脚，按当前明细数量调整数据区并重新计算单价及合计。PDF 目录中没有的旧明细将移除；主表明细中的人工修改不会保留。旧版已删除的模板文字不会自动补回，请补回文字或使用完整模板。

处理与恢复
只读预览不会重命名 PDF，也不会保存或清空工作簿。预览通过后才可执行：软件会改名、清空旧明细并重填两表、设置字体、调用 Excel 重算，并逐票复核金额。出现重名、字段不确定、金额不一致或模板结构异常时停止。解决异常后重新预览。

如果 Excel 操作或金额验证失败，解决原因后重新选择同一批次和工作簿进行只读预览，可继续未完成的处理。重启软件后仍可恢复；恢复期间请保持发票内容及识别版本一致。

识别原则
识别依据与 skill 相同：从 PDF 内容读取字段，合并规定的折扣与运费，保留重复明细，空数量按 1，金额逐分核对。当前不支持扫描图片 OCR。

规则更新与分发
在“规则与更新”中选择可信的 summarize-invoice-pdfs 文件夹，点击“同步本机 skill”。同步成功后，新规则保存在软件文件夹里的 recognition 目录。关闭软件，把整个软件文件夹打包发给别人，对方完整解压后直接运行即可使用随包规则。请一并保留 _internal 和 recognition 两个文件夹。

同步规则需要软件文件夹可写。你的本机 skill 路径绑定仅保存在本机；接收方无需绑定 skill 或导入规则包。仍可单独导出、导入离线更新包。处理时固定使用界面显示的识别版本。

只修改 SKILL.md 文字不会自动改进算法：需要同时更新对应脚本和测试。共享字段、模板约定或依赖变化可能要求升级软件。人工校正和清空重填由软件维护。更新前请由 skill 维护者运行其测试。

模板最低保留行采用与 skill 共用的 template_rules.json。同步后，按“第二联：财务报销”最后一个字实际所在行保留必要空白明细行，合计在其下方；预览报告显示实际行号。右侧模板需使用固定值，公式会报告坐标并停止。受支持的标识和排列声明可直接同步，未知策略或写表器变化需要升级软件。
""" + "\n" + BOUNDARY_GUIDE


class App:
    def __init__(self, root, state_dir=None, application_dir=None):
        self.root = root
        self.application_dir = Path(application_dir or application_root()).resolve()
        identity = hashlib.sha256(str(self.application_dir).casefold().encode("utf-8")).hexdigest()[:16]
        self.state_dir = Path(state_dir or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "InvoiceSummary/instances" / identity)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.store = EngineStore(self.application_dir / "recognition", resource_root() / "engine")
        except PermissionError as exc:
            raise ValueError(f"软件文件夹不可写，请完整解压到可写的文件夹后运行：{self.application_dir}") from exc
        self.events = queue.Queue()
        self.busy = False
        self.operation_stage = None
        self.preview_result = None
        self.controller = None
        self.last_result = None
        self.interactive = []
        self.pdf = tk.StringVar()
        self.book = tk.StringVar()
        self.status = tk.StringVar(value="选择文件，然后进行只读预览")
        self.summary = tk.StringVar(value="文件在本机处理 · Microsoft Excel 桌面版必需")
        self.stage_title = tk.StringVar(value="等待只读预览")
        self.stage_detail = tk.StringVar(value="选择完整批次的 PDF 文件夹和目标工作簿，然后点击“只读预览”。")
        self.version = tk.StringVar()
        self.source_status = tk.StringVar()
        settings = self.state_dir / "settings.json"
        try:
            saved = json.loads(settings.read_text(encoding="utf-8"))
            if not isinstance(saved, dict):
                raise ValueError("设置格式无效")
            source = saved.get("skill_source", "") if saved.get("recognition_version") == self.store.version() else ""
            if not isinstance(source, str):
                source = ""
        except (OSError, ValueError):
            source = ""
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
        self.root.geometry("1140x900")
        self.root.minsize(900, 760)
        self.root.configure(bg="#f4f7fb")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("TFrame", background="#f4f7fb")
        style.configure("TLabel", background="#f4f7fb", foreground="#18304e")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 22, "bold"))
        for name, background, foreground in (("Steps", "#eaf3ff", "#173b68"), ("Conditions", "#fff4dc", "#674515")):
            style.configure(f"{name}.TFrame", background=background)
            style.configure(f"{name}Title.TLabel", background=background, foreground=foreground, font=("Microsoft YaHei UI", 14, "bold"))
            style.configure(f"{name}Body.TLabel", background=background, foreground="#243d55")
        style.configure("Notice.TLabel", foreground="#874026", font=("Microsoft YaHei UI", 10, "bold"))
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
        process.rowconfigure(6, weight=1)
        guidance = ttk.Frame(process)
        guidance.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        guidance.columnconfigure((0, 1), weight=1, uniform="guidance")
        self._guide_card(guidance, 0, "执行步骤", EXECUTION_STEPS, "Steps", (0, 6))
        self._guide_card(guidance, 1, "必要条件", NECESSARY_CONDITIONS, "Conditions", (6, 0))
        notice = ttk.Label(guidance, text=PROCESS_NOTICE, style="Notice.TLabel", wraplength=780)
        notice.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        guidance.bind("<Configure>", lambda event: notice.configure(wraplength=max(180, event.width)))
        for row, label, variable, action in ((1, "PDF 文件夹", self.pdf, self._pick_pdf), (2, "目标工作簿", self.book, self._pick_book)):
            ttk.Label(process, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
            entry = ttk.Entry(process, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            self.interactive.append(entry)
            self._button(process, "选择", action).grid(row=row, column=2, padx=(10, 0))
        buttons = ttk.Frame(process)
        buttons.grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 8))
        self._button(buttons, "只读预览", self._preview).pack(side="left", padx=(0, 8))
        self.execute = self._button(buttons, "执行处理", self._apply)
        self.execute.pack(side="left", padx=(0, 8))
        self.execute.configure(state="disabled")
        self.correct_button = self._button(buttons, "人工校正", self._edit_detail)
        self.correct_button.pack(side="left", padx=(0, 8))
        self.correct_button.configure(state="disabled")
        self._button(buttons, "打开发票目录", lambda: self._open(self.pdf.get())).pack(side="left", padx=(0, 8))
        self._button(buttons, "打开工作簿", lambda: self._open(self.book.get())).pack(side="left")
        self.stage_card = tk.Frame(process, padx=12, pady=6, highlightthickness=1)
        self.stage_card.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(4, 4))
        self.stage_heading = tk.Label(self.stage_card, textvariable=self.stage_title, font=("Microsoft YaHei UI", 14, "bold"), anchor="w", justify="left")
        self.stage_heading.pack(fill="x")
        self.stage_body = tk.Label(self.stage_card, textvariable=self.stage_detail, font=("Microsoft YaHei UI", 10), anchor="w", justify="left", wraplength=900)
        self.stage_body.pack(fill="x", pady=(2, 0))
        self.stage_summary = tk.Label(self.stage_card, textvariable=self.summary, font=("Microsoft YaHei UI", 9), anchor="w", justify="left", wraplength=900)
        self.stage_summary.pack(fill="x", pady=(2, 0))
        def wrap_stage(event):
            for label in (self.stage_heading, self.stage_body, self.stage_summary):
                label.configure(wraplength=max(180, event.width - 26))
        self.stage_card.bind("<Configure>", wrap_stage)
        self._set_stage("idle", self.stage_title.get(), self.stage_detail.get())
        ttk.Label(process, text="完整批次明细 · 双击一行可人工校正 · 校正后重新检查").grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 4))
        table = ttk.Frame(process)
        table.grid(row=6, column=0, columnspan=3, sticky="nsew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        columns = ("sequence", "filename", "product_name", "spec", "unit", "quantity", "price", "amount", "manufacturer", "correction")
        self.tree = ttk.Treeview(table, columns=columns, show="headings")
        for name, label, width in zip(columns, ("序号", "PDF → 新文件名", "产品名称", "规格型号", "单位", "数量", "单价（自动）", "含税金额", "生产厂家", "人工校正"), (55, 290, 160, 125, 60, 70, 105, 105, 180, 85)):
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, minwidth=40, anchor="w" if name in ("filename", "product_name", "spec", "manufacturer") else "center", stretch=name == "filename")
        self.tree.tag_configure("corrected", background="#fff4dc")
        self.tree.bind("<Double-1>", self._edit_detail)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        scroll = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        scroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=scroll.set)
        ttk.Label(process, text="检查、异常与实际结果").grid(row=7, column=0, columnspan=3, sticky="w", pady=(10, 4))
        self.report = self._text(process, height=5)
        self.report.grid(row=8, column=0, columnspan=3, sticky="ew")
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(12, 5))
        self.progress_bar = ttk.Progressbar(outer, mode="indeterminate")
        self.progress_bar.pack(fill="x")
        ttk.Label(rules, textvariable=self.version, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(0, 10))
        ttk.Label(rules, text="同步仅更新共享规则；人工校正、清空重填等软件功能继续保留。同步成功后关闭软件，打包整个软件文件夹即可分发。", wraplength=950).pack(anchor="w")
        ttk.Label(rules, text=f"软件文件夹：{self.application_dir}", wraplength=950).pack(anchor="w", pady=(6, 0))
        source_row = ttk.Frame(rules)
        source_row.pack(fill="x", pady=10)
        entry = ttk.Entry(source_row, textvariable=self.source)
        entry.pack(side="left", fill="x", expand=True)
        self.interactive.append(entry)
        self._button(source_row, "选择 skill", self._pick_source).pack(side="left", padx=(8, 0))
        source_buttons = ttk.Frame(rules)
        source_buttons.pack(anchor="w", pady=5)
        for label, action in (("同步本机 skill", self._sync), ("打开软件文件夹", lambda: self._open(self.application_dir)), ("导出离线更新包", self._export), ("导入更新包", self._import), ("回退版本", self._rollback), ("解除绑定", self._unbind)):
            self._button(source_buttons, label, action).pack(side="left", padx=(0, 6))
        ttk.Label(rules, textvariable=self.source_status, wraplength=950).pack(anchor="w", pady=10)
        self.rule_tabs = ttk.Notebook(rules)
        self.rule_tabs.pack(fill="both", expand=True)
        boundary_tab = ttk.Frame(self.rule_tabs, padding=8)
        self.update_tab = ttk.Frame(self.rule_tabs, padding=8)
        reference_tab = ttk.Frame(self.rule_tabs, padding=8)
        self.rule_tabs.add(boundary_tab, text="功能归属")
        self.rule_tabs.add(self.update_tab, text="本次更新结果")
        self.rule_tabs.add(reference_tab, text="skill 原始说明")
        self.boundary_text = self._text(boundary_tab)
        self.boundary_text.pack(fill="both", expand=True)
        self._set_text(self.boundary_text, BOUNDARY_GUIDE)
        self._mark_headings(self.boundary_text, BOUNDARY_GUIDE)
        self.update_text = self._text(self.update_tab)
        self.update_text.pack(fill="both", expand=True)
        self._set_text(self.update_text, "同步、导入或回退共享规则后，这里会显示更新范围和保留的软件功能。\n\n" + "保留的软件功能：" + RETAINED_FEATURES)
        ttk.Label(reference_tab, text="此页保留 skill 原文作为共享规则来源参考。软件交互、人工校正及整批重填以“功能归属”页为准。", wraplength=950).pack(anchor="w", pady=(0, 6))
        self.rule_text = self._text(reference_tab)
        self.rule_text.pack(fill="both", expand=True)
        text_widget = self._text(help_tab)
        text_widget.pack(fill="both", expand=True)
        self._set_text(text_widget, HELP)
        self._mark_headings(text_widget, HELP)

    def _mark_headings(self, widget, content):
        widget.tag_configure("section", font=("Microsoft YaHei UI", 16, "bold"), foreground="#173b68", spacing1=12, spacing3=8)
        for line_number, line in enumerate(content.splitlines(), 1):
            if line in HELP_HEADINGS:
                widget.tag_add("section", f"{line_number}.0", f"{line_number}.end")

    def _guide_card(self, parent, column, title, items, style_name, padding):
        card = ttk.Frame(parent, padding=(14, 10), style=f"{style_name}.TFrame")
        card.grid(row=0, column=column, sticky="nsew", padx=padding)
        ttk.Label(card, text=title, style=f"{style_name}Title.TLabel").pack(anchor="w", pady=(0, 6))
        labels = []
        for item in items:
            label = ttk.Label(card, text=item, style=f"{style_name}Body.TLabel", wraplength=400, justify="left")
            label.pack(anchor="w", fill="x", pady=2)
            labels.append(label)
        def update_wrap(event):
            for label in labels:
                label.configure(wraplength=max(180, event.width - 28))
        card.bind("<Configure>", update_wrap)

    def _text(self, parent, height=15):
        return tk.Text(parent, height=height, wrap="word", bg="white", fg="#243d55", relief="flat", padx=10, pady=8, font=("Microsoft YaHei UI", 10), state="disabled")

    def _set_text(self, widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _set_stage(self, tone, title, detail):
        background, foreground, border = {
            "idle": ("#edf1f5", "#435367", "#c4ccd6"),
            "working": ("#eaf3ff", "#173b68", "#76a6db"),
            "success": ("#e8f5eb", "#205d32", "#6aab7a"),
            "warning": ("#fff4dc", "#79520e", "#c79939"),
            "error": ("#fdecea", "#962c25", "#ce776e"),
        }[tone]
        self.stage_title.set(title)
        self.stage_detail.set(detail)
        self.stage_card.configure(bg=background, highlightbackground=border, highlightcolor=border)
        for label in (self.stage_heading, self.stage_body, self.stage_summary):
            label.configure(bg=background, fg=foreground)

    def _complete_stage(self, tone, title, detail, *, notify=False, reason=None):
        self._set_stage(tone, title, detail)
        self.status.set(title)
        if notify:
            show = messagebox.showerror if tone == "error" else messagebox.showwarning if tone == "warning" else messagebox.showinfo
            message = detail + ("\n\n" + reason if reason else "")
            show(title, message, parent=self.root)

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
        self.correct_button.configure(state="disabled")
        self._set_stage("idle", "需要重新预览", "输入或规则已变更；请点击“只读预览”，完成检查后再执行。")
        self.status.set("需要重新预览")
        self.summary.set("完成新的只读预览后，将显示发票数量、明细数量和金额。")

    def _source_changed(self, *_):
        self._invalidate()
        self._save_settings()
        self._check_source()

    def _save_settings(self):
        (self.state_dir / "settings.json").write_text(json.dumps({"skill_source": self.source.get(), "recognition_version": self.store.version()}, ensure_ascii=False), encoding="utf-8")

    def _check_source(self):
        source = self.source.get().strip()
        if not source:
            self.source_status.set("使用随软件携带的共享规则；人工校正、清空重填等功能由软件版本维护。")
            return None
        try:
            status = self.store.source_status(source)
            if status["error"]:
                self.source_status.set(status["error"])
                return status["error"]
            if status["changed"]:
                value = "发现共享规则更新，请先同步：" + "、".join(describe_changes(status["changed"]))
                self.source_status.set(value)
                return value
            self.source_status.set("共享规则已与本机 skill 同步 · 来源：" + source)
            return None
        except Exception as exc:
            value = "绑定来源不可用：" + str(exc)
            self.source_status.set(value)
            return value

    def _periodic_source(self):
        if not self.busy:
            error = self._check_source()
            if error:
                self._invalidate()
                self._complete_stage("warning", "识别规则需要同步", "请到“规则与更新”同步规则，然后重新进行只读预览。")
        self.root.after(3000, self._periodic_source)

    def _refresh_version(self):
        self.version.set(f"软件 {__version__}  ·  共享规则版本 {self.store.version()}")
        self._set_text(self.rule_text, (self.store.active() / "SKILL.md").read_text(encoding="utf-8"))
        self._check_source()

    def _run(self, work, done, *, stage=None):
        if self.busy:
            return
        self.busy = True
        self.operation_stage = stage
        if stage:
            title = {"preview": "正在只读预览…", "correction": "正在检查人工校正…", "execute": "正在执行处理…"}[stage]
            self._set_stage("working", title, "请等待本阶段结束；完成后会显示结果与下一步。")
            self.status.set(title)
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
                    if self.operation_stage:
                        self.stage_detail.set(event[1])
                    continue
                stage = self.operation_stage
                self.operation_stage = None
                self.busy = False
                self.progress_bar.stop()
                for widget in self.interactive:
                    widget.configure(state="normal")
                self.execute.configure(state="disabled")
                self.correct_button.configure(state="normal" if self.preview_result and not self.preview_result.resume_pending else "disabled")
                if event[0] == "done":
                    event[1](event[2])
                else:
                    self._invalidate()
                    self.status.set("未完成，请查看原因")
                    self._set_text(self.report, event[1])
                    if stage:
                        title = {"preview": "只读预览未完成", "correction": "校正检查未完成", "execute": "执行处理未完成"}[stage]
                        self._complete_stage("error", title, "请查看下方原因，解决问题后重新进行只读预览。", notify=True, reason=event[1])
                    else:
                        messagebox.showerror("操作未完成", event[1], parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _preview(self):
        error = self._check_source()
        if error:
            self._invalidate()
            self._complete_stage("warning", "识别规则需要同步", "请到“规则与更新”同步规则，然后重新进行只读预览。")
            messagebox.showinfo("规则需要同步", error)
            return
        self._invalidate()
        directory, book = self.pdf.get(), self.book.get()
        self.controller = Controller(self.store.active(), lambda msg: self.events.put(("progress", msg)), state_dir=self.state_dir / "runs")
        self._run(lambda: self.controller.preview(directory, book), lambda preview: self._render_preview(preview, notify=True), stage="preview")

    def _render_preview(self, preview, *, notify=False):
        self.preview_result = preview
        self._render_table(preview.payload, corrections=preview.corrections)
        self.correct_button.configure(state="normal" if preview.payload.get("records") and not preview.resume_pending else "disabled")
        invoices = len(preview.payload.get("records", []))
        rows = sum(len(r.get("rows", [])) for r in preview.payload.get("records", []))
        self.summary.set(f"{invoices} 张发票 · 整批重填 {rows} 条明细 · 本批合计 ¥{preview.total} · 人工校正 {len(preview.corrections)} 条")
        parts = [f"目标工作簿：{preview.workbook}（原位更新，不自动创建备份）", f"识别版本：{preview.engine_version}", "填表方式：清空两表主表旧明细（含品牌、备注），按本次完整批次重填，保留右侧模板内容。"]
        for name, details in preview.sheet_details.items():
            parts.append(f"{name}：模板检查通过；将清空主表旧明细 {details['oldRowsToClear']} 行（含品牌、备注），重填 {details['rowsToFill']} 条；缩减明细区 {details['blankRowsToRemove']} 行；保留右侧模板内容 {details['fixedTextCellsToPreserve']} 个单元格。")
            if details["minimumRetainedRow"] is not None:
                parts.append(f"  共享模板规则：最低保留到第 {details['minimumRetainedRow']} 行，保留必要空白明细 {details['requiredBlankRows']} 行，合计放在第 {details['footerRow']} 行。")
            elif "template_rules.json" not in read_manifest(preview.engine_dir)["files"]:
                parts.append("  当前使用旧规则，尚无模板最低保留行；请同步更新后的本机 skill。")
            else:
                parts.append(f"  未检测到规则中的完整侧边标识，按实际明细收缩；合计放在第 {details['footerRow']} 行。")
        parts.extend(self._correction_lines(preview.original_payload, preview.corrections))
        parts.append("异常：\n" + "\n".join(preview.issues) if preview.issues else "异常：无；只读预览通过，尚未改动文件。")
        if preview.resume_pending:
            parts.append("检测到上次处理未完成；本次将继续字体、重算和金额验证。已重填且与预期完全对应的两表可跳过重复写入，否则按本次完整批次重填。")
            if preview.corrections:
                parts.append("已恢复上次人工校正；请先完成该次运行，恢复期间不能修改校正。")
        if preview.clean and not preview.has_changes:
            parts.append("没有可重填明细，无需处理。")
        self._set_text(self.report, "\n".join(parts))
        if preview.clean and preview.has_changes:
            self.execute.configure(state="normal")
        phase = "只读预览" if notify else "校正检查"
        if not preview.clean:
            self._complete_stage("warning", f"{phase}完成，发现 {len(preview.issues)} 项异常", "暂不能执行。请查看下方异常，校正字段或解决问题后重新检查。", notify=notify, reason=preview.issues[0])
        elif preview.has_changes:
            next_step = "检测到上次处理未完成，点击“执行处理”继续。" if preview.resume_pending else "文件尚未改动；核对明细后点击“执行处理”。"
            self._complete_stage("success", f"{phase}完成，预览通过", next_step, notify=notify, reason=self.summary.get())
        else:
            self._complete_stage("success", f"{phase}完成，无需处理", "没有可重填明细；可选择其他批次重新预览。", notify=notify)

    def _render_table(self, payload, renamed=None, corrections=None):
        self.tree.delete(*self.tree.get_children())
        plans = {p["source"]: p for p in (renamed or payload.get("rename_plan", []))}
        for record_index, record in enumerate(payload.get("records", [])):
            source = record["pdf"]
            destination = plans.get(source, {}).get("destination", source)
            mapping = Path(source).name if source == destination else f"{Path(source).name} → {Path(destination).name}"
            for row_index, row in enumerate(record.get("rows", [])):
                key = f"{record_index}:{row_index}"
                corrected = bool((corrections or {}).get(key))
                price = self._unit_price(row)
                self.tree.insert("", "end", iid=key, tags=("corrected",) if corrected else (), values=(record["sequence"], mapping, row.get("product_name") or "—", row.get("spec") or "—", row.get("unit") or "—", field_value(row, "quantity"), price, "¥" + str(row.get("amount", "—")), row.get("manufacturer") or "—", "已校正" if corrected else ""))

    def _unit_price(self, row):
        try:
            values = normalize({field: field_value(row, field) for field in ("quantity", "amount")})
            return format(Decimal(values["amount"]) / Decimal(values["quantity"]), ".6f")
        except (ValueError, InvalidOperation, ZeroDivisionError):
            return "—"

    def _correction_lines(self, original, changes):
        lines = []
        for key, fields in sorted(changes.items()):
            record_index, row_index = map(int, key.split(":"))
            record = original["records"][record_index]
            row = record["rows"][row_index]
            detail = "；".join(f"{LABELS[field]}：{field_value(row, field) or '空'} → {value or '空'}" for field, value in fields.items())
            lines.append(f"人工校正 · 序号 {record['sequence']} 第 {row_index + 1} 条：{detail}")
        return lines

    def _edit_detail(self, event=None):
        if self.busy:
            return
        preview = self.preview_result
        if preview is None:
            messagebox.showinfo("先进行预览", "请先进行只读预览，再选择一条明细进行人工校正。")
            return
        if preview.resume_pending:
            messagebox.showinfo("先完成上次处理", "恢复期间固定使用上次保存的校正，请先完成该次运行。")
            return
        if event is not None:
            if self.tree.identify_region(event.x, event.y) != "cell":
                return
            selected = self.tree.identify_row(event.y)
            if selected:
                self.tree.selection_set(selected)
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("选择明细", "请先选中一条需要校正的明细。")
            return
        record_index, row_index = map(int, selected[0].split(":"))
        record = preview.payload["records"][record_index]
        original = preview.original_payload["records"][record_index]["rows"][row_index]
        row = record["rows"][row_index]
        dialog = tk.Toplevel(self.root)
        dialog.title(f"人工校正 · 序号 {record['sequence']} 第 {row_index + 1} 条")
        dialog.transient(self.root)
        dialog.geometry("860x540")
        dialog.minsize(720, 500)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(2, weight=1)
        ttk.Label(frame, text=Path(record["pdf"]).name, font=("Microsoft YaHei UI", 12, "bold"), wraplength=790).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(frame, text="对照原 PDF 校正已有字段。保存仅更新预览，通过检查后再执行。", wraplength=790).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))
        for column, heading in enumerate(("字段", "原始识别值", "当前值（可修改）")):
            ttk.Label(frame, text=heading, font=("Microsoft YaHei UI", 10, "bold")).grid(row=2, column=column, sticky="w", padx=(0, 12), pady=(0, 6))
        variables = {}
        for position, field in enumerate(FIELDS, 3):
            ttk.Label(frame, text=LABELS[field]).grid(row=position, column=0, sticky="w", padx=(0, 12), pady=7)
            ttk.Label(frame, text=field_value(original, field) or "—", wraplength=270, justify="left").grid(row=position, column=1, sticky="w", padx=(0, 16), pady=7)
            variable = tk.StringVar(value=field_value(row, field))
            variables[field] = variable
            ttk.Entry(frame, textvariable=variable).grid(row=position, column=2, sticky="ew", pady=7)
        price = tk.StringVar()
        def refresh_price(*_):
            price.set("单价（自动计算）：" + self._unit_price({field: variable.get() for field, variable in variables.items()}))
        for field in ("quantity", "amount"):
            variables[field].trace_add("write", refresh_price)
        refresh_price()
        ttk.Label(frame, textvariable=price).grid(row=9, column=0, columnspan=3, sticky="w", pady=(8, 6))
        ttk.Label(frame, text="明细条数和票面总额固定；漏项、多项或整票解析失败请改进 skill。", wraplength=790).grid(row=10, column=0, columnspan=3, sticky="w", pady=(0, 12))
        def save(restore=False):
            if self.preview_result is not preview or self.busy:
                messagebox.showinfo("预览已失效", "请重新预览后再校正。", parent=dialog)
                return
            values = None
            if not restore:
                try:
                    values = normalize({field: variable.get() for field, variable in variables.items()})
                except ValueError as exc:
                    messagebox.showinfo("字段需要修正", str(exc), parent=dialog)
                    return
            controller = self.controller
            dialog.destroy()
            self._run(lambda: controller.correct(preview, record_index, row_index, values), self._render_preview, stage="correction")
        actions = ttk.Frame(frame)
        actions.grid(row=11, column=0, columnspan=3, sticky="w")
        for label, action in (("保存并检查", save), ("恢复识别值", lambda: save(True)), ("打开原发票", lambda: self._open(record["pdf"])), ("取消", dialog.destroy)):
            ttk.Button(actions, text=label, command=action).pack(side="left", padx=(0, 8))

    def _apply(self):
        preview = self.preview_result
        if preview is None:
            return
        error = self._check_source()
        if error:
            self._invalidate()
            self._complete_stage("warning", "识别规则需要同步", "请到“规则与更新”同步规则，然后重新进行只读预览。")
            messagebox.showinfo("规则需要同步", error)
            return
        self._run(lambda: self.controller.apply(preview), self._render_result, stage="execute")

    def _render_result(self, result):
        self.last_result = result
        self.preview_result = None
        self.correct_button.configure(state="disabled")
        self._render_table(result["payload"], result.get("rename_plan"), result.get("corrections"))
        outcome = "处理完成，逐分金额验证通过。" if result["status"] == "completed" else "无需处理，未改动文件。" if result["status"] == "no_change" else "处理未完成。"
        parts = [outcome, "已执行：" + "、".join(result.get("completed", []))]
        parts.extend(self._correction_lines(result.get("original_payload", {}), result.get("corrections", {})))
        if result.get("error"):
            parts.append(result["error"])
        if result.get("rename_plan"):
            actual = result["rename_plan"]
            parts.append(f"实际改名：{sum(p['status']=='renamed' for p in actual)} 个；未完成：{sum(p['status']=='not_completed' for p in actual)} 个")
        totals = result.get("totals", {})
        if result.get("rows_filled"):
            parts.append(f"实际清空两表旧明细（含品牌、备注），每表重填 {result['rows_filled']} 条。")
        if result.get("detail_rows_removed"):
            parts.append("实际缩减明细区：" + "；".join(f"{name} {count} 行" for name, count in result["detail_rows_removed"].items()))
        if totals:
            parts.append(f"PDF 合计 ¥{result['total']} · 验收合计 ¥{totals.get('acceptance_footer_total')} · 领用合计 ¥{totals.get('issue_footer_total')}")
        if result.get("verification", {}).get("exceptions"):
            parts.append("异常：" + json.dumps(result["verification"]["exceptions"], ensure_ascii=False))
        parts.append("临时文件清理：" + result["cleanup"])
        parts.append("继续处理前请重新进行只读预览。")
        self._set_text(self.report, "\n".join(parts))
        if result["status"] == "completed":
            if result["cleanup"] == "完成":
                detail = f"金额核对通过（本批合计 ¥{result['total']}），临时文件已清理。可点击“打开工作簿”查看结果。"
                self._complete_stage("success", "执行处理完成", detail, notify=True)
            else:
                self._complete_stage("warning", "处理完成，临时文件清理未完成", "填表和金额核对已完成；请查看下方清理原因。继续处理前请重新预览。", notify=True, reason=result["cleanup"])
        elif result["status"] == "no_change":
            self._complete_stage("success", "执行阶段结束，无需处理", "未改动文件；继续处理前请重新进行只读预览。", notify=True)
        else:
            reason = result.get("error") or "请查看下方“检查、异常与实际结果”中的具体原因。"
            self._complete_stage("error", "执行处理未完成", "部分步骤可能已完成；解决原因后重新预览，可继续未完成的处理。", notify=True, reason=reason)

    def _sync(self):
        source = self.source.get().strip()
        if not source:
            messagebox.showinfo("选择来源", "请先选择本机 skill 文件夹")
            return
        def work():
            try:
                return self.store.sync(source)
            except PermissionError as exc:
                raise ValueError(f"同步未完成，软件文件夹不可写：{self.application_dir}。请将整个软件文件夹放到可写位置后重新同步。") from exc
        self._run(work, lambda result: self._updated(result, action="同步"))

    def _updated(self, result, *, action):
        if self.source.get():
            try:
                source_status = self.store.source_status(self.source.get())
                if source_status["changed"] or source_status["error"]:
                    self.source.set("")
            except (OSError, ValueError):
                self.source.set("")
        self._save_settings()
        self._invalidate()
        self._refresh_version()
        self.status.set(f"共享规则{action}完成：" + result["version"])
        changed = describe_changes(result["changed"])
        scope = "\n".join("· " + item for item in changed) if changed else "共享规则已是当前版本，无需更换。"
        compatibility = "更新范围声明及写表组件版本检查通过。"
        if action != "回退":
            compatibility += "共享脚本的既定接口检查通过。"
        compatibility += "实际发票仍须只读预览和逐分复核。"
        report = (f"共享规则{action}完成\n\n"
                  f"共享规则版本：{result['previous_version']} → {result['version']}\n"
                  "本次涉及的共享范围：\n" + scope + "\n\n"
                  f"保留的软件功能：{RETAINED_FEATURES}\n"
                  f"这些功能由软件 {__version__} 维护，skill 更新包不能替换。\n\n"
                  "兼容性：" + compatibility + "\n"
                  f"规则所在的软件文件夹：{self.application_dir}\n"
                  "继续处理前请重新预览。关闭软件后，可将整个文件夹打包分发。")
        self._set_text(self.update_text, report)
        self.rule_tabs.select(self.update_tab)
        messagebox.showinfo(f"共享规则{action}完成", "本次涉及：\n" + scope + f"\n\n保留的软件功能：{RETAINED_FEATURES}\n\n关闭软件后，可把整个软件文件夹打包分发。", parent=self.root)

    def _export(self):
        source = self.source.get().strip()
        if not source:
            messagebox.showinfo("选择来源", "请先绑定已完成脚本适配和测试的本机 skill")
            return
        output = filedialog.asksaveasfilename(title="导出离线 skill 更新包", defaultextension=".zip", initialfile="invoice-skill-update.zip", filetypes=[("更新包", "*.zip")])
        if output:
            self._run(lambda: export_update(source, output, read_manifest(self.store.active())), lambda result: messagebox.showinfo("导出完成", "共享规则更新包已保存：" + output + f"\n\n该包声明共享规则范围；软件功能（{RETAINED_FEATURES}）随软件版本维护。", parent=self.root))

    def _import(self):
        path = filedialog.askopenfilename(title="选择可信的离线 skill 更新包", filetypes=[("更新包", "*.zip")])
        if path:
            self._run(lambda: self.store.install(path), lambda result: self._updated(result, action="导入"))

    def _rollback(self):
        def done(result):
            self.source.set("")
            self._updated(result, action="回退")
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
