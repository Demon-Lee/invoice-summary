# Left Aligned Details Implementation Plan

> 当前会话实施；requesting-code-review 独立只读复审。

**Goal:** 十列明细表头及内容统一左对齐，发布 1.1.6。

**Architecture:** 仅变更 Treeview 的 heading/column anchor，保留比例布局和现有接口。

**Tech Stack:** 现有 Python、Tkinter ttk、PyInstaller。

## Constraints

规则 6b9e6cdafb3f／42334e9f238e；App、ui_widgets、业务模块、engine、skill 与业务文件不改。不得新增或运行测试，不启动 GUI 或业务接口。原发布路径及 feature 分支沿用，检查路径、重解析点、规则、进程和 EXE，不强制终止软件。

- [ ] ui.py 十列统一：

```python
app.tree.heading(name, text=label, anchor="w")
app.tree.column(name, width=minimum, minwidth=minimum, anchor="w", stretch=False)
```

- [ ] 版本 1.1.6，README 与使用说明删除当前数字右对齐描述，改为表头和明细全部左对齐；边界说明随构建更新版本。
- [ ] 两个 Python 静态 compile 与 diff 空白检查，独立只读复审，确认列比例／数据／业务不改。
- [ ] 核对原规则，检查构建目标与重解析点，运行原 tools/build.ps1；读取归档确认版本、左对齐及源码字节码一致，核对说明／快照哈希。
- [ ] 两次检查软件未运行，暂存并核对 EXE／规则／原版本，归档 1.1.5 并更新原目录；提交及打包，逐成员核对发布／源码字节和校验值；记录提交后重新包装并核对最终源码，Git 状态干净。
