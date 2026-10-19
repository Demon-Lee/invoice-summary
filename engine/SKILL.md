---
name: summarize-invoice-pdfs
description: Use when users need help processing invoice PDFs, populating acceptance and issue sheets, reconciling invoice totals, or invoke /invoice-summary.
---

# Summarize Invoice PDFs

## Slash-command alias

Treat `/invoice-summary` as an explicit invocation of this skill. Read `commands/invoice-summary.md` first, then follow the same preview, issue-gated writing, and verification gates required below.

## Discount-and-fee detail rule

If both a parsed detail's amount and tax are negative, merge both components into the most recent genuine normal detail and emit only the merged row. 当明细金额为负、税额为 `0.00`、数量和单位均为空时，将其视为税额因四舍五入归零的折扣候选；仅当它与最近正常明细的规范化项目名称相同才合并，否则作为异常停止该发票。 A project name containing `配送费`, `运费`, `快递费`, `物流费`, `邮费`, or `运输费` is an additional-fee detail: merge both components into that same most recent genuine normal detail and emit no separate row. Consecutive discounts and additional fees each accumulate into the same most recent genuine normal detail; neither a discount nor a fee can become a merge target. If either appears before a genuine normal detail, surface an exception and do not write that invoice's rows. A mixed-sign non-fee detail, where one component is positive and the other is negative, is normal and is not merged. The merged row's amount remains amount plus tax, and exact-to-the-cent verification remains mandatory.

Coordinate `scripts/invoice_pipeline.py` and `scripts/write_summary.mjs`. Treat every source PDF and workbook as immutable input until the clean-run gate below passes or the user resolves a reported problem. The user's request to process the invoices authorizes the standard clean-run rename and direct workbook write; it does not authorize guessing, conflict overwrites, template repair, or expanded scope.

## Invoice-layout and filename rules

- Treat both `\u9879\u76ee\u540d\u79f0` and `\u8d27\u7269\u6216\u5e94\u7a0e\u52b3\u52a1\u3001\u670d\u52a1\u540d\u79f0` as detail-table headers. Shenzhen electronic invoices using the latter still use the seller name in the `\u9500\u65b9` section as the production manufacturer.
- A tax-rate field of `\u514d\u7a0e` or `\u4e0d\u5f81\u7a0e` means a valid zero-tax detail. If the PDF omits a unit, write a blank unit cell without raising an exception.
- 广东电子发票的销方可与深圳版处于同一侧或下方的销方区域。若“名称：”被 PDF 拆为相邻坐标文字（如“名”“称”“：”），按同一视觉行重组标签；买卖方左右并列时选最右标签、上下排列时选最下标签，并只读取该标签后的同一行名称。无法同时确认标签和候选值时保留销方解析异常。
- 同一发票中的同序号、同产品名称、同规格型号明细必须保留为独立明细行，按发票原始顺序写入；不得因键重复而合并或跳过。
- 数量为空时写入 1，并按金额除以 1 写入单价公式；零数量或非空非数值数量仍作为异常处理。
- For a wrapped `*\u7c7b\u522b*\u9879\u76ee\u540d\u79f0`, reconstruct the complete value from adjacent project-column words before deleting the two-asterisk category. This reconstructed project name is used for both the Excel product name and the PDF filename's project-name portion.
- 正常文本解析和坐标回退解析都要核对名称与规格的列归属：同一视觉行内完全位于项目名称列的普通文字片段，即使不含星号，也必须合入名称；规格取规格列实际文字，不按空格分词推断。按坐标保留同一视觉行的可见空格，跨行只去掉排版换行，不额外补空格；跨列的文字片段不能仅凭起点坐标当作名称。例如名称列首行 `VG101 VGA公`、次行 `对公线 1米`，规格列 `11673`，应得到名称 `VG101 VGA公对公线 1米`、规格 `11673`，同步用于 Excel 与 PDF 文件名。金额一致不能证明名称和规格正确，仍需核对这两个字段。
- 只有项目名称列坐标范围内以 `*` 开头的文字才能作为新明细起点；规格型号列中的星号文本属于规格续行（例如 `*Φ6*30-50`），应追加到该明细的规格型号，并继续合并项目名称列续行。
- 若产品文本以重复的前置星号类别段开头（例如 `*类别**类别*指示灯`），必须连续剥离每个完整的 `*类别*` 段，直至首字符不再是星号；产品名称应为剩余业务名称（示例为 `指示灯`），并同步用于 Excel 与 PDF 文件名。
- 规格型号仅能取自商品明细所在行，或其紧邻的一行纯字母数字续行；一旦出现金额、合计、销方名称或其他非续行文字，即停止续接。不得把下方销售方纳税人识别号等元数据拼入规格型号。
- 当单位列因版式换行被拆分为明细行与其紧邻的视觉续行时，仅在续行仍位于单位列坐标范围、处于下一明细或“合计”之前，且能唯一归属于该明细时拼接。例如“千克(公” + “斤)”写为“千克(公斤)”；无法唯一归属时作为单位解析异常，不得截断或猜测。
- Apply established semantic splits when their exact extracted text occurs: `\u9600\u95e8\u5185\u4e1d\u7ba1` + `\u4e0d\u9508\u94a2 6\u5206` becomes product `\u9600\u95e8 \u4e0d\u9508\u94a2\u5185\u4e1d\u7ba1` and specification `6\u5206`; `\u5fae\u578b` + `4\u82af\u516c\u7f06 4\u82af` becomes product `\u5fae\u578b 4\u82af\u516c\u7f06` and specification `4\u82af`. Use this normalized product text for both the workbook and the PDF filename.
- Use only Windows-safe PDF filename components. Replace `/` with `\uff0f` (and other reserved filename characters with their safe equivalents) only in the filename; retain the original project text in Excel.
- Treat source PDF filenames as opaque: extract the invoice content from the PDF rather than inferring a product or sequence from its original filename. The preview rename plan is the sole source of the final filename.
- Sort PDFs that have a numeric prefix by that prefix's numeric value (so `2.` precedes `10.`), then assign continuous sequence values from 1. Use those new values consistently in both renamed PDF filenames and the workbook's `\u5e8f\u53f7` column.
- For rename state, a computed destination equal to its source is `unchanged`, not a collision. In a mixed batch leave `unchanged` files in place and rename only `ready` files; abort the entire rename only when a destination exists for a different source file.
- 当 PDF 文本层将明细排在“合计”标签之后，或将相邻数量与单价粘连为一个 token 时，按页面坐标重建字段；仅在数量、单价和未税金额的拆分唯一且逐分校验通过时写入，否则作为异常保留，不得猜测。
- 当明细因文本层顺序异常进入坐标回退解析时，仍必须合并项目名称列的续行，不能只保留首行。按视觉行顺序重建完整名称，保留拉丁品牌、型号以及同一视觉行独立词之间的可见空格；跨行仅消除排版换行，不得删除原有词间空格或把规格型号列内容误并入名称。

