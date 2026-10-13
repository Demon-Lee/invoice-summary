# Proportional Columns Implementation Plan

> 当前会话内实施；requesting-code-review 独立只读审查。

**Goal:** 按用户截图比例分配全部十列，窗口缩放自适应并保留原生拖动。

**Architecture:** ui_widgets.ProportionalTreeviewColumns(tree, columns, weights, minimums) 负责布局；原 Treeview 保持值、对齐和事件接口，所有列 stretch=False。一个 after_idle 合并布局／拖动结束的比例采集，实际宽度缓存避免循环。

**Tech Stack:** 现有 Python、Tkinter ttk、PyInstaller，无新增依赖。

## Global Constraints

软件 1.1.5；共享规则 6b9e6cdafb3f／42334e9f238e。App、engine、controller、updates、workbook、corrections、template_rules、skill 与业务文件不改。不得新增／运行测试，不启动 GUI 或业务接口。沿用当前 feature 分支和原发布路径，检查绝对目标、重解析点、进程与规则状态，禁止强制结束软件。

## Task 1: 控件、接入与说明

Files: invoice_desktop/ui_widgets.py、ui.py、__init__.py、README.md、使用说明.txt，构建生成边界说明。

- [x] 新增比例列宽组件。_widths(available) 从目标 max(available,sum(minimums)) 分配；低于 minimum 的列先固定并从剩余空间／权重移除，余列比例向下取整，剩余像素按最大余数补齐。_apply 仅在实际宽度变化时写列宽；_press/_release/_finish_drag 暂停布局并在原生释放后采集当前宽度为比例，_destroyed 取消回调。所有事件 add="+"，不吞事件；实际列宽不变时不更新比例。
- [x] ui.py 导入并接入：

```python
weights = (2, 19, 18, 7, 4, 6, 9, 11, 19, 5)
minimums = (44, 180, 170, 90, 44, 58, 95, 100, 170, 84)
# 原 columns、heading、anchor、行值及滚动保持；初始化列为：
app.tree.column(name, width=minimum, minwidth=minimum, anchor=anchor, stretch=False)
app.detail_columns = ProportionalTreeviewColumns(app.tree, columns, weights, minimums)
```

- [x] 版本 1.1.5，两份用户说明写明截图比例、最小宽度及手动比例仅当前会话有效。
- [x] 静态 compile 三个变更 Python、git diff --check，独立只读审查比例算法、总宽／边缘、事件顺序、手动拖动、销毁与既有接口，不运行测试。修正“无变化点击也更新比例”的 Minor，最终复审无剩余问题。

## Task 2: 构建、发布和归档核对

- [x] 检查原发布规则快照及构建绝对路径／重解析点，修正后重新执行 tools/build.ps1，保留规则选择。只读提取编译归档核对新类、接入参数、源字节码与软件版本，检查两快照哈希／说明和 EXE 哈希。
- [x] 检查原程序退出，复制完整构建至唯一暂存目录，核对规则状态／EXE 和原目录状态；再次检查进程后将旧文件夹归档为 InvoiceSummary-1.1.4-archive，新版放回原目录，不终止用户进程。
- [ ] 记录并提交实现；从实际发布目录生成 Windows 与 Git 跟踪源码 ZIP，逐成员核对文件字节、规则、说明、校验值；记录提交后重新包装并核对最终源码，Git 状态干净。若原目录意外缺失，使用校验过的旧 ZIP 保留规则，旧 ZIP 继续保留。
