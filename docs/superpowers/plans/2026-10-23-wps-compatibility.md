# WPS Compatibility Implementation Plan

**Goal:** Add an automatically selected, isolated WPS spreadsheet backend with the existing processing/export checks.

**Architecture:** A software-owned PowerShell runtime confirms private Office processes and adapts the sole activation expression of the unchanged shared font script. Python pins the detected backend before business operations. Existing content fitting, pagination, PDF proof and signing stay in force.

**Constraints:** Local1.1.23 candidate; no GitHub upload. Never change business originals during tests or private signature data/skill/engine snapshots. Only owned new empty application processes may be hidden/closed/terminated. User explicitly authorized compatibility trials; keep all native fixtures in ignored scratch.

**User steering:** Auto selection must try WPS first, then Excel only when WPS cannot be activated as a private instance. Never fall back after document processing has begun.

## Tasks

- [x] Capture1.1.22 release, private files, rules, engine/skill and protected source baselines; use a new local feature branch.
- [x] Add tests/test_office_adapter.py first: backend validation/pinning, PowerShell backend argument/returned output, failure handling. Run and confirm failures against the old adapter. Add pure PowerShell AST adaptation tests before implementing that runtime function.
- [x] Add resources/office_runtime.ps1: Auto/Excel/WPS activation, process/handle/workbook checks, actual backend selection, safe owned cleanup/watchdog and exact AST font activation adaptation. Update check_excel.ps1, run_excel.ps1, format_workbook.ps1 and export_pdf.ps1 to accept OfficeBackend and use this runtime. Existing native layout logic remains unchanged; watchdogs match the selected owned process identity.
- [x] Update controller.ExcelAdapter with validated requested/detected backend, command argument propagation and ready JSON validation; update app requirements, summary/progress and error messages. Increment application/docs to1.1.23 and document WPS target version and software ownership.
- [x] Run new unit/native AST tests and existing unit suite, reporting unrelated baseline failures separately if found. Run production adapter explicitly against WPS and Excel temporary fixtures, then automatic selection; verify source values/formulas/merges, cached totals, complete PDFs, page grouping and simulated signatures. Exercise failed/reused activation without changing existing documents.
- [x] Independent static review, syntax/build and saved byte/resource/rule/private checks. Replace the original portable directory only when closed with archive/rollback protections; package exact tracked source and public binary without signatures. Record evidence and provide local preview, leaving GitHub unchanged.

Local delivery verified:1342saved files,24embedded application modules plusmain,13rule files; publicWindows archive1314members and source181members. Personal signature tree excluded from both archives and retained byte-for-byte in the local application. Previous1.1.22directory and packages retained. No GitHub mutations.

## Trial findings

- Actual standard-template exports were rejected by the published1.1.22 PDF proof as well as both new backends. Native PDF borders contain paired paths0.84pt apart and repeated short join paths. Added four red/green tests and corrected only border clustering/centering inpdf_layout.py;0.75pt glyph bounds, all exact header checks and per-cell proof remain unchanged. Missing detail/side-label glyph negative probes still reject export.
- Independent review found missing adapter forwarding from the UI to PDF export and an abbreviated COM parameter bypass in the AST gate. Both corrected with regression checks; follow-up static review found no remaining actionable issue.
- New11Python tests and11PowerShell checks pass. Full suite40tests retains exactly the same6failures/8errors as published baseline29tests; old tests assert obsolete incremental-writing behavior or use outdated writer fixtures. This is not an all-green legacy suite.
- Production adapter passes WPS single-page, actual template with current shared minimum-row policy, automatic17-row/two-page and60-row/four-page signed exports; explicit Excel actual-template signed export also passes. Original input content and export source bytes stay unchanged, cleanup completes. Activation fallback and rejection of a reused process are separately verified with controlled probes.
