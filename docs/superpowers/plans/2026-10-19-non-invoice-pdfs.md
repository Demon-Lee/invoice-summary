# Non-invoice PDF Handling Implementation Plan

> **For agentic workers:** 当前会话按 executing-plans 实施；requesting-code-review 独立只读复审。

**Goal:** 明确非发票在编号前自动跳过，弹窗与报告说明，发布 1.1.8。

**Architecture:** skill 提供 classify_pdf_document(path) 与可选 skipped_files 元数据；Controller 输入检查复用该函数，旧规则回退使用原接口；界面格式化跳过清单。不改写表算法。

**Tech Stack:** 现有 Python/pdfplumber、Tkinter、快照同步及 PyInstaller。

## Constraints

用户已确认设计边界；不按文件名或解析失败判断跳过，不修改原 PDF／工作簿。不给未知或损坏文件自动放行；无发票时禁止清空重填。同步前保留 skill 原文件及软件规则指针；旧规则 93933610c8ae 保留为 previous。不新增或运行测试套件，不启动 GUI／业务流程；同步自带接口兼容性检查不使用业务输入。此次仅更新本地。

## Task 1：共享分类

**Files:** 本机 skill SKILL.md、scripts/invoice_pipeline.py、commands/invoice-summary.md；仓库 engine 对应共享文件及 manifest.json。

- [ ] 备份实际 skill 三个来源文件、规则指针／快照哈希及 EXE。
- [ ] 实现 classify_pdf_document(pdf_path) -> {kind, reason}，全页读取：明确标题的非发票才跳过；invoice 特征优先于普通表单标题；未知／无文本／不可读取不跳过。查验报告单独分类，混合发票文件保留。
- [ ] main 在编号前分类；skipped_files 不进入 records，unknown 生成明确中文异常；rename／verify 保留元数据。
- [ ] 更新 skill 和命令说明中的查验报告与跳过反馈约定，不扩展清理或写表权限。

## Task 2：软件反馈

**Files:** invoice_desktop/controller.py、ui.py、app.py、policy.py、__init__.py、README.md、使用说明.txt。

- [ ] 输入指纹可选调用同一共享分类函数，旧规则继续使用 is_verification_report_pdf；不能把变化后的未知／发票继续排除。
- [ ] skipped_pdf_notice(payload, limit=None) 生成完整清单和最多八项的弹窗清单；追加到预览／完成报告、摘要与各结果弹窗。非阻塞项保持正常通过，零发票禁止执行。
- [ ] 版本 1.1.8，说明共享分类与软件提示的分工；不改人工校正、按钮、写表和金额计算。
- [ ] 静态 compile／diff 检查；独立只读复审并解决实际缺陷。

## Task 3：规则与发布

- [ ] 使用源 manifest_for_skill 生成完整仓库 engine 快照，明确仅同步共享白名单；保存原 skill 和上一规则，检查没有并发变化。
- [ ] 使用实际 EngineStore.sync 安装更新（执行其必需接口检查，不运行测试套件），保存新旧指针；构建保持已同步新规则。
- [ ] 核对固定依赖、构建路径与重解析点后构建；比对编译代码、活动／上一规则、说明和 EXE。
- [ ] 复查进程、规则、发布目录；暂存逐文件核对，归档旧 1.1.7 后更新原目录。
- [ ] 提交源码／记录，包装 Windows 和源码包，逐成员核对、更新检查记录并重包最终源码，确认 Git 状态。