## PDF classification and non-invoice exclusion

- 编号前使用 `scripts/invoice_pipeline.py` 的 `classify_pdf_document` 按 PDF 全部页面的实际文本分类，不从文件名推断，不把“发票字段解析失败”等同于“非发票”。有明确标题的验收／领用表、送货／出入库单、申请／报销表、报价／合同／说明书等，只有没有发票特征且每页均能确认为非发票时才自动跳过。含有发票页的混合文件继续发票识别，不得因其他页面为表单整份跳过。
- 扫描件、损坏文件、无文本／类型不明的页面仍报异常；疑似发票仍须通过完整字段、明细和逐分金额校验，不能因为缺字段自动跳过。只跳过明确的非发票，不支持的版式须改进识别。
- 查验报告仍要求 National VAT Invoice Verification Platform 标识加 `查验次数` 或 `查验时间`，按内容识别；若同页还出现独立原票标题，视为内容冲突并报告具体页号，不自动跳过。类型字段中的发票种类名称不作为原票标题。不将报告匹配、改名或纳入发票金额校验，也不按发票金额要求提供查验报告。
- 所有明确跳过文件记录在结果的 `skipped_files`，含 `pdf`、`kind`、`reason`，在 preview／rename／verify 间保留。它们不占发票序号，不改名，不填表，不计入发票数量或金额。在预览和完成反馈的“异常”项目下另列“已跳过（非阻塞）”清单与原因，明确未参与上述处理；查验报告仅作跳过说明，不作为发票处理结果。没有任何可处理发票时停止，不得清空工作簿。

## Required safety gate

