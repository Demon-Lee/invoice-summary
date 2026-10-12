import argparse
import json
import re
import sys
from decimal import Decimal, DecimalException, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

try:
    import pdfplumber
except ModuleNotFoundError:
    pdfplumber = None


SHIPPING_FEE_KEYWORDS = ("配送费", "运费", "快递费", "物流费", "邮费", "运输费")

INVOICE_NUMBER_PATTERN = re.compile(
    r"发\s*票\s*号\s*码\s*[：:]\s*([0-9]{8,20})"
)
INVOICE_NUMBER_LABEL_PATTERN = re.compile(r"发\s*票\s*号\s*码\s*[：:]")
STANDALONE_20_DIGIT_PATTERN = re.compile(r"(?<![0-9])([0-9]{20})(?![0-9])")
VERIFICATION_PLATFORM_MARKERS = (
    "国家税务总局全国增值税发票查验平台",
    "https://inv-veri.chinatax.gov.cn/index.html",
)
VERIFICATION_RESULT_MARKERS = ("查验次数", "查验时间")


def _invoice_number_candidates(text: str) -> list[str]:
    source = text or ""
    labeled_candidates = sorted(set(INVOICE_NUMBER_PATTERN.findall(source)))
    if labeled_candidates or not INVOICE_NUMBER_LABEL_PATTERN.search(source):
        return labeled_candidates
    wrapped_candidates = sorted(set(STANDALONE_20_DIGIT_PATTERN.findall(source)))
    return wrapped_candidates if len(wrapped_candidates) == 1 else []


def _is_verification_report_text(text: str) -> bool:
    source = text or ""
    return (
        any(marker in source for marker in VERIFICATION_PLATFORM_MARKERS)
        and any(marker in source for marker in VERIFICATION_RESULT_MARKERS)
    )


def clean_project_name(value: str) -> str:
    value = (value or "").strip()
    while value.startswith("*"):
        closing = value.find("*", 1)
        if closing < 0:
            break
        value = value[closing + 1 :]
    return value.strip()


def normalize_product_and_specification(name: str, specification: str) -> tuple[str, str]:
    """Apply stable invoice-layout corrections after extracting a detail row."""
    product = clean_project_name(name)
    specification = (specification or "").strip()
    corrections = {
        ("阀门内丝管", "不锈钢 6分"): ("阀门 不锈钢内丝管", "6分"),
        ("微型", "4芯公缆 4芯"): ("微型 4芯公缆", "4芯"),
    }
    return corrections.get((product, specification), (product, specification))


def safe_filename_component(value: str) -> str:
    """Return a Windows-safe filename component without altering source data."""
    replacements = str.maketrans({
        "<": "＜",
        ">": "＞",
        ":": "：",
        '"': "＂",
        "/": "／",
        "\\": "＼",
        "|": "｜",
        "?": "？",
        "*": "",
    })
    cleaned = (value or "").strip().translate(replacements).rstrip(". ")
    return cleaned or "未命名项目"


def _merge_detail_into_row(row: dict, amount: Decimal, tax: Decimal) -> None:
    merged_amount = Decimal(row["net_amount"]) + amount
    merged_tax = Decimal(row["tax"]) + tax
    row["net_amount"] = format(merged_amount, ".2f")
    row["tax"] = format(merged_tax, ".2f")
    row["amount"] = format(merged_amount + merged_tax, ".2f")


def _is_shipping_fee(detail: dict) -> bool:
    name = str(detail.get("name") or "")
    return any(keyword in name for keyword in SHIPPING_FEE_KEYWORDS)


def build_rows(sequence: int, seller: str, details: list[dict]) -> list[dict]:
    rows = []
    latest_normal_row = None
    for detail in details:
        amount = Decimal(str(detail.get("amount") or "0"))
        tax = Decimal(str(detail.get("tax") or "0"))
        if _is_shipping_fee(detail):
            if latest_normal_row is None:
                raise ValueError("fee detail has no previous normal detail")
            _merge_detail_into_row(latest_normal_row, amount, tax)
            continue
        zero_tax_discount_candidate = (
            amount < 0
            and tax == 0
            and not str(detail.get("quantity") or "").strip()
            and not str(detail.get("unit") or "").strip()
        )
        if zero_tax_discount_candidate:
            if latest_normal_row is None:
                raise ValueError("discount detail has no previous normal detail")
            product_name, _ = normalize_product_and_specification(
                str(detail.get("name") or ""), str(detail.get("spec") or "")
            )
            if product_name != latest_normal_row["product_name"]:
                raise ValueError("zero-tax discount detail does not match previous normal detail")
            _merge_detail_into_row(latest_normal_row, amount, tax)
            continue
        if amount < 0 and tax < 0:
            if latest_normal_row is None:
                raise ValueError("discount detail has no previous normal detail")
            _merge_detail_into_row(latest_normal_row, amount, tax)
            continue
        product_name, specification = normalize_product_and_specification(
            str(detail.get("name") or ""), str(detail.get("spec") or "")
        )
        quantity = str(detail.get("quantity") or "").strip() or "1"
        latest_normal_row = {
            "sequence": sequence,
            "product_name": product_name,
            "spec": specification,
            "unit": str(detail.get("unit") or ""),
            "quantity": quantity,
            "net_amount": format(amount, ".2f"),
            "tax": format(tax, ".2f"),
            "amount": format(amount + tax, ".2f"),
            "manufacturer": seller or "",
        }
        rows.append(latest_normal_row)
    return rows


