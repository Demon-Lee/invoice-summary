# Action Buttons Implementation Plan

> **For agentic workers:** 当前会话按 executing-plans 实施；requesting-code-review 使用独立只读复审。

**Goal:** 将主操作改为易辨识的独立按钮，发布本地 1.1.7。

**Architecture:** 新增 ui_actions.py 提供 ttk 图片元素和图标，ui.py 接入布局，App 展示方法更新文本与提示。原生按钮及现有业务状态保持。

**Tech Stack:** Python、Tkinter ttk、现有 Pillow、PyInstaller。

## Global Constraints

- 已批准设计：docs/superpowers/specs/2026-10-19-action-buttons-design.md。
- 不新增或运行测试，不执行 PDF／Excel 业务；静态语法、只读复审、构建及文件核对。
- 规则 active 93933610c8ae / previous 6b9e6cdafb3f，源文件和 skill 不修改。
- 沿用 feat/desktop-app；不终止运行的软件，替换前核对进程及绝对路径，保留旧版。
- 本次只更新本地发布包，不自动上传 GitHub。

## Task 1：原生按钮呈现

**Files:** 新建 invoice_desktop/ui_actions.py；修改 invoice_desktop/ui.py、invoice_desktop/app.py。

**Interfaces:** configure_action_styles(root, style, *, font, background) 注册 PreviewAction.TButton、ExecuteAction.TButton、CorrectAction.TButton；decorate_action_button(widget, role) 设置持久保留的状态图标。按钮继续由 App._button 建立和登记，不变更命令或 state 条件。

- [ ] 用 Pillow 高分辨率绘制圆角表面并缩小，ttk image element 九宫格拉伸；normal/active/pressed/disabled 和 focus 组合按禁用优先映射。保留原生 padding/label 布局和键盘行为。
- [ ] 16px 本地放大镜／播放／编辑图形，随 Tk 缩放，禁用图标灰色；明确 compound=left，图片由控件或根窗口保留引用。
- [ ] 三按钮使用固定角色样式，14px 主按钮间距，下方一行操作提示。App._update_action_styles 仅刷新标签、提示、光标和原阶段徽标，不交换样式或修改 state。
- [ ] busy 与 operation_stage 控制“正在预览…”／“正在处理…”；恢复标签时保留人工校正警示。
- [ ] 对变更 Python 使用 compile(source, filename, 'exec') 静态检查，git diff --check；requesting-code-review 只读复审并处理实际问题。

## Task 2：本地版本交付

**Files:** invoice_desktop/__init__.py、README.md、使用说明.txt、构建生成的功能归属与更新边界.txt。

- [ ] 版本设为 1.1.7，说明固定角色、禁用提示和处理中标签。
- [ ] 记录当前规则 active.json、所有快照文件哈希及旧 EXE；检查 dist/build/release 路径与重解析点，再运行 tools/build.ps1 -Python .build-venv/Scripts/python.exe，退出 0。
- [ ] 比较归档内新模块／ui／App 的编译代码与当前源，核对构建规则、文档及 EXE。
- [ ] 再次核对进程与规则无并发变化；暂存构建目录，保留 InvoiceSummary-1.1.6-archive，替换 release/InvoiceSummary。
- [ ] 提交实现及记录后运行 tools/package_release.py --directory release/InvoiceSummary，逐成员核对 Windows 包、源码包和 SHA256.json；记录实际检查范围及未运行的 GUI／业务流程。
