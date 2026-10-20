# Open Locations and Double-click Correction Implementation Plan

> **For agentic workers:** 使用 executing-plans 在当前会话实施，requesting-code-review 做独立只读复审。

**Goal:** 1.1.12 集中打开入口并强化双击校正提示。

**Architecture:** ui.py 负责三个原生按钮和提示标签布局，ui_actions.py 提供本地图标与按钮表面，app.py 管理可用状态与提示。实际编辑仍调用既有 _edit_detail，业务模块不变。

**Tech Stack:** Python／Tkinter／Pillow，已有 PyInstaller 便携构建。

## Global Constraints

- 遵循 specs/2026-10-20-open-locations-design.md，沿用 feat/desktop-app；用户本轮直接指定的布局和操作方式为需求依据。
- 不改共享规则、skill、业务算法、Excel／PDF 脚本；活动／上一版本保持现状。
- 不新增或运行测试，不启动 GUI／Excel，不处理业务文件。只进行语法编译、只读审查、构建、归档及文件完整性核对。
- 保留校正确认、失效检查、中断恢复、导出前后预览状态；不以提示状态代替实际校正门禁。

## Task 1：集中入口和双击引导

**Files:** invoice_desktop/ui.py、ui_actions.py、app.py。

- [x] 保存旧 EXE、规则与受保护源文件哈希。
- [x] 三个打开入口放在同一“打开位置”区域，分别使用文件夹／表格／导出文件夹图标及完整文字；窄窗口按实际所需宽度自动折行。
- [x] 移除人工校正按钮及全部引用；原控件可用状态迁移为仅用于展示的提示状态，导出恢复保存该状态。
- [x] 有效明细显示浅金色双击提示，其他状态显示原因；已有校正提醒保留。双击只响应实际单元格，Enter 使用同一校正方法。
- [x] 说明与版本更新为 1.1.12，删除当前说明中点击人工校正按钮和分散打开入口的描述。

## Task 2：复审与本地发布

**Files:** invoice_desktop/__init__.py、README.md、使用说明.txt、生成的功能归属与更新边界.txt、docs/release-checks.md。

- [x] Python 静态编译、引用搜索和 diff 检查；独立只读审查状态恢复、空白／表头、键盘和布局问题，处理实际问题。
- [x] 构建前检查路径／重解析点；构建退出 0，EXE 内编译代码、脚本、说明和规则逐项核对。
- [ ] 暂存逐文件哈希核对；确认原程序未占用、旧哈希一致后归档 1.1.11，并更新 release/InvoiceSummary，不结束用户程序。
- [ ] 提交实现／记录，生成 Windows 和源码 ZIP，逐成员读取对应发布／Git 文件，核对 SHA256.json；最终记录提交后重包源码，Git 状态干净。
