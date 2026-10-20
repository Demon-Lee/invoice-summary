# UI Text Trim Implementation Plan

> **For agentic workers:** 按用户已指定的删除方案，在本会话使用executing-plans实施，requesting-code-review完成独立只读复审。

**Goal:** 1.1.14删除两行冗余文字和使用说明主选项卡。

**Architecture:** ui.py删除控件、主表行号连续排列；app.py删除已无控件使用的帮助／说明数据，保留预览按钮清除校正的文案行为。业务模块不改动。

**Tech Stack:** 现有Python／Tkinter和PyInstaller便携构建。

## Global Constraints

- 用户的三项明确删除为最终范围，不再要求重复确认；沿用当前feat/desktop-app分支及已激活规则。
- 不新增或运行测试、GUI、Excel或业务流程，仅静态编译、独立只读复审和构建／包完整性检查。
- 本次本地更新release/InvoiceSummary，保留旧版目录，生成Windows／源码包；不上传GitHub。

## Task 1：界面删减

- [ ] 保存当前EXE、规则、skill、engine及受保护业务源文件基线。
- [ ] ui.py删除process_notice／preview_note／help_text参数，删除通知控件、明细说明控件、help_tab及帮助内容；主表各区行号依次0至8，rowconfigure(6, weight=1)保持明细扩展。
- [ ] app.py删除PROCESS_NOTICE／PREVIEW_NOTE／HELP与preview_note变量；_build参数同步。_update_preview_note改为_update_preview_button，仅在有校正且非恢复期间显示“重新预览（清除校正）”，其他情况“只读预览”；三个调用点同步。HELP_HEADINGS缩减命名为BOUNDARY_HEADINGS，保留规则页标题格式化。
- [ ] 版本改为1.1.14，README及使用说明反映仅两个主页面，并保留外部说明文件。
- [ ] 静态编译14模块、无旧引用、diff检查及独立复审；修复实际问题。

## Task 2：本地交付

- [ ] 构建退出0，核对EXE中14模块、资源、规则和受保护源文件，暂存逐文件哈希一致。
- [ ] 确认原程序未占用并检查绝对路径及重解析点，归档1.1.13，更新原软件目录。
- [ ] 提交实现及发布记录、生成两类ZIP，逐成员对应发布／Git源码并核对SHA256；记录提交后重包源码并确认工作区干净。
