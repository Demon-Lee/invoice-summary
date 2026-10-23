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

## Follow-up: Save beside position content

The user requests moving Save up beside the settings. Keep it right-aligned immediately after the role cards and optional warnings inside roles_body; preserve all draft/save operations. The library keeps its separate status-only footer. Version1.1.22 and the GitHub approval gate stay unchanged.

- [x] Capture the current closed release/private/rule and all other module baselines in ignored .superpowers/role-save-near-content.
- [x] In signature_ui.py create a role action row at grid row len(role_cards)+1 with a left status label and the existing Save callback/button at the right. Keep the library footer status-only. _set_status updates both labels; _update_footer shows the outer footer only on the library page with nonempty status. Preserve tab/scroll/save conditions and pending data.
- [x] Statically review geometry parents, initial selection/status setup and save/close/callback paths; compile modules/main, build, compare embedded code/protected/private files, then replace the closed local release with guarded archive/rollback and repackage. No tests/GUI automation/Excel execution. Provide local preview and keep GitHub on hold.

## Follow-up: Fit the initial window to signature positions

The user requests opening the manager large enough to see the positions without scrolling. Keep the existing width preference, measure role content after the requested width settles, and replace the fixed700px height cap with the measured content height plus internal chrome and8px slack. Cap the client size to the main window's monitor work area minus80px for outer borders/room. On an undersized display or manual shrink, normal scrolling remains; tab changes never resize the dialog.

- [x] Capture fresh release/private/rule baselines, protecting every other source module except signature_ui.py and the new readonly work-area helper in dialogs.py.
- [x] Add dialog_work_area_size(parent) to dialogs.py using the existing Windows placement declarations without installing hooks, with Tk screen fallback. In signature_ui.py keep roles_body as a manager reference; set the initial bounded geometry, update idle layout, then set height to role requested height plus (dialog requested height minus canvas requested height) plus8px, clamped to the work-area limit and existing440px minimum where possible. Preserve centering and save/close state.
- [x] Statically review sizing/geometry ordering, fallback and page behavior; compile modules/main, build, compare embedded/protected/private files, then update the closed original and repackage with previous files archived. No tests, GUI automation, Excel or business execution. Keep1.1.22 and the GitHub approval hold; open the local app for user preview.
