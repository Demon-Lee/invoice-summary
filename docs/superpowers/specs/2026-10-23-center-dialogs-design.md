# 弹窗统一相对主窗口居中

用户要求完成提示、报错及其他弹出窗口在当前主界面中央出现，尤其最大化后不能默认落在屏幕左上角。

代码定位：result_dialog、signature_ui及人工校正窗口仅设置尺寸；pdf_export_ui有独立的客户区居中计算；部分messagebox缺少parent。统一在自定义窗口完成布局、显示前设置初始位置，Windows映射时再以真实窗口边框矩形定位，参考主窗口而非嵌套弹窗，限制在主窗口所属显示器可用区域。不会在用户移动弹窗后持续拉回。

原生messagebox、文件/文件夹选择器和签名名称输入通过小范围包装执行：补齐parent，在该模态调用期间对本UI线程安装CBT回调，仅处理原生对话框或Tk顶层首次激活；使用Windows窗口矩形和显示器工作区居中，调用结束卸载，不修改尺寸、焦点或其他程序窗口。回调不调用Tk，异常不阻断原调用。卸载失败时禁用定位但保留回调引用，避免释放仍在使用的函数指针。

现有模态、复制诊断、签名保存及业务状态不变，沿用V1.1.21，仅本地更新，保留个人签名/规则。用户未请求测试，本轮不新增/运行测试；执行静态复查、语法、构建及产物核对，明确实际最大化/多显示器GUI行为尚未运行确认。

依据：Microsoft CBTProc（https://learn.microsoft.com/en-us/windows/win32/winmsg/cbtproc）、Positioning Objects on Multiple Display Monitors（https://learn.microsoft.com/en-us/windows/win32/gdi/positioning-objects-on-multiple-display-monitors）及本机Python3.12 tkinter.simpledialog._place_window源码。原生定位不改变进程DPI模式。
