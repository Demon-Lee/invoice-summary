# Non-invoice PDF Handling Implementation Plan

> **For agentic workers:** 当前会话按 executing-plans 实施；requesting-code-review 独立只读复审。

**Goal:** 明确非发票在编号前自动跳过，弹窗与报告说明，发布 1.1.8。

**Architecture:** skill 提供 classify_pdf_document(path) 与可选 skipped_files 元数据；Controller 为支持该函数的新规则固定全部 PDF 输入指纹，以保持跳过清单有效，旧规则回退使用原接口；界面格式化跳过清单。不改写表算法。

**Tech Stack:** 现有 Python/pdfplumber、Tkinter、快照同步及 PyInstaller。

## Constraints

用户已确认设计边界；不按文件名或解析失败判断跳过，不修改原 PDF／工作簿。不给未知或损坏文件自动放行；无发票时禁止清空重填。同步前保留 skill 原文件及软件规则指针；旧规则 93933610c8ae 保留为 previous。不新增或运行测试套件，不启动 GUI／业务流程；同步自带接口兼容性检查不使用业务输入。此次仅更新本地。

## Task 1：共享分类

**Files:** 本机 skill SKILL.md、scripts/invoice_pipeline.py、commands/invoice-summary.md；仓库 engine 对应共享文件及 manifest.json。

- [x] 备份实际 skill 三个来源文件、规则指针／快照哈希及 EXE。
- [x] 实现 classify_pdf_document(pdf_path) -> {kind, reason}，全页读取：明确标题的非发票才跳过；invoice 特征优先于普通表单标题；未知／无文本／不可读取不跳过。查验报告单独分类，混合发票文件保留。
- [x] main 在编号前分类；skipped_files 不进入 records，unknown 生成明确中文异常；rename／verify 保留元数据。
- [x] 更新 skill 和命令说明中的查验报告与跳过反馈约定，不扩展清理或写表权限。

## Task 2：软件反馈

**Files:** invoice_desktop/controller.py、ui.py、app.py、policy.py、__init__.py、README.md、使用说明.txt。

- [x] 新规则将全部 PDF 纳入输入完整性检查，防止预览后的跳过清单过期；不把跳过文件计作发票。旧规则继续使用 is_verification_report_pdf 原逻辑。
- [x] skipped_pdf_notice(payload, limit=None) 生成完整清单和最多八项的弹窗清单；追加到预览／完成报告、弹窗摘要与各结果弹窗。非阻塞项保持正常通过，零发票禁止执行。
- [x] 版本 1.1.8，说明共享分类与软件提示的分工；不改人工校正、按钮、写表和金额计算。
- [x] 静态 compile／diff 检查；独立只读复审并解决实际缺陷。

## Task 3：规则与发布

- [x] 使用源 manifest_for_skill 生成完整仓库 engine 快照，明确仅同步共享白名单；保存原 skill 和上一规则，检查没有并发变化。
- [x] 使用实际 EngineStore.sync 在隔离规则暂存目录安装更新（执行其必需接口检查，不运行测试套件），保存新旧指针；构建保持已同步新规则。
- [x] 核对固定依赖、构建路径与重解析点后构建；比对编译代码、活动／上一规则、说明和 EXE。
- [x] 复查进程、规则、发布目录；暂存逐文件核对，归档旧 1.1.7 后更新原目录。
- [x] 提交源码／记录，包装 Windows 和源码包，逐成员核对、更新检查记录并重包最终源码，确认 Git 状态。

## 实施记录

- skill 三文件原内容保存在忽略目录 .superpowers/non-invoice-baseline/skill，原规则指针 93933610c8ae / 6b9e6cdafb3f 和哈希同目录保留。
- 独立静态复审关闭三项分类缺陷：未知页必须优先阻塞；同页原票标题与查验标记冲突时不得跳过；“普通发票兼送货单”等原票／普通表单混合标题也优先保留。类型字段名称不当作原票标题。
- “摘要”说明限定为实际存在的预览通过弹窗摘要。新规则完整输入指纹修正后再次只读复审，无剩余 Critical / Important / Minor。
- 新规则 38af3849e1ca，previous 93933610c8ae；两次实际同步流程在隔离暂存目录执行其空输入接口检查，未使用业务 PDF／工作簿。未发布的中间规则未成为最终 previous。
- 仓库 engine 采用同一五文件快照及模板规则，保证源码独立构建有新功能；源 writer 哈希未变。相比本次前的最新 skill，原明细解析、字段规范化、金额及改名函数 AST 不变。
- 固定依赖、Python 静态语法、diff 空白检查通过；最终构建退出 0，六个 PYZ 模块编译代码与源码一致；bundled／active 与本机 skill 的共享清单、活动／上一规则和说明文件逐项匹配。
- 发布目录 1316 文件暂存逐个 SHA-256 核对，原目录归档为 release/InvoiceSummary-1.1.7-archive-20261019-173149，再更新原路径。原业务目录记录的 18 个输入哈希未变。
- 新 EXE SHA-256：a462afa7253fd07b6cbd7e5325f7d9e991118dcfb3f312efb70b331c9c46b781。
- 实现提交 e245ffc；Windows 包 1316 成员、源码包 114 成员全部读取核对发布目录／Git 跟踪源文件，SHA256.json 匹配；当前五个共享文件与本机 skill 一致，原 EXE／规则备份逐文件匹配。最终记录提交后重新包装并重新核对源码包，收据位于 .superpowers/non-invoice-package-verification.json。
- 未运行测试套件、GUI、原始 PDF 预览或 Excel 处理；实际版式分类和弹窗交互待用户确认。本次不上传 GitHub。
