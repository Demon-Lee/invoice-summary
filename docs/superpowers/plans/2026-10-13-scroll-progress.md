# Scroll and Progress Implementation Plan

> Use executing-plans in this session and requesting-code-review for independent read-only review.

**Goal:** 实施用户选择的自动隐藏滚动条与美化细线进度条，发布至原软件目录。

**Architecture:** ui_widgets.py 提供界面专用组件，保持原生 Treeview/Text；通过标准 set(first,last)、xview/yview 和 progress start/stop 接口集成。两边固定空白操作区不随显示状态变化，消除内容跳动。软件业务模块和共享规则不变。

**Tech Stack:** 现有 Python、Tkinter Canvas/Text/ttk、PyInstaller；无新增依赖。

## Constraints

软件 1.1.3，规则 6b9e6cdafb3f／42334e9f238e。不修改 App 工作流、controller、updates、corrections、workbook、engine 或 skill。不新增／运行测试，不启动 GUI、诊断、同步接口或业务处理。继续使用当前 feature 分支与原发布路径。

## Task 1: 界面控件

Files: create invoice_desktop/ui_widgets.py; modify invoice_desktop/ui.py.

- [x] AutoHideScrollbar(Canvas)：orient、command 参数；set(first,last) 接原生滚动回调；attach(view,host) 追加原控件活动绑定，不覆盖已有动作。固定空白边缘定位，滑块约 6px，操作区 14px，无箭头，视图溢出时显示，1.4秒闲置隐藏；按实际剩余行程映射拖动，抓住时不隐藏。
- [x] 保留所追加绑定的函数 ID，销毁时逐项解绑、取消隐藏回调；滚轮在原内容上只唤醒滚动条，在滑块上转发到对应 xview/yview。
- [x] AutoScrollText(Text)：创建白色外框，原生 Text 与固定右边距；使用新纵向滚动条，参照本机 ScrolledText 委托 Pack/Grid/Place，排除 config/configure。保留 get/delete/insert/tag/yview/readonly/复制等方法。
- [x] 明细保持原行列配置和双击，将旧两个 Scrollbar 替换为自动隐藏组件，固定右／下边缘预留，接 xscrollcommand/yscrollcommand。
- [x] ThinProgressbar(Canvas)：start(interval=...)／stop() 与旧接口一致，浅色圆角轨道和蓝色渐变移动片段；使用 monotonic 时间计算位置，避免回调延迟改变动画速度；只维护一个动画计时器，停止及销毁取消回调。

## Task 2: 文档与审查

Files: invoice_desktop/__init__.py, README.md, 使用说明.txt, 自动生成边界说明、规格／计划／发布记录。

- [x] 版本 1.1.3，说明自动隐藏的触发、拖动与细线忙碌提示。
- [x] 静态编译变更 Python、检查 diff；独立只读审查绑定、几何管理、拖动换算、隐藏和动画生命周期及既有接口，修正实际问题。

## Task 3: 构建、发布

- [x] 检查构建绝对路径与重解析点，构建并读取编译归档确认新组件和实际版本，核对规则哈希和说明。
- [x] 两次检查原软件未运行，暂存完整目录并核对 EXE／规则选择，更新原目录。原目录已不存在，从已核对的旧 ZIP 恢复便携规则后重建发布目录，旧 ZIP 保留；不终止用户进程。
- [ ] 提交、打包 Windows／源码 ZIP，核对包内程序、规则、文档、源码、校验值；完成记录提交后重新包装源码。
