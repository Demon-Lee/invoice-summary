"""Software-owned export of saved worksheets, independent of invoice rules."""
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

import pdfplumber
from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries

from .controller import ExcelAdapter
from .updates import sha256
from .layout import sheet_layout
from .pdf_layout import PDFContentFitError, layout_reports, validate_pdf_layout
from .signatures import SLOTS
from .workbook import text
from .pdf_signatures import add_signatures
from .invoice_pdf_summary import FILENAME as INVOICE_SUMMARY, snapshot_invoices, merge_invoice_pdfs, verify_sources

OUTPUTS = {"验收": "验收单.pdf", "领用": "领用单.pdf"}
_SAFE_ROW_WIDTH_FACTOR = 0.85


class ProcessedWorkbookChanged(ValueError):
    """The saved workbook no longer matches the completed processing run."""


def _reparse(path):
    return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT) if os.name == "nt" else path.is_symlink()


def _fingerprint(path):
    if not os.path.lexists(path):
        return None
    if _reparse(path) or not path.is_file():
        raise ValueError(f"输出位置不是普通文件，不能替换：{path}")
    return sha256(path)


def output_fingerprints(directory, *, include_invoice_summary=False):
    directory = Path(directory).resolve()
    if directory.exists() and not directory.is_dir():
        raise ValueError(f"导出位置不是文件夹：{directory}")
    names = (*OUTPUTS.values(), INVOICE_SUMMARY) if include_invoice_summary else tuple(OUTPUTS.values())
    return {name: _fingerprint(directory / name) for name in names}


def _sheet_plan(ws, filename, with_signatures=False, *, office_backend=None):
    plan = sheet_layout(ws)
    plan["file_name"] = filename
    footer = plan["footer_row"]
    # With ten columns, a narrow measurement probe makes many acceptance
    # manufacturer names appear to wrap even when they fit in the printed cell.
    plan["print_row_width_factor"] = _SAFE_ROW_WIDTH_FACTOR
    if ws.title == "验收":
        plan["print_row_width_factor"] = 0.90 if office_backend == "Excel" else 0.94
    sequence_column = plan["columns"]["序号"]
    plan["print_detail_rows"] = [row for row in range(plan["header_row"] + 1, plan["last_detail_row"] + 1)
                                 if text(ws.cell(row, sequence_column).value)]
    main_end = max(cell.column for cell in ws[plan["header_row"]] if cell.value is not None)
    roles = {plan["columns"][key]: value for key, value in (
        ("产品名称", (100.0, 3.0)), ("规格型号", (72.0, 2.0)), ("单位", (28.0, 0.25)))}
    if "生产厂家" in plan["columns"]:
        roles[plan["columns"]["生产厂家"]] = (112.0, 2.6)
    plan["print_columns"] = []
    for index in range(1, plan["print_end_column"] + 1):
        wrap = index <= main_end and index not in plan["numeric_columns"]
        minimum, weight = roles.get(index, (32.0, 0.5)) if wrap else (0.0, 0.0)
        plan["print_columns"].append(dict(index=index, wrap=wrap, min_width=minimum, weight=weight))
    plan["print_minimum_cells"] = [cell.coordinate for row in ws.iter_rows(min_row=footer + 1, max_row=plan["print_end_row"], max_col=plan["print_end_column"])
                                  for cell in row if cell.value is not None and cell.coordinate not in plan["caption_spans"]
                                  and not any(cell.coordinate in merged for merged in ws.merged_cells.ranges)]
    # Footer captions share columns with the detail table. Reserve their space
    # before allocating long product/specification text, even without images.
    date_label = "验收日期" if ws.title == "验收" else "领用日期"
    date_cell = next(cell for cell in ws[footer + 1] if text(cell.value).rstrip("：:") == date_label)
    if date_cell.column <= 4:
        raise ValueError(f"{ws.title} 日期标签须位于第二个签字位置右侧")
    date_value = ws.cell(footer + 1, date_cell.column + 1)
    value_span = plan["caption_spans"].get(date_value.coordinate, date_value.coordinate)
    for merged in ws.merged_cells.ranges:
        if date_value.coordinate in merged:
            value_span = str(merged)
            break
    plan["print_footer_spans"] = [
        dict(kind="signature", anchor=ws.cell(footer + 1, start).coordinate,
             start_column=start, end_column=end, blank_width=110.0)
        for start, end in ((1, 3), (4, date_cell.column - 1))
    ] + [
        dict(kind="date_label", anchor=date_cell.coordinate, start_column=date_cell.column,
             end_column=date_cell.column, blank_width=0.0),
        dict(kind="date_value", anchor=date_value.coordinate, start_column=date_value.column,
             end_column=range_boundaries(value_span)[2], blank_width=0.0),
    ]
    if with_signatures:
        row_height = ws.row_dimensions[footer + 1].height or ws.sheet_format.defaultRowHeight or 15.0
        plan["signature_slots"] = []
        for column, (key, sheet_name, label) in zip((1, 4), (slot for slot in SLOTS if slot[1] == ws.title)):
            cell = ws.cell(footer + 1, column)
            plan["signature_slots"].append({"key": key, "label": label, "row_height": float(row_height),
                                            "font_size": float(cell.font.sz or 11),
                                            "vertical_alignment": cell.alignment.vertical or "bottom"})
        plan["signature_date_label"] = date_label
    return plan


