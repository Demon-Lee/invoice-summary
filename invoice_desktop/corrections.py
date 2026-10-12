"""Application-only field overlays; source records and row structure stay fixed."""
import copy
import math
import re
from decimal import Decimal, InvalidOperation

FIELDS = ("product_name", "spec", "unit", "quantity", "amount", "manufacturer")
LABELS = dict(zip(FIELDS, ("产品名称", "规格型号", "单位", "数量", "含税金额", "生产厂家")))


def field_value(row, field):
    value = str(row.get(field) or "").strip()
    return value or "1" if field == "quantity" else value


def normalize(values):
    if not isinstance(values, dict) or set(values) - set(FIELDS):
        raise ValueError("人工校正仅允许修改已有明细的六项字段")
    result = {}
    for field, value in values.items():
        value = str(value if value is not None else "").strip()
        if len(value) > 32767 or any(ord(char) < 32 for char in value):
            raise ValueError(f"{LABELS[field]}包含无效字符或内容过长")
        if field in ("product_name", "manufacturer") and not value:
            raise ValueError(f"{LABELS[field]}不能为空")
        if field in ("quantity", "amount"):
            if field == "quantity" and not value:
                value = "1"
            try:
                parsed = Decimal(value.replace(",", ""))
                converted = float(parsed)
                if not parsed.is_finite() or not math.isfinite(converted) or (parsed != 0 and converted == 0):
                    raise ValueError("数字无效")
                if field == "quantity" and parsed == 0:
                    raise ValueError("数量不能为零")
                if field == "amount" and parsed != parsed.quantize(Decimal("0.01")):
                    raise ValueError("金额最多保留两位小数")
            except (InvalidOperation, OverflowError, ValueError) as exc:
                raise ValueError(f"{LABELS[field]}必须为有效{'逐分金额' if field == 'amount' else '非零数字'}") from exc
            significant_digits = len("".join(map(str, parsed.as_tuple().digits)).rstrip("0"))
            if significant_digits > 15 or Decimal(str(converted)) != parsed:
                raise ValueError(f"{LABELS[field]}超出 Excel 可准确保存的数字精度（最多 15 位有效数字）")
            value = format(parsed, ".2f" if field == "amount" else "f")
        result[field] = value
    if "quantity" in result and "amount" in result:
        try:
            price = Decimal(result["amount"]) / Decimal(result["quantity"])
            converted = float(price)
            if not math.isfinite(converted) or (price != 0 and converted == 0):
                raise ValueError("单价超出 Excel 可用数字范围")
        except (InvalidOperation, OverflowError, ZeroDivisionError) as exc:
            raise ValueError("单价超出 Excel 可用数字范围") from exc
    return result


def row_changes(original_row, values):
    changes = {}
    for field, value in normalize(values).items():
        before = field_value(original_row, field)
        try:
            before = normalize({field: before})[field]
        except ValueError:
            pass
        if value != before:
            changes[field] = value
    return changes


def apply_corrections(original, changes):
    payload = copy.deepcopy(original)
    amount_records = set()
    if not isinstance(changes, dict):
        raise ValueError("人工校正记录格式无效")
    for key, values in changes.items():
        if not isinstance(key, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*):(?:0|[1-9][0-9]*)", key):
            raise ValueError("人工校正明细位置无效")
        record_index, row_index = map(int, key.split(":"))
        try:
            row = payload["records"][record_index]["rows"][row_index]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("人工校正明细已不存在，请重新预览") from exc
        values = normalize(values)
        row.update(values)
        if "amount" in values:
            amount_records.add(record_index)
    for index in amount_records:
        record = payload["records"][index]
        try:
            total = sum((Decimal(str(row["amount"]).replace(",", "")) for row in record["rows"]), Decimal("0.00"))
            record["detail_total"] = format(total, ".2f")
        except (InvalidOperation, KeyError, TypeError) as exc:
            raise ValueError("校正后的明细金额无效") from exc
    return payload
