# Business UI Implementation Plan

> **For agentic workers:** Use executing-plans in this session. Use requesting-code-review for independent read-only review of the completed changes.

**Goal:** 将用户确认的简洁商务效果应用到便携桌面软件，显示实际 V1.1.1 版本并发布原软件目录。

**Architecture:** 新建 ui.py 管理颜色、原生控件布局、图标与阶段样式；App 继续负责原事件、操作门禁与后台处理。四项摘要使用独立 StringVar，直接从 preview/result 数据填充；主题调整不进入 skill 快照或业务处理模块。

**Tech Stack:** 现有 Python、Tkinter/ttk、ScrolledText、PyInstaller；不新增依赖。

## Global Constraints

不新增或运行测试，不启动 GUI、诊断或实际 PDF／Excel 流程。当前共享规则保持 6b9e6cdafb3f，上一规则保持 42334e9f238e。不得修改 skill、识别／写表算法、controller、updates、六字段规范化或业务文件。保留现有操作状态、门禁、校正确认、完成弹窗、完整报告复制、恢复及不自动备份要求。沿用现有 feature 分支，无其他工作区改动。

### Task 1: 统一视觉与原生布局

Files: create invoice_desktop/ui.py; modify invoice_desktop/app.py.

Interfaces: build_interface(app, *, execution_steps, necessary_conditions, process_notice, preview_note, help_text, boundary_guide, retained_features) 创建既有 App 属性及交互控件；configure_theme(root) 定义全局原生样式；set_stage_style(app, tone) 更新图标、颜色和阶段徽记。只通过 App 原有方法绑定命令。

- [x] 配置浅灰背景、白色分区、蓝色主操作，统一字体、边框、标签、滚动条和导航。
- [x] 标题紧凑，右上角使用动态版本：
  ```python
  ttk.Label(header, text=f"V{__version__}", style="Version.TLabel")
  ```
- [x] 构建两张常驻指引卡、原风险提示、两行文件选择、原顺序操作按钮、阶段卡、四项摘要、十列表格和报告；新布局创建原 App 依赖的控件属性，继续注册 interactive。
- [x] configure_theme 使用 ttk 的 Primary.TButton、Secondary.TButton、Link.TButton。App 更新主次样式，不改变 enabled 状态：
  ```python
  execute_primary = not self.busy and str(self.execute.cget("state")) == "normal"
  self.execute.configure(style="Primary.TButton" if execute_primary else "Secondary.TButton")
  self.preview_button.configure(style="Secondary.TButton" if execute_primary or self.busy else "Primary.TButton")
  ```
- [x] 独立摘要直接使用业务对象：
  ```python
  records = payload.get("records", [])
  self.metric_invoices.set(str(len(records)))
  self.metric_rows.set(str(sum(len(record.get("rows", [])) for record in records)))
  self.metric_total.set("—" if total is None else f"¥{total}")
  self.metric_corrections.set(str(len(corrections or {})))
  ```
  新输入重置为占位，执行后显示该次实际结果，不从 summary 文本反解析，不改数值精度。
- [x] 表格按全局可见行号设置 odd/even，校正行单独 corrected 标签；单价／数量／金额右对齐，原值、列顺序及横纵滚动保留。
- [x] 同风格应用规则页、说明页和校正窗口；六字段、单价计算、保存／恢复动作与状态条件保持。

### Task 2: 版本、效果图与用户说明

Files: invoice_desktop/__init__.py, README.md, 使用说明.txt, docs/design/business-ui-preview.html, docs/design/business-ui-preview.jpg, 自动生成的功能归属与更新边界.txt.

- [x] 软件版本设为 1.1.1；右上角显示 V1.1.1，规则页继续区分共享版本。
- [x] 效果图右上角“正式版”改为 V1.1.1，更新本地预览与截图。
- [x] 使用说明与 README 说明新增视觉布局和软件版本显示，保留必要条件、清空范围及更新边界。

### Task 3: 静态审查与正式交付

Files: docs/release-checks.md, 本计划及发布资产。

- [x] 静态语法编译变更 Python、git diff --check；由独立审查员只读检查布局属性、回调、状态、摘要数据来源和业务范围，修复实际问题。
- [x] 验证构建绝对路径与重解析点，执行既有 tools/build.ps1；直接读取编译归档确认版本与新 ui.py，核对便携规则快照哈希，不执行模块。
- [x] 检查原软件进程；若占用则请用户关闭，不结束进程。暂存完整构建，核对规则选择和 EXE，归档旧 1.0.0、替换原发布目录。
- [ ] 提交改动，生成 Windows／源码 ZIP，核对包内 EXE、规则、说明、源码和 SHA256；记录检查范围与未运行 GUI／业务的限制，最终源码包包含完成记录。
