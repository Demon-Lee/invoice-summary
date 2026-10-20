# Stage and Input Selection Implementation Plan

> **For agentic workers:** 使用executing-plans在本会话实施，requesting-code-review独立只读复审。

**Goal:** 1.1.15阶段卡只留居中标题，左侧高亮选择按钮结合预览后路径锁定及原按钮改选。

**Architecture:** ui.py负责标题及两列输入布局；ui_actions.py扩展两个选择角色并复用本地图标；app.py独立管理输入状态与事务式改选。

**Tech Stack:** 现有Python／Tkinter／Pillow图标及PyInstaller目录构建。

## Global Constraints

- 采用用户已明确确认的原按钮改选方案，不新增重新选择入口。
- 沿用feat/desktop-app和随包规则，不改识别、校正字段、写表、金额及PDF打印实现。
- 不新增或运行测试、GUI、Excel或业务流程，只静态检查、独立复审及构建完整性核对。
- 本地归档旧目录并替换release/InvoiceSummary，生成Windows与源码ZIP；不上传GitHub。

## Task 1：界面与输入状态

- [x] 保存旧EXE、规则、skill、engine和受保护业务源文件基线。
- [x] ui.py将STAGES简化为三色；删除draw_stage_icon及stage_body／stage_badge／stage_icon控件，stage_heading单列居中并按实际宽度换行。内部阶段详情仍供既有流程保存，不显示小字。
- [x] ui_actions.py新增ChooseFolder／ChooseWorkbook蓝色角色，复用文件夹／表格图标；ui.py改为左按钮右路径框，创建input_buttons与input_entries引用，输入控件不进入通用interactive列表。
- [x] app.py新增_inputs_locked、_choosing_input、_input_change_approved和输入控件状态缓存；_update_input_controls统一控制忙态、禁用路径和按钮角色，挂入_update_action_styles；_button增加默认register=True参数。
- [x] _choose_input先确认、再选择，只有不同非空路径才修改StringVar；取消／原路径保留资格和校正，真实改选避免第二次校正提示；_pick_pdf／_pick_book复用该方法。预览、后台运行、定时来源检查和关闭入口避开输入窗口。
- [x] _invalidate解除路径锁；_render_preview按clean且has_changes设置锁定；_render_result在completed时保持锁定、no_change解锁；_render_pdf_result仅成功后解锁。完成资格失效、_show_stale_preview及通用错误的失效预览分支均解锁；去掉旧阶段badge刷新引用。
- [x] 更新版本及当前说明为1.1.15，记录状态／改选语义；14模块纯语法编译、引用及diff检查，独立只读复审后修正实际问题。

## Task 2：构建与本地发布

- [x] 构建退出0，核对EXE内14模块、资源、说明、规则及受保护源文件。
- [x] 暂存逐文件哈希核对；检查绝对路径、重解析点和旧版占用，归档1.1.14并更新原目录。
- [x] 提交实现及发布记录，生成Windows／源码包，逐成员对应实际文件并核对SHA256；记录提交后重包并保持工作区干净。

## 完成记录

实现提交156b925。独立复审提出同一Minor的三条失效解锁入口，补齐后无剩余Critical／Important／Minor。14模块纯语法编译和18处界面方法的静态差异范围核对通过，其他33个既有方法AST相同；未运行应用代码或测试。

最终构建退出0，1311个发布文件、EXE内14模块及13个规则文件完整性通过。原1.1.14归档为release/InvoiceSummary-1.1.14-archive-20261020-222632，原路径已更新1.1.15；EXE SHA256为c2faddb41ce429060272ebc8d34c0cd5437c2208d6856ac22e1b5a37a10e7d05。Windows包1311项、源码包127项，逐成员对应发布／Git源码，记录提交后重包。未运行GUI／Excel、测试或业务流程，未上传GitHub；详见docs/release-checks.md的1.1.15记录。
