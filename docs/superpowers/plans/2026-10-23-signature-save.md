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
- [ ] Archive old portable directory and same-version ZIPs, publish original release/InvoiceSummary, repackage without signatures, verify hashes/member lists and record actual scope in docs/release-checks.md.
