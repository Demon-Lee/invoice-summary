# Detail Columns Implementation Plan

> 在当前会话实施；requesting-code-review 用于独立只读审查。

**Goal:** 文件名不独占全屏新增空间，产品名称、规格及厂家有足够显示位置，发布 1.1.4。

**Architecture:** 仅变更现有 Treeview.column 的 stretch/minwidth 参数；默认宽度、字段顺序、数值对齐、原生拖动与滚动接口保留。

**Tech Stack:** Python、Tkinter ttk、PyInstaller，现有构建环境与 feature 分支。

## Global Constraints

规则 6b9e6cdafb3f／42334e9f238e。App、ui_widgets、engine、controller、updates、workbook、corrections、template_rules、skill 及业务文件不改。上级指令要求未经用户要求不新增／运行测试；不启动 GUI 或业务接口。原路径不存在时从可信旧 ZIP 恢复规则；路径与重解析点检查，发布前检查进程，不强制终止。

## Task 1: 界面和说明

Files: invoice_desktop/ui.py、__init__.py、README.md、使用说明.txt、自动生成边界说明。

- [ ] 原列配置改为：

```python
stretch_columns = {"product_name", "spec", "manufacturer"}
# 原 heading、width、anchor 不变；column 参数：
minwidth=width if name in stretch_columns else 40
stretch=name in stretch_columns
```

- [ ] 版本 1.1.4，说明文件名默认宽度、额外空间分配和手动拖动边界。
- [ ] compile 静态检查两个变更 Python；git diff --check；独立只读审查分配、最小宽度、手动边界和原接口，不运行测试。

## Task 2: 构建和发布

Files: dist、release（忽略目录）；docs/release-checks.md。

- [ ] 原目录存在时保留已选规则；不存在时核对 1.1.3 ZIP SHA256、快照白名单及各文件哈希，仅恢复规则到 .superpowers 下的新目录。
- [ ] 执行 release_assets.py 和原 PyInstaller 命令；prepare_portable.py --preserve 指向已核对来源，复制两份说明和许可。读取编译归档确认版本和新列参数；核对规则和 EXE 哈希。
- [ ] 原程序未运行时将构建复制至 release 下唯一暂存目录；再次核对 EXE／规则、进程及目标状态，旧文件夹存在则归档后更新，缺失则直接重建原目录；保留旧 ZIP。
- [ ] 提交实现、从实际发布目录生成两份 ZIP，读取每个成员与发布／跟踪源码逐字节对应，核对规则及 SHA256.json，记录并提交；再包装并核对最终源码，Git 状态干净。
