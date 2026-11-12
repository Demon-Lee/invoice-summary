# 导出窗口签名选择 Implementation Plan

**Goal:** 在导出确认窗口直接选择四个位置的签名并在开始导出时记住人选。

**Architecture:** 使用独立 ExportSignaturePicker 面板维护草稿、下拉框和后台预览；SignatureTasks 串行读取、生成预览和提交选择；SignatureStore 在同一锁内验证、构造快照和保存。导出绘制流程接收原有不可变快照，不更改。

**Tech Stack:** Python 3.12、Tkinter/ttk、Pillow、现有 SignatureTasks、PyInstaller。

## Global Constraints

- 已确认设计见同日 specs/2026-11-12-export-signature-picker-design.md。
- 保留现有私人图片和配置、13 份便携规则及本机 skill，公开包排除签名和业务文件。
- 不新增或运行测试；静态/语法、构建和文件完整性检查作为本次核对范围。
- 版本 1.1.24，仅本地交付。复用当前清洁 checkout，使用独立功能分支；不新增工作树。

## Task 1: 原子保存导出签名选择

Files: invoice_desktop/signatures.py、invoice_desktop/signature_tasks.py。

- [x] 保留 snapshot(expected_revision=None)，提取 _snapshot(config) 供两个入口共用。
- [x] 新增 save_export_selection(bindings, expected_revision=None)：完整校验四个位置，在原锁内构造图片快照成功后才调用 _save；返回快照。
- [x] SignatureTasks 的 save_export 请求直接返回上述快照，避免额外 read 与保存后状态竞争。
- [x] 静态检查非法位置、无效图片、版本冲突、全空选择与保存失败路径；纯语法编译。

## Task 2: 导出窗口选择面板

Files: 新建 invoice_desktop/export_signature_ui.py，修改 invoice_desktop/pdf_export_ui.py。

- [x] ExportSignaturePicker(parent, store, on_state_change) 提供 confirm(callback)、close()、saving、can_confirm；confirm 成功回调快照或无签名的 None。
- [x] 两张卡片各含两个 readonly 下拉框、缩略图；默认加载已保存人选。阻止四种滚轮事件触发选择。
- [x] 复用 SignatureTasks 的 read/role_previews/save_export；主线程创建 PhotoImage，按请求编号和人选指纹拒收过期预览。
- [x] 保留添加开关、管理入口；未选择的待确认位置不允许带签名导出。刷新保留未变化的人选草稿。
- [x] 导出窗口保留输出位置及开始/取消操作，以固定底栏、按溢出滚动的内容区域适应工作区。确认保存期间禁用修改和关闭，取消不提交。
- [x] 静态审查异步结果、关闭、刷新、管理返回、无签名以及失败恢复路径；纯语法编译。

## Task 3: 便携交付

Files: invoice_desktop/__init__.py、README.md、使用说明.txt、功能归属与更新边界.txt、docs/releases/1.1.24.md、docs/release-checks.md。

- [x] 更新版本和使用说明；记录开始导出记住人选及取消不保存。
- [x] 独立代码复查，处理实质问题。静态检查及语法通过后提交。
- [x] 用现有 build.ps1 和构建环境构建；核对 EXE 内全部应用模块及原生资源与源码一致。
- [x] 确认软件已关闭后验证绝对路径、规则和私人文件指纹，备份原目录并更新 release/InvoiceSummary。
- [x] 打包 1.1.24 软件/源码、逐成员核对并检查无私人图片和业务文件；记录本次验证范围。