1. Require selected PDF paths or a selected PDF directory and a workbook ending in `.xlsx`. Reject any other workbook extension before inspection or writing.
2. Use `preview` first. Review its detail rows, shared per-PDF sequence, filename derived from the first cleaned detail name, invoice rename plan, and exceptions.
3. Run the workbook writer with `--dry-run` to inspect the `验收` and `领用` headers and preview the mapping. Do not rename a PDF or write a workbook in this phase.
4. Show the invoice rename plan, all preview exceptions, and the exact user-provided workbook path that will be changed. Classify the run before mutating anything.
5. A run is blocked when it has any unresolved invoice parsing or required-field exception, non-unique candidate, real rename collision, zero or non-numeric nonblank quantity, workbook extension/header/date/footer/mapping failure, writer dry-run exception, amount mismatch, required guess, template repair, conflict overwrite, or expanded authority. A parsing exception resolved through unique coordinate reconstruction and exact-to-the-cent validation is disclosed as resolved and does not block.
6. For a clean run with changes, display the fixed preview response below and then, in the same turn without waiting for another user reply, run `rename --apply`, write directly into the provided `.xlsx` workbook with `--in-place`, apply mixed fonts, collect totals, and verify. Do not create an automatic backup or a separate workbook copy.
7. For a blocked run, display the same fixed table and ordered summary, identify every problem and the operations not performed, ask one concise question needed to resolve it, and stop. Do not rename any invoice PDF or write the workbook before the user responds.
8. If there is no new invoice change, no workbook row to add, and both dry-run `blankRowsToRemove` counts are zero, report that no action is needed and perform no mutation. If either count is positive, the standard clean-run write also removes those surplus blank rows.

## Fixed preview response format

After `preview` and workbook `--dry-run` pass, use this response contract exactly. Begin with:

`只读预览与 dry-run 已通过，尚未改动文件。计划如下：`

Then show one Markdown table with exactly these headers:

| 序号 | 新增 PDF → 新文件名 | 规格型号 | 单位 | 数量 | 含税金额 |
|---:|---|---|---|---:|---:|

Populate the table as follows:

- Include only invoices that this run will add or rename. Show each mapping as `source.pdf → sequence. cleaned-project.pdf`.
- Emit one row per written detail. For a multi-detail invoice, repeat its sequence and PDF mapping on every detail row in source order.
- Use the written row's specification, unit, effective quantity, and tax-inclusive `amount`. Format the amount as `¥0.00`.
- Display `—` when specification or unit is blank.
- The cleaned product name appears only inside the destination PDF filename; do not add a `产品名称` or `明细` column.

After the table, present these items in this exact order:

1. `新增合计` and `写入后总计`; for a non-incremental batch, use `本批合计` instead of `新增合计`.
2. `原有文件`: state the unchanged invoice range, or `无`.
3. `异常`: separate resolved exceptions from unresolved exceptions and state `无` for either group when empty.
4. `dry-run`: state the `验收`/`领用` header, mapping, footer, and exception results.
5. `目标工作簿`: show the exact user-provided `.xlsx` path, say it will be updated in place, and say no automatic backup will be created.

For a clean run with changes (including surplus blank-row removal), end the preview response exactly with:

`未发现阻塞问题，现继续执行改名、写入和验证。`

After displaying that sentence, continue immediately in the same turn; do not ask for `确认执行` or any other clean-run confirmation. If a problem blocks apply or writing, keep the same table and ordered items but end with one concise question needed to resolve the listed problem, then stop without mutation. When there is no new invoice to list, keep the table headers and add a single row whose first cell is `无新增发票`. Report each sheet's pending blank-row removal count; continue the clean-run write if either is positive. State that no action is needed and perform no mutation only when there is also no workbook row to add and both removal counts are zero.

## Fixed completion response format

After rename, workbook writing, mixed-font application, totals collection, and `verification` all succeed, show the same invoice table again as the actual completion result. Introduce it with `处理完成，实际已完成的发票如下：` rather than presenting another plan, and use exactly these headers:

| 序号 | 新增 PDF → 新文件名 | 规格型号 | 单位 | 数量 | 含税金额 |
|---:|---|---|---|---:|---:|

Populate it with the invoices and detail rows actually completed in this run, using the final PDF filename and the values written to the workbook. Keep the same row, blank-value, multi-detail, and currency-format rules as the preview table. For a run that only removes surplus blank rows, use the same `无新增发票` row and report the removal counts. After the table, report the verified new or batch total, post-write total, sequence verification result, both worksheet footer totals, exceptions, and the final PDF/workbook outputs. Do not replace this completion table with prose or a different action-summary table.

## Required post-run cleanup

Track the exact scratch paths created during the current run. After their contents have been read for reporting, clean them up before the final response on successful, blocked, no-change, and failed runs. Current-run scratch artifacts include the run directory's `preview.json`, `rename-report.json`, `totals.json`, and `verification.json`; writer-generated `.inspect.ndjson` files; and the generated `.exceptions.json` report. Remove the current run directory after its files are deleted, and remove a parent temporary directory only when this run created it and it is empty.

