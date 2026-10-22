# Complete-cell layout implementation plan

> Execute isolated native formatting, native pagination and Python plan/validation tasks using subagent-driven-development. Parent integrates atomic formatting and publication. User approved fallback group-to-next-page.

**Goal:** All managed cell content visible in saved Excel/PDF, with the final detail/footer group on one page.

**Architecture:** Shared software-owned Python geometry plan, native Excel content fitter, native PDF pagination with per-cell proof, and Python PDF proof validation. Existing skill/engine fonts remain unchanged; parent stages formatting and verifies value/formula fidelity before publication.

## Global constraints

- V1.1.21, Windows10/11, existing dependencies. Do not change skill/engine, invoices, amounts, signature storage or runtime eligibility. Parent alone commits/publishes.
- No tests, GUI/Excel/application execution, business-file reads or processing by agents. Static compile/AST/review only; no runtime success claim.
- All new/edited PowerShell resource scripts must be ASCII so Windows PowerShell5.1 reads safely. All Chinese worksheet/header/content strings come from UTF8 JSON input. Close only a verified privately created Excel process, never user's Excel.
- Preserve personal signatures and rule files byte-for-byte in local upgrade; exclude all personal files from public archives. No GitHub upload this turn.
- Preserve original cell values/formulas/number formats/fonts/merges; wrapping/height/necessary numeric column expansion only. Never silently clip, truncate or shrink source fonts. Row height cannot exceed409pt.
- All columns remain one printed page wide, pages A4 landscape. At most5% extra shrink relative to width-fitting base zoom; otherwise move final detail+all footer content together. Fail explicitly if it cannot fit one page.

## Shared JSON geometry contract

`invoice_desktop/layout.py` exports `sheet_layout(ws)->dict` and `layout_plan(path)->dict` with `schema_version:1,sheets:[...]`. Each sheet includes:

```
name, header_row, footer_row, last_detail_row,
print_end_row, print_end_column, print_area (A1:...),
numeric_columns:[1-based indices for sequence,quantity,price,amount],
content_cells:[A1 addresses of every nonempty cell anchor, sorted row/column],
columns:{Chinese header:1-based column},
tail_start_row:last_detail_row, tail_end_row:print_end_row
repeat_start_row,repeat_end_row: preserved original print-title rows, default 1:header
```

Validate unique headers/footer/roles/dates, actual last product-bearing sequence row, bounds/merges and meaningful nonempty content. `content_cells` includes formulas and text; no styled-only cells. Max print range extends to merged extents of nonempty anchors. All rows/columns in scope visible. Do not infer last detail as footer-1 where retained blanks exist.

`pdf_export._sheet_plan` starts from sheet_layout and adds file_name and existing optional signature metadata, preserving current names/types. Export script reports `status:completed,sheets:original plan.sheets,layout:[...]` (do not mutate input plan.sheets).

Native layout report each sheet:

```
name, zoom (10..100 integer), base_zoom, expected_pages,
break_rows:[row numbers after which the next page begins, i.e. HPageBreak.Location.Row],
tail_start_row,tail_end_row,
cells:[{address,page:1-based,box:[left,top,right,bottom] in PDF points,
        text:actual Excel formatted .Text,orientation:numeric}]
```

Each source content cell appears on its native page; repeated title cells also on later pages. Cell boxes include merged area extents. Compute from actual margins, numeric zoom, optional horizontal centering, actual HPageBreak rows and actual repeated-title heights. Force vertical centering off for deterministic row flow. Empty formula display may have text="". Row/text/number values themselves must not change. Python checks coverage of every content address, valid page/box and actual PDF text in each crop (NFKC/whitespace normalization; rotated text can use normalized character counts). All group cells/native breaks must prove a single final page.

## Task 1: Native Excel fitting (agent)

Own new resources/excel_layout.ps1 and resources/format_workbook.ps1 only.

- [ ] excel_layout.ps1 defines `Fit-InvoiceContent($book,$item)`; no script-level side effects. Whole book/plan passed by native caller. Fit wraps/shrink-disabled, numeric widths at least template (avoid merged title in column AutoFit), native row AutoFit plus original minimum, explicit merged-cell measurement on a temporary unmerged probe sheet using actual combined width/rich fonts. Preserve source merges/content. Any temporary measure sheet deleted even on failure. Check numeric hashes/errors and409pt cap with sheet/address errors. Keep required blank rows and side content.
- [ ] format_workbook.ps1 params WorkbookInput,PlanFile; create and prove own Excel instance with Hwnd/PID/start-time and no existing books, watchdog; disable events/macros/links. Open staged file readwrite, apply both sheets through Fit-InvoiceContent, calculate/save only on success, cleanup all COM/owned instance. Reuse existing export ownership pattern. No original-file publication here; parent owns that.
- [ ] Static PowerShell AST parse, source self-review, report .superpowers/complete-cell-layout/fit-report.md. No execution of these scripts, Excel, tests or commits.