def verify_invoice(
    grand_total: Decimal, detail_total: Decimal, excel_total: Decimal
) -> dict:
    values = [grand_total, detail_total, excel_total]
    return {
        "status": "passed" if grand_total == detail_total == excel_total else "failed",
        "grand_total": str(grand_total),
        "detail_total": str(detail_total),
        "excel_total": str(excel_total),
    }


def build_rename_plan(pairs, sequences=None):
    """Create a dry-run-only rename plan, using sequential defaults when omitted."""
    plan = []
    explicit_sequences = iter(sequences) if sequences is not None else None
    for index, (source, project) in enumerate(pairs, 1):
        sequence = next(explicit_sequences) if explicit_sequences is not None else index
        source_path = Path(source)
        destination = source_path.with_name(
            f"{sequence}. {safe_filename_component(project)}.pdf"
        )
        if source_path.resolve() == destination.resolve():
            status = "unchanged"
        elif destination.exists():
            status = "collision"
        else:
            status = "ready"
        plan.append(
            {
                "source": str(source_path),
                "destination": str(destination),
                "status": status,
            }
        )
    return plan


def _validate_combined_rename_plan(entries):
    """Mark competing destinations as collisions without changing unchanged entries."""
    validated = [dict(entry) for entry in entries]
    destinations = {}
    for entry in validated:
        destination = str(Path(entry["destination"]).resolve()).casefold()
        destinations.setdefault(destination, []).append(entry)
    for group in destinations.values():
        sources = {str(Path(entry["source"]).resolve()).casefold() for entry in group}
        if len(sources) > 1:
            for entry in group:
                if entry["status"] != "unchanged":
                    entry["status"] = "collision"
    return validated


def _apply_rename_entries(entries):
    """Preflight and apply a complete rename batch without partial changes."""
    invalid_sources = [entry for entry in entries if not Path(entry["source"]).is_file()]
    collisions = [entry for entry in entries if entry["status"] == "collision"]
    if invalid_sources:
        return [
            _exception(
                entry["source"],
                "rename",
                f"rename aborted because source is missing or not a regular file: {entry['source']}",
            )
            for entry in invalid_sources
        ]
    if collisions:
        return [_exception("", "rename", "rename aborted because a destination collision exists")]
    for entry in entries:
        if entry["status"] == "ready":
            Path(entry["source"]).rename(entry["destination"])
            entry["status"] = "renamed"
    return []


def record_filename_project(record: dict) -> str:
    """Use the first emitted row so filename and workbook share one product name."""
    rows = record.get("rows") or []
    if rows:
        return str(rows[0].get("product_name") or "")
    details = record.get("details") or []
    return clean_project_name(str(details[0].get("name") or "")) if details else ""


def _exception(pdf_path, field, message):
    return {"pdf": str(pdf_path), "field": field, "message": message}


def _as_decimal(value):
    return Decimal(str(value).replace(",", "").replace("¥", "").replace("￥", ""))


def _extract_seller(text):
    labels_normalized = re.sub(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])", "", text)
    markers = list(re.finditer(r"\u540d\u79f0\s*[:\uff1a]\s*", labels_normalized))
    if len(markers) < 2:
        return ""
    return labels_normalized[markers[1].end() :].splitlines()[0].strip()


def _is_seller_label_residue(value: str) -> bool:
    return bool(re.fullmatch(r"[\u8d2d\u9500\u4e70\u5356\u65b9\s]+", value or ""))


def _visual_rows(words: list[dict], tolerance: float = 5) -> list[list[dict]]:
    """Group nearby extracted words into visual rows without changing PDF values."""
    rows = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        for row in rows:
            if abs(row[0]["top"] - word["top"]) <= tolerance:
                row.append(word)
                break
        else:
            rows.append([word])
    return [sorted(row, key=lambda item: item["x0"]) for row in rows]


