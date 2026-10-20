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
from .updates import EngineStore, export_update, read_manifest, SharedInterfaceIncompatible, sha256
from .corrections import FIELDS, LABELS, field_value, normalize
from .policy import BOUNDARY_GUIDE, RETAINED_FEATURES, describe_changes
from .ui import FONT, PALETTE, build_interface, set_stage_style, surface, text_widget, skipped_pdf_notice
from .ui_actions import decorate_action_button
from .pdf_export import export_workbook_pdfs, output_fingerprints
from .pdf_export_ui import choose_export_directory

EXECUTION_STEPS = (
    "1. 选择完整批次的 PDF 文件夹和目标 .xlsx 工作簿。",
    "2. 点击“只读预览”；字段有误可双击明细人工校正。",
    "3. 预览通过后点击“执行处理”，清空旧明细并整批重填。",
    "4. 查看完成提示与金额复核；需要时点击“导出 PDF”。",
)
NECESSARY_CONDITIONS = (
    "Windows 10/11，已安装 Microsoft Excel 桌面版。",
    "有文本层的电子 PDF，不支持扫描件；选择完整批次。",
    "约定格式的 .xlsx，含“验收”“领用”、表头、日期与三行页脚。",
    "执行前关闭目标工作簿；软件和输入文件所在目录须可写。",
)
SOURCE_PROBLEMS = {
    "unavailable": ("本机规则来源不可用", "到“规则与更新”重新选择正确的 skill 文件夹；或点击“解除绑定”，继续使用软件已安装的规则。"),
    "invalid_source": ("本机规则内容需要修正", "请维护者检查来源文件和规则声明；新增未支持的策略须先适配软件。也可解除绑定，继续使用已安装的规则。"),
    "incompatible": ("本机规则与软件不兼容", "请维护者检查规则实现与软件接口；新增接口或依赖须适配并发布新版软件。要继续使用已安装的规则，可先解除绑定。"),
    "needs_adaptation": ("本机规则尚未完成实现", "请维护者补齐与规则说明对应的脚本或模板声明后再同步；也可解除绑定，继续使用已安装的规则。"),
    "update_available": ("发现本机规则更新", "到“规则与更新”点击“同步本机 skill”；更新成功后重新进行只读预览。"),
    "installed_invalid": ("软件已安装的规则无法读取", "请完整解压发布包，或联系维护者恢复可用规则。解除本机来源绑定不能修复损坏的随包规则。"),
    "source_changed": ("本机规则检查尚未稳定", "请等待维护者保存完成后重新检查或同步；本次尚未激活变化的规则。"),
}
BOUNDARY_HEADINGS = ("功能归属与更新边界", "一、与 skill 保持一致：共享规则", "二、软件独有功能：随软件版本更新", "三、双方共同遵守：数据与模板约定", "软件执行流程", "原始 skill 说明的适用范围", "以后更新与分发")


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
        self._has_previewed = False
        self._correction_hint_enabled = False
        self._correction_hint_state = None
        self._preview_input_text = ("", "")
        self._restoring_inputs = False
        self._confirming_discard = False
        self.source_issue = None
        self._shown_source_issue = None
        self._source_saved_report = None
        self.controller = None
        self.last_result = None
        self._pdf_export_receipt = None
        self.last_pdf_output_dir = None
        self._last_pdf_report = None
        self._pdf_report_base = ""
        self.interactive = []
        self.input_buttons = []
        self.input_entries = []
        self._inputs_locked = False
        self._choosing_input = False
        self._input_change_approved = False
        self._input_control_state = None
        self.pdf = tk.StringVar()
        self.book = tk.StringVar()
        self.status = tk.StringVar(value="选择文件，然后进行只读预览")
        self.summary = tk.StringVar(value="文件在本机处理 · Microsoft Excel 桌面版必需")
        self.metric_invoices = tk.StringVar(value="—")
        self.metric_rows = tk.StringVar(value="—")
        self.metric_total = tk.StringVar(value="—")
        self.metric_corrections = tk.StringVar(value="—")
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

    def _button(self, parent, label, action, *, style="Secondary.TButton", register=True):
        widget = ttk.Button(parent, text=label, command=action, style=style)
        if register:
            self.interactive.append(widget)
        return widget

    def _build(self):
        icon = resource_root() / "resources/app.ico"
        if icon.exists():
            self.root.iconbitmap(str(icon))
        build_interface(self, execution_steps=EXECUTION_STEPS, necessary_conditions=NECESSARY_CONDITIONS,
                        boundary_guide=BOUNDARY_GUIDE, retained_features=RETAINED_FEATURES)

    def _mark_headings(self, widget, content):
        widget.tag_configure("section", font=(FONT, 13, "bold"), foreground=PALETTE["heading"], spacing1=14, spacing3=8)
        for line_number, line in enumerate(content.splitlines(), 1):
            if line in BOUNDARY_HEADINGS:
                widget.tag_add("section", f"{line_number}.0", f"{line_number}.end")

    def _text(self, parent, height=15):
        return text_widget(parent, height)

    def _set_text(self, widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")
        widget.yview_moveto(0)
        if widget is getattr(self, "report", None):
            widget.tag_configure("report_title", font=(FONT, 9, "bold"), foreground=PALETTE["heading"])
            widget.tag_add("report_title", "1.0", "1.end")
            self.copy_report_button.configure(state="normal" if value and not self.busy else "disabled")

    def _copy_report(self):
        value = self.report.get("1.0", "end-1c")
        if not value:
            self.status.set("暂无可复制的报告，请先进行只读预览。")
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
        except tk.TclError as exc:
            messagebox.showwarning("报告未能复制", str(exc), parent=self.root)
            return
        self.status.set("完整报告已复制，可粘贴保存或提供给维护者。")

    def _update_preview_button(self, preview=None):
        clear_corrections = bool(preview and preview.corrections and not preview.resume_pending)
        self.preview_button.configure(text="重新预览（清除校正）" if clear_corrections else "只读预览")

    def _confirm_discard_corrections(self, action):
        count = len(self.preview_result.corrections) if self.preview_result else 0
        if not count or self.preview_result.resume_pending:
            return True
        self._confirming_discard = True
        try:
            return messagebox.askyesno("确认清除本次校正", f"本次已有 {count} 条人工校正。{action}会清除这些校正。\n\n选择“是”继续；选择“否”保留当前预览和校正。", default="no", parent=self.root)
        finally:
            self._confirming_discard = False

    def _update_correction_hint(self):
        if getattr(self, "correction_hint", None) is None:
            return
        preview = self.preview_result
        active = bool(preview and self._correction_hint_enabled and not preview.resume_pending and not self.busy)
        label = ("处理中，暂不可校正" if self.busy else
                 "恢复期间暂不可校正" if preview and preview.resume_pending else
                 "双击明细，可人工校正" if active else
                 "当前预览暂不可校正" if preview else "预览后可双击校正")
        state = (label, active)
        if state == self._correction_hint_state:
            return
        self._correction_hint_state = state
        self.correction_hint.configure(text=label, bg="#fff2d6" if active else PALETTE["background"],
                                       fg="#8a5816" if active else PALETTE["muted"],
                                       highlightbackground="#e6c987" if active else PALETTE["line"],
                                       image=self.root._correction_icons[0 if active else 1])

    def _can_export_pdf(self):
        receipt = self._pdf_export_receipt
        return bool(not self.busy and receipt
                    and receipt["inputs"] == (self.pdf.get(), self.book.get()))

    def _refresh_pdf_export_receipt(self):
        """Check pinned rules on events/source ticks, not action-style refresh."""
        receipt = self._pdf_export_receipt
        if receipt is None:
            return None
        try:
            if self.store.version() == receipt["engine_version"]:
                return None
            reason = "共享规则版本已变化，请重新预览并执行处理后再导出 PDF。"
        except Exception:
            reason = "共享规则版本暂无法确认，请解决规则问题后重新预览并执行处理。"
        self._pdf_export_receipt = None
        self._inputs_locked = False
        return reason

    def _update_input_controls(self):
        state = (self.busy, self._choosing_input, self._inputs_locked)
        if state == self._input_control_state:
            return
        self._input_control_state = state
        unavailable = self.busy or self._choosing_input
        for widget in self.input_entries:
            widget.configure(state="disabled" if unavailable or self._inputs_locked else "normal")
        for widget, normal_role, locked_role in self.input_buttons:
            decorate_action_button(widget, locked_role if self._inputs_locked else normal_role)
            widget.configure(state="disabled" if unavailable else "normal", cursor="arrow" if unavailable else "hand2")

    def _update_action_styles(self):
        self._update_input_controls()
        stage = self.operation_stage if self.busy else None
        preview = self.preview_result
        preview_label = "重新预览（清除校正）" if preview and preview.corrections and not preview.resume_pending else "只读预览"
        for widget, label in (
            (self.preview_button, "正在预览…" if stage == "preview" else preview_label),
            (self.execute, "正在处理…" if stage == "execute" else "执行处理"),
            (self.pdf_export_button, "正在导出…" if stage == "export" else "导出 PDF"),
        ):
            if widget.cget("text") != label:
                widget.configure(text=label)
        export_enabled = self._can_export_pdf()
        export_state = "normal" if export_enabled else "disabled"
        if str(self.pdf_export_button.cget("state")) != export_state:
            self.pdf_export_button.configure(state=export_state)
        for widget, available in (
            (self.open_invoice_folder_button, bool(self.pdf.get().strip())),
            (self.open_workbook_button, bool(self.book.get().strip())),
            (self.open_pdf_folder_button, bool(self.last_pdf_output_dir)),
        ):
            state = "normal" if available and not self.busy else "disabled"
            if str(widget.cget("state")) != state:
                widget.configure(state=state)
        self._update_correction_hint()
        for widget in (self.preview_button, self.execute, self.pdf_export_button,
                       self.open_invoice_folder_button, self.open_workbook_button, self.open_pdf_folder_button):
            cursor = "arrow" if widget.instate(("disabled",)) else "hand2"
            if str(widget.cget("cursor")) != cursor:
                widget.configure(cursor=cursor)

    def _update_metrics(self, payload=None, total=None, corrections=None):
        if payload is None:
            for variable in (self.metric_invoices, self.metric_rows, self.metric_total, self.metric_corrections):
                variable.set("—")
            return
        records = payload.get("records", [])
        self.metric_invoices.set(str(len(records)))
        self.metric_rows.set(str(sum(len(record.get("rows", [])) for record in records)))
        self.metric_total.set("—" if total is None else f"¥{total}")
        self.metric_corrections.set(str(len(corrections or {})))

    def _set_stage(self, tone, title, detail):
        self.stage_title.set(title)
        self.stage_detail.set(detail)
        set_stage_style(self, tone)
        self._update_action_styles()

    def _complete_stage(self, tone, title, detail, *, notify=False, reason=None):
        self._set_stage(tone, title, detail)
        self.status.set(title)
        if notify:
            show = messagebox.showerror if tone == "error" else messagebox.showwarning if tone == "warning" else messagebox.showinfo
            message = detail + ("\n\n" + reason if reason else "")
            show(title, message, parent=self.root)

    def _choose_input(self, variable, choose):
        if self.busy or self._choosing_input:
            return
        self._choosing_input = True
        self._update_input_controls()
        try:
            if self.preview_result or self._pdf_export_receipt or self._inputs_locked:
                if not messagebox.askyesno("确认重新选择", "更换后将清除当前预览、人工校正和 PDF 导出资格，须重新预览并执行。\n\n此前已处理的文件会保留。是否继续选择？", default="no", parent=self.root):
                    return
            value = choose()
            current = variable.get()
            same_path = value == current
            if value and current and not same_path:
                try:
                    same_path = Path(value).resolve() == Path(current).resolve()
                except (OSError, ValueError):
                    pass
            if value and not same_path:
                self._input_change_approved = True
                try:
                    variable.set(value)
                finally:
                    self._input_change_approved = False
        finally:
            self._choosing_input = False
            self._update_input_controls()

    def _pick_pdf(self):
        self._choose_input(self.pdf, lambda: filedialog.askdirectory(title="选择完整批次的发票 PDF 文件夹", parent=self.root))

    def _pick_book(self):
        self._choose_input(self.book, lambda: filedialog.askopenfilename(title="选择要原位更新的工作簿", filetypes=[("Excel 工作簿", "*.xlsx")], parent=self.root))

    def _pick_source(self):
        value = filedialog.askdirectory(title="选择包含 SKILL.md 和 scripts 的 skill 文件夹")
        if value:
            self.source.set(value)

    def _invalidate(self, *_):
        if self._restoring_inputs:
            return
        if _ and not self._input_change_approved and self.preview_result and self.preview_result.corrections:
            inputs = (self.pdf.get(), self.book.get())
            if inputs == self._preview_input_text:
                return
            if not self._confirm_discard_corrections("更换输入路径"):
                self._restoring_inputs = True
                try:
                    self.pdf.set(self._preview_input_text[0])
                    self.book.set(self._preview_input_text[1])
                finally:
                    self._restoring_inputs = False
                return
        self.preview_result = None
        self._pdf_export_receipt = None
        self._inputs_locked = False
        self._update_preview_button()
        self._update_metrics()
        self.execute.configure(state="disabled")
        self._correction_hint_enabled = False
        title = "需要重新预览" if self._has_previewed else "等待只读预览"
        detail = "输入或规则已变更；请点击“只读预览”，完成检查后再执行。" if self._has_previewed else "选择完整批次的 PDF 文件夹和目标工作簿，然后点击“只读预览”。"
        self._set_stage("idle", title, detail)
        self.status.set(title)
        self.summary.set("完成新的只读预览后，将显示发票数量、明细数量和金额。")

    def _source_changed(self, *_):
        self._save_settings()
        problem = self._check_source()
        if problem:
            self._show_source_problem(problem)
        else:
            self._restore_source_preview()

    def _save_settings(self):
        (self.state_dir / "settings.json").write_text(json.dumps({"skill_source": self.source.get(), "recognition_version": self.store.version()}, ensure_ascii=False), encoding="utf-8")

    def _check_source(self):
        self.source_issue = None
        source = self.source.get().strip()
        try:
            if not source:
                self.store.active()
                self.source_status.set("正在使用随软件携带的规则，无需绑定本机 skill；人工校正、清空重填等功能由软件版本维护。")
                return None
            status = self.store.source_status(source)
        except Exception as exc:
            status = {"kind": "installed_invalid", "error": str(exc), "changed": [], "version": None}
        if status["kind"] == "current":
            self.source_status.set("共享规则已与本机 skill 同步 · 来源：" + source)
            return None
        title, next_step = SOURCE_PROBLEMS[status["kind"]]
        reason = status["error"] or "涉及：" + "、".join(describe_changes(status["changed"]))
        self.source_issue = dict(status, title=title, next_step=next_step, reason=reason)
        self.source_status.set(f"{title}。{next_step}\n原因：{reason}")
        return self.source_issue

    def _show_source_problem(self, problem, *, notify=False):
        self.execute.configure(state="disabled")
        self._correction_hint_enabled = False
        key = (problem["kind"], problem["reason"], problem["version"])
        if key != self._shown_source_issue or notify:
            self._complete_stage("warning", problem["title"], problem["next_step"], notify=notify, reason=problem["reason"])
        if key != self._shown_source_issue:
            if self._source_saved_report is None:
                self._source_saved_report = self.report.get("1.0", "end-1c")
            kept = "\n\n原预览和已保存校正仍保留；解决来源问题后继续。" if self.preview_result else ""
            original = "\n\n原检查报告：\n" + self._source_saved_report if self._source_saved_report else ""
            self._set_text(self.report, f"{problem['title']}\n处理办法：{problem['next_step']}\n原因：{problem['reason']}" + kept + original)
            self._shown_source_issue = key

    def _restore_source_preview(self):
        self._refresh_pdf_export_receipt()
        saved_report = self._source_saved_report
        self._source_saved_report = self._shown_source_issue = None
        if self.preview_result:
            problem = self._preview_problem(self.preview_result)
            if problem:
                if saved_report is not None:
                    self._set_text(self.report, saved_report)
                self._show_stale_preview(problem)
            else:
                self._render_preview(self.preview_result, phase="原预览")
        else:
            if self._can_export_pdf():
                self._set_stage("success", "本次处理已完成，可导出 PDF", "工作簿已通过本次金额核对，可继续导出 PDF。")
            else:
                self._invalidate()
            if saved_report is not None:
                self._set_text(self.report, saved_report)

    def _preview_problem(self, preview):
        try:
            if preview.engine_version != self.store.version():
                return "已安装规则版本发生变化"
            if Path(self.pdf.get()).resolve() != preview.pdf_dir or Path(self.book.get()).resolve() != preview.workbook:
                return "所选输入路径发生变化"
            if self.controller is None or self.controller._fingerprints(preview.pdf_dir, preview.workbook) != preview.fingerprints:
                return "发票目录或工作簿内容发生变化"
        except Exception as exc:
            return "原输入或规则无法读取：" + str(exc)
        return None

    def _show_stale_preview(self, reason, *, notify=False):
        self._inputs_locked = False
        self.execute.configure(state="disabled")
        self._correction_hint_enabled = False
        self._complete_stage("warning", "原预览已失效", "原校正保留供核对；请重新预览，确认后才会清除原校正。", notify=notify, reason=reason)
        original = self.report.get("1.0", "end-1c")
        heading = f"原预览已失效\n原因：{reason}\n下一步：原校正仅供核对，需重新预览；不能直接重试执行或保存校正。\n\n原报告：\n"
        if not original.startswith(heading):
            self._set_text(self.report, heading + original)

    def _periodic_source(self):
        if not self.busy and not self._confirming_discard and not self._choosing_input:
            export_issue = self._refresh_pdf_export_receipt()
            previous_issue = self.source_issue
            problem = self._check_source()
            if problem:
                self._show_source_problem(problem)
            else:
                if previous_issue:
                    self._restore_source_preview()
                if export_issue:
                    self._complete_stage("warning", "PDF 导出需重新处理", export_issue)
        self.root.after(3000, self._periodic_source)

    def _refresh_version(self):
        self.version.set(f"软件 {__version__}  ·  共享规则版本 {self.store.version()}")
        self._set_text(self.rule_text, (self.store.active() / "SKILL.md").read_text(encoding="utf-8"))
        self._check_source()

    def _run(self, work, done, *, stage=None):
        if self.busy or self._choosing_input:
            return
        if stage in ("preview", "correction", "execute"):
            self._pdf_export_receipt = None
        self.busy = True
        self.operation_stage = stage
        if stage:
            title = {"preview": "正在只读预览…", "correction": "正在检查人工校正…", "execute": "正在执行处理…", "export": "正在导出 PDF…"}[stage]
            self._set_stage("working", title, "请等待本阶段结束；完成后会显示结果与下一步。")
            self.status.set(title)
        self.execute.configure(state="disabled")
        for widget in self.interactive:
            widget.configure(state="disabled")
        self._update_action_styles()
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
                self._correction_hint_enabled = bool(self.preview_result and not self.preview_result.resume_pending
                                                      and any(record.get("rows") for record in self.preview_result.payload.get("records", [])))
                self.copy_report_button.configure(state="normal" if self.report.get("1.0", "end-1c") else "disabled")
                if stage == "export":
                    self.execute.configure(state=self._execute_before_export)
                    self._correction_hint_enabled = self._correction_hint_before_export
                    if event[0] == "done":
                        event[1](event[2])
                    else:
                        self._render_pdf_result({"status": "failed", "files": [], "error": event[1], "cleanup": "请查看失败原因"})
                    continue
                if event[0] == "done":
                    event[1](event[2])
                else:
                    retained = self.preview_result
                    export_issue = self._refresh_pdf_export_receipt()
                    completed_export_ready = not retained and self._can_export_pdf()
                    validity_problem = self._preview_problem(retained) if retained else None
                    current = retained and validity_problem is None
                    if current:
                        self._render_preview(retained, phase="原预览")
                    elif not retained:
                        if not completed_export_ready:
                            self._invalidate()
                    else:
                        self._inputs_locked = False
                        self.execute.configure(state="disabled")
                        self._correction_hint_enabled = False
                    note = "\n原预览和已保存校正已保留；本次失败的修改未保存。" if retained else ""
                    if completed_export_ready:
                        note += "\n此前已完成的处理结果保留，可继续导出 PDF。"
                    elif export_issue:
                        note += "\n" + export_issue
                    if validity_problem:
                        note += "\n原预览已失效：" + validity_problem + "；原校正仅供核对，须重新预览。"
                    previous_report = "\n\n原检查报告：\n" + self.report.get("1.0", "end-1c") if retained or completed_export_ready else ""
                    self.status.set("未完成，请查看原因")
                    self._set_text(self.report, "本次操作未完成\n原因：" + event[1] + note + previous_report)
                    if stage:
                        title = {"preview": "只读预览未完成", "correction": "校正检查未完成", "execute": "执行处理未完成"}[stage]
                        detail = "原预览和已保存校正已保留。请解决下方原因后重试本次操作。" if current else "原校正保留供核对，预览已失效；请解决下方原因后重新预览。" if retained else "请查看下方原因，解决问题后重新进行只读预览。"
                        self._complete_stage("error", title, detail, notify=True, reason=event[1])
                    else:
                        messagebox.showerror("操作未完成", event[1] + note, parent=self.root)
        except queue.Empty:
            pass
        self._update_action_styles()
        self.root.after(100, self._poll)

    def _preview(self):
        if self.busy or self._choosing_input:
            return
        problem = self._check_source()
        if problem:
            self._show_source_problem(problem, notify=True)
            return
        if not self._confirm_discard_corrections("重新预览"):
            return
        self._source_saved_report = self._shown_source_issue = None
        self._invalidate()
        directory, book = self.pdf.get(), self.book.get()
        self.controller = Controller(self.store.active(), lambda msg: self.events.put(("progress", msg)), state_dir=self.state_dir / "runs")
        self._run(lambda: self.controller.preview(directory, book), lambda preview: self._render_preview(preview, notify=True), stage="preview")

    def _render_preview(self, preview, *, notify=False, phase=None):
        self._has_previewed = True
        self.preview_result = preview
        self._inputs_locked = bool(preview.clean and preview.has_changes)
        self._preview_input_text = (self.pdf.get(), self.book.get())
        self._update_preview_button(preview)
        self._render_table(preview.payload, corrections=preview.corrections)
        self._correction_hint_enabled = bool(any(record.get("rows") for record in preview.payload.get("records", [])) and not preview.resume_pending)
        invoices = len(preview.payload.get("records", []))
        rows = sum(len(r.get("rows", [])) for r in preview.payload.get("records", []))
        self._update_metrics(preview.payload, preview.total, preview.corrections)
        self.summary.set(f"{invoices} 张发票 · 整批重填 {rows} 条明细 · 本批合计 ¥{preview.total} · 人工校正 {len(preview.corrections)} 条")
        skipped = preview.payload.get("skipped_files", [])
        if skipped:
            self.summary.set(self.summary.get() + f" · 已跳过 {len(skipped)} 份非发票 PDF")
        notice = skipped_pdf_notice(preview.payload)
        popup_notice = skipped_pdf_notice(preview.payload, limit=8)
        parts = ["异常：\n" + "\n".join(preview.issues), "下一步：可校正的字段请双击明细修改；结构或模板问题解决后再重新预览。"] if preview.issues else ["异常：无；只读预览通过，尚未改动文件。"]
        if notice:
            parts.append(notice)
        parts.extend([f"目标工作簿：{preview.workbook}（原位更新，不自动创建备份）", f"识别版本：{preview.engine_version}", "填表方式：清空两表主表旧明细（含品牌、备注），按本次完整批次重填，保留右侧模板内容。"])
        for name, details in preview.sheet_details.items():
            parts.append(f"{name}：模板检查通过；将清空主表旧明细 {details['oldRowsToClear']} 行（含品牌、备注），重填 {details['rowsToFill']} 条；缩减明细区 {details['blankRowsToRemove']} 行；保留右侧模板内容 {details['fixedTextCellsToPreserve']} 个单元格。")
            if details["minimumRetainedRow"] is not None:
                parts.append(f"  共享模板规则：最低保留到第 {details['minimumRetainedRow']} 行，保留必要空白明细 {details['requiredBlankRows']} 行，合计放在第 {details['footerRow']} 行。")
            elif "template_rules.json" not in read_manifest(preview.engine_dir)["files"]:
                parts.append("  当前使用旧规则，尚无模板最低保留行；请同步更新后的本机 skill。")
            else:
                parts.append(f"  未检测到规则中的完整侧边标识，按实际明细收缩；合计放在第 {details['footerRow']} 行。")
        parts.extend(self._correction_lines(preview.original_payload, preview.corrections))
        if preview.resume_pending:
            parts.append("检测到上次处理未完成；本次将继续字体、重算和金额验证。已重填且与预期完全对应的两表可跳过重复写入，否则按本次完整批次重填。")
            if preview.corrections:
                parts.append("已恢复上次人工校正；请先完成该次运行，恢复期间不能修改校正。")
        if preview.clean and not preview.has_changes:
            parts.append("没有可重填明细，无需处理。")
        self._set_text(self.report, "\n".join(parts))
        if preview.clean and preview.has_changes:
            self.execute.configure(state="normal")
        phase = phase or ("只读预览" if notify else "校正检查")
        if not preview.clean:
            self._complete_stage("warning", f"{phase}完成，发现 {len(preview.issues)} 项异常", "暂不能执行。请查看下方异常，校正字段或解决问题后重新检查。", notify=notify, reason="\n\n".join(filter(None, (preview.issues[0], popup_notice))))
        elif preview.has_changes:
            next_step = "检测到上次处理未完成，点击“执行处理”继续。" if preview.resume_pending else "双击明细可人工校正；核对后点击“执行处理”。文件尚未改动。"
            self._complete_stage("success", f"{phase}完成，预览通过", next_step, notify=notify, reason="\n\n".join(filter(None, (self.summary.get(), popup_notice))))
        else:
            self._complete_stage("success", f"{phase}完成，无需处理", "没有可重填明细；可选择其他批次重新预览。", notify=notify, reason=popup_notice)

    def _render_table(self, payload, renamed=None, corrections=None):
        self.tree.delete(*self.tree.get_children())
        plans = {p["source"]: p for p in (renamed or payload.get("rename_plan", []))}
        visible_row = 0
        for record_index, record in enumerate(payload.get("records", [])):
            source = record["pdf"]
            destination = plans.get(source, {}).get("destination", source)
            mapping = Path(source).name if source == destination else f"{Path(source).name} → {Path(destination).name}"
            for row_index, row in enumerate(record.get("rows", [])):
                key = f"{record_index}:{row_index}"
                corrected = bool((corrections or {}).get(key))
                price = self._unit_price(row)
                self.tree.insert("", "end", iid=key, tags=("corrected",) if corrected else ("odd" if visible_row % 2 else "even",), values=(record["sequence"], mapping, row.get("product_name") or "—", row.get("spec") or "—", row.get("unit") or "—", field_value(row, "quantity"), price, "¥" + str(row.get("amount", "—")), row.get("manufacturer") or "—", "已校正" if corrected else ""))
                visible_row += 1

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
        clicked = None
        if event is not None:
            if self.tree.identify_region(event.x, event.y) != "cell":
                return
            clicked = self.tree.identify_row(event.y)
            if not clicked:
                return
        problem = self._check_source()
        if problem:
            self._show_source_problem(problem, notify=True)
            return
        preview = self.preview_result
        if preview is None:
            messagebox.showinfo("先进行预览", "请先进行只读预览，再选择一条明细进行人工校正。")
            return
        stale = self._preview_problem(preview)
        if stale:
            self._show_stale_preview(stale, notify=True)
            return
        if preview.resume_pending:
            messagebox.showinfo("先完成上次处理", "恢复期间固定使用上次保存的校正，请先完成该次运行。")
            return
        if clicked:
            self.tree.selection_set(clicked)
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
        dialog.configure(bg=PALETTE["background"])
        dialog.grab_set()
        frame = surface(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(1, minsize=260)
        ttk.Label(frame, text=Path(record["pdf"]).name, style="Section.TLabel", wraplength=790).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(frame, text="对照原 PDF 校正已有字段。保存仅更新预览，通过检查后再执行。", style="Muted.TLabel", wraplength=790).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 14))
        for column, heading in enumerate(("字段", "原始识别值", "当前值（可修改）")):
            ttk.Label(frame, text=heading, style="Section.TLabel").grid(row=2, column=column, sticky="w", padx=(0, 12), pady=(0, 8))
        variables = {}
        for position, field in enumerate(FIELDS, 3):
            ttk.Label(frame, text=LABELS[field], style="Surface.TLabel").grid(row=position, column=0, sticky="w", padx=(0, 16), pady=7)
            ttk.Label(frame, text=field_value(original, field) or "—", style="Muted.TLabel", wraplength=250, justify="left").grid(row=position, column=1, sticky="w", padx=(0, 16), pady=7)
            variable = tk.StringVar(value=field_value(row, field))
            variables[field] = variable
            ttk.Entry(frame, textvariable=variable).grid(row=position, column=2, sticky="ew", pady=7)
        price = tk.StringVar()
        def refresh_price(*_):
            price.set("单价（自动计算）：" + self._unit_price({field: variable.get() for field, variable in variables.items()}))
        for field in ("quantity", "amount"):
            variables[field].trace_add("write", refresh_price)
        refresh_price()
        ttk.Label(frame, textvariable=price, style="Section.TLabel").grid(row=9, column=0, columnspan=3, sticky="w", pady=(10, 8))
        ttk.Label(frame, text="明细条数和票面总额固定；漏项、多项或整票解析失败请改进 skill。", style="Muted.TLabel", wraplength=790).grid(row=10, column=0, columnspan=3, sticky="w", pady=(0, 12))
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
        actions = ttk.Frame(frame, style="Surface.TFrame")
        actions.grid(row=11, column=0, columnspan=3, sticky="w")
        for label, action in (("保存并检查", save), ("恢复识别值", lambda: save(True)), ("打开原发票", lambda: self._open(record["pdf"])), ("取消", dialog.destroy)):
            ttk.Button(actions, text=label, command=action, style="Primary.TButton" if label == "保存并检查" else "Secondary.TButton").pack(side="left", padx=(0, 8))

    def _apply(self):
        preview = self.preview_result
        if preview is None:
            return
        problem = self._check_source()
        if problem:
            self._show_source_problem(problem, notify=True)
            return
        stale = self._preview_problem(preview)
        if stale:
            self._show_stale_preview(stale, notify=True)
            return
        inputs = (self.pdf.get(), self.book.get())
        controller = self.controller
        def work():
            result = dict(controller.apply(preview))
            if result["status"] == "completed":
                try:
                    result["_pdf_export_receipt"] = {
                        "inputs": inputs, "workbook": str(preview.workbook),
                        "sha256": sha256(preview.workbook), "engine_version": preview.engine_version,
                    }
                except OSError as exc:
                    result["_pdf_export_blocked"] = "无法读取处理完成的工作簿，PDF 导出暂不可用：" + str(exc) + "；请关闭相关文件后重新预览并执行处理。"
            return result
        self._run(work, self._render_result, stage="execute")

    def _render_result(self, result):
        self.last_result = result
        if result["status"] in ("completed", "no_change"):
            self._inputs_locked = result["status"] == "completed"
        self._pdf_export_receipt = result.get("_pdf_export_receipt") if result["status"] == "completed" else None
        export_issue = self._refresh_pdf_export_receipt()
        if export_issue:
            result["_pdf_export_blocked"] = export_issue
        export_ready = self._can_export_pdf()
        self.preview_result = None
        self._update_preview_button()
        self._correction_hint_enabled = False
        self._render_table(result["payload"], result.get("rename_plan"), result.get("corrections"))
        self._update_metrics(result["payload"], result.get("total"), result.get("corrections"))
        outcome = "处理完成，逐分金额验证通过。" if result["status"] == "completed" else "无需处理，未改动文件。" if result["status"] == "no_change" else "处理未完成。"
        parts = [outcome]
        notice = skipped_pdf_notice(result["payload"])
        popup_notice = skipped_pdf_notice(result["payload"], limit=8)
        if notice:
            parts.append(notice)
        if result.get("error"):
            parts.append("原因：" + result["error"])
        if result.get("_pdf_export_blocked"):
            parts.append(result["_pdf_export_blocked"])
        if result.get("verification", {}).get("exceptions"):
            parts.append("异常：" + json.dumps(result["verification"]["exceptions"], ensure_ascii=False))
        parts.append("下一步：解决原因后重新预览，可继续未完成流程。" if result["status"] == "failed" else
                     "下一步：可打开工作簿查看结果，或导出本次已完成表格的 PDF；重新预览后须再次执行成功才可导出。" if export_ready else
                     "下一步：打开工作簿查看结果；需完成本次预览、执行及金额核对后才可导出 PDF。")
        parts.append("已执行：" + "、".join(result.get("completed", [])))
        parts.extend(self._correction_lines(result.get("original_payload", {}), result.get("corrections", {})))
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
        parts.append("临时文件清理：" + result["cleanup"])
        parts.append("需要 PDF 可先导出；开始下一批处理前再进行只读预览。" if export_ready else "继续处理前请重新进行只读预览。")
        self._set_text(self.report, "\n".join(parts))
        if result["status"] == "completed":
            if result["cleanup"] == "完成":
                detail = f"金额核对通过（本批合计 ¥{result['total']}），临时文件已清理。" + ("可查看工作簿，或点击“导出 PDF”。" if export_ready else "可查看工作簿；PDF 导出暂不可用，原因见检查报告。")
                self._complete_stage("success" if export_ready else "warning", "执行处理完成" if export_ready else "执行处理完成，PDF 导出暂不可用", detail,
                                     notify=True, reason="\n\n".join(filter(None, (result.get("_pdf_export_blocked"), popup_notice))))
            else:
                detail = "填表和金额核对已完成；请查看下方清理原因。" + ("需要 PDF 可先导出；开始下一批处理前再重新预览。" if export_ready else "PDF 导出暂不可用，原因见检查报告。")
                self._complete_stage("warning", "处理完成，临时文件清理未完成", detail, notify=True,
                                     reason="\n\n".join(filter(None, (result["cleanup"], result.get("_pdf_export_blocked"), popup_notice))))
        elif result["status"] == "no_change":
            self._complete_stage("success", "执行阶段结束，无需处理", "未改动文件；继续处理前请重新进行只读预览。", notify=True, reason=popup_notice)
        else:
            reason = result.get("error") or "请查看下方“检查、异常与实际结果”中的具体原因。"
            self._complete_stage("error", "执行处理未完成", "部分步骤可能已完成；解决原因后重新预览，可继续未完成的处理。", notify=True, reason="\n\n".join(filter(None, (reason, popup_notice))))

    def _export_pdf(self):
        if self.busy:
            return
        export_issue = self._refresh_pdf_export_receipt()
        if not self._can_export_pdf():
            messagebox.showinfo("请先完成执行处理", export_issue or "本次只读预览、执行处理并通过金额核对后，才能导出 PDF。", parent=self.root)
            return
        receipt = self._pdf_export_receipt
        try:
            workbook = Path(receipt["workbook"])
            if workbook.suffix.lower() != ".xlsx" or not workbook.is_file():
                self._pdf_export_receipt = None
                raise ValueError("本次处理完成的工作簿已不可用，请重新预览并执行处理")
            directory = choose_export_directory(self.root, workbook)
            if not directory:
                return
            approved = output_fingerprints(directory)
        except (OSError, ValueError) as exc:
            messagebox.showwarning("暂不能导出 PDF", str(exc), parent=self.root)
            return
        existing = [str(Path(directory) / name) for name, digest in approved.items() if digest is not None]
        if existing and not messagebox.askyesno("确认替换已有 PDF", "以下文件已存在：\n\n" + "\n".join(existing) + "\n\n两份 PDF 都生成成功后才会替换。是否继续？", default="no", parent=self.root):
            return
        export_issue = self._refresh_pdf_export_receipt()
        if self._pdf_export_receipt is not receipt or not self._can_export_pdf():
            messagebox.showwarning("处理状态已变化", export_issue or "请重新预览并执行处理，完成后再导出 PDF。", parent=self.root)
            return
        current_report = self.report.get("1.0", "end-1c")
        if current_report != self._last_pdf_report:
            self._pdf_report_base = current_report
        self._execute_before_export = str(self.execute.cget("state"))
        self._correction_hint_before_export = self._correction_hint_enabled
        self._run(lambda: export_workbook_pdfs(workbook, directory, approved, expected_workbook_sha256=receipt["sha256"],
                                              progress=lambda msg: self.events.put(("progress", msg))),
                  self._render_pdf_result, stage="export")

    def _render_pdf_result(self, result):
        export_issue = self._refresh_pdf_export_receipt()
        if result.get("requires_processing"):
            self._pdf_export_receipt = None
        completed = result["status"] == "completed"
        if completed:
            self._inputs_locked = False
        parts = ["PDF 导出完成" if completed else "PDF 导出未完成", "本次导出未修改工作簿；原检查报告保留在下方。"]
        if result.get("workbook"):
            parts.append("工作簿：" + result["workbook"])
        for item in result.get("files", []):
            parts.append(f"{item['sheet']}：{item['path']}（{item['pages']} 页）")
        if result.get("error"):
            parts.append("原因：" + result["error"])
        if export_issue:
            parts.append(export_issue)
        parts.append("临时文件清理：" + result["cleanup"])
        if self._pdf_report_base:
            parts.append("此前检查报告：\n" + self._pdf_report_base)
        report = "\n\n".join(parts)
        self._set_text(self.report, report)
        self._last_pdf_report = report
        if completed:
            self.last_pdf_output_dir = result["output_dir"]
            detail = "两份 PDF 已保存；A4 横向、所有列一页宽，明细向下自动分页。可点击“打开导出目录”查看。"
            tone = "success" if result["cleanup"] == "完成" and not export_issue else "warning"
            reason = "\n".join(f"{item['path']}（{item['pages']} 页）" for item in result["files"])
            if tone == "warning":
                if result["cleanup"] != "完成":
                    reason += "\n\n临时文件清理：" + result["cleanup"]
                if export_issue:
                    reason += "\n\n" + export_issue
            title = "PDF 导出完成" if tone == "success" else "PDF 已导出，后续需重新处理" if export_issue else "PDF 已导出，临时文件待清理"
            self._complete_stage(tone, title, detail, notify=True, reason=reason)
        else:
            reason = result.get("error", "请查看检查报告")
            if result["cleanup"] != "完成":
                reason += "\n\n" + result["cleanup"]
            detail = export_issue or ("工作簿已变化，请重新预览并执行处理后再导出。" if result.get("requires_processing") else "本次处理报告已保留；解决下方原因后可重试导出。")
            self._complete_stage("error", "PDF 导出未完成", detail, notify=True, reason=reason)

    def _sync(self):
        source = self.source.get().strip()
        if not source:
            messagebox.showinfo("选择来源", "请先选择本机 skill 文件夹")
            return
        problem = self._check_source()
        if problem and problem["kind"] != "update_available":
            self._show_source_problem(problem, notify=True)
            return
        if problem and not self._confirm_discard_corrections("更新规则"):
            return
        expected_version = problem["version"] if problem else self.store.version()
        def work():
            try:
                return self.store.sync(source, expected_version=expected_version)
            except PermissionError as exc:
                raise ValueError(f"同步未完成，软件文件夹不可写：{self.application_dir}。请将整个软件文件夹放到可写位置后重新同步。") from exc
        self._run(work, lambda result: self._updated(result, action="同步"))

    def _updated(self, result, *, action):
        version_changed = result["version"] != result["previous_version"]
        if self.source.get():
            try:
                source_status = self.store.source_status(self.source.get())
                if action != "同步" and (source_status["changed"] or source_status["error"]):
                    self.source.set("")
            except (OSError, ValueError):
                self.source.set("")
        self._save_settings()
        if version_changed:
            self._invalidate()
            self._source_saved_report = self._shown_source_issue = None
        else:
            self._restore_source_preview()
        self._refresh_version()
        if self.source_issue:
            self._show_source_problem(self.source_issue)
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
                  + ("规则版本已变化，继续处理前请重新预览。" if version_changed else "规则版本未变化，当前预览和校正保留。")
                  + "关闭软件后，可将整个文件夹打包分发。")
        if self.source_issue:
            report += f"\n\n绑定来源还有待处理问题：{self.source_issue['title']}。{self.source_issue['next_step']}"
        self._set_text(self.update_text, report)
        self.rule_tabs.select(self.update_tab)
        message = "本次涉及：\n" + scope + f"\n\n保留的软件功能：{RETAINED_FEATURES}\n\n关闭软件后，可把整个软件文件夹打包分发。"
        if self.source_issue:
            message += f"\n\n绑定来源还有待处理问题：{self.source_issue['title']}。{self.source_issue['next_step']}"
        (messagebox.showwarning if self.source_issue else messagebox.showinfo)(f"共享规则{action}完成", message, parent=self.root)

    def _export(self):
        source = self.source.get().strip()
        if not source:
            messagebox.showinfo("选择来源", "请先绑定已完成脚本适配和测试的本机 skill")
            return
        output = filedialog.asksaveasfilename(title="导出离线 skill 更新包", defaultextension=".zip", initialfile="invoice-skill-update.zip", filetypes=[("更新包", "*.zip")])
        if output:
            def work():
                try:
                    result = export_update(source, output, read_manifest(self.store.active()))
                except SharedInterfaceIncompatible as exc:
                    self.store.remember_interface_failure(getattr(exc, "version", None), exc)
                    raise
                self.store.clear_interface_failure(result["version"])
                return result
            self._run(work, lambda result: messagebox.showinfo("导出完成", "共享规则更新包已保存：" + output + f"\n\n该包声明共享规则范围；软件功能（{RETAINED_FEATURES}）随软件版本维护。", parent=self.root))

    def _import(self):
        path = filedialog.askopenfilename(title="选择可信的离线 skill 更新包", filetypes=[("更新包", "*.zip")])
        if path and self._confirm_discard_corrections("导入规则更新"):
            self._run(lambda: self.store.install(path), lambda result: self._updated(result, action="导入"))

    def _rollback(self):
        if not self._confirm_discard_corrections("回退规则版本"):
            return
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
        if self._choosing_input:
            return
        if self.busy:
            messagebox.showinfo("正在运行", "当前操作结束后再关闭软件，结果会显示在窗口中。")
            return
        if not self._confirm_discard_corrections("关闭软件"):
            return
        self.root.destroy()