Delete only artifacts proven to have been created during the current run. Never delete a final renamed PDF, workbook, template, user-provided input, or any pre-existing file. Do not use a broad filename or directory deletion unless its matches are first intersected with the tracked current-run paths. The final response must state the cleanup status; if any scratch artifact could not be removed, list its exact path instead of claiming cleanup succeeded.

## Default execution scope

For every invoice-processing request, use the core workflow by default: input discovery, `preview`, writer `--dry-run`, fixed plan feedback, clean-run automatic rename/apply and in-place write, and exact-to-the-cent verification. Stop for user input only when the problem gate above is triggered.

Automatic removal of surplus trailing data rows is part of the core workflow, including preserving the moved footer's existing row heights. After the required verification passes, stop. Do **not** render PDFs or workbook sheets, export print previews, inspect print layout, alter pagination, change column widths or row heights, or perform visual-format QA unless the user explicitly requests printing, layout, visual review, or formatting improvements.

If verification fails, diagnose only the specific failure and make the smallest change needed to satisfy the required data and amount checks. Do not turn a verification failure into a print-layout or presentation-polish task. Treat the following as explicit requests for the enhanced workflow: `打印`, `打印版`, `版式`, `视觉检查`, `渲染`, `预览图片`, `格式美化`.

## Workbook run-date contract

- On every formal workbook write, read the machine-local date once and write the same `YYYY.M.D` value, without zero padding, into both footer signature rows.
- In `验收`, require exactly one `验收日期：` label in the validated signature row and replace the cell immediately to its right. In `领用`, apply the same rule to `领用日期：`.
- If either label is missing, duplicated, or has no adjacent date cell, stop and report the worksheet and row instead of guessing a destination.
- `--dry-run` may validate this contract in memory but must not save a workbook or change the input file.

## Workbook footer contract

- 在 dry-run、正式写入和写后复验中，`验收`与`领用`都必须各有一个唯一三行页脚，连续结构为“合计—签字—说明”。`验收`签字行的 A/D 列分别以“经办人/验收人”开头；`领用`分别以“保管人/领用人”开头；说明行 A 列以“说明”开头。
- 缺少、重复或残缺页脚时立即停止并报告工作表及行号。若出现多个“合计”，不得自动选择其中一行继续；失败时不得替换原工作簿或遗留暂存文件。
- 页脚结构异常时只报告并等待处理。未经用户确认，不得从外部模板自动覆盖或修复页脚；用户确认修复时还必须先确认模板可信且与当前工作簿匹配。

## Expanding workbook data areas

- When the requested details exceed the blank rows in either acceptance or issue sheet, add exactly the required number of data rows immediately below the headers and before the validated unique total row. Never write over a footer or append details after it.
- New data rows must inherit the template data-row border, row height, number formats, and other layout attributes. Written fields must then be centered; Chinese text uses Songti and Latin text/numbers use Times New Roman.
- Move the complete three-row footer block down by the same number of rows, including labels, formulas, row heights, cell styles, and merges. When source and destination rows overlap, copy from the bottom row upward so no source footer row is overwritten. Update the quantity and amount total formulas to include every data row. A merged footer must not overlap a data row.
- After all footer-layout restoration and workbook re-import steps, recompute quantity and amount footer formulas in both sheets from the final header and footer positions; verify the final saved formulas.
- Preserve SpreadsheetML namespaces during any XML layout repair; an unprefixed row in a prefixed worksheet is invalid for Excel and must be normalized before completion.
- Formula caches may contain insignificant IEEE-754 tails (for example `1540.1100000000001`). Treat a footer total as cent-exact when its deviation from a two-decimal value is at most `0.000001`; continue rejecting a material fractional-cent difference.

## Removing surplus blank data rows

- `scripts/template_rules.json` 是与桌面软件共用的可同步模板规则；写表器读取其中的完整侧边标识、忽略标点和允许的单格／连续同列排列方式。`schema_version: 1` 的 `sidebar-label-end` 策略按工作簿实际坐标确定最低保留行，主表终列包括覆盖表头的合并区域。`label_value_source: literal-cells` 要求右侧模板内容为固定值，遇到右侧公式即停止并报告坐标，不依赖公式缓存判断标识。修改这些声明时同步维护本节说明；不能仅修改文档让软件自动生成算法。新增未支持的策略、接口或写表器算法需要先适配软件。

