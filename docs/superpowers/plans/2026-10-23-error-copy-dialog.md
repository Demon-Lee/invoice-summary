# Error Copy Dialog Implementation Plan

> Execute inline; obtain independent read-only review before publication.

**Goal:** Remove main-page report UI and offer copyable diagnostic snapshots only in warning/error dialogs.

**Architecture:** App._report_text replaces Tk report storage. Existing report assembly writes through _set_report. result_dialog.py provides a scrollable modal result view, with an optional immutable diagnostics string; its copy callback never reads mutable App state. Success gets only a confirmation button. Main table takes remaining space.

## Constraints

- V1.1.21, local only, preserve current signature/recognition bytes and all business gates.
- No tests without request; syntax/build/saved-byte verification and static review only.
- No user process termination; archive old directory/packages before replacing original portable folder.

## Tasks

- [x] Delete ui.py report rows/buttons; replace all App Tk report calls with a string buffer, remove unused text/toggle/copy helpers and button updates.
- [x] Add result_dialog.show_result_dialog(parent,title,message,diagnostics=None,tone=...), fixed footer, scrollable readonly message, modal grab/focus restore, local copy failure feedback.
- [x] Route error/warning stage and standalone errors through diagnostic snapshot dialogs. Update rule/stale records before showing; success dialogs omit diagnostic copy. Preserve raw errors and supplemental skip/output notices separately.
- [x] Show complete skipped-file lists in scrollable completion dialogs, remove dead detail-link wording from summaries/messages/docs, keep recovery guidance and business gating intact.
- [x] Independently review modal lifetimes/snapshot copying/report parity, compile/build and verify saved code/resources, protected code/rules/private files. Corrected-field validation now notifies only when issues remain; clean corrections/restored previews remain silent.
- [x] Once app is closed archive previous portable directory/packages, publish original release/InvoiceSummary and public ZIPs excluding signatures. Record evidence/limits and repackage source after documentation commit.

## Actual completion

Implementationf2be56e. Static review's P2 about silent blocking correction results is resolved: only correction results with issues now open the warning/copy dialog; clean corrections and preview restoration stay silent. Minor cleanup wording fixed. Final independent static review has no remaining findings.23modules compile; Windows build exits0; saved EXE/modules/resources match current code.19protected modules, all5PowerShell resources, engine/skill/rules and27private files preserve the task baseline.

Original release/InvoiceSummary updated at unchangedV1.1.21 after the application was closed. Previous directory: release/InvoiceSummary-1.1.21-before-error-copy-dialog-fix-20261023-103749. EXE SHA25649eeac2fcbf176f9a4f9d6a3891e8735f6601b5288cf6020fd226c048e4fc64e. Public Windows ZIP1313members/source160members; signatures excluded. No tests, clipboard/UI interaction, Excel or PDF/business runs performed; static/build checks do not establish runtime dialog behavior.
