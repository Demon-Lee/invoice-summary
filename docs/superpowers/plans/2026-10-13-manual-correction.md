# Manual Correction Implementation Plan

> Use executing-plans inline in the existing isolated application project. The user's explicit scope authorizes implementation without an additional approval gate.

**Goal:** Let users correct six existing detail fields inside the software while retaining structural recognition gates and exact-cent totals.

**Architecture:** A small corrections module constructs field-only overlays on immutable raw preview data. Controller revalidates effective records and shares them with rename/write/verify. Workbook planning admits explicit before/after matches for changed rows. Existing pending-state storage carries correction bindings through interrupted runs.

**Tech Stack:** Existing Python/tkinter, Decimal, JSON, openpyxl and PyInstaller; no added dependency.

## Constraints

- Do not edit the skill, bundled engine or recognition snapshot.
- No row creation/deletion/reorder, invoice identity edits, exception removal or forced conflict overwrite.
- Fix editable fields only; derive unit price and standard filenames.
- Revalidate all existing gates and source hashes before execution.
- No tests added or executed; use read-only review and builds only.
- Original business files remain untouched during development.

## Task 1: Field overlays and effective preview

Files: create `invoice_desktop/corrections.py`; modify `invoice_desktop/controller.py` and `invoice_desktop/workbook.py`.

- [x] Define the six editable fields, labels, normalization, exact-cent amount and nonzero quantity checks; expose `apply_corrections(original, changes)` and a stable `record_index:row_index` key. Deep-copy raw data and change existing row fields only; recompute detail_total only for amount-corrected records, preserving source grand_total and all exceptions.
- [x] Add raw payload, corrections, base issues and corrected-existing-row count to Preview. Factor reusable validation from `preview()` so correction and reset refresh template/amount/rename/hash gates without deleting baseline failures.
- [x] Add Controller correction/reset entry points returning a new Preview. Regenerate rename plans through the existing read-only rename CLI. Reject editing pending runs and changed inputs.
- [x] Extend workbook planning with optional original payload. For changed rows match existing full business values against the explicit original or effective values; preserve conflict protection for every other row. Count changed existing rows so execution and resume do not skip required writes.
- [x] Save correction bindings in pending records when applying. Restore records by pinned source/destination path plus hash and original sequence from freshly parsed PDFs; check row count and correction whitelist, then revalidate. Preserve old pending records without manual data.
- [x] Include correction values in actual execution records and result; use existing rename/write/totals/verify pipeline.

## Task 2: Minimal correction UI

File: `invoice_desktop/app.py`.

- [x] Add product/manufacturer/automatic price/correction status columns and stable row IDs to Treeview; mark changed rows visibly.
- [x] Add “人工校正” button and double-click binding. A modal dialog shows original and editable current values, automatic unit price, original-PDF button, save-and-check, restore and cancel.
- [x] Save through background Controller validation; disable execute while busy and when any issue remains. Reject editing actual-result rows without a live preview and explain pending-run editing limits.
- [x] Show changed-field before/after values and corrected-existing-row counts in preview/result reports.

## Task 3: Documentation and release

Files: `invoice_desktop/__init__.py`, `使用说明.txt`, `README.md`, `docs/release-checks.md`.

- [x] Bump version to 0.1.3, document selecting a row, editing, rechecking and executing. State the current-preview scope, existing-row authorization limits and structural errors requiring skill improvement.
- [x] Obtain read-only independent code review and fix substantive findings; no GUI launch, diagnostics or tests.
- [x] Build with existing `tools/build.ps1`, retaining active recognition rules. Check selected rule version and required files.
- [x] Publish the new directory after exact path and running-process checks. On resuming after the user closed the application, the old release directory was absent; the existing 0.1.2 Windows ZIP remains available, and 0.1.3 was placed at `release/InvoiceSummary`.
- [x] Commit and package from `release/InvoiceSummary`, documenting the unperformed runtime checks.