def _source_cells(ws, sheet):
    """Keep independent raw text/type/merge expectations out of native JSON."""
    merged_ends = {ws.cell(m.min_row, m.min_col).coordinate: m.max_row for m in ws.merged_cells.ranges}
    result = {}
    for address in sheet["content_cells"]:
        cell = ws[address]
        kind = "formula" if cell.data_type == "f" else "literal" if cell.data_type in ("s", "inlineStr") else "formatted"
        result[address] = {"kind": kind, "text": str(cell.value), "end_row": merged_ends.get(address, cell.row)}
    return result


def _print_plan(workbook, with_signatures=False, *, source_cells=None, office_backend=None):
    wb = load_workbook(workbook, read_only=False, data_only=False, keep_links=False)
    try:
        missing = set(OUTPUTS) - set(wb.sheetnames)
        if missing:
            raise ValueError("工作簿缺少工作表：" + "、".join(sorted(missing)))
        sheets = [_sheet_plan(wb[name], filename, with_signatures, office_backend=office_backend)
                  for name, filename in OUTPUTS.items()]
        if source_cells is not None:
            source_cells.update({sheet["name"]: _source_cells(wb[sheet["name"]], sheet) for sheet in sheets})
        return {"schema_version": 1, "sheets": sheets}
    finally:
        wb.close()


def _cleanup_owned(path, parent, prefix):
    """Only remove our own exact directory; never traverse reparse points."""
    if path is None or not path.exists():
        return
    if path.resolve() != path or path.parent != parent.resolve() or not path.name.startswith(prefix) or _reparse(path):
        raise ValueError(f"临时目录范围变化，已停止清理：{path}")
    for base, directories, files in os.walk(path, followlinks=False):
        for name in directories + files:
            if _reparse(Path(base) / name):
                raise ValueError(f"临时目录出现链接，已停止清理：{path}")
    shutil.rmtree(path)


def _validate_pdfs(stage, plan, report, source_cells):
    layouts = layout_reports(plan, report)
    files = []
    for sheet in plan["sheets"]:
        path = stage / sheet["file_name"]
        if not path.is_file() or path.stat().st_size == 0 or _reparse(path):
            raise ValueError(f"{sheet['name']} 未生成有效 PDF")
        with path.open("rb") as stream:
            if not stream.read(8).startswith(b"%PDF-"):
                raise ValueError(f"{sheet['name']} 的输出不是 PDF")
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                raise ValueError(f"{sheet['name']} 的 PDF 没有页面")
            for page in pdf.pages:
                if abs(page.width - 841.89) > 2 or abs(page.height - 595.28) > 2:
                    width_mm, height_mm = page.width * 25.4 / 72, page.height * 25.4 / 72
                    raise ValueError(f"{sheet['name']} 第 {page.page_number} 页实际尺寸为 {width_mm:.1f} × {height_mm:.1f} 毫米，"
                                     "需要 A4 横向（297 × 210 毫米），已停止保存 PDF。"
                                     "可尝试启用 Windows 的 Microsoft Print to PDF 后重新导出。")
            validate_pdf_layout(pdf, sheet, layouts[sheet["name"]], source_cells.get(sheet["name"]))
            files.append({"sheet": sheet["name"], "name": path.name, "pages": len(pdf.pages)})
    return files


