"""Place signature images in staged Excel PDFs without rasterizing their pages.

Coordinates used for layout are pdfplumber's (left, top, right, bottom), in
printed PDF points. Only the final image matrix converts to PDF bottom origin.
API/lifetime references (pypdfium2 5.14 and pdfplumber 0.11):
https://pypdfium2.readthedocs.io/en/stable/python_api.html
https://github.com/jsvine/pdfplumber#extracting-text
"""
import io
import math
import os
import re
import stat
import tempfile
import threading
from collections.abc import Mapping
from contextlib import ExitStack
from pathlib import Path
from statistics import median

import pdfplumber
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from PIL import Image, ImageChops


_ROLES = {
    "验收": (("acceptance_handler", "经办人"), ("acceptance_inspector", "验收人")),
    "领用": (("issue_keeper", "保管人"), ("issue_recipient", "领用人")),
}
_DATES = {"验收": "验收日期", "领用": "领用日期"}
_PDFIUM_LOCK = threading.Lock()
_PAD = 2.0
_TOLERANCE = 0.1


class _SignatureError(ValueError):
    """A user-facing failure, as distinct from an image decoder exception."""


def _error(sheet, message):
    raise _SignatureError(f"{sheet} PDF 签名：{message}；已停止带签名导出")


def _number(value, sheet, field):
    if isinstance(value, bool):
        _error(sheet, f"{field}无效")
    try:
        result = float(value)
    except (TypeError, ValueError):
        _error(sheet, f"{field}无效")
    if not math.isfinite(result) or result <= 0:
        _error(sheet, f"{field}无效")
    return result


def _near(left, right):
    return len(left) == len(right) and all(abs(a - b) <= _TOLERANCE for a, b in zip(left, right))


def _rect(obj):
    return tuple(float(obj[key]) for key in ("x0", "top", "x1", "bottom"))


