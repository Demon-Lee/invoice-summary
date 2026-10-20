# Initial Preview Copy Implementation Plan

> **For agentic workers:** 本会话按用户明确要求实施，requesting-code-review独立只读复审。

**Goal:** 1.1.17首次选输入显示等待预览，删除主操作行小字与品牌副标题。

**Architecture:** app.py会话标志区分首次与已有预览失效；ui.py删除控件并同步移除动态引用。

**Tech Stack:** 现有Python／Tkinter及PyInstaller便携构建。

## Constraints

- 只静态编译、只读复审及构建／文件核对，不新增或运行测试、GUI、Excel或业务流程。
- 保留路径锁定、原选择按钮改选、校正及PDF导出资格；不修改共享skill和业务源文件。
- 本地归档1.1.16并更新原目录及两类ZIP，不结束用户程序，不上传GitHub。

## Steps

- [x] 保存EXE、规则、skill、engine及受保护源文件基线。
- [x] app.py初始化_has_previewed=False，_render_preview置True，_invalidate按标志选择等待／重新预览标题与底部状态；ui.py删除副标题及action_hint，app.py删除提示刷新及无用局部变量。
- [x] 版本与说明更新1.1.17，14模块纯语法编译、引用／差异范围核对、独立只读复审及构建完整性通过。
- [x] 暂存逐文件核对，确认旧版已关闭，检查绝对路径和重解析点后归档旧目录并更新原路径。
- [x] 提交实现及发布记录，生成Windows／源码包并逐成员对应实际文件；最终记录提交后重包，工作区干净。

## 完成记录

实现提交f4b1daa，独立只读复审无Critical／Important／Minor。14模块纯语法编译、4处界面方法差异范围及其他47个既有方法AST保持不变的检查通过；构建退出0，EXE中14模块与源码对应，13个受保护源文件及1311个发布文件完整性通过。

原1.1.16归档为release/InvoiceSummary-1.1.16-archive-20261020-224211，原路径已更新1.1.17；Windows ZIP1311项，源码ZIP131项，逐成员对应实际文件，记录提交后重包。未运行测试、GUI／Excel或业务流程，未上传GitHub；详细证据见docs/release-checks.md。
