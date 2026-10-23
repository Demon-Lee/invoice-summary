# Role-only Save Implementation Plan

**Goal:** Show Save only on the signature-position page, reclaim the library footer, and preview each position's selected signature without changing draft/save semantics.

**Publication gate:** Local1.1.22 preview only. Wait for explicit user approval before any GitHub push, tag, asset upload or Release publication.

## Tasks

- [x] Capture fresh local release/private/rule and protected source baselines in ignored .superpowers/role-save-only; signature_ui.py and the readonly preview path in signature_tasks.py may change, other modules stay protected.
- [x] In signature_ui.py keep a self.footer reference, move initial roles selection after footer creation, and add _update_footer to pack Save on roles, forget it on library, and grid the footer only for roles or nonempty status. Add _set_status(text) and replace existing status text writes with this presenter, retaining their original values and control logic. Call _update_footer when switching pages.
- [x] Keep the current window size after the user added four role previews. Add one fixed110px preview host per selector; preserve aspect and cap images200x90. The UI keeps expected ID/fingerprint snapshots and strong Tk image references, clears changed/empty/error selections immediately, requests only missing thumbnails after assignment/refresh, and ignores stale results.
- [x] In SignatureTasks retain the existing library preview API/channel; add separately coalesced role_previews jobs, cancellation/current-request checks and per-image errors. Deduplicate up to four IDs per batch, use store.image_bytes with expected revision/size, and keep all Tk calls out of the worker. Read/mutate/store behavior remains unchanged.
- [x] Statically review initial selection/async callbacks/tab changes/status/focus/save/close, compile24modules/main, build and compare saved code/resources/protected/private bytes. No tests, GUI automation, Excel or business execution.
- [x] Commit source, replace original app only after it is closed, archive previous directory and same-version packages, repackage and verify. Keep GitHub publication on hold and provide local preview.