def _overlaps(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _line_box(edge):
    x0, top, x1, bottom = _rect(edge)
    half = max(0.25, float(edge.get("linewidth") or 0) / 2)
    return x0 - half, top - half, x1 + half, bottom + half


def _check_empty(page, box, sheet, label):
    for char in page.chars:
        if str(char.get("text", "")).strip() and _overlaps(box, _rect(char)):
            _error(sheet, f"“{label}”签字区域已有文字，不能覆盖")
    for edge in page.edges:
        if _overlaps(box, _line_box(edge)):
            _error(sheet, f"“{label}”签字区域与线条或边框重叠")
    for obj in page.images + (page.annots or []):
        if _overlaps(box, _rect(obj)):
            _error(sheet, f"“{label}”签字区域已有图片或批注，不能覆盖")
    for obj in page.rects + page.curves:
        color = obj.get("non_stroking_color")
        white = color == 1 or color in ((1, 1, 1), (0, 0, 0, 0))
        if obj.get("fill") and not white and _overlaps(box, _rect(obj)):
            _error(sheet, f"“{label}”签字区域已有填充图形，不能覆盖")


def _find_labels(pdf, sheet, labels):
    candidates = {}
    for label in labels:
        # Whitespace within the label is allowed, but not a line break or a
        # larger word containing the label. Include either printed colon.
        body = r"[^\S\r\n]*".join(re.escape(char) for char in label)
        pattern = rf"(?<!\w){body}(?!\w)(?:[^\S\r\n]*[:：])?"
        matches = []
        for index, page in enumerate(pdf.pages):
            for match in page.search(pattern, regex=True, return_chars=True, layout=False):
                chars = [c for c in match["chars"] if str(c["text"]).strip()]
                if not chars:
                    continue
                sizes = [_number(c.get("size"), sheet, "打印字号") for c in chars]
                size = median(sizes)
                box = (min(c["x0"] for c in chars), min(c["top"] for c in chars),
                       max(c["x1"] for c in chars), max(c["bottom"] for c in chars))
                matches.append({"page": index, "box": box, "size": size, "chars": chars})
        if not matches:
            _error(sheet, f"未找到“{label}”标签")
        candidates[label] = matches

    # Footer instructions legitimately mention the signer names again. Select
    # the complete role/role/date row, rather than requiring each word to occur
    # only once in the document. Keep rejecting multiple complete rows.
    first_label, second_label, date_label = labels
    found = None
    for date in candidates[date_label]:
        for first in candidates[first_label]:
            if first["page"] != date["page"] or first["box"][2] >= date["box"][0]:
                continue
            for second in candidates[second_label]:
                if (second["page"] != date["page"] or first["box"][2] >= second["box"][0]
                        or second["box"][2] >= date["box"][0]):
                    continue
                anchors = (first, second, date)
                centers = [(a["box"][1] + a["box"][3]) / 2 for a in anchors]
                if max(centers) - min(centers) > max(1.0, min(a["size"] for a in anchors) * 0.3):
                    continue
                if found is not None:
                    _error(sheet, "存在多处完整签字行，无法确定签名位置")
                found = dict(zip(labels, anchors))
    if found is None:
        _error(sheet, "未找到同页、同一行且顺序正确的签字与日期标签")

    for label, anchor in found.items():
        chars, size = anchor["chars"], anchor["size"]
        if any(not c.get("upright", False) for c in chars):
            _error(sheet, f"“{label}”的文字方向无法确认")
        for char in chars:
            matrix = char.get("matrix", ())
            if (len(matrix) != 6 or matrix[0] <= 0 or matrix[3] <= 0
                    or abs(matrix[1]) > 0.001 or abs(matrix[2]) > 0.001):
                _error(sheet, f"“{label}”的文字存在旋转或倾斜，无法可靠定位")
        sizes = [_number(c.get("size"), sheet, "打印字号") for c in chars]
        if max(sizes) - min(sizes) > max(0.15, size * 0.05):
            _error(sheet, f"“{label}”使用混合打印字号，无法确定缩放")
        if anchor["box"][3] - anchor["box"][1] > size * 1.3:
            _error(sheet, f"“{label}”跨行，无法确定签字行")
    return found


def _usable_box(page, slot, anchor, following, sheet):
    label = slot["label"]
    x0, top, x1, bottom = anchor["box"]
    scale = anchor["size"] / _number(slot.get("font_size"), sheet, f"“{label}”原字号")
    height = _number(slot.get("row_height"), sheet, f"“{label}”原行高") * scale
    if height + _TOLERANCE < bottom - top:
        _error(sheet, f"“{label}”的打印行高小于文字高度")
    align = slot.get("vertical_alignment") or "bottom"
    # Keeping the glyph's edge inside the estimated band is conservative for
    # Excel's top/bottom cell padding; actual printed edges further limit it.
    if align == "center":
        center = (top + bottom) / 2
        band_top, band_bottom = center - height / 2, center + height / 2
    elif align == "top":
        band_top, band_bottom = top, top + height
    elif align == "bottom":
        band_top, band_bottom = bottom - height, bottom
    else:
        _error(sheet, f"“{label}”的垂直对齐方式“{align}”无法可靠定位")
    left, right = x1, following["box"][0]
    if right <= left:
        _error(sheet, f"“{label}”后方没有独立签字区域")
    # Only lines actually crossing this field constrain it. Never infer a row
    # from unrelated body-table edges elsewhere on the page.
    for edge in page.edges:
        ex0, etop, ex1, ebottom = _line_box(edge)
        if ex1 <= left or ex0 >= right or edge.get("orientation") != "h":
            continue
        if ebottom <= top + _TOLERANCE:
            band_top = max(band_top, ebottom)
        elif etop >= bottom - _TOLERANCE:
            band_bottom = min(band_bottom, etop)
    box = (max(0, left) + _PAD, max(0, band_top) + _PAD,
           min(page.width, right) - _PAD, min(page.height, band_bottom) - _PAD)
    if box[2] - box[0] < 24 or box[3] - box[1] < 8:
        _error(sheet, f"“{label}”可用签字区域过小")
    _check_empty(page, box, sheet, label)
    return box


def _text_record(page):
    return [(c["text"], _rect(c)) for c in page.chars]


def _layout(path, sheet):
    name = sheet["name"]
    slots = sheet.get("signature_slots", [])
    expected = _ROLES[name]
    if (len(slots) != 2 or any(not isinstance(s, Mapping) for s in slots)
            or [(s.get("key"), s.get("label")) for s in slots] != list(expected)
            or sheet.get("signature_date_label", "").rstrip("：:") != _DATES[name]):
        _error(name, "签字位置或日期配置不完整")
    with pdfplumber.open(path) as pdf:
        if not pdf.pages:
            _error(name, "没有可用页面")
        baseline = []
        for page in pdf.pages:
            if page.rotation or not _near(page.bbox, (0, 0, page.width, page.height)):
                _error(name, "页面旋转或坐标原点不受支持")
            baseline.append({"size": (page.width, page.height), "text": _text_record(page)})
        found = _find_labels(pdf, name, [label for _, label in expected] + [_DATES[name]])
        page_index = found[expected[0][1]]["page"]
        page = pdf.pages[page_index]
        anchors = [found[label] for _, label in expected] + [found[_DATES[name]]]
        if not all(a["box"][2] < b["box"][0] for a, b in zip(anchors, anchors[1:])):
            _error(name, "签字标签与日期标签的左右顺序不正确")
        scales = [a["size"] / _number(s.get("font_size"), name, "原字号")
                  for a, s in zip(anchors, slots)]
        if abs(scales[0] - scales[1]) > max(scales) * 0.05:
            _error(name, "两个签字位置的打印缩放不一致")
        boxes = [{"slot": slot["key"], "role": slot["label"], "page": page_index,
                  "box": _usable_box(page, slot, anchors[i], anchors[i + 1], name)}
                 for i, slot in enumerate(slots)]
    return {"name": name, "path": path, "baseline": baseline, "boxes": boxes}


def _read_images(snapshot, stack):
    if not isinstance(snapshot, Mapping) or any(not isinstance(snapshot.get(k), Mapping)
                                              for k in ("bindings", "images", "labels")):
        _error("签名库", "快照格式无效")
    bindings, labels = snapshot["bindings"], snapshot["labels"]
    valid_slots = {key for roles in _ROLES.values() for key, _ in roles}
    if set(bindings) - valid_slots:
        _error("签名库", "包含未知签字位置")
    selected = {key: value for key, value in bindings.items() if value is not None}
    if not selected:
        _error("签名库", "尚未为任何签字位置选择签名")
    images = {}
    for item_id in selected.values():
        if not isinstance(item_id, str) or not item_id:
            _error("签名库", "签名标识无效")
        if item_id in images:
            continue
        label, data = labels.get(item_id), snapshot["images"].get(item_id)
        if not isinstance(label, str) or not label.strip() or not isinstance(data, bytes) or not data:
            _error("签名库", "已选签名缺少名称或图片")
        if len(data) > 32 * 1024 * 1024:
            _error("签名库", f"“{label}”图片文件过大")
        try:
            with Image.open(io.BytesIO(data)) as source:
                if (source.format != "PNG" or getattr(source, "n_frames", 1) != 1
                        or max(source.size) > 16384 or source.width * source.height > 40_000_000):
                    _error("签名库", f"“{label}”不是受支持的单帧 PNG 图片")
                source.verify()
            with Image.open(io.BytesIO(data)) as source:
                source.load()
                image = source.convert("RGBA")
            stack.callback(image.close)
            # Even a corrupt/stale snapshot must not silently add a blank image.
            with Image.new("RGBA", image.size, "white") as white:
                with Image.alpha_composite(white, image) as visible:
                    with ImageChops.difference(visible, white) as difference:
                        with difference.convert("RGB") as rgb:
                            if rgb.getbbox() is None:
                                _error("签名库", f"“{label}”没有可见笔迹")
            images[item_id] = image
        except _SignatureError:
            raise
        except Exception as exc:
            _error("签名库", f"“{label}”图片不可读取（{exc}）")
    return selected, images


def _image_records(page):
    records = []
    for obj in page.get_objects(filter=[pdfium_raw.FPDF_PAGEOBJ_IMAGE]):
        meta = obj.get_metadata()
        records.append({"bounds": tuple(obj.get_bounds()), "pixels": (meta.width, meta.height),
                        "bits": meta.bits_per_pixel, "matrix": obj.get_matrix().get(), "level": obj.level})
    return records


def _write_signed(layout, destination, placements, images):
    """Document/page own inserted objects; caller owns loose objects/bitmaps."""
    with ExitStack() as stack:
        pdf = stack.enter_context(pdfium.PdfDocument(layout["path"]))
        original_metadata = pdf.get_metadata_dict()
        originals = []
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                width, height = layout["baseline"][index]["size"]
                if (page.get_rotation() != 0 or not _near(page.get_size(), (width, height))
                        or not _near(page.get_bbox(), (0, 0, width, height))
                        or not _near(page.get_mediabox(), (0, 0, width, height))):
                    _error(layout["name"], "页面坐标或裁切区域无法安全放置签名")
                originals.append(_image_records(page))
                for placement in (p for p in placements if p["page"] == index):
                    bitmap = pdfium.PdfBitmap.from_pil(images[placement["image_id"]])
                    # Keep immutable bitmap storage through content generation
                    # and save. ExitStack closes bitmap handles before the PDF.
                    stack.callback(bitmap.close)
                    obj = pdfium.PdfImage.new(pdf)
                    try:
                        obj.set_bitmap(bitmap)
                        obj.set_matrix(pdfium.PdfMatrix(*placement["matrix"]))
                        page.insert_obj(obj)
                    finally:
                        # close() is documented as a no-op for page-owned
                        # objects, and frees a loose object on an insertion error.
                        obj.close()
                if any(p["page"] == index for p in placements):
                    page.gen_content()
            finally:
                page.close()
        pdf.save(destination)
    return original_metadata, originals


def _verify_signed(layout, destination, placements, images, metadata, originals):
    name = layout["name"]
    with pdfplumber.open(destination) as pdf:
        if len(pdf.pages) != len(layout["baseline"]):
            _error(name, "保存后的页数发生变化")
        for page, baseline in zip(pdf.pages, layout["baseline"]):
            if not _near((page.width, page.height), baseline["size"]):
                _error(name, "保存后的页面尺寸发生变化")
            current = _text_record(page)
            if len(current) != len(baseline["text"]) or any(
                    a[0] != b[0] or not _near(a[1], b[1]) for a, b in zip(current, baseline["text"])):
                _error(name, "保存后的正文、页码或文字位置发生变化")
    with pdfium.PdfDocument(destination) as pdf:
        if len(pdf) != len(originals) or pdf.get_metadata_dict() != metadata:
            _error(name, "保存后的文档页数或元数据校验失败")
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                width, height = layout["baseline"][index]["size"]
                if (page.get_rotation() != 0 or not _near(page.get_size(), (width, height))
                        or not _near(page.get_bbox(), (0, 0, width, height))
                        or not _near(page.get_mediabox(), (0, 0, width, height))):
                    _error(name, f"第 {index + 1} 页保存后的页面坐标或裁切区域发生变化")
                records = _image_records(page)
                expected = [p for p in placements if p["page"] == index]
                if len(records) != len(originals[index]) + len(expected):
                    _error(name, f"第 {index + 1} 页的签名图片数量校验失败")
                for placement in expected:
                    matching = [r for r in records if r["level"] == 0
                                and _near(r["matrix"], placement["matrix"])
                                and r["pixels"] == images[placement["image_id"]].size
                                and r["bits"] > 0]
                    if len(matching) != 1:
                        _error(name, f"“{placement['role']}”保存后的图片位置或尺寸校验失败")
                    records.remove(matching[0])
                for old, new in zip(originals[index], records):
                    if (old["pixels"] != new["pixels"] or old["bits"] != new["bits"]
                            or old["level"] != new["level"] or not _near(old["bounds"], new["bounds"])
                            or not _near(old["matrix"], new["matrix"])):
                        _error(name, f"第 {index + 1} 页的原有图片发生变化")
            finally:
                page.close()


def add_signatures(stage: Path, plan: dict, snapshot: dict) -> dict:
    """Validate all four regions, add selected images, then replace staged PDFs.

    Accepts read-only mappings for the snapshot. This function never publishes
    output files; its caller owns stage cleanup and atomic pair publication.
    """
    stage = Path(stage).resolve()
    sheets = plan.get("sheets", [])
    if len(sheets) != 2 or {s.get("name") for s in sheets} != set(_ROLES):
        _error("导出", "需要完整的验收、领用工作表配置")
    with ExitStack() as stack:
        bindings, images = _read_images(snapshot, stack)
        layouts, names = [], set()
        for sheet in sheets:
            filename = sheet.get("file_name", "")
            if (not isinstance(filename, str) or Path(filename).name != filename
                    or Path(filename).suffix.lower() != ".pdf" or filename in names):
                _error(sheet["name"], "临时 PDF 文件名无效")
            names.add(filename)
            path = stage / filename
            if (not path.is_file() or path.is_symlink() or (os.name == "nt" and
                    path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)):
                _error(sheet["name"], "临时 PDF 不存在或不是普通文件")
            layouts.append(_layout(path, sheet))
        regions = [region for layout in layouts for region in layout["boxes"]]
        width = min(r["box"][2] - r["box"][0] for r in regions)
        height = min(r["box"][3] - r["box"][1] for r in regions)
        applied, pending = [], []
        # PDFium is not thread-safe; serialize this module's callers.
        with _PDFIUM_LOCK:
            for layout in layouts:
                placements = []
                for region in layout["boxes"]:
                    item_id = bindings.get(region["slot"])
                    if item_id is None:
                        continue
                    image = images[item_id]
                    ratio = min(width / image.width, height / image.height)
                    iw, ih = image.width * ratio, image.height * ratio
                    if min(iw, ih) < 3:
                        _error(layout["name"], f"“{region['role']}”图片比例过于狭长，适配后无法清晰显示")
                    x0, top, x1, bottom = region["box"]
                    # The usable box already starts after the colon and padding.
                    left = x0
                    image_top = (top + bottom - ih) / 2
                    page_height = layout["baseline"][region["page"]]["size"][1]
                    placements.append({**region, "image_id": item_id,
                                       "matrix": (iw, 0, 0, ih, left, page_height - image_top - ih)})
                    applied.append({"sheet": layout["name"], "slot": region["slot"],
                                    "role": region["role"], "label": snapshot["labels"][item_id],
                                    "page": region["page"] + 1})
                if not placements:
                    continue
                fd, temporary = tempfile.mkstemp(prefix=".signed-", suffix=".pdf", dir=stage)
                os.close(fd)
                temporary = Path(temporary)
                # The parent owns cleanup of this entire stage, also on failure.
                metadata, originals = _write_signed(layout, temporary, placements, images)
                _verify_signed(layout, temporary, placements, images, metadata, originals)
                pending.append((temporary, layout["path"]))
            # All files have passed validation and all readers/native handles
            # are closed before replacement (required especially on Windows).
            for temporary, target in pending:
                os.replace(temporary, target)
        return {"applied": applied, "box_width": width, "box_height": height}
