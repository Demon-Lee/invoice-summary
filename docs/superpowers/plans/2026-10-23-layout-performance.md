# Layout Performance Implementation Plan

> **For agentic workers:** Execute inline using executing-plans, with an independent static review before publication.

**Goal:** Complete the reproduced20-detail batch within the existing210-second native formatting guard while preserving complete content and readable timeout errors.

**Architecture:** Use Excel native column/row AutoFit for all detail columns and retain the two-pass formula snapshot guards. Remove scratch-copy measurement, width searches and caches. Preserve template width/height minima, reject unsupported merged details or capacity failures, and retain lightweight error/hash checks.

**Tech Stack:** Python3.12, PowerShell5.1, Microsoft Excel COM, existing PDF tooling.

## Global Constraints

- V1.1.21; local release only; shared engine/skill and private signatures unchanged.
- Runtime work uses temporary copies only; no invoice processing or renaming.
- Keep210-second native deadline, private-process ownership, source fingerprints and atomic replacement.

### Task1: Replace per-cell fitting with native AutoFit

Files: resources/excel_layout.ps1.

- [x] Establish red baseline: full20-detail production run exceeds210s and reports RPC.
- [x] Apply user final steering: AutoFit all detail columns over header/details and total values; row fitting stops before totals. Preserve original width/height minima and template footer.
- [x] Delete scratch workbook/per-cell copies/width searches/cache/numeric-band helpers. Keep formula snapshot and ownership guards.
- [x] Validate full20 and single1 formatting, exact source preservation, long text, capacity and merged-detail rejection.

### Task2: Preserve timeout diagnosis

Files: resources/format_workbook.ps1, invoice_desktop/controller.py.

- [x] Before cleanup, translate TimedOut into `INVOICE_FORMAT_TIMEOUT` plus current stage and elapsed seconds. Keep other original errors.
- [x] Guard cleanup operations individually so disconnected COM cannot mask the primary failure or skip owned-process cleanup.
- [x] Map the stable timeout marker in ExcelAdapter._run to a concise Chinese error; retain existing behavior for other failures.
- [x] Force a short deadline in an ignored diagnostic script copy, verify the marker/Chinese translation and unchanged public workbook copy; never shorten production timeout.

### Task3: Fix actual PDF print metrics and publish original portable folder

Files: docs/release-checks.md; ignored runtime/build/publication helpers.

- [x] Validate contiguous complete native row bands against full-width physical PDF borders and <=0.75pt per-row height differences. Freeze only General numeric display through literal number formats in the read-only export instance, preserving numeric/formula types and custom formats. Refresh calculation and assert full-plan formula snapshots before printing.
- [x] Validate20-detail and1-detail temporary formatting and PDF exports; render both sheets and review text/footer layout. Record timings for formatting and PDF separately. Exercise two-page repeated headers and final detail/footer grouping.
- [x] Exercise long literal/formula/merged content via temporary fixtures; preserve values, formulas, merged ranges, fonts and number formats where applicable. Reject constant errors and numeric all-hash displays.
- [x] Run only focused authorized checks, syntax/AST, independent static review, Windows build and saved-byte integrity checks.
- [x] Verify app closed; archive old portable directory/packages and replace original release/InvoiceSummary. Preserve signatures/rules, exclude signatures from ZIPs.
- [x] Repackage source, binary and checksums; record actual evidence and remaining scope; no GitHub upload.

## Actual completion

Implementation: d267557. Native formatting/font stage: full20 11.437s, single1 8.141s, both cached totals correct. Authorized temporary-copy PDF exports pass for both sheets, including two-page repeated headers and final detail/footer grouping. Original workbook fingerprints preserved. Forced diagnostic watchdog reports a readable timeout without an RPC cleanup error; production guard remains210s. Constant errors, all-hash numeric displays, merged details and over-capacity fixtures fail without publication. Independent static review has no remaining blocking findings.

Original portable directory replaced after closure and byte checks; previous folder archived as release/InvoiceSummary-1.1.21-before-layout-performance-fix-20261023-092452. Saved executable SHA256: 356f6ef2f4ce7cb5140751b9c2dfacab944db383000e802a77b5f2a800adf0c7. Public Windows archive contains1313 files, source152; private signatures excluded. Full GUI, invoice recognition/renaming/writing and signed export were not rerun. See docs/release-checks.md for evidence and scope.
