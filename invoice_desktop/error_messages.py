"""Short user-facing summaries; original diagnostics stay in the full report."""

import re


def error_summary(value):
    text = str(value).strip()
    lower = text.lower()
    if "恢复未完成" in text:
        directory = re.search(r"请保留并核对恢复目录[:：]\s*([^\r\n]+)", text)
        location = "\n恢复目录：" + directory.group(1).strip() if directory else ""
        return ("文件恢复未完成。请先保留恢复目录并核对现有文件，暂勿直接重试；点击“复制错误信息”反馈给维护者。"
                + location)
    fields = {
        "invoice_number": "发票号码", "seller": "销售方", "grand_total": "价税合计",
        "details": "项目明细", "detail": "项目明细中的必要字段",
    }
    first_line = text.splitlines()[0] if text else ""
    _, separator, field_text = first_line.partition(" · ")
    field = re.match(r"\s*(invoice_number|seller|grand_total|details|detail)\s*[:：]",
                     field_text if separator else first_line, flags=re.I)
    if field and "could not be parsed" in lower:
        name = text.split(" · ", 1)[0] if " · " in text else ""
        prefix = name[:65] + "：" if name and "\n" not in name else ""
        return (prefix + f"未能完整识别{fields[field.group(1).lower()]}。"
                "请核对该 PDF 的内容，再重新预览；仍有问题时点击“复制错误信息”反馈。")
    if "排版超时" in text or ("excel" in lower and any(s in lower for s in ("timeout", "timed out"))):
        return "Excel 处理超时。请关闭目标工作簿，按阶段提示重试；再次失败时点击“复制错误信息”反馈。"
    if "0x800706ba" in lower or "rpc server is unavailable" in lower:
        return "与 Excel 的连接已中断。请确认目标工作簿已关闭，重新预览后再试；再次失败时点击“复制错误信息”反馈。"
    if any(s in lower for s in ("permission denied", "access is denied", "winerror 32", "winerror 5")) or any(
            s in text for s in ("被占用", "没有写入权限", "无法写入", "文件夹无法写入", "拒绝访问")):
        return "无法访问或修改文件。请关闭对应文件，并确认所在文件夹有读写权限后重试。"
    if "merged cells" in lower or "合并单元格" in text:
        return "表格的合并单元格不符合处理要求。请核对模板，重新预览后再试。"
    if any(s in lower for s in ("content fitting failed", "detail autofit failed", "row-height capacity", "409 pt", "409pt")):
        return "Excel 未能自动调整表格。请核对过长的文字和模板布局，重新预览后再试。"
    if "PDF 完整排版校验" in text:
        return "PDF 未通过内容完整性检查，已停止替换已有 PDF。请点击“复制错误信息”反馈具体位置。"
    if any(s in text for s in ("逐分金额验证失败", "金额与明细金额不一致", "金额核对未通过")):
        return "金额核对未通过。请核对发票与两张表的金额，再重新预览。"
    if "excel" in lower and any(s in lower for s in ("class not registered", "80040154")):
        return "无法启动 Microsoft Excel。请确认已安装可正常打开工作簿的 Excel 桌面版。"
    if "manifest.json" in lower and any(s in lower for s in ("missing", "not found", "hash", "缺少", "损坏")):
        return "软件或识别规则文件不完整。请重新完整解压软件包，或联系维护者。"
    # Preserve an already concise Chinese business message, excluding paths,
    # traceback fragments and untranslated technical words.
    if text and len(text) <= 160 and "\n" not in text and re.search(r"[\u4e00-\u9fff]", text):
        remaining = re.sub(r"\b(?:PDF|Excel|Microsoft|Windows|PNG|JPG|JPEG|xlsx|A4)\b", "", text, flags=re.I)
        if not re.search(r"[A-Za-z]:[\\/]|[A-Za-z_]{3,}|0x[0-9a-f]+", remaining, flags=re.I):
            return text
    return "暂时无法确定具体原因。请点击“复制错误信息”，反馈给维护者排查。"
