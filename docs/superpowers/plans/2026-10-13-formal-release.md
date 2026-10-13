# Formal Release Implementation Plan

> **For agentic workers:** Use executing-plans in this session and requesting-code-review for independent static review.

**Goal:** 完成获批的四项用户体验改进并发布 1.0.0。

**Architecture:** 保持共享规则与业务处理原逻辑；软件层实现校正丢弃提醒、报告呈现和结构化来源状态，更新普通用户／维护者说明。

**Tech Stack:** Python、Tkinter/ScrolledText、PyInstaller、现有便携规则快照。

## Global Constraints

不新增或运行测试，不启动 GUI 或实际发票流程，不修改 skill 或业务文件。当前共享规则保持 6b9e6cdafb3f，保留旧快照。沿用完整批次重填、六字段校正、Excel 依赖和不自动备份的用户要求。

### Task 1: UI 与来源状态

Files: invoice_desktop/app.py, invoice_desktop/updates.py.

- [x] source_status 返回 kind，明确区分不可用来源、无效内容、未实现说明、接口不兼容、可更新及当前状态；旧调用的 changed/error/version 字段保留。
- [x] UI 使用对应标题与下一步，预览／执行／校正及定时来源检查复用同一提示。
- [x] 有校正时重新预览明确提示并确认；取消保留当前结果。失败检查保留仍有效的原预览；实际新规则激活仍使预览失效。
- [x] 主报告异常／失败优先，增加垂直滚动条和完整报告复制按钮；界面说明可见滚动。

### Task 2: 正式版说明

Files: invoice_desktop/__init__.py, policy.py, README.md, 使用说明.txt, 自动生成的功能归属与更新边界.txt.

- [x] 版本改为 1.0.0。
- [x] 普通使用者解压即用；维护者同步规则。删除等待旧规则试同步的发布说明。
- [x] 说明校正保护、报告复制与分类型问题的解决办法；既有功能边界不变。

### Task 3: 审查、构建、发布

Files: docs/release-checks.md、规格／计划与发布资产。

- [x] 静态编译变更 Python，检查 diff，独立源码审查并处理问题。
- [x] 构建，读取编译归档确认正式版及新 UI 模块；核对共享规则快照未改变。
- [x] 检查软件运行状态和发布路径，安全替换原发布目录并归档旧版。
- [ ] 提交变更、生成正式版 ZIP，核对 ZIP 内容／哈希并记录证据。
