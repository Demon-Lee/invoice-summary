# Invoice Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. Execute inline; no delegated work is required.

**Goal:** Deliver a Windows offline invoice app with exact-cent verification and compatible offline skill updates.

**Architecture:** A tkinter interface calls an isolated Python controller. The controller pins a versioned skill engine, previews inputs and workbook edits, checks fingerprints, then applies rename/write/Excel/verification. openpyxl replaces the non-distributable Node workbook component.

**Tech Stack:** Python 3.12, tkinter/ttk, pdfplumber, openpyxl, Windows PowerShell/Excel COM, PyInstaller.

## Global Constraints

- Windows 10/11, Microsoft Excel desktop required.
- Complete batch PDF directory and `.xlsx` only; all processing offline.
- Use skill invoice parser as the recognition source, keep policy and code versions visible.
- No input mutations before clean preview; no guessing, conflict overwrite, template repair or automatic invoice/workbook backup.
- Exact-cent per-invoice and batch/footer verification; inspect status fields, not just exit codes.
- Preserve duplicate details, source order, footer structure/styles/heights/merges, dates and remarks.
- Pin the engine for a run; reject changed input fingerprints before execution.
- Whitelist and hash-check engine update files; refuse policy-only and writer-incompatible updates.
- Remove current-run scratch data after every outcome.

## Files and Interfaces

- `invoice_desktop/workbook.py`: `plan_workbook(path, payload, run_date=None) -> WorkbookPlan`, `write_workbook(plan) -> None`; plan validates in memory, captures changes and staged workbook, never saves inputs.
- `invoice_desktop/updates.py`: `EngineStore(root, bundled).active() -> Path`, `export_update(skill_dir, output, baseline=None) -> dict`, `sync(source) -> dict`; immutable checked snapshots with atomic active pointer.
- `invoice_desktop/controller.py`: `Controller(engine_dir, progress).preview(pdf_dir, workbook) -> Preview`, `apply(preview) -> dict`; strict state gates, fingerprints, scratch cleanup.
- `invoice_desktop/app.py`: threaded native UI and result presentation; worker results delivered through a queue to the main thread.
- `main.py`: GUI entry plus diagnostic mode for packaged smoke checks.
- `engine/`: exact source copies of approved skill parser, totals collector, font script and policy; `manifest.json` records file hashes and writer compatibility marker.
- `tools/export_update.py`: developer offline update exporter; `tools/build.ps1`: reproducible windowed package builder.
- `tests/test_workbook.py`, `tests/test_controller.py`, `tests/test_updates.py`: synthetic fixtures and data protection regressions.

### Task 1: Shared recognition snapshot and updates

- [x] Copy only the four whitelisted skill files, record original writer SHA-256, do not include node_modules.
- [x] Add tests that fail before `EngineStore` exists: ZIP traversal/hash mismatch rejected; SKILL.md-only changes rejected; compatible parser change produces a new immutable snapshot.
- [x] Implement manifest `format_version=1`, SHA-256 file map, writer marker, API validation of `main(argv)` and dependency import smoke check.
- [x] Validate with `python -m unittest tests.test_updates -v`; expect all checks pass and rejected packages leave active pointer unchanged.
- [x] Commit engine snapshot and update implementation.

### Task 2: Workbook writer parity

- [x] Write tests before implementation for dry-run immutability, duplicate keys, quantity normalization, conflicts, unique footer/date labels and expanded/compacted footer row heights/merges.
- [x] Map one unique row containing all required headers; map manufacturer by prefix. Validate the exact three-row footer and single signature date label.
- [x] Match existing rows by `(sequence, product, spec, occurrence)` and compare business values. Block missing source invoices or conflicting fields. Append missing records in source order while retaining remarks/internal blank rows.
- [x] Stage changes in memory, explicitly remap footer merges, row dimensions and print areas, copy template styles for added rows, refresh SUM and unit-price formulas.
- [x] Save to a current-run sibling staging file, reopen to validate structure, then `os.replace` the selected workbook. Always remove failed staging files.
- [x] Run `python -m unittest tests.test_workbook -v`; inspect expected final formulas and both footers, then commit.

### Task 3: Pipeline controller and Excel adapter

- [x] Add tests for preview exception/collision/amount blocking, mutation calls denied when blocked, changed input rejection, cleanup on failure, and verification `failed` despite exit code zero.
- [x] Invoke pinned engine `main` with redirected output and current-run report paths. Validate payload schemas and money before writer planning.
- [x] Snapshot SHA-256 of workbook and selected directory PDF members; require exact equality immediately before apply.
- [x] Check Excel COM registration and workbook lock on Windows, run existing font/recalculation script using hidden noninteractive PowerShell.
- [x] Apply rename, writer, Excel, totals, verification sequentially; record completed stages and precise failures. Inspect every exceptions/status field.
- [x] Run `python -m unittest tests.test_controller -v`; then test generated workbook via actual Excel, commit.

### Task 4: Desktop interface and usage

- [x] Build path pickers, preview Treeview, summary/status text and disabled execute button until a clean preview.
- [x] Worker threads never touch tkinter; use queue and `after` for progress, results and exceptions; refuse close during active processing.
- [x] Add source-skill binding, changed version detection, sync/import/export and previous-engine rollback controls. Display active engine hash and software version.
- [x] Add result-folder buttons and embedded use/update instructions; no automatic backups, force-continue buttons or silent compatibility claims.
- [x] Add a startup diagnostic JSON command for package dependency checks; verify GUI initializes in a hidden smoke mode.
- [x] Commit UI and user documentation.

### Task 5: Windows distribution and release checks

- [x] Create isolated build environment, install pinned build dependency, build a PyInstaller windowed distribution containing engine and PowerShell resources.
- [x] Include Python package third-party license notices, source version, source update export tool and Chinese quick-start instructions.
- [x] Run full `python -m unittest discover -s tests -v` and the original skill parser/collector Python regressions once. Repeat only for changes/failures.
- [ ] Execute packaged diagnostic and hidden GUI smoke; perform temporary-copy full pipeline with real Excel and check original hashes unchanged. Source GUI and temporary-copy pipeline checks were completed; final packaged runtime checks are deferred. See docs/release-checks.md.
- [x] Zip the portable distribution, report path, version, verification evidence and any packaging limitation.

## Coverage and Self-review

Every design section maps to Tasks 1–5. Update safety is Task 1; workbook principles Task 2; pipeline protection and cleanup Task 3; user flow Task 4; offline artifact and source delivery Task 5. No invoice data is included in repository or release. All interfaces above use the same parameter names across tasks.

## Review fixes

Formula references now follow mapped cells; unsupported functions and special references block preview. Pending runs persist the recognition version, invoice content hashes and successful workbook-write phase, enabling safe resumption after an Excel failure. Updates validate signatures, required helpers, dependency loads and generated-input output contracts before activation. Final two refinements received read-only review without a new regression run.
