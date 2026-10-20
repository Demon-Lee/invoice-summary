# Remove Rule Management Page Implementation Plan

> **For agentic workers:** 本会话executing-plans实施，requesting-code-review独立静态复审。

**Goal:** 1.1.18仅保留发票处理界面，规则由维护者准备后随完整软件包分发。

**Architecture:** ui.py删除导航及维护页面；app.py删除来源绑定和维护动作，仅保留随包规则检查及既有业务门禁；policy.py只更新说明常量。

**Tech Stack:** 现有Python／Tkinter、EngineStore和PyInstaller。

## Constraints

- 不改updates.py、识别、校正、填表、金额或PDF导出实现；保留源码维护接口及构建工具。
- 不读取／写入旧skill_source设置，不删除旧设置和恢复记录；随包损坏时停止处理并提供有效恢复提示。
- 不新增或运行测试、GUI、Excel或业务流程，仅静态核对、独立复审及构建完整性。
- 本地归档旧版并更新原目录和ZIP，旧版占用则等用户关闭；不上传GitHub。

## Steps

- [ ] 捕获EXE、规则、skill、engine和受保护业务源文件基线。
- [ ] ui.py的build_interface仅接收执行步骤和必要条件；删除Notebook／build_rules／底部规则导航及无用导航样式。处理页直接pack填满主窗口。
- [ ] app.py删除SOURCE_PROBLEMS／BOUNDARY_HEADINGS、维护导入和12个页面／来源／更新动作方法；初始化不再读settings，移除来源StringVar与trace。来源问题状态及4个检查／展示／恢复／周期方法改为随包规则语义，各业务调用点同步，保留3秒检查及导出资格。
- [ ] policy.py只改BOUNDARY_GUIDE，README／使用说明反映无维护入口、更新通过完整包、旧绑定忽略及有效规则损坏处理；版本1.1.18。
- [ ] 14模块纯语法编译、所有旧控件／回调／源路径引用搜索、业务及policy差异范围核对；独立复审并修复实际问题，构建退出0且归档内容对应源码。
- [ ] 暂存逐文件哈希核对，检查绝对路径／重解析点及旧程序占用，归档1.1.17并更新原目录。
- [ ] 提交实现及发布记录，生成Windows／源码ZIP逐成员对应发布／Git文件，记录提交后重包，工作区干净。
