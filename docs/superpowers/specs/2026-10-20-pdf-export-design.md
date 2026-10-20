# 验收与领用 PDF 导出

用户选择第 1 种分页：全部列缩放到一页宽，明细多时纵向自动分页。其他已提出默认值采用 A4 横向、分别导出两个 PDF、默认工作簿旁“导出PDF”子文件夹并可更换、重名提示、完成后可打开目录。此功能由软件维护，不修改 skill。

## 使用流程

处理完成后可点击独立的“导出PDF”。也可选择已有填好内容的工作簿直接导出，避免重新清空填表。弹窗说明导出的是已保存内容，预览或校正尚未执行时不会进入 PDF；默认目标为工作簿同级“导出PDF”，可通过目录选择器更换。

一次生成“验收单.pdf”和“领用单.pdf”。遇到同名文件列出确切路径，默认不覆盖；两份 PDF 都成功生成并检查后才替换输出。执行中目录同名文件若被其他程序修改，停止覆盖；第二个文件替换失败时恢复第一个，失败恢复所需备份保留并报告路径。

完成弹窗列出两份文件及页数，界面提供“打开导出目录”。导出结果与原检查报告同时保留；导出失败可重试，不清空已有预览或改写金额核对结论。

## 排版与原文件

读取保存后的 .xlsx 快照，检查“验收”“领用”唯一完整表头、三行页脚和已填明细。根据实际内容及有内容的合并范围确定打印区域，包含标题、所有实际内容列、签字／说明和右侧“第二联：财务报销”，忽略只有格式的远端空单元格。复制工作簿后用 Excel 原生 Worksheet.ExportAsFixedFormat 导出，不保存临时排版设置回原文件。

临时副本设置 A4、横向、Zoom=False、FitToPagesWide=1、FitToPagesTall=False，移除手动分页，逐张工作表单独选中后导出。原有打印标题保留；未设打印标题时重复标题到表头行，确保多页可阅读。页边距、单元格字体／样式和行列尺寸沿用保存内容。每个 PDF 允许多页；所有页应为 A4 横向。

参考微软接口：[Worksheet.ExportAsFixedFormat](https://learn.microsoft.com/en-us/office/vba/api/excel.worksheet.exportasfixedformat)、[FitToPagesWide](https://learn.microsoft.com/en-us/office/vba/api/excel.pagesetup.fittopageswide)、[FitToPagesTall](https://learn.microsoft.com/en-us/office/vba/api/excel.pagesetup.fittopagestall)。

## 实现与检查

Python 独立导出模块负责快照、稀疏内容检查、输出确认、PDF 文件检查及成对替换。软件自有 PowerShell 负责 Excel COM；独立实例关闭时不保存工作簿，超时守护仅允许结束本次新建且 PID／启动时间匹配的 Excel 实例。App 增加导出阶段、选择目录和查看输出，保留已有预览／金额／规则／恢复逻辑。

基于干净的 1f122bb（1.1.9）发布本地 1.1.10，保留实际当前规则 280db9d722ae、previous 38af3849e1ca，旧软件目录归档。不新增或运行测试，不运行 Excel 导出／业务流程；执行 Python／PowerShell／C# 静态编译、独立只读复审、构建及发布文件／压缩包核对，实际导出排版由用户试用确认。本次不自动上传 GitHub。
