# Template Margin Preservation Implementation Plan

> **For agentic workers:** Use executing-plans to carry out these steps sequentially. Requesting-code-review supplies the independent read-only review.

**Goal:** 清空业务明细时保留主表右侧“第二联：财务报销”等模板内容。

**Architecture:** 从完整表头确定主表列边界。固定区域在内存中快照，主表清空及调整行数后恢复原坐标，公式移动与正式保存复验遵守同一边界。

**Tech Stack:** Python、openpyxl、Tkinter、PyInstaller。

## Global Constraints

- 无发票明细为只读参照，所有业务文件保持不写入。
- 品牌、备注及主表其他手填内容仍清空。
- 不更改 skill 及共享识别引擎，不从外部工作簿自动修复业务模板。
- 不新增或运行测试；只读检查、代码审查、构建和发布资产检查的结论分别记录。

## Steps

- [x] 只读查明验收 K7:K13、领用 I7:I13 的固定文字及表头边界。
- [x] 修改 `invoice_desktop/workbook.py`：限定清空范围，保存及恢复右侧区域，更新计数、恢复匹配、公式转换及保存复验。
- [x] 修改 `invoice_desktop/app.py`、`policy.py`、`__init__.py`、README 与使用说明：显示主表清空／右侧保留范围，版本为 0.1.7。
- [x] 独立只读审查并解决重要问题，记录到 `docs/release-checks.md`。
- [ ] 使用 `tools/build.ps1` 构建，安全替换原发布目录，保留原便携规则。
- [ ] 使用 `tools/package_release.py` 从实际发布目录生成 0.1.7 Windows 与源码包，检查资产和版本、记录发布证据。
