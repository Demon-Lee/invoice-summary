"""Software-owned export of saved worksheets, independent of invoice rules."""
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

import pdfplumber
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from .controller import ExcelAdapter
from .updates import sha256
from .workbook import HEADERS, SIGNERS, text

OUTPUTS = {"验收": "验收单.pdf", "领用": "领用单.pdf"}


def _reparse(path):
    return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT) if os.name == "nt" else path.is_symlink()


def _fingerprint(path):
    if not os.path.lexists(path):
        return None
    if _reparse(path) or not path.is_file():
        raise ValueError(f"输出位置不是普通文件，不能替换：{path}")
    return sha256(path)


def output_fingerprints(directory):
    directory = Path(directory).resolve()
    if directory.exists() and not directory.is_dir():
        raise ValueError(f"导出位置不是文件夹：{directory}")
    return {name: _fingerprint(directory / name) for name in OUTPUTS.values()}


def _sheet_plan(ws, filename):
    # Sparse access avoids scanning the potentially huge style-only UsedRange.
    cells = {(c.row, c.column): c for c in ws._cells.values() if text(c.value)}
    rows = {}
    required = HEADERS + (("生产厂家",) if ws.title == "验收" else ())
    for cell in cells.values():
        value = text(cell.value)
        key = "生产厂家" if value.startswith("生产厂家") else value
        if key in required:
            rows.setdefault(cell.row, {}).setdefault(key, []).append(cell.column)
    headers = [(row, mapping) for row, mapping in rows.items() if all(key in mapping for key in required)]
    if len(headers) != 1 or any(len(cols) != 1 for cols in headers[0][1].values()):
        raise ValueError(f"{ws.title} 需要唯一完整且无重复的表头")
    header, mapping = headers[0]
    columns = {key: cols[0] for key, cols in mapping.items()}
    footers = [r for (r, c), cell in cells.items() if c == 1 and r > header and text(cell.value).startswith("合计")]
    if len(footers) != 1:
        raise ValueError(f"{ws.title} 需要唯一的合计页脚")
    footer = footers[0]
    def value(row, column):
        cell = cells.get((row, column))
        return text(cell.value) if cell else ""
    first, second = SIGNERS[ws.title]
    if (not value(footer + 1, 1).startswith(first)
            or not value(footer + 1, 4).startswith(second)
            or not value(footer + 2, 1).startswith("说明")):
        raise ValueError(f"{ws.title} 的“合计—签字—说明”三行页脚不完整")
    if not any(header < r < footer and c == columns["序号"] and value(r, columns["产品名称"])
               for r, c in cells):
        raise ValueError(f"{ws.title} 没有已填写的明细，请先完成填表")
    last_row = max(r for r, _ in cells)
    last_col = max(c for _, c in cells)
    for merge in ws.merged_cells.ranges:
        if (merge.min_row, merge.min_col) in cells:
            last_row = max(last_row, merge.max_row)
            last_col = max(last_col, merge.max_col)
    return {"name": ws.title, "file_name": filename, "header_row": header,
            "print_area": f"A1:{get_column_letter(last_col)}{last_row}"}


def _print_plan(workbook):
    wb = load_workbook(workbook, read_only=False, data_only=False, keep_links=False)
    try:
        missing = set(OUTPUTS) - set(wb.sheetnames)
        if missing:
            raise ValueError("工作簿缺少工作表：" + "、".join(sorted(missing)))
        return {"sheets": [_sheet_plan(wb[name], filename) for name, filename in OUTPUTS.items()]}
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


def _validate_pdfs(stage, plan):
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
                    raise ValueError(f"{sheet['name']} 的 PDF 不是 A4 横向，已停止发布")
            files.append({"sheet": sheet["name"], "name": path.name, "pages": len(pdf.pages)})
    return files


def _publish_pair(stage, directory, approved, installed):
    """Back up both outputs, then replace; roll back any completed replacement."""
    backups = {}
    if output_fingerprints(directory) != approved:
        raise ValueError("导出目录的同名文件已变化，请重新导出并确认覆盖")
    for name, digest in approved.items():
        if digest is not None:
            backup = stage / (name + ".previous")
            shutil.copyfile(directory / name, backup)
            if sha256(backup) != digest or _fingerprint(directory / name) != digest:
                raise ValueError(f"备份期间文件已变化，请重新导出：{name}")
            backups[name] = backup
    try:
        for name in OUTPUTS.values():
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


def export_workbook_pdfs(workbook, directory, approved, *, progress=None, excel=None):
    progress = progress or (lambda message: None)
    workbook, directory = Path(workbook).resolve(), Path(directory).resolve()
    result = {"status": "failed", "workbook": str(workbook), "output_dir": str(directory), "files": [], "cleanup": "完成"}
    scratch = stage = None
    installed = {}
    published = False
    temp_parent = Path(tempfile.gettempdir()).resolve()
    try:
        if workbook.suffix.lower() != ".xlsx" or not workbook.is_file():
            raise ValueError("请选择已有的 .xlsx 工作簿")
        if not isinstance(approved, dict) or set(approved) != set(OUTPUTS.values()):
            raise ValueError("导出文件确认信息不完整，请重新导出")
        if output_fingerprints(directory) != approved:
            raise ValueError("导出目录的同名文件已变化，请重新确认")
        progress("正在读取已保存的工作簿，准备 PDF 排版…")
        scratch = Path(tempfile.mkdtemp(prefix="invoice-pdf-input-", dir=temp_parent)).resolve()
        snapshot = scratch / "workbook.xlsx"
        before = sha256(workbook)
        shutil.copyfile(workbook, snapshot)
        if sha256(snapshot) != before or sha256(workbook) != before:
            raise ValueError("工作簿在读取期间发生变化，请保存并关闭后重新导出")
        plan = _print_plan(snapshot)
        directory.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".invoice-pdf-stage-", dir=directory)).resolve()
        plan_file, report_file = scratch / "plan.json", scratch / "report.json"
        plan_file.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        progress("正在通过 Excel 导出验收单和领用单，请稍候…")
        (excel or ExcelAdapter()).export_pdf(snapshot, plan_file, stage, report_file)
        report = json.loads(report_file.read_text(encoding="utf-8-sig"))
        if report.get("status") != "completed" or report.get("sheets") != plan["sheets"]:
            raise ValueError("Excel 导出结果不完整，未替换已有 PDF")
        progress("正在检查两份 PDF 并保存到导出目录…")
        files = _validate_pdfs(stage, plan)
        _publish_pair(stage, directory, approved, installed)
        published = True
        result.update(status="completed", files=[dict(item, path=str(directory / item["name"])) for item in files])
    except Exception as exc:
        result["error"] = str(exc)
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
