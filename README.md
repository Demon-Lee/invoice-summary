# 发票汇总助手

Windows 离线桌面软件，使用 summarize-invoice-pdfs 的识别脚本与规则快照。电脑须安装 Microsoft Excel 桌面版。

## 使用

解压发布包，双击 `InvoiceSummary.exe`。选择完整 PDF 批次目录与目标 `.xlsx`，先只读预览，检查无异常后执行。原位更新工作簿，不自动创建备份。电子发票需包含可解析文本层，首版不提供 OCR。

## skill 更新

识别引擎有独立版本。0.1.1 起，当前规则和回退快照保存在软件文件夹的 `recognition` 目录中。

维护者操作：更新 skill → 打开“规则与更新”并选择整个 skill 文件夹 → 点击“同步本机 skill” → 等待更新完成 → 关闭软件 → 打包整个 `InvoiceSummary` 文件夹。请保留 `InvoiceSummary.exe`、`_internal` 和 `recognition`。

接收方完整解压软件包后直接运行即可使用随包规则，无需绑定 skill 或导入更新包。请在新文件夹完整解压新版，或完整替换旧软件文件夹；只复制 EXE 不会携带规则及依赖。

软件文件夹需可写才能同步或回退规则。维护者的 skill 路径绑定和未完成业务运行记录保存在本机 AppData，按软件目录区分，不包含在分发目录中。软件不会自动绑定接收方电脑的 skill；当随包识别版本变化时，旧绑定失效。

仍可用“导出离线更新包”“导入更新包”单独传递规则。“回退版本”切回上一个识别快照并解除本机来源绑定；再次打包软件目录时会携带回退后选中的版本。

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
python tools/package_release.py --directory release/InvoiceSummary
```

流程诊断只处理临时复制的 PDF 和新生成的测试工作簿，原始 PDF 不会修改。诊断报告不要作为发布包资产。

构建时，`tools/prepare_portable.py` 优先保留现有 `release/InvoiceSummary` 中的规则；首次升级才读取旧 AppData 中兼容的规则。只复制规则白名单和清单，不复制个人路径、设置或业务记录。运行中的软件直接使用所在目录的规则，旧 AppData 规则不参与选择。

## 实现

Python/tkinter、pdfplumber、openpyxl 与 Microsoft Excel 自动化。现有 Node 写表器依赖的 OpenAI 内部评估组件不随软件分发，软件使用独立的 openpyxl 写表器执行同一模板约定。openpyxl 的行移动不会自动维护所有相关结构，因此软件明确处理页脚合并、行高、打印区域和总计公式；参考 [openpyxl 行编辑说明](https://openpyxl.readthedocs.io/en/3.1.1/editing_worksheets.html)。打包采用 [PyInstaller 的目录分发方式](https://www.pyinstaller.org/en/stable/usage.html)。

