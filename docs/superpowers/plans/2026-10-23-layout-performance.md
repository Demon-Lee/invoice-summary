# Layout Performance Implementation Plan

> **For agentic workers:** Execute inline using executing-plans, with an independent static review before publication.

**Goal:** Complete the reproduced20-detail batch within the existing210-second native formatting guard while preserving complete content and readable timeout errors.

**Architecture:** Retain Excel bulk AutoFit and the existing two-pass, frozen-formula workflow. Limit costly scratch-copy measurements to actual overflow and nonstandard geometry; cache only verified scratch-column conversions.

**Tech Stack:** Python3.12, PowerShell5.1, Microsoft Excel COM, existing PDF tooling.

## Global Constraints

- V1.1.21; local release only; shared engine/skill and private signatures unchanged.
- Runtime work uses temporary copies only; no invoice processing or renaming.
- Keep210-second native deadline, private-process ownership, source fingerprints and atomic replacement.

### Task1: Reduce redundant native measurements

Files: resources/excel_layout.ps1.

- [x] Establish red baseline: .superpowers/rpc-format-investigation/reproduction.json records20-detail failure,210.765s watchdog timeout, original unchanged.
- [ ] Add optional width cache to Set-InvoiceColumnPoints and Measure-InvoiceCell. Key by exact invariant point width; use only in the current scratch workbook; verify native Width after applying a cached setting before accepting it.
- [ ] In Fit-InvoiceContent, measure numeric width only for the native display matching `^#+$`; preserve existing expansion and overflow failure.
- [ ] After native row AutoFit, independently measure merged ranges, selected caption spans, and ordinary cells with RowHeight>=408pt. Ordinary cells below that limit retain native AutoFit's result; all cells retain error/hash checks.
- [ ] Re-run the exact full-batch temporary production adapter and require completion below210 seconds, unchanged contents and correct cached totals.

### Task2: Preserve timeout diagnosis

Files: resources/format_workbook.ps1, invoice_desktop/controller.py.

- [ ] Before cleanup, translate TimedOut into `INVOICE_FORMAT_TIMEOUT` plus current stage and elapsed seconds. Keep other original errors.
- [ ] Guard cleanup operations individually so disconnected COM cannot mask the primary failure or skip owned-process cleanup.
- [ ] Map the stable timeout marker in ExcelAdapter._run to a concise Chinese error; retain existing behavior for other failures.
- [ ] Force a short deadline in an ignored diagnostic script copy, verify the marker/Chinese translation and unchanged public workbook copy; never shorten production timeout.

### Task3: Verify and publish original portable folder

Files: docs/release-checks.md; ignored runtime/build/publication helpers.

- [ ] Validate20-detail and1-detail temporary formatting and PDF exports; render both sheets and review text/footer layout. Record timings for formatting and PDF separately.
- [ ] Exercise long literal/formula/merged content via temporary fixtures; preserve values, formulas, merged ranges, fonts and number formats where applicable.
- [ ] Run only focused authorized checks, syntax/AST, independent static review, Windows build and saved-byte integrity checks.
- [ ] Verify app closed; archive old portable directory/packages and replace original release/InvoiceSummary. Preserve signatures/rules, exclude signatures from ZIPs.
- [ ] Repackage source, binary and checksums; record actual evidence and remaining scope; no GitHub upload.
