"""Merge the completed invoice batch without changing or rasterizing originals."""
import hashlib
import os
import re
import shutil
import stat
from contextlib import closing
from pathlib import Path

import pypdfium2 as pdfium
import pdfplumber

from .pdf_signatures import _PDFIUM_LOCK
from .updates import sha256

FILENAME = "发票汇总.pdf"


def _normalize_sources(sources):
    if not isinstance(sources, (list, tuple)) or not sources:
        raise ValueError("发票汇总缺少本次处理成功的发票清单，请重新预览并执行处理")
    normalized = []
    for item in sources:
        if (not isinstance(item, dict) or type(item.get("sequence")) is not int
                or not isinstance(item.get("path"), str) or not Path(item["path"]).is_absolute()
                or not isinstance(item.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
            raise ValueError("发票汇总清单格式不完整，请重新预览并执行处理")
        path = Path(item["path"])
        if path.suffix.lower() != ".pdf":
            raise ValueError("发票汇总清单包含非 PDF 文件")
        normalized.append(dict(sequence=item["sequence"], path=str(path), sha256=item["sha256"]))
    normalized.sort(key=lambda item: item["sequence"])
    if ([item["sequence"] for item in normalized] != list(range(1, len(normalized) + 1))
            or len({str(Path(item["path"]).resolve()).casefold() for item in normalized}) != len(normalized)):
        raise ValueError("发票汇总的文件重复或序号不连续，请重新预览并执行处理")
    return normalized


def sources_from_processing(result, fingerprints):
    """Pin one final PDF per invoice, independently of its detail-row count."""
    if result.get("status") != "completed":
        raise ValueError("发票汇总仅能使用本次执行成功的发票清单")
    records = result.get("payload", {}).get("records", [])
    plan = result.get("rename_plan", [])
    by_source = {entry["source"]: entry for entry in plan}
    if len(records) != len(plan) or len(by_source) != len(plan):
        raise ValueError("发票汇总与本次处理结果不对应")
    sources = []
    for record in records:
        entry = by_source.get(record["pdf"])
        if entry is None or entry.get("status") not in ("renamed", "unchanged"):
            raise ValueError("发票汇总中有尚未完成改名的发票")
        sources.append(dict(sequence=record["sequence"], path=entry["destination"],
                            sha256=fingerprints.get(record["pdf"])))
    return _normalize_sources(sources)


def verify_sources(sources):
    for item in _normalize_sources(sources):
        path = Path(item["path"])
        try:
            attrs = path.lstat()
            reparse = bool(attrs.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT) if os.name == "nt" else path.is_symlink()
            valid = not reparse and path.is_file() and sha256(path) == item["sha256"]
        except OSError:
            valid = False
        if not valid:
            raise ValueError(f"发票汇总：第 {item['sequence']} 张原始发票已变化或不可用：{path.name}。"
                             "请恢复文件或重新预览并执行处理。")


def snapshot_invoices(sources, scratch, output_directory):
    sources = _normalize_sources(sources)
    output_directory = Path(output_directory).resolve()
    if any(Path(item["path"]).resolve().parent == output_directory for item in sources):
        raise ValueError("发票汇总请保存到单独的导出文件夹，避免下次被当作新发票识别")
    verify_sources(sources)
    directory = Path(scratch) / "invoice-sources"
    directory.mkdir()
    snapshots = []
    for item in sources:
        destination = directory / f"{item['sequence']}.pdf"
        try:
            shutil.copyfile(item["path"], destination)
            valid = sha256(destination) == item["sha256"]
        except OSError:
            valid = False
        if not valid:
            raise ValueError(f"发票汇总：第 {item['sequence']} 张发票在读取时发生变化，请重新导出")
        snapshots.append(dict(item, snapshot=str(destination)))
    verify_sources(sources)
    return snapshots


def _page_properties(page):
    with closing(page.get_textpage()) as text:
        digest = hashlib.sha256(text.get_text_bounded().encode("utf-8")).hexdigest()
    return (tuple(page.get_size()), tuple(page.get_mediabox()), tuple(page.get_cropbox()), page.get_rotation(), digest)


def merge_invoice_pdfs(snapshots, destination):
    """Copy all vector pages and validate their count, geometry and text."""
    if not snapshots:
        raise ValueError("发票汇总没有可合并的发票")
    destination = Path(destination)
    if os.path.lexists(destination):
        raise ValueError("发票汇总的暂存输出已存在，已停止覆盖")
    expected = []
    # PDFium is not thread-safe; share the existing signature-export lock.
    with _PDFIUM_LOCK, pdfium.PdfDocument.new() as merged:
        for item in snapshots:
            try:
                if sha256(item["snapshot"]) != item["sha256"]:
                    raise ValueError("发票快照已变化")
                # Page import cannot preserve these document-level features.
                # Fail clearly instead of silently changing visible content.
                with pdfplumber.open(item["snapshot"]) as parsed:
                    catalog = parsed.doc.catalog
                    if "AcroForm" in catalog:
                        raise ValueError("该 PDF 含交互表单，当前不支持直接合并")
                    if "OCProperties" in catalog:
                        raise ValueError("该 PDF 含可选图层，当前不支持直接合并")
                with pdfium.PdfDocument(item["snapshot"]) as source:
                    if not len(source):
                        raise ValueError("PDF 没有页面")
                    for page in source:
                        with closing(page):
                            expected.append(_page_properties(page))
                    merged.import_pages(source)
            except Exception as exc:
                raise ValueError(f"发票汇总：第 {item['sequence']} 张发票无法读取，已停止合并："
                                 f"{Path(item['path']).name}；{exc}") from exc
        merged.save(destination)
    with _PDFIUM_LOCK, pdfium.PdfDocument(destination) as saved:
        if len(saved) != len(expected):
            raise ValueError("发票汇总页数校验未通过，未替换已有 PDF")
        for index, properties in enumerate(expected):
            with closing(saved[index]) as page:
                if _page_properties(page) != properties:
                    raise ValueError(f"发票汇总第 {index + 1} 页内容或页面尺寸校验未通过，未替换已有 PDF")
    return dict(sheet="发票汇总", name=FILENAME, pages=len(expected), invoices=len(snapshots))
