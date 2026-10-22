"""Fail-closed, per-cell proof of Excel PDF text and page geometry.

Excel's formatted .Text is authoritative for numbers/dates/formula results;
comparing it with str(raw_value) would reject normal displayed rounding. Literal
strings are independently compared with the saved source before PDF extraction.
"""
from bisect import bisect_right
from collections import Counter
from collections.abc import Mapping
import math
import unicodedata

from openpyxl.utils.cell import coordinate_to_tuple
from pdfplumber.utils import extract_text

_EDGE_TOLERANCE = 0.75  # PDF points: rounding/font bearings, never a whole glyph.


def _error(name, message):
    raise ValueError(f"{name} PDF 完整排版校验：{message}；未替换已有 PDF")


def _normalized(value):
    return "".join(unicodedata.normalize("NFKC", value).split())


def _integer(value, name, label, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        _error(name, f"{label}无效")
    return value


def layout_reports(plan, report):
    """Require exactly one native proof for each planned worksheet."""
    sheets = plan.get("sheets", [])
    layouts = report.get("layout") if isinstance(report, Mapping) else None
    names = [s["name"] for s in sheets]
    if (len(names) != 2 or len(set(names)) != 2 or not isinstance(layouts, list)
            or len(layouts) != 2 or any(not isinstance(item, Mapping) for item in layouts)):
        _error("导出", "缺少两份完整的 Excel 排版证明")
    actual = [item.get("name") for item in layouts]
    if any(not isinstance(name, str) for name in actual) or set(actual) != set(names):
        _error("导出", "Excel 排版证明与工作表不一致")
    return {item["name"]: item for item in layouts}


def _box(value, page, name, address):
    if (not isinstance(value, (list, tuple)) or len(value) != 4
            or any(isinstance(n, bool) or not isinstance(n, (float, int))
                   or not math.isfinite(n) for n in value)):
        _error(name, f"{address} 的打印区域无效")
    left, top, right, bottom = map(float, value)
    if (right <= left or bottom <= top or left < -_EDGE_TOLERANCE or top < -_EDGE_TOLERANCE
            or right > page.width + _EDGE_TOLERANCE or bottom > page.height + _EDGE_TOLERANCE):
        _error(name, f"{address} 的打印区域超出页面或为空")
    return left, top, right, bottom


def _cell_chars(page, box, name, address):
    """Crop while retaining original glyph bounds to detect partial clipping.

    pdfplumber.crop clips character boxes itself. Using original page.chars
    prevents that clipping from turning a partially visible glyph into proof of
    a complete one. Centers must remain inside the cell, which prevents a crop
    tolerance from borrowing an adjacent cell's matching digit/character.
    """
    left, top, right, bottom = box
    expanded = (max(0, left - _EDGE_TOLERANCE), max(0, top - _EDGE_TOLERANCE),
                min(page.width, right + _EDGE_TOLERANCE), min(page.height, bottom + _EDGE_TOLERANCE))
    # Validate the actual crop against the page before selecting original boxes.
    page.crop(expanded, strict=True)
    chars = []
    for char in page.chars:
        raw = str(char.get("text", ""))
        if not _normalized(raw):
            continue
        x0, y0, x1, y1 = (float(char[key]) for key in ("x0", "top", "x1", "bottom"))
        center_x, center_y = (x0 + x1) / 2, (y0 + y1) / 2
        if not (left <= center_x <= right and top <= center_y <= bottom):
            continue
        if (x0 < expanded[0] or y0 < expanded[1] or x1 > expanded[2] or y1 > expanded[3]):
            _error(name, f"{address} 的文字超出单元格或被裁切")
        chars.append(char)
    return chars


def validate_pdf_layout(pdf, sheet, native, source):
    """Validate native coverage and every expected PDF cell occurrence.

    ``source`` is a private map captured from the same saved workbook used to
    build the plan. It is deliberately not serialized into the native report.
    """
    name = sheet["name"]
    if not isinstance(source, Mapping) or set(source) != set(sheet["content_cells"]):
        _error(name, "源单元格记录与排版范围不一致")
    zoom = _integer(native.get("zoom"), name, "打印缩放", 10, 100)
    base = _integer(native.get("base_zoom"), name, "宽度适配缩放", 10, 100)
    if zoom > base or zoom + 1e-9 < base * 0.95:
        _error(name, "打印缩放超出最多额外缩小 5% 的限制")
    count = _integer(native.get("expected_pages"), name, "预计页数", 1, sheet["print_end_row"])
    breaks = native.get("break_rows")
    if not isinstance(breaks, list):
        _error(name, "缺少实际分页位置")
    for row in breaks:
        _integer(row, name, "分页行", sheet["repeat_end_row"] + 1, sheet["print_end_row"])
    if breaks != sorted(set(breaks)) or count != len(breaks) + 1 or len(pdf.pages) != count:
        _error(name, "实际 PDF 页数与 Excel 分页证明不一致")
    start, end = sheet["tail_start_row"], sheet["tail_end_row"]
    if (native.get("tail_start_row") != start or native.get("tail_end_row") != end
            or native.get("repeat_start_row") != sheet["repeat_start_row"]
            or native.get("repeat_end_row") != sheet["repeat_end_row"]
            or start != sheet["last_detail_row"] or end != sheet["print_end_row"]
            or any(start < row <= end for row in breaks)
            or bisect_right(breaks, start) + 1 != count):
        _error(name, "最后一条明细及全部页脚未完整保留在最后同一页")
    expected = set()
    for address in sheet["content_cells"]:
        row, _ = coordinate_to_tuple(address)
        record = source[address]
        if any(row < line <= record["end_row"] for line in breaks):
            _error(name, f"{address} 的合并单元格跨越分页位置")
        page_number = bisect_right(breaks, row) + 1
        if sheet["repeat_start_row"] <= row <= sheet["repeat_end_row"]:
            expected.update((address, p) for p in range(1, count + 1))
        else:
            expected.add((address, page_number))
    cells = native.get("cells")
    if not isinstance(cells, list):
        _error(name, "缺少逐单元格排版证明")
    seen = set()
    used_chars = {}
    for cell in cells:
        if not isinstance(cell, Mapping) or not isinstance(cell.get("address"), str):
            _error(name, "逐单元格排版证明格式无效")
        address = cell["address"]
        page_number = _integer(cell.get("page"), name, f"{address} 页码", 1, count)
        occurrence = address, page_number
        if occurrence not in expected or occurrence in seen:
            _error(name, f"{address} 出现于错误页面或被重复记录")
        seen.add(occurrence)
        page = pdf.pages[page_number - 1]
        if page.rotation or any(abs(a - b) > 0.1 for a, b in zip(page.bbox, (0, 0, page.width, page.height))):
            _error(name, f"第 {page_number} 页旋转或坐标原点不受支持")
        box = _box(cell.get("box"), page, name, address)
        display = cell.get("text")
        orientation = cell.get("orientation")
        if (not isinstance(display, str) or isinstance(orientation, bool)
                or not isinstance(orientation, (float, int)) or not math.isfinite(orientation)
                or not (-90 <= orientation <= 90 or orientation in (255, -4166, -4128, -4171, -4170))):
            _error(name, f"{address} 缺少实际显示文字或文字方向")
        normalized = _normalized(display)
        record = source[address]
        if record["kind"] == "literal" and normalized != _normalized(record["text"]):
            _error(name, f"{address} 的 Excel 显示文字与保存的原文不一致")
        if not normalized and record["kind"] != "formula":
            _error(name, f"{address} 的非空源内容未显示")
        if record["kind"] != "literal" and normalized and set(normalized) == {"#"}:
            _error(name, f"{address} 显示为溢出符号，内容未完整显示")
        chars = _cell_chars(page, box, name, address)
        for char in chars:
            key = page_number, id(char)
            if key in used_chars:
                _error(name, f"{address} 与 {used_chars[key]} 的打印区域重复使用同一文字")
            used_chars[key] = address
        if orientation not in (0, -4128):
            # Rotated/stacked extraction order differs across PDF fonts. Exact
            # counts still reject missing/repeated characters without relying
            # on a renderer's ordering of the rotated glyph stream.
            actual = _normalized("".join(str(c.get("text", "")) for c in chars))
            matches = Counter(actual) == Counter(normalized)
        else:
            actual = _normalized(extract_text(chars, x_tolerance=1, y_tolerance=2) or "")
            matches = actual == normalized
        if not matches:
            _error(name, f"第 {page_number} 页 {address} 的文字缺失、被裁切或与 Excel 显示不一致")
    if seen != expected:
        missing = sorted(expected - seen, key=lambda item: (item[1], coordinate_to_tuple(item[0])))
        address, page_number = missing[0]
        _error(name, f"缺少第 {page_number} 页 {address} 的完整排版证明")