- Every formal write automatically removes the removable continuous blank rows before the validated unique `合计—签字—说明` footer, independently in `验收` and `领用`. Rows with any text, value, remark, or formula (including outside mapped invoice columns) count as populated; preserve internal blank rows and all invoice detail rows.
- 删除末尾多余空行时，动态定位主表右侧完整的“第二联：财务报销”标识；支持整句位于一个单元格，或在同一列连续多个单元格中逐字／分段排列。以该标识最后一个“销”字实际所在行作为模板最低保留行，不能固定为第 13 行，也不能仅搜索任意一个“销”字。每张表独立判断；没有该标识时沿用原删行规则，不从外部模板补字。
- 明细区域最终保留到“最后有内容的行”和“模板最低保留行”中的较大者。项目较少时，两者之间的空白明细行必须保留原边框、样式和行高，不写入假序号、数量或金额；三行页脚紧随保留区域。若标识结束于第 13 行且最后一条明细在第 5 行，保留到第 13 行，合计在第 14 行；标识结束行变化时按实际行号计算。若明细超过该标识，则按更靠后的实际内容行确定页脚。
- Preserve the footer's cell contents, signature dates, borders, fonts, row heights, and merged cells while updating row coordinates and print-area references. Recompute quantity and amount SUM ranges for the retained data area, including its required blank rows; use `=0` only when the retained data area has no rows. 标识已经落在合计、签字、说明行或其下方时，预览停止并报告实际结束行与合计行，要求恢复完整模板；不继续生成页脚在标识上方的结果，不自动从其他工作簿修复。
- The writer's `--dry-run` reports per-sheet `blankRowsToRemove` and `minimumRetainedRows` (the actual one-based legend ending row, or `null` when absent), without changing the workbook. Formal writing compacts the staged workbook before replacing the target, checks that the original legend cells remain intact and the footer stays below the template minimum, and rejects removable blank rows below the retained area. Required blank rows up to the template minimum are valid. Then apply mixed fonts/recalculation and run the normal amount verification.
- A later incremental run passes the complete directory preview (existing and new invoices) to the writer, expands the compacted data area when needed, and moves the complete footer down again. Do not pass only the new subset of records to this writer. For example, headers in row 3 and 14 populated detail rows place the final detail in row 17; when the side legend ends no later than row 17 and there is no other later content, the footer occupies rows 18–20 and unused template rows 18–61 are removed. A side legend ending later requires retaining data rows through its actual ending row instead.

## Verification

After writing, run `collect_excel_totals.py` before `invoice_pipeline.py verify`; it reads the workbook without changing it and writes the required totals JSON. It must apply the same unique three-row footer contract as the writer and reject duplicate or malformed footers instead of selecting the first or last marker. Verification requires the batch PDF grand-total sum, the acceptance footer amount, and the issue footer amount to match exactly to the cent. It also requires each PDF grand total, detail amount-plus-tax total, and matching acceptance sequence amount total to match exactly to the cent. Treat a missing header, invalid footer structure, or amount value as an explicit verification error.

## Commands

Use the bundled Python and Node runtimes already configured for this workspace.

```powershell
python scripts/invoice_pipeline.py preview --pdf-dir <selected-pdf-dir> --report <preview.json>
node scripts/write_summary.mjs --input <template.xlsx> --records <preview.json> --dry-run
python scripts/invoice_pipeline.py rename --records <preview.json> --apply --report <rename-report.json>
node scripts/write_summary.mjs --input <user-workbook.xlsx> --records <preview.json> --in-place --exceptions <exceptions.json>
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/apply_mixed_fonts_excel.ps1 -WorkbookInput <user-workbook.xlsx>
python scripts/collect_excel_totals.py --input <user-workbook.xlsx> --output <totals.json>
python scripts/invoice_pipeline.py verify --records <preview.json> --excel-totals <totals.json> --report <verification.json>
```

Write each PDF detail into `验收` and synchronize `领用`. In `验收`, normalize a blank quantity to `1`, then write the unit-price formula as `=amount-cell/quantity-cell` only for a numeric nonzero quantity; do not round or precompute it. Copy values only (never formulas) to `领用` for exactly: sequence, product name, specification, unit, quantity, unit price, and amount. Do not copy manufacturer.

Finish by collecting the read-only totals JSON and then running `invoice_pipeline.py verify --records <preview.json> --excel-totals <totals.json> --report <verification.json>`. Pass only if each PDF total, detail amount-plus-tax total, and matching `验收` sequence amount total match exactly to the cent, and the batch PDF grand-total sum, `验收` footer `金额`, and `领用` footer `金额` all match exactly to the cent. Present every exception (missing fields, collisions, zero quantity, missing header/footer/amount, or mismatch) and leave affected rows unchanged where the script reports a conflict.
