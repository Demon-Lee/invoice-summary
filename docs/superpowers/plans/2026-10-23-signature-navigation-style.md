# Signature Navigation Style Implementation Plan

> Execute inline; request read-only static review before publication.

**Goal:** Modern signature navigation and two grouped signature cards, with a visible main-action divider after PDF export.

**Architecture:** Replace manager Notebook with flat navigation and two existing independently scrollable frames, preserving data controls and all asynchronous logic. Extend the existing flow-row measurement in ui.py with a single divider whose orientation follows the group boundary.

**Tech Stack:** Python3.12, Tkinter/ttk, existing theme and portable build tools.

## Constraints

- V1.1.21; local release only. Preserve signatures, recognition, shared engine/skill and business functions.
- No tests or GUI/Excel execution without user request. Static review, syntax, Windows build and saved-code/archive checks.
- Default roles page, explicit Save, unchanged draft/library/task behavior, no reads or saves on tab change.
- Three workflow buttons before divider; four auxiliary buttons after it. Keep full labels, icons, states and responsive wrapping.

## Tasks

- [x] Capture current release/private/rule/protected hashes in ignored .superpowers/signature-style; reuse guarded publication and archive verifiers with current baseline.
- [x] In ui.py move the boundary to index3. Include button indexes in row geometry; place a thin vertical divider in the group gap when index3 shares a row, or a horizontal divider in extra spacing when index3 begins a new row. Keep dynamic request-size/width cache and parent height accurate.
- [x] In signature_ui.py replace Notebook with a shared white header/nav and stacked independently mapped pages. Add _select_tab(key, focus=False) to toggle visible page/selected nav state/underline without touching data; add _cycle_tab for arrows and Ctrl+Tab. Initial focus targets visible nav. Use native ttk buttons with flat text/padding layout and explicit background/foreground state maps.
- [x] Rebuild role presentation as two white sheet cards with two equal-width fields each, retaining selectors keys/callbacks and no-wheel-selection bindings. Update _show_warnings captions to local role names; keep full sheet/role context in warning messages and mirror warning notices across pages. Preserve library canvas refresh and pending drafts/save/close methods.
- [x] Update README.md/使用说明.txt, compile24modules/main, statically review old Notebook references, keyboard/focus, wheel, warnings, drafts and responsive separator; request independent read-only review. Build with tools/build.ps1 and compare embedded code/resources plus protected/private/rule bytes.
- [ ] Commit source, publish original release once closed, archive prior directory/packages, package without signatures and verify all members. Record actual checks/limitations, commit notes and repackage source.
