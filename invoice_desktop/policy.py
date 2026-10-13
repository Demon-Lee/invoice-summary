"""Application-owned boundaries; never supplied by a skill update package."""

SHARED_FILES = ("SKILL.md", "invoice_pipeline.py", "collect_excel_totals.py", "apply_mixed_fonts_excel.ps1")
SOFTWARE_POLICY_VERSION = 1
DATA_CONTRACT_VERSION = 1
WORKBOOK_CONTRACT_VERSION = 1


def shared_scope():
    return {
        "update_scope": "shared-invoice-rules",
        "data_contract_version": DATA_CONTRACT_VERSION,
        "workbook_contract_version": WORKBOOK_CONTRACT_VERSION,
    }


def validate_scope(manifest):
    version = manifest.get("format_version")
    if type(version) is not int or version not in (1, 2):
        raise ValueError("更新包格式不兼容，需要升级软件")
    fields = {"format_version", "version", "files", "source_writer_sha256"}
    if version == 1:
        if set(manifest) != fields:
            raise ValueError("旧格式更新包含未支持的范围声明，请重新导出")
        if DATA_CONTRACT_VERSION != 1 or WORKBOOK_CONTRACT_VERSION != 1:
            raise ValueError("旧格式更新包未声明当前软件的新接口版本；请适配共享规则后重新导出")
        return
    scope = manifest.get("scope")
    expected = shared_scope()
    if (not isinstance(scope, dict) or set(scope) != set(expected)
            or any(type(scope[key]) is not type(value) or scope[key] != value for key, value in expected.items())):
        raise ValueError("更新包的作用范围或数据／工作簿接口版本不兼容；请升级软件后再同步。人工校正和清空重填由软件维护。")
    if set(manifest) != (fields | {"scope"}):
        raise ValueError("更新包包含未支持的声明；仅允许更新共享规则")


def describe_changes(changed):
    labels = {
        "SKILL.md": "共享规则来源说明",
        "invoice_pipeline.py": "PDF 识别、排序、文件名与金额核对",
        "collect_excel_totals.py": "写后金额采集与页脚检查",
        "apply_mixed_fonts_excel.ps1": "字体处理与 Excel 重算",
        "manifest.json": "更新范围与接口版本声明",
    }
    return [labels[name] for name in changed if name in labels]


RETAINED_FEATURES = "人工校正、清空旧明细并整批重填、阶段完成提示、中断恢复"

BOUNDARY_GUIDE = """功能归属与更新边界

一、与 skill 保持一致：共享规则
PDF 内容识别、字段提取与规范化、折扣和运费处理、重复明细保留、排序和文件名生成、逐分金额核对。字体处理、Excel 重算和写后金额采集采用对应的共享脚本。
同步或导入 skill 更新包，只更新这些共享脚本及其来源说明。

二、软件独有功能：随软件版本更新
人工校正已有明细的六项字段；正式执行前清空两表全部旧明细（含品牌、备注）并整批重填；完成提示；中断恢复；界面操作和整文件夹分发。
这些功能由软件自身管理，同步、导入或回退 skill 规则均会保留。人工校正只作用于本次处理，不回写或训练 skill。

三、双方共同遵守：数据与模板约定
字段含义、金额精度、发票和明细序号、表头、三行页脚、签字日期、单价和合计，以及识别、改名、金额采集与验证接口。
更新包的范围或接口版本不兼容时停止导入。skill 写表组件变化时，须核对共享约定并适配软件后重新发布；软件的人工校正和清空重填策略继续保留。

软件执行流程
skill 识别 → 可选人工校正 → 重新校验 → 正式执行时清空旧明细并整批重填 → 写后金额复核。
只读预览和校正不保存工作簿。结构识别问题（例如漏项）仍需改进 skill；校正后的每票金额必须与原票面总额逐分一致。

原始 skill 说明的适用范围
软件保留原文供查看识别来源。skill 的对话回复格式、对话中的自动执行步骤和增量匹配填表方式属于 skill 工作流；软件采用上述界面流程和整批重填方式。原文不会作为修改软件功能的指令执行。

以后更新与分发
更新 skill 的规则及对应脚本 → 软件中同步本机 skill → 查看更新范围和兼容性结果 → 关闭软件 → 打包整个 InvoiceSummary 文件夹发给对方。
共享规则版本与软件版本分别显示。若需要改进人工校正或清空重填等软件功能，应升级软件；接收方完整解压后直接运行。
"""
