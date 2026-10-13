# Navigation Appearance Correction Plan

> Use systematic-debugging and receiving-code-review for the reported mismatch; requesting-code-review for final independent static review.

**Goal:** 将实际导航改为已获认可的白底、蓝色文字和下划线样式，修正 V1.1.1 中的传统页签边框。

**Evidence:** 用户提供的实际截图仍有凸起矩形边框。ui.py 仅设置了 TNotebook.Tab 的颜色和 borderwidth，仍沿用 clam 的 Notebook.tab 绘制结构；本地 clamTheme.tcl 的选中态 padding 也仍可继承。原 HTML 预览是白色导航及底部蓝线。

**Architecture:** 保留原生 ttk.Notebook 与现有 add/select/keyboard 行为，显式使用新的 Underline.TNotebook.Tab 布局与 Tk 图片背景元素替换旧 Notebook.tab。三像素底部边界不拉伸，选中态填蓝色底线；其他区域白色，轻微悬停，保留键盘焦点。图片引用保存在 root，确保不会被 Python 回收。主导航与规则页内部切换共用新样式。

**Scope:** 只修改 ui.py、软件版本及用户说明。识别、写表、校正、状态门禁、原生内容页和 rule_tabs.select(update_tab) 继续使用原接口；规则保持 6b9e6cdafb3f／42334e9f238e。不新增依赖，不新增或运行测试，不启动 GUI 或业务处理。

## Tasks

- [x] 用 Tk PhotoImage 创建白底、悬停及选中底线四种元素状态，border=(0,0,0,3)，sticky=nswe；显式布局包含 InvoiceNavigation.tab → Notebook.padding → Notebook.focus → Notebook.label。
- [x] Underline.TNotebook.Tab 取消继承的选中 padding／展开；两个 Notebook 指定 Underline.TNotebook 样式。保留真正的 Notebook、页面父子关系和回调。
- [x] 软件版本发布为 1.1.2，动态版本显示及用户说明同步。
- [x] 静态编译、diff 检查与独立源码复审；构建并只读核对编译归档、规则和说明。
- [x] 确认原程序退出、目标路径合法；暂存、归档旧版并替换原目录，生成和核对分发包，记录实际运行未验证的限制。

## 完成记录

实现提交 f1163dd。独立只读复审无剩余 Critical / Important / Minor；构建退出 0，编译归档确认两处导航使用自定义样式。V1.1.2 已放回原发布目录，旧版为 InvoiceSummary-1.1.1-archive；规则选择及文件哈希保持一致。Windows ZIP 1308 项，源码 ZIP 99 项，程序／规则／说明／源码均核对一致，校验值记录于 release/SHA256.json。最终记录提交后重新打包。未启动原生 GUI 或实际业务，实际外观未经运行截图确认。

## Primary references

Tcl/Tk 8.6 官方 ttk_image 文档说明状态图片及固定边界拉伸：https://www.tcl-lang.org/man/tcl8.6/TkCmd/ttk_image.htm 。本地 Tk clamTheme.tcl 与 Python tkinter/ttk.py 用于核对当前环境的布局和参数格式，不执行 GUI。