def _seller_label_words(words: list[dict]) -> list[dict]:
    """Find complete or split Name labels while preserving their page coordinates."""
    labels = []
    for row in _visual_rows(words):
        for start in range(len(row)):
            label_text = ""
            for end in range(start, min(start + 3, len(row))):
                label_text += str(row[end].get("text", "")).strip()
                if label_text in {"\u540d\u79f0:", "\u540d\u79f0\uff1a"}:
                    labels.append({
                        "x0": row[start]["x0"],
                        "x1": row[end]["x1"],
                        "top": row[start]["top"],
                        "bottom": row[end]["bottom"],
                    })
                    break
    return labels


def _select_seller_label(labels: list[dict]) -> dict:
    """Choose the right seller label for side-by-side or stacked invoice layouts."""
    horizontal_span = max(label["x0"] for label in labels) - min(label["x0"] for label in labels)
    if horizontal_span > 80:
        return max(labels, key=lambda label: (label["x0"], label["top"]))
    return max(labels, key=lambda label: (label["top"], label["x0"]))


def _extract_seller_from_words(words: list[dict]) -> str:
    labels = _seller_label_words(words)
    if not labels:
        return ""
    label = _select_seller_label(labels)
    candidates = [
        word for word in words
        if word["x0"] >= label["x1"] - 5
        and abs(word["top"] - label["top"]) <= 4
        and str(word.get("text", "")).strip()
    ]
    candidate = "".join(
        str(word["text"]).strip()
        for word in sorted(candidates, key=lambda word: word["x0"])
    )
    return "" if _is_seller_label_residue(candidate) else candidate


def _extract_grand_total(text):
    match = re.search(
        r"\u4ef7\s*\u7a0e\s*\u5408\s*\u8ba1.*?[\uff08(]\s*\u5c0f\s*\u5199\s*[\uff09)]\s*[\u00a5\uffe5]?\s*(-?[\d,]+\.\d{2})",
        text,
        flags=re.DOTALL,
    )
    return _as_decimal(match.group(1)) if match else None


def _extract_grand_total_from_words(words: list[dict]):
    """Read a small-sum total when PDF text order separates its label and value."""
    for index, word in enumerate(words):
        text = str(word.get("text", ""))
        match = re.search(
            r"(?:\u5c0f\u5199[\uff09)])?\s*[\u00a5\uffe5]\s*(-?[\d,]+\.\d{2})", text
        )
        if match and "\u5c0f\u5199" in text:
            return _as_decimal(match.group(1))
        if "\u5c0f\u5199" not in text:
            continue
        midpoint = (word["top"] + word["bottom"]) / 2
        for candidate in words[index + 1 :]:
            candidate_midpoint = (candidate["top"] + candidate["bottom"]) / 2
            if abs(candidate_midpoint - midpoint) > 5:
                continue
            match = re.search(r"[\u00a5\uffe5]\s*(-?[\d,]+\.\d{2})", str(candidate.get("text", "")))
            if match:
                return _as_decimal(match.group(1))
    return None


def _split_merged_quantity_price(value: str, amount: Decimal):
    """Return the one quantity/price split that exactly reproduces amount."""
    candidates = []
    value = str(value).strip()
    for index in range(1, len(value)):
        quantity_text, unit_price_text = value[:index], value[index:]
        try:
            quantity = Decimal(quantity_text)
            unit_price = Decimal(unit_price_text)
        except InvalidOperation:
            continue
        if quantity <= 0 or unit_price <= 0:
            continue
        if (quantity * unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ) == amount:
            candidates.append((quantity_text, unit_price_text))
    return candidates[0] if len(candidates) == 1 else None


def _invoice_detail_lines(text):
    lines = [line.strip() for line in text.splitlines()]
    header_markers = ("\u9879\u76ee\u540d\u79f0", "\u8d27\u7269\u6216\u5e94\u7a0e\u52b3\u52a1\u3001\u670d\u52a1\u540d\u79f0")
    start = next(
        (index for index, line in enumerate(lines) if any(marker in line for marker in header_markers)),
        None,
    )
    if start is None:
        return []
    result = []
    previous_was_detail = False
    for line in lines[start + 1 :]:
        if re.match(r"\u5408\s*\u8ba1", line) or "\u4ef7\u7a0e\u5408\u8ba1" in line:
            break
        if line.startswith("*"):
            result.append([line, ""])
            previous_was_detail = True
        elif result and previous_was_detail and re.fullmatch(r"[-.A-Za-z0-9]+", line):
            # pdfplumber can split a long alphanumeric specification onto its
            # own visual line. Preserve it only as an adjacent continuation;
            # later alphanumeric seller fields (for example taxpayer IDs) are
            # not part of this detail row.
            result[-1][1] += line
            previous_was_detail = False
        else:
            previous_was_detail = False
    return result


