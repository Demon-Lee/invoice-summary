"""Application-owned boundaries; never supplied by a skill update package."""

LEGACY_SHARED_FILES = ("SKILL.md", "invoice_pipeline.py", "collect_excel_totals.py", "apply_mixed_fonts_excel.ps1")
SHARED_FILES = (*LEGACY_SHARED_FILES, "template_rules.json")
SOFTWARE_POLICY_VERSION = 1
DATA_CONTRACT_VERSION = 1
WORKBOOK_CONTRACT_VERSION = 1
TEMPLATE_RULES_CONTRACT_VERSION = 1
# Pin the skill adapters whose common template contract was reviewed.
LEGACY_WRITER_SHA256 = "6b196680c47d483ec11c3216282b2147781e02420f38a47c627c879e8777a2b9"
TEMPLATE_WRITER_SHA256 = "aa8b7aac7fb0ce62e1771d0a41aec821c4898b28a99ce5dc0a250f0ff6b2a9b7"
SUPPORTED_TEMPLATE_WRITER_SHA256S = frozenset({
    "a2392109e01f7d3ae7ae2e57769dd7b7dbedb291539d0b339a21f8b438853a85",
    TEMPLATE_WRITER_SHA256,
})


def shared_scope(format_version=3):
    scope = {
        "update_scope": "shared-invoice-rules",
        "data_contract_version": DATA_CONTRACT_VERSION,
        "workbook_contract_version": WORKBOOK_CONTRACT_VERSION,
    }
    if format_version >= 3:
        scope["template_rules_contract_version"] = TEMPLATE_RULES_CONTRACT_VERSION
    return scope


def snapshot_files(manifest):
    return SHARED_FILES if manifest["format_version"] == 3 else LEGACY_SHARED_FILES


def validate_scope(manifest):
    version = manifest.get("format_version")
    if type(version) is not int or version not in (1, 2, 3):
        raise ValueError("更新包格式不兼容，需要升级软件")
    fields = {"format_version", "version", "files", "source_writer_sha256"}
    if version == 1:
        if set(manifest) != fields:
            raise ValueError("旧格式更新包含未支持的范围声明，请重新导出")
        if DATA_CONTRACT_VERSION != 1 or WORKBOOK_CONTRACT_VERSION != 1:
            raise ValueError("旧格式更新包未声明当前软件的新接口版本；请适配共享规则后重新导出")
        return
    scope = manifest.get("scope")
    expected = shared_scope(version)
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
        "template_rules.json": "模板最低保留行规则（按侧边标识实际位置判断）",
        "write_summary.mjs": "共享写表约定适配",
        "manifest.json": "更新范围与接口版本声明",
    }
    return [labels[name] for name in changed if name in labels]


RETAINED_FEATURES = "人工校正、清空主表旧明细并整批重填、保留右侧模板文字、WPS优先与Excel后备、单元格完整显示与末尾同页排版、阶段完成提示、中断恢复、验收与领用 PDF 导出、便携签名库与 PDF 签名"

BOUNDARY_GUIDE = """功能归属与更新边界

一、与 skill 保持一致：共享规则
PDF内容分类、识别、字段提取和规范化、折扣／运费、重复明细、排序／文件名及逐分金额核对；字体、重算与金额采集采用对应共享脚本。只跳过内容明确的非发票，类型不明、扫描件或疑似发票缺字段仍停止。
模板最低保留行使用共享template_rules.json，按完整侧边标识最后一个字的实际行保留必要空白明细，合计放在保留区域之后；不得写死行号。右侧内容须为固定值，公式报告坐标并停止。
这些规则由维护者在维护环境准备，经兼容性检查后随完整软件包分发。

二、软件独有功能：随软件版本更新
人工校正已有明细的六项字段；正式执行前清空两表主表旧明细（含品牌、备注）并整批重填，保留右侧模板文字；阶段提示、中断恢复、PDF导出和便携分发由软件维护。人工校正只作用于本次处理，不回写或训练skill。
PDF分别导出验收单和领用单，A4横向、所有列一页宽、明细向下分页。仅本次执行及金额核对成功后启用，输入／规则变化、重新预览或重启后须重新处理；导出前确认完成工作簿未变，普通失败可重试。
软件自动优先选择WPS，无法创建可用的独立WPS实例时再选择Excel；处理开始后不切换。办公软件激活、独立实例确认及字体脚本创建入口适配由软件维护，原共享字体脚本不改写或另存规则。
所有明细列由软件调用所选表格软件的原生自动列宽，保留原列宽/行高下限、内容、字体和数字格式；达到列宽上限时换行，使用未合并的标准明细区，标题及页脚合并保持。容量不足或错误值会停止发布排版副本。导出优先让最后一条明细至合计、签字、说明同页，最多额外缩小约5%，仍不足时整组移至下一页；超过单页容量时停止。分页设置只保存在导出副本中。
统一签名库、签名标签与四处位置选择由软件维护；个人图片与配置保存在软件旁signatures文件夹，只在PDF中添加，原Excel不添加签名。签名按四处最小可用框等比例适配；转移个人软件时复制整个目录，公开发布包排除个人签名。

三、双方共同遵守：数据与模板约定
字段含义、金额精度、序号、表头、三行页脚、日期（领用当天、验收前一天）、单价／合计及共享脚本输入输出接口保持一致。未知策略、写表器、依赖或接口变化须先适配软件。

软件执行流程
识别 → 可选人工校正 → 重新检查 → 清空旧明细并整批重填 → 写后金额核对 → 可选导出PDF。只读预览和校正不保存工作簿；漏项、多项及整票识别问题由维护者改进识别规则。

规则来源与分发
1.1.18起软件界面没有规则管理、来源绑定或规则更新入口，直接使用随包规则；识别版本在预览报告中显示。旧本机skill来源设置不再读取或监测，业务恢复记录继续保留。
普通使用者完整解压软件包，保留_internal和recognition即可。需要新规则时获取维护者发布的完整新版软件包。
维护者在源码维护环境更新skill及对应脚本和声明，使用既有开发接口准备规则、构建并打包整个软件文件夹分发。SKILL.md仅作规则来源，文字变化不会自动生成算法，其中的对话回复格式和增量写表流程不作为软件界面操作指令。
"""
