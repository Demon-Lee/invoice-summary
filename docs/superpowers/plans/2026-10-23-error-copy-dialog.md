# Error Copy Dialog Implementation Plan

> Execute inline; obtain independent read-only review before publication.

**Goal:** Remove main-page report UI and offer copyable diagnostic snapshots only in warning/error dialogs.

**Architecture:** App._report_text replaces Tk report storage. Existing report assembly writes through _set_report. result_dialog.py provides a scrollable modal result view, with an optional immutable diagnostics string; its copy callback never reads mutable App state. Success gets only a confirmation button. Main table takes remaining space.

## Constraints

- V1.1.21, local only, preserve current signature/recognition bytes and all business gates.
- No tests without request; syntax/build/saved-byte verification and static review only.
- No user process termination; archive old directory/packages before replacing original portable folder.

## Tasks

- [ ] Delete ui.py report rows/buttons; replace all App Tk report calls with a string buffer, remove unused text/toggle/copy helpers and button updates.
- [ ] Add result_dialog.show_result_dialog(parent,title,message,diagnostics=None,tone=...), fixed footer, scrollable readonly message, modal grab/focus restore, local copy failure feedback.
- [ ] Route error/warning stage and standalone errors through diagnostic snapshot dialogs. Update rule/stale records before showing; success dialogs omit diagnostic copy. Preserve raw errors and supplemental skip/output notices separately.
- [ ] Show complete skipped-file lists in scrollable completion dialogs, remove dead detail-link wording from summaries/messages/docs, keep recovery guidance and business gating intact.
- [ ] Independently review modal lifetimes/snapshot copying/report parity, compile/build and verify saved code/resources, protected code/rules/private files.
- [ ] Once app is closed archive previous portable directory/packages, publish original release/InvoiceSummary and public ZIPs excluding signatures. Record evidence/limits and repackage source after documentation commit.