def _join_wrapped_name_parts(parts: list[str]) -> str:
    result = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        latin_brand = re.fullmatch(r"[（(]([A-Za-z0-9][A-Za-z0-9._+-]*)[）)]", part)
        if latin_brand:
            part = f"({latin_brand.group(1)})"
        if result and re.search(r"[A-Za-z0-9)]$", result) and not re.match(r"[,，。:：;；)）]", part):
            result += " "
        result += part
    return result


def _join_wrapped_name_words(words: list[dict]) -> str:
    result = ""
    for row in _visual_rows(words, tolerance=4):
        row_result = ""
        for word in sorted(row, key=lambda item: item["x0"]):
            part = _join_wrapped_name_parts([str(word["text"])])
            if row_result and re.fullmatch(r"[\u3400-\u9fff]", part):
                row_result += f" {part}"
            else:
                row_result = _join_wrapped_name_parts([row_result, part])
        result += row_result
    return result


def _join_wrapped_column_words(words: list[dict]) -> str:
    """Reconstruct a wrapped non-name detail field in visual reading order."""
    return "".join(
        str(word["text"]).strip()
        for word in sorted(words, key=lambda word: (word["top"], word["x0"]))
    )


def _wrapped_detail_continuations(page_words: list[list[dict]]) -> list[dict]:
    """Return name/spec suffixes from detail rows wrapped within invoice columns."""
    continuations = []
    for words in page_words:
        starts = sorted(
            (
                word for word in words
                if str(word.get("text", "")).startswith("*")
                and DETAIL_COLUMN_BOUNDS["name"][0]
                <= float(word.get("x0", -1))
                < DETAIL_COLUMN_BOUNDS["name"][1]
            ),
            key=lambda word: word["top"],
        )
        for index, start in enumerate(starts):
            next_top = starts[index + 1]["top"] if index + 1 < len(starts) else float("inf")
            summary_tops = [
                word["top"] for word in words
                if word["top"] > start["bottom"]
                and (
                    str(word.get("text", "")) in {"\u5408", "\u5408\u8ba1"}
                    or "\u4ef7\u7a0e\u5408\u8ba1" in str(word.get("text", ""))
                )
            ]
            end_top = min([next_top, *summary_tops])
            wrapped = [
                word for word in words
                if word["top"] > start["bottom"] and word["top"] < end_top
            ]
            start_midpoint = (start["top"] + start["bottom"]) / 2
            inline_name_parts = [
                str(word["text"])
                for word in sorted(words, key=lambda word: word["x0"])
                if word is not start
                and word["x0"] >= start["x1"] - 1
                and word["x0"] < 119
                and abs(((word["top"] + word["bottom"]) / 2) - start_midpoint) <= 4
            ]
            name_words = [word for word in wrapped if word["x0"] < 119]
            spec_words = [word for word in wrapped if 119 <= word["x0"] < 192]
            unit_words = [
                word for word in wrapped
                if DETAIL_COLUMN_BOUNDS["unit"][0] <= word["x0"] < DETAIL_COLUMN_BOUNDS["unit"][1]
            ]
            continuations.append({
                "name": _join_wrapped_name_words(name_words),
                "inline_name": _join_wrapped_name_words([
                    word for word in words
                    if word is not start
                    and word["x0"] >= start["x1"] - 1
                    and word["x0"] < 119
                    and abs(((word["top"] + word["bottom"]) / 2) - start_midpoint) <= 4
                ]),
                "full_name": _join_wrapped_name_parts([
                    str(start["text"]),
                    *inline_name_parts,
                    _join_wrapped_name_words(name_words),
                ]),
                "spec": "".join(str(word["text"]) for word in spec_words),
                "unit": _join_wrapped_column_words(unit_words),
            })
    return continuations


def _apply_detail_continuation(detail, continuation, text_spec_continuation):
    if "*" in continuation["inline_name"]:
        detail["name"] = continuation["full_name"]
        inline_name = continuation["inline_name"]
        if inline_name and detail["spec"].startswith(inline_name):
            detail["spec"] = detail["spec"][len(inline_name) :].lstrip()
    elif "\u4ef7\u7a0e\u5408\u8ba1" not in continuation["full_name"]:
        detail["name"] += continuation["name"]
    if (
        continuation["spec"]
        and continuation["spec"] != text_spec_continuation
        and not detail["spec"].endswith(continuation["spec"])
    ):
        detail["spec"] += continuation["spec"]
    if continuation.get("unit"):
        detail["unit"] += continuation["unit"]


