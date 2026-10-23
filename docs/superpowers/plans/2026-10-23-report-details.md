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
- [ ] After app closure archive old directory/packages, publish original release/InvoiceSummary and repackage. Check saved file/archive bytes, record scope, commit notes and repackage current source; no GitHub upload.
