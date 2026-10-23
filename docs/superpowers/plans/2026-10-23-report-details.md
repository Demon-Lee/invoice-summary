# Collapsed Reports and Chinese Error Summary Implementation Plan

> Execute inline with executing-plans and an independent static review.

**Goal:** Remove footer status clutter, collapse detailed reports by default and show readable Chinese error popups.

**Architecture:** Keep the existing report Text widget and rendering/state paths. Toggle only its visibility and the copy button. Add a pure presentation helper for bounded Chinese summaries; send raw errors to the existing full report and summaries to dialogs. Known error rules must not alter controller outputs, processing permissions or financial verification.

**Tech Stack:** Python3.12, Tk/ttk, existing Windows portable build.

## Constraints

- V1.1.21, local only; preserve signatures, shared engine/skill/rules and Excel/PDF behavior.
- No tests without request; use static review, syntax/build and saved file checks.
- Do not terminate user processes. Replace original portable directory only after it is closed; preserve old directory/packages.

## Tasks

- [x] ui.py: remove footer status label/container, retain progress; replace report heading with a 查看详情 toggle, initially hide report panel and copy button.
- [x] app.py: add _toggle_report; keep full reports and copying; give copy completion feedback on its button because the footer is gone.
- [x] Add error_messages.py with known field/Excel/permission/template/PDF summaries and a generic unknown fallback. Preserve short Chinese business messages; never echo raw technical stacks in a popup.
- [x] app.py: separate diagnostic text from supplemental skip/output notices in _complete_stage; update preview/apply/export errors and standalone main-window errors. Retain raw errors in full reports, previous reports, all skip records, processing state and export gates.
- [x] Update visible instructions to refer to 查看详情 and update user documentation. Independently review errors/warnings, collapsed report state, copy and record preservation; compile/build and compare embedded/current code, protected modules/scripts, rules and private hashes. Resolve filename/field ambiguity and mixed primary/cleanup diagnostics; explicitly preserve recovery-failure instructions.
- [x] After app closure archive old directory/packages, publish original release/InvoiceSummary and repackage. Check saved file/archive bytes, record scope, commit notes and repackage current source; no GitHub upload.

## Actual completion

Implementation1e31199. Independent static review's two P2 findings (field name captured from a filename and mixed primary/cleanup errors) resolved; recovery failures explicitly preserve the directory/check instructions. Final static review has no remaining blocking findings.22modules compile; Windows build exits0. Embedded modules and resources correspond to current source.19other modules, all5PowerShell scripts, engine/skill/rules and27private files preserve the current task baseline.

Updated original release/InvoiceSummary at unchangedV1.1.21 after the app was closed. Old directory: release/InvoiceSummary-1.1.21-before-report-details-ui-fix-20261023-101955. EXE SHA256 d63c89990894f89f9608ab087542dc0964d96bfe3ec9919e577290b01c0d6a45. Public archive1313members/source157members; signatures excluded. No tests, GUI interaction, Excel, PDF export or business processing executed this task; static/build/file checks do not claim runtime interaction validation.
