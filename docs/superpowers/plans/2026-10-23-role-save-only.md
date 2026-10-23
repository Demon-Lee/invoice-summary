# Role-only Save Implementation Plan

**Goal:** Show Save only on the signature-position page and compact the library page without losing operation status or draft state.

**Publication gate:** Local1.1.22 preview only. Wait for explicit user approval before any GitHub push, tag, asset upload or Release publication.

## Tasks

- [ ] Capture fresh local release/private/rule and protected source baselines in ignored .superpowers/role-save-only; only signature_ui.py is allowed to change among application modules.
- [ ] In signature_ui.py keep a self.footer reference, move initial roles selection after footer creation, and add _update_footer to pack Save on roles, forget it on library, and grid the footer only for roles or nonempty status. Add _set_status(text) and replace existing status text writes with this presenter, retaining their original values and control logic. Call _update_footer when switching pages.
- [ ] Change initial manager height cap700 to640 while preserving minsize/resize and scrolling. Document that library operations commit individually and Save belongs to role bindings.
- [ ] Statically review initial selection/async callbacks/tab changes/status/focus/save/close, compile24modules/main, build and compare saved code/resources/protected/private bytes. No tests, GUI automation, Excel or business execution.
- [ ] Commit source, replace original app only after it is closed, archive previous directory and same-version packages, repackage and verify. Keep GitHub publication on hold and provide local preview.
