# Compact Actions and Signature Tabs Implementation Plan

> Execute inline. Obtain read-only static review of layout and hidden-tab interactions if available.

**Goal:** Put all seven main actions into a responsive shared row, and open signature management on its signature-position tab.

**Architecture:** ui.py measures native button requests and positions one ordered flow in a height-managed frame. signature_ui.py retains the existing library canvas/controls and adds a separately scrollable roles tab through ttk.Notebook. Existing storage/tasks remain unchanged.

**Tech Stack:** Python3.12, Tkinter/ttk, existing Pillow button surfaces, PyInstaller.

## Constraints

- Keep V1.1.21 and update locally; preserve personal signatures, rules, engine/skill and business functions.
- No tests unless requested. Syntax/static/build/saved-byte checks only; no GUI/Excel execution.
- Tabs do not rescan or save. Save remains explicit, closing discards pending position choices.
- Keep button labels/icons/states/order, active-page scroll routing, no wheel changes to combo selection, and accessible warnings.

## Tasks

- [ ] Capture current release/protected/private/rule hashes in ignored .superpowers/compact-tabs, reusing publication/archive verification helpers with this task name.
- [ ] In invoice_desktop/ui.py replace separate action/location cards with one parent and ordered buttons. Measure reqwidth/reqheight, flow in natural order with a wider group gap after the fourth, place each button vertically centered within its row, and set the parent height. React to container/button Configure plus initial idle, caching geometry to avoid repeated placement.
- [ ] In invoice_desktop/ui_actions.py add transparent=False to _surface_image; use RGBA transparent initial pixels for location roles only. Keep all drawing sizes and input/other surfaces unchanged.
- [ ] In invoice_desktop/signature_ui.py create styled Notebook with roles_page then library_page, create independent auto-hide canvas/body pairs, keep self.canvas as library canvas for existing refresh restoration, add self.roles_canvas and role-page warning label. Select roles_page explicitly; focus notebook on open. Route _scroll_body to selected page, mirror existing warnings, and preserve all store/tasks/draft/save logic. Do not bind tab change to reading or saving.
- [ ] Update README.md/使用说明.txt. Statically inspect all hidden-control, wheel, warning, refresh and save dependencies; request read-only review. Compile24modules/main, build and compare executable embedded code/resources plus protected/private/rule bytes.
- [ ] Commit source, replace original release after it closes, archive old directory/packages, package without signatures, verify every archive member and record scope/limitations. Commit notes and rebuild source archive.