DETAIL_COLUMN_BOUNDS = {
    "name": (0, 119),
    "spec": (119, 192),
    "unit": (192, 240),
    "quantity": (240, 334),
    "unit_price": (334, 406),
    "amount": (406, 446),
    "tax_rate": (446, 551),
    "tax": (551, float("inf")),
}


def _positioned_column_text(words: list[dict], column: str) -> str:
    left, right = DETAIL_COLUMN_BOUNDS[column]
    selected = [
        word for word in words
        if left <= float(word.get("x0", -1)) < right and str(word.get("text", "")).strip()
    ]
    return "".join(
        str(word["text"]).strip()
        for word in sorted(selected, key=lambda word: (word["top"], word["x0"]))
    )


def _recover_left_edge_amount(words: list[dict], quantity: str, unit_price: str):
    candidates = [
        word for word in words
        if 405 <= float(word.get("x0", -1)) < 406
        and str(word.get("text", "")).strip()
    ]
    if len(candidates) != 1:
        return None
    try:
        candidate_amount = _as_decimal(candidates[0]["text"])
        parsed_quantity = Decimal(quantity)
        parsed_unit_price = Decimal(unit_price)
    except (InvalidOperation, KeyError):
        return None
    if not all(
        value.is_finite()
        for value in (candidate_amount, parsed_quantity, parsed_unit_price)
    ):
        return None
    if candidate_amount <= 0 or parsed_quantity <= 0 or parsed_unit_price <= 0:
        return None
    try:
        cent_exact = (parsed_quantity * parsed_unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ) == candidate_amount
    except DecimalException:
        return None
    if not cent_exact:
        return None
    return candidate_amount


def _character_segments(chars: list[dict], row_midpoint: float) -> list[str]:
    selected = sorted(
        (
            char for char in chars
            if DETAIL_COLUMN_BOUNDS["quantity"][0] <= float(char.get("x0", -1))
            < DETAIL_COLUMN_BOUNDS["unit_price"][1]
            and abs(((char["top"] + char["bottom"]) / 2) - row_midpoint) <= 5
        ),
        key=lambda char: char["x0"],
    )
    if not selected:
        return []
    segments = [str(selected[0]["text"])]
    previous = selected[0]
    for char in selected[1:]:
        gap = float(char["x0"]) - float(previous.get("x1", previous["x0"]))
        if gap > 2:
            segments.append(str(char["text"]))
        else:
            segments[-1] += str(char["text"])
        previous = char
    return segments


def _parse_positioned_detail(words: list[dict], chars: list[dict]):
    """Parse one visual invoice row, allowing a quantity/price token split by glyph gap."""
    starts = [
        word for word in words
        if str(word.get("text", "")).startswith("*")
        and DETAIL_COLUMN_BOUNDS["name"][0] <= float(word.get("x0", -1)) < DETAIL_COLUMN_BOUNDS["name"][1]
    ]
    if not starts:
        return None
    start = min(starts, key=lambda word: word["top"])
    row_midpoint = (start["top"] + start["bottom"]) / 2
    inline_words = [
        word for word in words
        if abs(((word["top"] + word["bottom"]) / 2) - row_midpoint) <= 5
    ]
    name = str(start["text"]).strip()
    amount_text = _positioned_column_text(inline_words, "amount")
    tax_text = _positioned_column_text(inline_words, "tax")
    rate = _positioned_column_text(inline_words, "tax_rate")
    quantity = _positioned_column_text(inline_words, "quantity")
    unit_price = _positioned_column_text(inline_words, "unit_price")
    if not name.startswith("*") or not tax_text:
        return None
    if not rate.endswith("%") and rate not in {"免税", "不征税"}:
        return None
    try:
        tax = _as_decimal(tax_text)
    except InvalidOperation:
        return None
    if amount_text:
        try:
            amount = _as_decimal(amount_text)
        except InvalidOperation:
            return None
        amount_words = [
            word for word in inline_words
            if DETAIL_COLUMN_BOUNDS["amount"][0] <= float(word.get("x0", -1))
            < DETAIL_COLUMN_BOUNDS["amount"][1]
        ]
        if not amount_words:
            return None
        amount_word = amount_words[0]
        row_midpoint = (amount_word["top"] + amount_word["bottom"]) / 2
        if not unit_price:
            segments = _character_segments(chars, row_midpoint)
            if len(segments) == 2:
                candidate = _split_merged_quantity_price("".join(segments), amount)
                if candidate == tuple(segments):
                    quantity, unit_price = candidate
            if not unit_price:
                candidate = _split_merged_quantity_price(quantity, amount)
                if candidate:
                    quantity, unit_price = candidate
    else:
        unit_price = _positioned_column_text(
            [
                word for word in inline_words
                if float(word.get("x0", -1)) < 405
            ],
            "unit_price",
        )
        amount = _recover_left_edge_amount(inline_words, quantity, unit_price)
        if amount is None:
            return None
    try:
        if Decimal(quantity) <= 0 or Decimal(unit_price) <= 0:
            return None
    except InvalidOperation:
        return None
    specification = _positioned_column_text(words, "spec")
    if not specification:
        unit_words = [
            word for word in inline_words
            if DETAIL_COLUMN_BOUNDS["unit"][0] <= float(word.get("x0", -1))
            < DETAIL_COLUMN_BOUNDS["unit"][1]
        ]
        if unit_words:
            unit_left = min(word["x0"] for word in unit_words)
            specification = "".join(
                str(word["text"]).strip()
                for word in sorted(
                    (
                        word for word in inline_words
                        if word is not start
                        and word["x0"] >= start["x1"] - 1
                        and word["x0"] < unit_left
                    ),
                    key=lambda word: word["x0"],
                )
            )
    return {
        "name": name,
        "spec": specification,
        "unit": _positioned_column_text(words, "unit"),
        "quantity": quantity,
        "amount": format(amount, ".2f"),
        "tax": format(tax, ".2f"),
    }


