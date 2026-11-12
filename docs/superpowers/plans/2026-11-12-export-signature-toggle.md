# 添加签名开关 Implementation Plan

**Goal:** 将导出窗口旧勾选框替换为主界面配色的圆角开关外观。

**Architecture:** 新增ui_switches.py生成高DPI开关图像并注册专用ttk.Checkbutton样式；ExportSignaturePicker继续使用原Checkbutton、BooleanVar及状态控制。

**Global constraints:** 1.1.24；不变更签名存储与导出语义；不新增/运行测试；保留私人数据、规则和业务文件；只本地交付。

- [ ] 新建configure_signature_toggle(parent, font, palette)，使用原生状态匹配图像并在根窗口保留图片引用，避免重复注册元素。选中蓝色、未选浅灰，兼顾禁用、悬停、焦点。
- [ ] 在export_signature_ui.py创建原Checkbutton时应用专用样式，保留回调及现有状态逻辑。
- [ ] 更新使用说明；静态及独立只读复查，纯语法和Windows构建，核对EXE中应用代码、原生资源和私人规则指纹。
- [ ] 原程序关闭时备份并更新release/InvoiceSummary，重包1.1.24，逐成员和隐私检查；记录验证范围与结果。
