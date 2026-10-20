# Completed Processing PDF Export Gate Implementation Plan

> **For agentic workers:** 当前会话按executing-plans实施，requesting-code-review独立只读复审。

**Goal:** 1.1.13 只允许导出本次执行成功并通过金额核对的工作簿。

**Architecture:** App记录会话级完成资格，按钮及实际点击共用检查；后台导出服务在稳定副本创建时检查完成哈希。资格不持久保存，不修改Controller和打印脚本。

**Tech Stack:** 现有Python／Tkinter／SHA256／Excel导出及PyInstaller便携构建。

## Global Constraints

- 采用用户已确认的specs/2026-10-20-export-gate-design.md，沿用feat/desktop-app及当前规则。
- 不改识别、写表、金额算法、skill、打印脚本或既有界面布局；仅软件自有流程资格及说明。
- 不新增或运行测试，不启动GUI／Excel或业务流程；只静态编译、只读复审、构建／文件完整性核对。

## Task 1：完成资格和导出检查

- [x] 保存当前EXE／规则／受保护源文件基线。
- [x] 初始化资格为空，输入接受变更和新的预览／校正／执行清空；仅completed后在后台获取完成文件指纹并绑定原输入。
- [x] 主按钮、点击前及目录／覆盖确认后统一检查资格；普通导出失败、取消和重复导出保留资格。
- [x] pdf_export.py增加可选expected_workbook_sha256，稳定快照与完成哈希匹配才调用Excel；失配结构化返回requires_processing并由App撤销资格。
- [x] 更新主提示、完成报告、弹窗、软件归属及当前说明为1.1.13，删除直接导出已有工作簿的现行操作说明。

## Task 2：复审、构建、交付

- [x] 纯Python编译、引用／说明搜索及diff检查；独立只读核对全部状态路径、线程／弹窗及快照竞态，修正实际问题。
- [ ] 检查路径／重解析点，构建退出0，核对EXE内14模块、资源、规则及受保护源文件；暂存逐文件校验。
- [ ] 确认旧程序未占用及原哈希不变后归档1.1.12，更新release/InvoiceSummary，不结束用户程序。
- [ ] 提交实现和发布记录，生成Windows／源码包，逐成员读取对应发布／Git文件并核对SHA256.json；记录提交后重包源码，Git状态干净。