def _positioned_details(page_words: list[list[dict]], page_chars: list[list[dict]]):
    details = []
    for words, chars in zip(page_words, page_chars):
        continuations = _wrapped_detail_continuations([words])
        starts = sorted(
            (
                word for word in words
                if str(word.get("text", "")).startswith("*")
                and DETAIL_COLUMN_BOUNDS["name"][0]
                <= float(word.get("x0", -1))
                < DETAIL_COLUMN_BOUNDS["name"][1]
            ),
            key=lambda word: word["top"],
        )
        for index, start in enumerate(starts):
            next_top = starts[index + 1]["top"] if index + 1 < len(starts) else float("inf")
            summary_tops = [
                word["top"] for word in words
                if word["top"] > start["bottom"]
                and (
                    str(word.get("text", "")) in {"合", "合计"}
                    or "价税合计" in str(word.get("text", ""))
                )
            ]
            end_top = min([next_top, *summary_tops])
            row_words = [
                word for word in words
                if word["top"] >= start["top"] - 2 and word["top"] < end_top
            ]
            detail = _parse_positioned_detail(row_words, chars)
            if detail is not None:
                if index < len(continuations):
                    _apply_detail_continuation(detail, continuations[index], "")
                details.append(detail)
    return details


def _parse_detail_line(line, spec_continuation=""):
    tokens = line.split()
    if len(tokens) < 4 or not tokens[0].startswith("*"):
        return None
    try:
        amount = _as_decimal(tokens[-3])
        tax = _as_decimal(tokens[-1])
    except (InvalidOperation, IndexError):
        return None
    if not tokens[-2].endswith("%") and tokens[-2] not in {"\u514d\u7a0e", "\u4e0d\u5f81\u7a0e"}:
        return None

    prefix = tokens[1:-3]
    detail = {
        "name": tokens[0],
        "spec": "",
        "unit": "",
        "quantity": "",
        "amount": format(amount, ".2f"),
        "tax": format(tax, ".2f"),
    }
    if len(prefix) >= 3:
        try:
            Decimal(prefix[-1])
            Decimal(prefix[-2])
        except InvalidOperation:
            return None
        detail["spec"] = " ".join(prefix[:-3])
        if spec_continuation:
            if not detail["spec"]:
                return None
            detail["spec"] += spec_continuation
        detail["unit"] = prefix[-3]
        detail["quantity"] = prefix[-2]
    elif len(prefix) == 2:
        try:
            Decimal(prefix[-1])
            Decimal(prefix[-2])
        except InvalidOperation:
            return None
        detail["quantity"] = prefix[-2]
    elif prefix:
        return None
    return detail


