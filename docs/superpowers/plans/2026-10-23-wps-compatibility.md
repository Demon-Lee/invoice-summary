# WPS Compatibility Implementation Plan

**Goal:** Add an automatically selected, isolated WPS spreadsheet backend with the existing processing/export checks.

**Architecture:** A software-owned PowerShell runtime confirms private Office processes and adapts the sole activation expression of the unchanged shared font script. Python pins the detected backend before business operations. Existing content fitting, pagination, PDF proof and signing stay in force.

**Constraints:** Local1.1.23 candidate; no GitHub upload. Never change business originals during tests or private signature data/skill/engine snapshots. Only owned new empty application processes may be hidden/closed/terminated. User explicitly authorized compatibility trials; keep all native fixtures in ignored scratch.

## Tasks

- [ ] Capture1.1.22 release, private files, rules, engine/skill and protected source baselines; use a new local feature branch.
- [ ] Add tests/test_office_adapter.py first: backend validation/pinning, PowerShell backend argument/returned output, failure handling. Run and confirm failures against the old adapter. Add pure PowerShell AST adaptation tests before implementing that runtime function.
- [ ] Add resources/office_runtime.ps1: Auto/Excel/WPS activation, process/handle/workbook checks, actual backend selection, safe owned cleanup/watchdog and exact AST font activation adaptation. Update check_excel.ps1, run_excel.ps1, format_workbook.ps1 and export_pdf.ps1 to accept OfficeBackend and use this runtime. Existing native layout logic remains unchanged; watchdogs match the selected owned process identity.
- [ ] Update controller.ExcelAdapter with validated requested/detected backend, command argument propagation and ready JSON validation; update app requirements, summary/progress and error messages. Increment application/docs to1.1.23 and document WPS target version and software ownership.
- [ ] Run new unit/native AST tests and existing unit suite, reporting unrelated baseline failures separately if found. Run production adapter explicitly against WPS and Excel temporary fixtures, then automatic selection; verify source values/formulas/merges, cached totals, complete PDFs, page grouping and simulated signatures. Exercise failed/reused activation without changing existing documents.
- [ ] Independent static review, syntax/build and saved byte/resource/rule/private checks. Replace the original portable directory only when closed with archive/rollback protections; package exact tracked source and public binary without signatures. Record evidence and provide local preview, leaving GitHub unchanged.
