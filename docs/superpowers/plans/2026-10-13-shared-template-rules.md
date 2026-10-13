# Shared Template Rules Implementation Plan

> **For agentic workers:** Use executing-plans to implement the approved adaptation in this session; use requesting-code-review for independent static review.

**Goal:** Skill 和软件共同读取可同步的模板最低保留行规则，保留软件独有功能。

**Architecture:** 添加严格版本化的 JSON 模板规则。软件解释已支持的策略，skill 原写表器采用相同参数；更新包格式 3 携带规则，旧快照保持旧策略。

**Tech Stack:** Python/openpyxl、Tkinter、Node skill writer、JSON、PyInstaller。

## Global Constraints

不增加或运行测试，不处理实际 PDF、不修改业务工作簿。用户将在软件中试同步。保持 Microsoft Excel 要求和原发布路径。未知协议和写表器变化停止更新，不能用取消检查绕过兼容性。保留旧快照和中断恢复。

### Task 1: 共享规则与兼容协议

Files: skill `scripts/template_rules.json`, `scripts/write_summary.mjs`, `SKILL.md`; desktop `invoice_desktop/template_rules.py`, `policy.py`, `updates.py`, `tools/prepare_portable.py`.

- [x] 新增 schema_version=1 的侧边标识规则；标签、忽略标点、单格／连续同列排列由声明控制。
- [x] skill 写表器读取 JSON；保持动态定位、原文保护、非法页脚停止等既有逻辑。
- [x] 软件严格校验 JSON，通过 `load_template_rules(engine_dir)` 读取；`minimum_retained_row(ws, header, last_column, rules)` 返回实际一基行号或 None。
- [x] 清单格式 3 声明 template_rules_contract_version=1，文件哈希包含 JSON；按候选清单的文件集合复制／导入／分发；旧格式不包含 JSON。
- [x] 指纹支持已知旧 writer 与本次 JSON writer；检查候选是否真正有共享实现，说明更新不假称算法变化。

### Task 2: 填表、恢复与提示

Files: `workbook.py`, `controller.py`, `app.py`.

- [x] `plan_workbook(..., template_rules=None)` 按本次行数和规则最低行的较大值收缩，源模板页脚不得位于最低行或上方。
- [x] 只清空主表业务区，保存必要空行的格式／行高及右侧文字原坐标。
- [x] `_matches_sheet` 检查规则决定的页脚和主表必要空行，写后验证实际页脚及必留空行。
- [x] 预览和执行由固定 engine_dir 加载同一规则，更新规则后沿用原来的重新预览要求。
- [x] 预览报告显示模板最低保留行、额外保留空行与合计行；功能边界明确模板规则属于共享范围。

### Task 3: 审查与发布

Files: version、README、使用说明、生成的功能归属说明、发布记录。

- [x] 更新到 0.1.8，明确手动同步步骤和旧模板异常处理。
- [x] 对变更 Python 源码作静态语法编译，Node 作语法检查，检查 diff 空白问题。
- [x] 请求独立源码审查并解决发现的问题，不运行测试。收到三项 Important 和一项 Minor 并已处理；审查员随后因额度限制结束，修复后采用本地静态自查，未取得独立最终复审。
- [x] 构建便携软件，核对源／发布文件及规则清单，安全发布到 release/InvoiceSummary；ZIP 和哈希记录随包装完成。
- [ ] 记录审查和构建证据、提交变更、打包完整文件夹与源码。
