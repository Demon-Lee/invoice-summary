# Full Batch Refill Implementation Plan

> Execute inline in the existing isolated application project with executing-plans. User approval of the full clear scope authorizes implementation and packaging; no additional approval gate is required.

**Goal:** Clear every old detail field in acceptance and issue sheets and refill them from the complete current PDF preview.

**Architecture:** Replace business-key matching with deterministic detail-area rebuilding in the in-memory workbook plan. Expose exact expected-content matching for interrupted-run recovery separately from the normal always-refill policy. Keep the skill parser and manual overlays unchanged.

**Tech Stack:** Existing Python/tkinter, Decimal, openpyxl, PowerShell Excel COM and PyInstaller; no new dependencies.

## Global Constraints

- Clear all values, formulas, comments and hyperlinks inside both detail regions, including brand and remarks, as explicitly authorized by the user.
- Retain structure/styles/footer/other sheets and protect unsupported formula or structure movement.
- Preview never saves input files; only formal execution writes through the existing staged-save mechanism.
- Keep parsing, manual correction, precision checks, invoice identity and exact-cent verification.
- Do not modify skill or bundled/portable recognition engines.
- No tests added or run; no GUI, diagnostics or business execution. Perform read-only review, builds and release inspection only.

## Task 1: Workbook and recovery

Files: `invoice_desktop/workbook.py`, `invoice_desktop/controller.py`.

- [x] Replace matching loops with full area clearing and sequential writes. Retain existing styles; copy first detail-row styles for expansion; move the unique footer to `header + len(rows) + 1` using `_shift_rows`.
- [x] Discard formulas in the cleared region, regenerate price and total formulas, and map retained formulas outside that region safely. Refuse empty rows and missing reusable data-row format.
- [x] Add `rows_to_fill` and `workbook_matches` to `WorkbookPlan` and `Preview`. Keep existing diagnostic count fields compatible; do not use them to decide whether a normal refill is needed.
- [x] Add a content matcher for exact sequential business fields, derived price, footer sums and absence of extra content/comments/hyperlinks; use it only for safe pending recovery.
- [x] Persist the refill policy and pre-write workbook hash. Detect the crash-before-phase-marker case for all runs; require a complete expected match before resuming that uncertain state. Existing old pending records remain readable.
- [x] Use `plan_workbook(book, payload)` in preview, correction and apply. Normal preview with valid rows always has changes; only an already-written, fully matched pending run may skip writing.

## Task 2: Product guidance

Files: `invoice_desktop/app.py`, `invoice_desktop/__init__.py`, `README.md`, `使用说明.txt`.

- [x] Bump version to 0.1.4 and replace incremental wording with full refill. Show old rows to clear and current rows to fill per sheet.
- [x] Explicitly state full PDF directory, cleared brand/remarks, retained template and current-preview manual corrections in top notice and help/docs.
- [x] Distinguish actual refill from a pending run that only resumes Excel/verification; show row reduction as detail-region resizing.

## Task 3: Review and release

Files: `docs/release-checks.md`, this plan, `release/InvoiceSummary` and release ZIPs.

- [x] Obtain independent read-only review via requesting-code-review and fix substantive findings without tests.
- [x] Build with `tools/build.ps1` using the existing build venv; confirm retained engine version and required files.
- [ ] Commit source changes; safely preserve old release, publish 0.1.4 to `release/InvoiceSummary`, and package from that exact directory using `tools/package_release.py`.
- [ ] Record publication/build/review evidence and unperformed runtime checks, commit documentation, and regenerate the source package to include final records.