## Task 2: Native PDF pagination/proof (agent)

Own resources/export_pdf.ps1 and optional new resources/pdf_pagination.ps1 only. Keep current process ownership, printer selection, timeout/cleanup and no Save.

- [ ] Consume geometry fields. Actual A4 landscape print area, native repeated headers, no repeated columns. Set numeric zoom from print width and confirm no VPageBreak within range (decrease if necessary). Native breaks after PrintCommunication/DisplayPageBreaks refresh; preserve all content and heights.
- [ ] Check group split; try up to5% lower zoom to hold on current/earlier page. If no candidate succeeds, restore base zoom and Add HPageBreak before tail_start_row. If header-only first page/oversize group or resulting native breaks still split group, fail with worksheet reason. Do not use FitTo mode for manual breaks.
- [ ] Emit report contract with expected pages and per-cell actual text/merged area source geometry in PDF point coordinates. Handle repeated-title rows, centered width and margins; force vertical centering false. Detect any numeric #### and out-of-page content. Export only after native checks, report extra layout without modifying echoed plan.sheets. Do not save workbook.
- [ ] Static PowerShell AST parse, source self-review, report .superpowers/complete-cell-layout/pagination-report.md. No execution/Excel/tests/commits.

## Task 3: Python geometry/PDF validation (agent)

Own new invoice_desktop/layout.py, invoice_desktop/pdf_layout.py and invoice_desktop/pdf_export.py only.

- [ ] Implement shared geometry contract, dynamic complete tail and full content anchors. Keep no dependency on controller/pdf_export in layout.py; can import workbook HEADERS/SIGNERS/text. Implement layout_plan load/close with openpyxl (no actual file execution during development).
- [ ] Adapt _sheet_plan to geometry while preserving optional source row/font signature metadata. Production export requires native report.layout (two matching sheets). Existing report.sheets equality retained.
- [ ] pdf_layout validates native coverage/pages/group/no split/boxes, actual per-cell crop text normalized NFKC+whitespace; rotated text character counts allowed. Validate source expected content per known geometry addresses, not missing silent cells. Use existing pdfplumber, no new dependency. Integrate _validate_pdfs before signing and after signing with report proof, preserving A4/pair publication/source fingerprint guards.
- [ ] Static Python compile/self-review, report .superpowers/complete-cell-layout/python-report.md. Do not run modules, PDFs, workbooks, tests or commits.

## Task 4: Parent integration and release

- [ ] ExcelAdapter.apply creates same-directory staged .xlsx and temp plan JSON, calls shared engine fonts then software content fitter on staged file. Verify source fingerprint unchanged and compare all worksheets/nonempty cell values/types/formulas/merges before os.replace; clean only exact owned temporary file. All formatting failure paths preserve original workbook (already-written detail stage remains existing workflow state).
- [ ] run_excel.ps1 accepts LayoutPlanFile, calls engine then format_workbook; errors propagate. Set writer data wrap/shrink alignment flags in memory before native fitting without changing values.
- [ ] Update policy/user guide/README/version1.1.21 and feature boundaries. Static review all task interfaces, PowerShell AST and watchdog C# compilation only, Python compile, independent whole-change review; resolve material findings.
- [ ] Capture baseline private/rules/engine/skill/protected bytes, build, verify embedded source/resources/format scripts, preserve private data and rules. Guard running software/path/reparse points; archive old directory, update original release folder, create new1.1.21 ZIP/source/checksums and verify all members/no private files. Record runtime limitations; no GitHub upload.

## Progress

Implementation and independent static reviews complete; final Windows build and saved-artifact integrity passed. Native probes use a separate unsaved scratch workbook, frozen formula-result values and literal string assignment; saved source formula values/types are checked after fitting and saving. Geometry/native report coordinate repeat_start_row/repeat_end_row for preserved custom title ranges. Original personal signature files and rule snapshots match the built copy byte-for-byte. Local publication/packaging follows. Actual Excel/PDF rendering not exercised.
