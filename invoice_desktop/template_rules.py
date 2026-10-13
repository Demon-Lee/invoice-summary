"""Interpret the versioned template policy also consumed by the skill writer."""
import json
import re
from pathlib import Path


def _normalize(value, ignored):
    # ECMAScript whitespace, matching the skill writer's /\s/gu.
    normalized = re.sub(r"[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]", "", "" if value is None else str(value))
    for character in ignored:
        normalized = normalized.replace(character, "")
    return normalized


def validate_template_rules(rules):
    if (not isinstance(rules, dict) or set(rules) != {"schema_version", "minimum_detail_area"}
            or type(rules["schema_version"]) not in (int, float) or rules["schema_version"] != 1):
        raise ValueError("模板规则版本不兼容，请升级软件后再同步")
    area = rules["minimum_detail_area"]
    keys = {"strategy", "label_value_source", "labels", "ignore_characters", "allow_single_cell", "allow_vertical_cells"}
    if (not isinstance(area, dict) or set(area) != keys or area["strategy"] != "sidebar-label-end"
            or area["label_value_source"] != "literal-cells"
            or not isinstance(area["labels"], list) or not 1 <= len(area["labels"]) <= 16
            or not isinstance(area["ignore_characters"], str) or len(area["ignore_characters"]) > 32
            or type(area["allow_single_cell"]) is not bool or type(area["allow_vertical_cells"]) is not bool
            or not (area["allow_single_cell"] or area["allow_vertical_cells"])):
        raise ValueError("模板规则策略或字段不兼容，请适配共享规则并升级软件")
    labels = area["labels"]
    if any(not isinstance(label, str) or len(label) > 160 or not _normalize(label, area["ignore_characters"]) for label in labels):
        raise ValueError("模板规则中的完整标识为空或过长")
    if len(set(_normalize(label, area["ignore_characters"]) for label in labels)) != len(labels):
        raise ValueError("模板规则中的完整标识重复")
    return rules


def read_template_rules(path):
    return validate_template_rules(json.loads(Path(path).read_text(encoding="utf-8")))


def load_template_rules(engine_dir):
    # Old snapshots have no template policy and retain their previous behavior.
    from .updates import read_manifest
    manifest = read_manifest(engine_dir)
    if manifest["format_version"] < 3:
        return None
    return read_template_rules(Path(engine_dir) / "template_rules.json")


def minimum_retained_row(ws, header, last_column, rules):
    """Return the last actual row of a complete side label, or None (one based)."""
    if rules is None:
        return None
    area = validate_template_rules(rules)["minimum_detail_area"]
    targets = [_normalize(label, area["ignore_characters"]) for label in area["labels"]]
    last = None
    for row in ws.iter_rows(min_row=header+1, min_col=last_column+1):
        for cell in row:
            if cell.data_type == "f":
                raise ValueError(f"{ws.title} 右侧模板 {cell.coordinate} 包含公式，无法确定标识实际所在行；请使用固定文字后重新预览")
    for column in range(last_column + 1, ws.max_column + 1):
        for start in range(header + 1, ws.max_row + 1):
            first = _normalize(ws.cell(start, column).value, area["ignore_characters"])
            if not first:
                continue
            for target in targets:
                if not target.startswith(first):
                    continue
                joined = ""
                for row in range(start, ws.max_row + 1):
                    original = ws.cell(row, column).value
                    if original is None or not str(original).strip():
                        break
                    joined += _normalize(original, area["ignore_characters"])
                    if not target.startswith(joined):
                        break
                    allowed = area["allow_single_cell"] if row == start else area["allow_vertical_cells"]
                    if joined == target and allowed:
                        last = max(last or header, row)
                        break
                    if not area["allow_vertical_cells"]:
                        break
    return last
