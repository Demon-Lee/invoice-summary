# Stage Vertical Alignment Implementation Plan

> **For agentic workers:** 本会话按用户明确纠正的方向执行，requesting-code-review独立只读复审。

**Goal:** 1.1.16阶段大标题左对齐、上下居中。

**Architecture:** ui.py修改锚点、段落对齐和网格伸缩，保留其他布局及状态逻辑。

**Tech Stack:** 现有Tkinter与PyInstaller。

## Constraints

- 只读复审及静态编译，不新增或运行测试、GUI、Excel或业务处理。
- 不关闭用户程序；构建及暂存完成后，等用户关闭旧版才能替换原目录。
- 本地归档旧版及生成Windows／源码包，不上传GitHub。

## Steps

- [x] 保存旧EXE、规则、skill、engine与受保护源文件基线。
- [x] ui.py设置stage_card.rowconfigure(0, weight=1)，stage_heading使用anchor=w、justify=left、sticky=nsew；版本与说明更新1.1.16。
- [x] 14模块纯语法编译、引用／diff检查及独立只读复审；构建退出0，核对编译归档、资源、规则及受保护源文件。
- [x] 暂存逐文件哈希核对；确认旧版已不再运行，检查绝对路径和重解析点，归档1.1.15并替换原目录。
- [x] 提交实现和发布记录，生成两类ZIP并逐成员核对；记录提交后重包，工作区干净。

## 完成记录

实现提交d57b1c7。独立静态复审无C/I/M，14模块纯语法编译、构建和编译归档核对通过。1311个发布文件、13个规则文件及14个受保护源文件完整性通过；未运行测试、GUI或业务流程。

原1.1.15保留为release/InvoiceSummary-1.1.15-archive-20261020-223317，原目录已更新1.1.16。Windows ZIP1311项、源码ZIP129项对应实际发布／Git文件，记录提交后重包；详细证据见docs/release-checks.md。