def extract_pdf_record(pdf_path, sequence):
    """Read an invoice PDF and return a record plus explicit parse exceptions."""
    pdf_path = Path(pdf_path)
    exceptions = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            page_words = [getattr(page, "extract_words", lambda: [])() for page in pdf.pages]
            page_chars = [getattr(page, "chars", []) for page in pdf.pages]
            seller_words = [
                word
                for words in page_words
                for word in words
            ]
            tables = [table for page in pdf.pages for table in page.extract_tables()]
    except Exception as error:  # pdfplumber exposes several parser-specific errors.
        return None, [_exception(pdf_path, "pdf", f"unable to read PDF: {error}")]

    invoice_numbers = _invoice_number_candidates(text)
    if len(invoice_numbers) != 1:
        exceptions.append(
            _exception(
                pdf_path,
                "invoice_number",
                f"required unique invoice number could not be parsed; found {len(invoice_numbers)}",
            )
        )

    text_seller = _extract_seller(text)
    word_seller = _extract_seller_from_words(seller_words)
    seller = word_seller or text_seller
    if _is_seller_label_residue(seller):
        seller = ""
    if not seller:
        exceptions.append(_exception(pdf_path, "seller", "required seller could not be parsed"))

    grand_total = _extract_grand_total(text) or _extract_grand_total_from_words(seller_words)
    if grand_total is None:
        exceptions.append(_exception(pdf_path, "grand_total", "required grand total could not be parsed"))

    details = []
    text_spec_continuations = []
    for line, spec_continuation in _invoice_detail_lines(text):
        detail = _parse_detail_line(line, spec_continuation)
        if detail is None:
            exceptions.append(
                _exception(pdf_path, "detail", f"required detail values could not be parsed: {line}")
            )
        else:
            details.append(detail)
            text_spec_continuations.append(spec_continuation)
    for detail, text_spec_continuation, continuation in zip(
        details, text_spec_continuations, _wrapped_detail_continuations(page_words)
    ):
        _apply_detail_continuation(detail, continuation, text_spec_continuation)
    if not details:
        details = _positioned_details(page_words, page_chars)
        if details:
            exceptions = [
                exception for exception in exceptions
                if exception["field"] not in {"detail", "details"}
            ]
    if not details:
        exceptions.append(_exception(pdf_path, "details", "required detail rows could not be parsed"))

    # Keep table extraction in this path so invoice layouts that expose only tables
    # are still inspected without inventing values from unstructured data.
    if not tables:
        exceptions.append(_exception(pdf_path, "tables", "no PDF table could be extracted"))

    if exceptions:
        return None, exceptions

    detail_total = sum(
        (_as_decimal(detail["amount"]) + _as_decimal(detail["tax"]) for detail in details),
        Decimal("0.00"),
    )
    try:
        rows = build_rows(sequence, seller, details)
    except ValueError as error:
        return None, [_exception(pdf_path, "details", str(error))]
    return (
        {
            "pdf": str(pdf_path),
            "sequence": sequence,
            "seller": seller,
            "invoice_number": invoice_numbers[0],
            "grand_total": format(grand_total, ".2f"),
            "detail_total": format(detail_total, ".2f"),
            "details": details,
            "rows": rows,
        },
        [],
    )


def is_verification_report_pdf(pdf_path):
    """Return whether a PDF is a verification report that must be skipped."""
    pdf_path = Path(pdf_path)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        # Let the invoice parser produce the canonical unreadable-PDF exception.
        return False
    return _is_verification_report_text(text)


def _rename_status(source: Path, destination: Path) -> str:
    if source.resolve() == destination.resolve():
        return "unchanged"
    return "collision" if destination.exists() else "ready"


def _pdf_sort_key(path: Path):
    match = re.match(r"^(\d+)\.\s*", path.name)
    if match:
        return (0, int(match.group(1)), path.name.casefold())
    return (1, 0, path.name.casefold())


def _selected_pdfs(arguments):
    selected = [Path(path) for path in arguments.pdf]
    if arguments.pdf_dir:
        selected.extend(Path(arguments.pdf_dir).glob("*.pdf"))
    return sorted(set(selected), key=_pdf_sort_key)


def _load_records(path):
    with Path(path).open(encoding="utf-8") as records_file:
        data = json.load(records_file)
    return data if isinstance(data, dict) else {"records": data}


def _load_excel_totals(path):
    with Path(path).open(encoding="utf-8") as totals_file:
        raw_totals = json.load(totals_file)
    nested_totals = raw_totals.get("sequences")
    sequence_totals = nested_totals if isinstance(nested_totals, dict) else raw_totals
    return {
        "sequences": {
            str(sequence): _as_decimal(total) for sequence, total in sequence_totals.items()
        },
        "acceptance_footer_total": (
            _as_decimal(raw_totals["acceptance_footer_total"])
            if raw_totals.get("acceptance_footer_total") is not None
            else None
        ),
        "issue_footer_total": (
            _as_decimal(raw_totals["issue_footer_total"])
            if raw_totals.get("issue_footer_total") is not None
            else None
        ),
    }


def _verify_records(records, excel_totals):
    verification = []
    exceptions = []
    for record in records:
        sequence = record.get("sequence")
        excel_total = excel_totals.get(str(sequence))
        if excel_total is None:
            exceptions.append(
                _exception(record.get("pdf", ""), "excel_total", f"missing total for sequence {sequence}")
            )
            continue
        result = verify_invoice(
            _as_decimal(record["grand_total"]),
            _as_decimal(record["detail_total"]),
            excel_total,
        )
        result["sequence"] = sequence
        if result["status"] == "failed":
            result["reason"] = "grand_total, detail_total, and excel_total must match exactly to the cent"
        verification.append(result)
    return verification, exceptions