def _export_tables(office, workbook, plan, stage, scratch, source_cells, progress):
    plan_file, report_file = scratch / "plan.json", scratch / "report.json"
    while True:
        plan_file.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        office.export_pdf(workbook, plan_file, stage, report_file)
        report = json.loads(report_file.read_text(encoding="utf-8-sig"))
        if report.get("status") != "completed" or report.get("sheets") != plan["sheets"]:
            raise ValueError("表格软件导出结果不完整，未替换已有 PDF")
        try:
            return _validate_pdfs(stage, plan, report, source_cells), report
        except PDFContentFitError as error:
            sheet = next((s for s in plan["sheets"] if s["name"] == error.sheet), None)
            if sheet is None or sheet.get("print_row_width_factor", _SAFE_ROW_WIDTH_FACTOR) <= _SAFE_ROW_WIDTH_FACTOR:
                raise
            # One retry on the previously verified, roomier sizing. The first
            # attempt stays private and neither attempt publishes unchecked PDFs.
            sheet["print_row_width_factor"] = _SAFE_ROW_WIDTH_FACTOR
            for filename in OUTPUTS.values():
                (stage / filename).unlink(missing_ok=True)
            report_file.unlink()
            progress(f"{error.sheet}单的紧凑排版需要更多行高，正在重新导出…")


def _publish_outputs(stage, directory, approved, installed):
    """Back up the selected outputs and reverse any incomplete publication."""
    backups = {}
    if output_fingerprints(directory, include_invoice_summary=INVOICE_SUMMARY in approved) != approved:
        raise ValueError("导出目录的同名文件已变化，请重新导出并确认覆盖")
    for name, digest in approved.items():
        if digest is not None:
            backup = stage / (name + ".previous")
            shutil.copyfile(directory / name, backup)
            if sha256(backup) != digest or _fingerprint(directory / name) != digest:
                raise ValueError(f"备份期间文件已变化，请重新导出：{name}")
            backups[name] = backup
    try:
        for name in approved:
            if _fingerprint(directory / name) != approved[name]:
                raise ValueError(f"导出文件已变化，请重新确认：{name}")
            digest = sha256(stage / name)
            os.replace(stage / name, directory / name)
            installed[name] = digest
    except Exception as exc:
        recovery = []
        for name, digest in reversed(list(installed.items())):
            try:
                target = directory / name
                if _fingerprint(target) != digest:
                    raise ValueError("输出文件又被其他程序修改，不能覆盖")
                if name in backups:
                    os.replace(backups[name], target)
                else:
                    target.unlink()
                del installed[name]
            except Exception as rollback_error:
                recovery.append(f"{name}：{rollback_error}")
        if recovery:
            # Caller keeps stage (and any backups) until the user recovers them.
            raise ValueError(f"发布未完成：{exc}\n恢复未完成：{'；'.join(recovery)}\n请保留并核对恢复目录：{stage}") from exc
        raise ValueError(f"发布未完成，已恢复原有 PDF（如有）：{exc}") from exc


