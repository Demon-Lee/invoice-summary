# Center Dialogs Implementation Plan

> Execute inline; obtain independent read-only static review before publication.

**Goal:** Center application and native dialogs over the current main window, including maximized mode.

**Architecture:** dialogs.py provides shared Tk placement and scoped provider wrappers. Custom Toplevels withdraw during layout and call center_dialog before deiconify. A first Map placement uses native outer rectangles. Native modal providers use a same-thread CBT hook with retained callback lifetime and guaranteed cleanup; no Tk calls inside native callback and no focus/size changes.

## Constraints

- V1.1.21, local only; preserve engine/skill/rules, private signatures and business/confirmation semantics.
- No tests without user request. Static review, compile/build and saved-byte/package verification only.
- Never terminate user processes. Ask to close the app only when the concrete replacement is ready if it remains open.

## Tasks

- [ ] Implement dialogs.py: typed Win32 geometry/work-area and native modal centering, safe callback ownership, shared Tk first-map positioning, wrappers for existing messagebox/filedialog/simpledialog APIs.
- [ ] Apply shared placement to result, signature, export and correction Toplevels; replace isolated positioning and add missing parent arguments. Route native calls through scoped wrappers, including startup error.
- [ ] Keep modal lifecycle, values, confirms, default buttons and diagnostics unchanged; independently review hook ABI/lifetime, ownership scope, negative coordinates, fallback, geometry and root selection.
- [ ] Compile all modules/main; build Windows app and compare saved modules/main script/resources, protected code/rules/private bytes. Prepare reviewable replacement before requesting closure.
- [ ] Archive old directory/packages and replace original release/InvoiceSummary once closed; package without signatures, verify content/hashes and record actual scope, commit notes and repackage source.
