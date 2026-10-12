# 发票汇总助手

Windows 离线桌面软件，使用 summarize-invoice-pdfs 的识别脚本与规则快照。电脑须安装 Microsoft Excel 桌面版。

## 执行步骤

1. 完整解压发布包，双击 `InvoiceSummary.exe`。
2. 选择完整批次的 PDF 文件夹和目标 `.xlsx` 工作簿。
3. 点击“只读预览”，核对文件名、明细、金额和异常；解决异常后重新预览。
4. 预览通过后点击“执行处理”，等待完成。
5. 查看金额复核结果和临时文件清理状态。继续处理前重新预览。

**执行会重命名 PDF，并直接更新原工作簿；不自动创建备份。**

## 必要条件

- Windows 10/11，已安装 Microsoft Excel 桌面版；软件离线运行，无需安装 Python 或 Node.js。
- 完整解压整个软件文件夹，保留 `InvoiceSummary.exe`、`_internal` 和 `recognition`。
- 有文本层的电子 PDF；选择完整批次，不支持扫描图片 OCR。
- `.xlsx` 含“验收”“领用”两表，以及约定的表头、日期标签和唯一“合计—签字—说明”三行页脚。已有明细须能在所选 PDF 批次中找到对应发票。
- 执行前关闭 Excel 中的目标工作簿；软件和输入文件所在目录须可写。

0.1.2 起，软件默认处理页顶部直接显示“执行步骤”和“必要条件”；“使用说明”页和发布包内的说明文件也优先展示这两项。

## 人工校正

0.1.3 起，在只读预览中选中明细并点击“人工校正”，或直接双击该行。对照原 PDF 修改产品名称、规格型号、单位、数量、含税金额和生产厂家；单价自动计算。弹窗同时显示原识别值和当前值，支持“打开原发票”和“恢复识别值”。

点击“保存并检查”只更新本次预览；软件重新检查金额、改名碰撞、工作簿模板与已有明细对应关系，通过后才允许执行。校正过的明细会高亮，检查结果记录修改前后值。已有表格行仅在业务字段与原识别值或校正值明确对应时按本次校正更新，不强制覆盖不对应的内容。

这是软件本地功能，不修改或训练 skill。只能校正已有明细字段，不能增删明细、改序号或修改票面总额；漏项、多项和整票解析失败仍需改进 skill。数量空白按 1，非空须为有效非零数字；名称、生产厂家不能为空，规格和单位可空。校正后的每票明细合计必须仍与原票面总额逐分一致。

校正只对本次预览有效；重新发起普通预览会重新识别，需要再次校正。执行中断时校正随本机恢复记录保留，核对 PDF 哈希和识别版本后恢复；恢复期间先完成上次运行，再进行新的人工校正。记录不会随软件目录分发。

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