def export_workbook_pdfs(workbook, directory, approved, *, progress=None, excel=None, expected_workbook_sha256=None,
                         signatures=None, invoice_sources=None):
    progress = progress or (lambda message: None)
    workbook, directory = Path(workbook).resolve(), Path(directory).resolve()
    result = {"status": "failed", "workbook": str(workbook), "output_dir": str(directory), "files": [], "cleanup": "完成"}
    scratch = stage = None
    installed = {}
    published = False
    signing_report = None
    include_invoice_summary = invoice_sources is not None
    invoice_snapshots = None
    result["invoice_summary_requested"] = include_invoice_summary
    temp_parent = Path(tempfile.gettempdir()).resolve()
    try:
        if workbook.suffix.lower() != ".xlsx" or not workbook.is_file():
            if expected_workbook_sha256 is not None:
                raise ProcessedWorkbookChanged("本次处理完成的工作簿已不可用，请重新预览并执行处理后再导出")
            raise ValueError("请选择已有的 .xlsx 工作簿")
        names = {*OUTPUTS.values(), INVOICE_SUMMARY} if include_invoice_summary else set(OUTPUTS.values())
        if not isinstance(approved, dict) or set(approved) != names:
            raise ValueError("导出文件确认信息不完整，请重新导出")
        if output_fingerprints(directory, include_invoice_summary=include_invoice_summary) != approved:
            raise ValueError("导出目录的同名文件已变化，请重新确认")
        progress("正在读取已保存的工作簿，准备 PDF 排版…")
        scratch = Path(tempfile.mkdtemp(prefix="invoice-pdf-input-", dir=temp_parent)).resolve()
        snapshot = scratch / "workbook.xlsx"
        before = sha256(workbook)
        if expected_workbook_sha256 is not None and before != expected_workbook_sha256:
            raise ProcessedWorkbookChanged("工作簿在本次执行完成后发生变化，请重新预览并执行处理后再导出")
        shutil.copyfile(workbook, snapshot)
        if sha256(snapshot) != before or sha256(workbook) != before:
            if expected_workbook_sha256 is not None:
                raise ProcessedWorkbookChanged("工作簿在读取期间发生变化，请重新预览并执行处理后再导出")
            raise ValueError("工作簿在读取期间发生变化，请保存并关闭后重新导出")
        if include_invoice_summary:
            progress("正在核对本次发票清单并读取原始 PDF…")
            invoice_snapshots = snapshot_invoices(invoice_sources, scratch, directory)
        source_cells = {}
        office = excel or ExcelAdapter()
        plan = _print_plan(snapshot, with_signatures=signatures is not None, source_cells=source_cells,
                           office_backend=getattr(office, "backend", None))
        directory.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".invoice-pdf-stage-", dir=directory)).resolve()
        progress("正在通过表格软件导出验收单和领用单，请稍候…")
        # Always prove the unsigned PDF before signature insertion can run.
        files, report = _export_tables(office, snapshot, plan, stage, scratch, source_cells, progress)
        if signatures is not None:
            progress("正在定位四处签字栏并添加已保存签名…")
            signing_report = add_signatures(stage, plan, signatures)
        progress("正在检查两份 PDF 并保存到导出目录…")
        if signatures is not None:
            files = _validate_pdfs(stage, plan, report, source_cells)
        if include_invoice_summary:
            progress("正在按明细序号生成发票汇总并核对全部页面…")
            files.append(merge_invoice_pdfs(invoice_snapshots, stage / INVOICE_SUMMARY))
        if sha256(workbook) != before:
            raise ProcessedWorkbookChanged("工作簿在导出期间发生变化，请重新预览并执行处理后再导出")
        if include_invoice_summary:
            verify_sources(invoice_sources)
        _publish_outputs(stage, directory, approved, installed)
        published = True
        result.update(status="completed", files=[dict(item, path=str(directory / item["name"])) for item in files])
        if signing_report is not None:
            result["signatures"] = signing_report
    except Exception as exc:
        result["error"] = str(exc)
        missing_source = (expected_workbook_sha256 is not None and isinstance(exc, FileNotFoundError)
                          and str(exc.filename).casefold() == str(workbook).casefold())
        if isinstance(exc, ProcessedWorkbookChanged) or missing_source:
            result["requires_processing"] = True
            if missing_source:
                result["error"] = "本次处理完成的工作簿已不存在，请重新预览并执行处理后再导出"
    finally:
        cleanup_errors = []
        if installed and not published:
            cleanup_errors.append(f"保留恢复目录：{stage}")
        elif stage is not None:
            try:
                _cleanup_owned(stage, directory, ".invoice-pdf-stage-")
            except Exception as exc:
                cleanup_errors.append(str(exc))
        try:
            _cleanup_owned(scratch, temp_parent, "invoice-pdf-input-")
        except Exception as exc:
            cleanup_errors.append(str(exc))
        if cleanup_errors:
            result["cleanup"] = "；".join(cleanup_errors)
    return result