def _verify_batch(records, acceptance_footer_total, issue_footer_total):
    pdf_grand_total_sum = sum(
        (_as_decimal(record["grand_total"]) for record in records), Decimal("0.00")
    )
    result = {
        "status": "passed",
        "pdf_grand_total_sum": format(pdf_grand_total_sum, ".2f"),
        "acceptance_footer_total": (
            format(acceptance_footer_total, ".2f")
            if acceptance_footer_total is not None
            else None
        ),
        "issue_footer_total": (
            format(issue_footer_total, ".2f") if issue_footer_total is not None else None
        ),
    }
    exceptions = []
    for name, footer_total in (
        ("acceptance", acceptance_footer_total),
        ("issue", issue_footer_total),
    ):
        if footer_total is None:
            exceptions.append(_exception("", "footer_total", f"missing {name} footer total"))
        elif footer_total != pdf_grand_total_sum:
            exceptions.append(
                _exception(
                    "",
                    "footer_total",
                    f"{name} footer total must match the PDF grand-total sum exactly to the cent",
                )
            )
    if exceptions:
        result["status"] = "failed"
    return result, exceptions


def _write_json(payload, report_path=None):
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if report_path:
        report = Path(report_path)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(rendered + "\n", encoding="utf-8")
    sys.stdout.write(rendered + "\n")


def _extend_unique_exceptions(target, additions):
    existing = {
        (item.get("pdf"), item.get("field"), item.get("message"))
        for item in target
    }
    for item in additions:
        key = (item.get("pdf"), item.get("field"), item.get("message"))
        if key not in existing:
            target.append(item)
            existing.add(key)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract invoice PDFs without unsafe default actions.")
    parser.add_argument("command", nargs="?", choices=("preview", "rename", "extract", "verify"), default="preview")
    parser.add_argument("--pdf", action="append", default=[], help="selected invoice PDF; repeat for more files")
    parser.add_argument("--pdf-dir", help="directory containing selected invoice PDFs")
    parser.add_argument("--records", help="JSON report produced by preview or extract")
    parser.add_argument("--excel-totals", help="JSON object mapping sequence to Excel total")
    parser.add_argument("--report", help="optional path to write the JSON result")
    parser.add_argument("--apply", action="store_true", help="required before rename mutates any PDF")
    arguments = parser.parse_args(argv)

    payload = {
        "records": [],
        "rename_plan": [],
        "exceptions": [],
        "verification": [],
    }
    if arguments.command == "verify":
        if not arguments.records or not arguments.excel_totals:
            parser.error("verify requires --records and --excel-totals")
        source = _load_records(arguments.records)
        payload["records"] = source.get("records", [])
        excel_totals = _load_excel_totals(arguments.excel_totals)
        payload["verification"], exceptions = _verify_records(
            payload["records"], excel_totals["sequences"]
        )
        payload["batch_verification"], batch_exceptions = _verify_batch(
            payload["records"],
            excel_totals["acceptance_footer_total"],
            excel_totals["issue_footer_total"],
        )
        payload["exceptions"].extend(source.get("exceptions", []))
        payload["exceptions"].extend(exceptions)
        payload["exceptions"].extend(batch_exceptions)
        _write_json(payload, arguments.report)
        return 0

    if arguments.command == "rename" and arguments.records:
        source = _load_records(arguments.records)
        payload["records"] = source.get("records", [])
        _extend_unique_exceptions(payload["exceptions"], source.get("exceptions", []))
    else:
        pdf_paths = _selected_pdfs(arguments)
        invoice_paths = [
            pdf_path for pdf_path in pdf_paths if not is_verification_report_pdf(pdf_path)
        ]
        if not pdf_paths:
            payload["exceptions"].append({"pdf": "", "field": "pdf", "message": "no PDF files selected"})
        for sequence, pdf_path in enumerate(invoice_paths, 1):
            record, exceptions = extract_pdf_record(pdf_path, sequence)
            _extend_unique_exceptions(payload["exceptions"], exceptions)
            if record is not None:
                payload["records"].append(record)

    pairs = [
        (Path(record["pdf"]), record_filename_project(record))
        for record in payload["records"]
    ]
    payload["rename_plan"] = build_rename_plan(
        pairs, [record["sequence"] for record in payload["records"]]
    )
    payload["rename_plan"] = _validate_combined_rename_plan(payload["rename_plan"])

    if arguments.command == "rename" and arguments.apply:
        payload["exceptions"].extend(_apply_rename_entries(payload["rename_plan"]))

    _write_json(payload, arguments.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
