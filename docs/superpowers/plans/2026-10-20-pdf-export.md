# PDF Export Implementation Plan

> **For agentic workers:** 当前会话按 executing-plans 实施；requesting-code-review 独立只读复审。

**Goal:** 导出验收单、领用单为两份 A4 横向 PDF，全部列一页宽、行数自动分页，发布本地 1.1.10。

**Architecture:** 新增 pdf_export.py 与软件自有 resources/export_pdf.ps1，读保存副本、原生 Excel 导出及成对发布；pdf_export_ui.py 只选择目录，App 管理导出阶段及反馈。导出与 skill 解耦。

**Tech Stack:** 已有 Python/openpyxl/pdfplumber、Tkinter、Windows PowerShell/.NET/Excel COM、PyInstaller。

## Global Constraints

- 使用已确认 specs/2026-10-20-pdf-export-design.md，沿用现有 feat/desktop-app。
- 不修改 skill、engine、识别／写表算法及业务输入；规则保持 280db9d722ae / 38af3849e1ca。
- 不新增或运行测试，不实际启动 Excel、GUI 或导出业务文件。只做语法／编译、只读审查及构建完整性核对。
- 默认工作簿同级“导出PDF”，允许更换；同名默认不覆盖，确认后才替换；实际输出变化不能静默覆盖。
- 不保存原工作簿打印设置；成对发布失败恢复已有 PDF，无法恢复的备份保留并明确报告。
- 只结束本次新建且 PID／启动时间匹配的 Excel；不能终止用户的 Excel 或主程序。
- 本次更新本地目录及压缩包，不自动上传 GitHub。

## Task 1：独立导出服务

**Files:** 新增 invoice_desktop/pdf_export.py、resources/export_pdf.ps1；修改 invoice_desktop/controller.py 的 ExcelAdapter 新增 export_pdf 入口和可选 timeout。

**Interfaces:** output_fingerprints(directory) -> {filename: sha256|None}；export_workbook_pdfs(workbook, directory, approved, *, progress=None, excel=None) -> dict(status, output_dir, files, error?, cleanup)。sheet plan 包含 name/file_name/print_area/header_row。

- [x] 保存当前 EXE、共享快照和 skill 哈希。
- [x] 从已保存 .xlsx 一致复制，稀疏检查表头／页脚／已填明细，实际内容和合并范围确定 A1 起打印区域。
- [x] 自有 Excel 实例原生导出：A4 横向，一页宽、高度不限、重置手动分页、单表选择；保留或补充重复表头。原文件不写入。
- [x] C# 超时守护仅结束新建且 PID／启动时间匹配的 Excel，finally 关闭副本并释放 COM。
- [x] 检查两份 PDF 都非空、至少一页、每页 A4 横向，再核对原输出指纹后成对替换；失败恢复旧文件，备份恢复失败则保留并报告。

## Task 2：界面与说明

**Files:** 新增 invoice_desktop/pdf_export_ui.py；修改 app.py、ui.py、ui_actions.py、policy.py、__init__.py、README.md、使用说明.txt。

- [x] 原生目录设置弹窗明确“已保存内容”，默认导出PDF子目录，选择其他位置；取消无输出副作用。
- [x] 操作行增加独立 PDF 按钮，报告区增加打开导出目录；忙时禁用、导出时文字反馈。
- [x] 新 export 阶段独立保留原预览及执行状态，不把导出失败当发票处理失败；导出报告附上原检查结果，完成弹窗列出路径与页数。
- [x] 软件版本 1.1.10，功能归属明确 PDF 导出由软件维护。
- [x] Python compile、PowerShell AST 解析、C# 类型编译及 diff 检查；独立只读复审并解决实际问题。

## Task 3：构建与交付

- [x] 检查固定依赖、构建／发布绝对路径与重解析点，构建退出 0；核对编译代码、新资源、说明、活动及上一规则和 source skill 哈希。
- [x] 原目录未占用且规则未变化时暂存逐文件核对，归档 1.1.9 后更新 release/InvoiceSummary；有占用则请用户关闭，不强制结束。
- [x] 提交实现／记录，包装完整 Windows 和源码压缩包，逐成员读取核对及 SHA256.json；最终记录提交后重包源码，保持 Git 状态干净。

## 完成记录

实现提交 b991571。最终只读复审无待处理问题，静态 Python／PowerShell／C# 编译及构建完成。1.1.10 已放回原软件目录，1.1.9 保留在带时间戳归档中；EXE 内 14 个源码模块、1311 个发布文件、13 个活动／上一规则文件、Windows ZIP 和 119 项源码逐项核对。详见 docs/release-checks.md 的 1.1.10 记录。

未启动应用、Excel 或实际导出；实际分页和 COM 行为由用户试用确认。本轮没有上传 GitHub。
