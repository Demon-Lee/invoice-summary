# 发票汇总助手

Windows 离线桌面软件，使用 summarize-invoice-pdfs 的识别脚本与规则快照。电脑须安装 Microsoft Excel 桌面版。

## 使用

解压发布包，双击 `InvoiceSummary.exe`。选择完整 PDF 批次目录与目标 `.xlsx`，先只读预览，检查无异常后执行。原位更新工作簿，不自动创建备份。电子发票需包含可解析文本层，首版不提供 OCR。

## skill 更新

识别引擎有独立版本。当前电脑绑定 `C:\Users\aaa\.agents\skills\summarize-invoice-pdfs`，通过“同步本机 skill”更新。其他电脑通过“导入更新包”接收同一离线版本。“回退版本”切回上一个识别快照并解除本机来源绑定。

软件采用 skill 的 `invoice_pipeline.py`、`collect_excel_totals.py` 和 `apply_mixed_fonts_excel.ps1`；`SKILL.md` 是流程和规则依据。更新时应共同维护文档、脚本和测试。仅改变规则文字会被标记为待适配；原 Node 写表器改变时需同步修改软件写表器后重新发布，避免错误宣称原则一致。

开发者导出离线包：

```powershell
python tools/export_update.py --skill C:\path\to\summarize-invoice-pdfs --output C:\path\to\invoice-skill-update.zip
```

更新包检查版本、入口、路径白名单和 SHA-256。新依赖或接口改变需要升级主程序。请只选择可信的 skill 来源；校验和用于完整性检查。

激活前还会检查必需函数的参数、实际依赖加载和预览／改名／金额采集／验证的输出接口。检查只使用临时生成的空输入，不会接触业务文件；接口不兼容时保持当前版本。

如果 Excel 操作或验证中断，再次选择同一批次和工作簿进行只读预览，即可继续未完成流程；重启软件后也有效。恢复期间需保持发票内容和识别版本一致。完成验证后清除恢复记录。

移动明细和页脚时会同步更新原有公式的普通、绝对和跨表引用。涉及动态引用、命名区域等无法安全迁移的结构时，预览会停止并指出原因。

## 开发与验证

```powershell
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -v
python main.py --smoke-gui gui-check.json
python main.py --pipeline-smoke C:\path\to\invoice.pdf --output pipeline-check.json
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build.ps1
```

流程诊断只处理临时复制的 PDF 和新生成的测试工作簿，原始 PDF 不会修改。诊断报告不要作为发布包资产。

## 实现

Python/tkinter、pdfplumber、openpyxl 与 Microsoft Excel 自动化。现有 Node 写表器依赖的 OpenAI 内部评估组件不随软件分发，软件使用独立的 openpyxl 写表器执行同一模板约定。openpyxl 的行移动不会自动维护所有相关结构，因此软件明确处理页脚合并、行高、打印区域和总计公式；参考 [openpyxl 行编辑说明](https://openpyxl.readthedocs.io/en/3.1.1/editing_worksheets.html)。打包采用 [PyInstaller 的目录分发方式](https://www.pyinstaller.org/en/stable/usage.html)。

