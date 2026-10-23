# Signature Position Save Implementation Plan

> **For agentic workers:** Execute inline with executing-plans; request an independent static review before publication.

**Goal:** Apply the user's exact copy changes and require Save to commit signature position edits.

**Architecture:** The Tk manager keeps local slot edits and image fingerprints. SignatureStore.assign_many validates all edited slots against one revision and saves once under the existing serialized mutation guard. Existing background tasks perform the write without blocking Tk; successful Save clears the draft, closing never submits it.

**Tech Stack:** Python3.12, Tk/ttk, existing portable signature store and Windows packaging.

## Global Constraints

- Remain V1.1.21, local update only. Preserve personal signatures, engine/skill/rules and Excel/PDF behavior.
- No new or executed tests without a user request; perform static review, compile/build and saved-byte/package checks only.
- Reuse current feat/desktop-app checkout; it contains no uncommitted edits at start. Do not terminate the running user's application.

## Tasks

- [x] In signature_ui.py remove the subtitle and bottom note; add the exact format hint immediately after 签名库. Replace close_button with save_button bound to save_bindings; retain titlebar/Escape close.
- [x] In signatures.py add assign_many(bindings, expected_revision=None), validate every slot and referenced image before updating any bindings, clear only explicitly submitted attention slots and call _save once under @_serialized.
- [x] In signature_ui.py keep pending_bindings, pending_fingerprints and invalidated slot attention. Selecting updates only the draft. Refresh preserves unchanged image selections, invalidates deleted/changed images, and never clears pending drafts on an ordinary library mutation.
- [x] Save via existing background mutate task with one revision. Clear drafts only after confirmed success; keep the dialog open. Preserve failed drafts and require refresh. Treat SignatureRefreshError as saved but awaiting refresh, with no success-close shortcut. Retire submitted drafts on the next successful read after a post-save refresh failure.
- [x] In ui.py remove the 离线处理 label and 打开位置 caption, and recompute wrapping of the three location buttons without a caption column.
- [x] Independently review changed code, compile modules, build Windows binary, compare embedded modules/resources, protected source/rules and private hashes, then ask to close the app if still running. App already closed before publication; no extra close request needed.
- [x] Archive old portable directory and same-version ZIPs, publish original release/InvoiceSummary, repackage without signatures, verify hashes/member lists and record actual scope in docs/release-checks.md.

## Actual completion

Implementation6f539a0. Independent static review's P3 about stale pending state after successful save/failing refresh is resolved with saved_awaiting_refresh; final review has no remaining findings.21modules compile, Windows build exits0, embedded code/resources correspond to current source.18other modules,5PowerShell scripts, engine/skill/rules and24private files preserve their baselines. App was already closed; no process terminated.

Original release/InvoiceSummary updated at unchangedV1.1.21. Previous folder: release/InvoiceSummary-1.1.21-before-signature-save-ui-fix-20261023-095449. EXE SHA256 d0014b39858c04af12f1d45e7a7c91cc17f5e486827d34877900503d63451b83. Public archives exclude signatures; Windows1313members/source154members. No tests,GUI,Excel,PDF export or business processing executed this task; saved artifact checks are not a runtime interaction test.
