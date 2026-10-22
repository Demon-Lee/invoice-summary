# Signature manager performance repair

**Goal:** Remove repeated full-library pixel processing and keep opening/refreshing/previewing responsive. User reports list selection and opening/refresh as the slow operations (2026-10-22).

**Evidence:** Static call tracing shows show_selected→image_bytes→_read→_scan→_png for every image, then selected _bytes→_png and another UI decode/resize. run() mutates with another full scan, then refresh scans again, then selection preview scans again. All run synchronously on Tk's UI thread. Current library metadata: 10 active images, 2,618,069 source bytes, 8,758,532 pixels; largest 2,510,158 pixels. No app/GUI/benchmark execution was performed to gather this evidence.

## Constraints

- Keep V1.1.20, existing dependencies and data format2. This repair preserves filename discovery, role confirmations, wheel behavior, export gating, uniform PDF sizing and personal data exclusion.
- No tests, GUI/Excel launches, timing benchmarks or business processing. Static compilation, independent source review, build and saved-file/package checks only. Do not claim measured speedup.
- No GitHub upload this turn. User authorized the previous upload; current request is local performance repair.
- Store cache is process memory only, bounded to16MiB/32 entries for PNG variants and256 successful validation digests. Never use timestamps/sizes alone to trust image content. Read current bytes and hash before reuse, including preview and signed snapshot.
- Parent owns Git commits, build and release publication. Preserve all actual current private files, not a historical migration baseline.

## Task 1: Content cache and selected-image reads (parent)

Files: invoice_desktop/signatures.py.

- [x] Add per-instance bounded LRU for normalized PNG/thumbnail byte variants and a bounded successful-validation digest cache. Cache keys include original bytes SHA256 and requested size; no disk cache.
- [x] Scan continues reading/hashing every active file for external changes, but only new content needs pixel decode/normalization. Reuse cache on migration/import/selected bytes/snapshot. Invalid content is not marked valid.
- [x] Extend `image_bytes(item_id, expected_revision=None, *, size=None) -> PNG bytes`: load current config without full-library scan (migrate only legacy config), verify displayed config revision if supplied, read/hash selected file, normalize or thumbnail in memory. UI requests size=(280,180). Snapshot stays full-library sync plus strict raw-byte verification, attention and displayed-version checks.

## Task 2: Background management operations (implementation agent)

Files: invoice_desktop/signature_ui.py; optional small invoice_desktop/signature_tasks.py helper.

- [x] Show the modal promptly with a brief loading state; move opening read/refresh/selected thumbnail decoding out of Tk's thread. Keep all widgets, ImageTk creation, after(), dialogs and callbacks on Tk's thread.
- [x] Use one daemon worker/queue, main-thread result polling, request IDs and cancellation/discarding of obsolete previews. Coalesce rapid preview requests. Closing cancels pending callbacks/results; worker never accesses or retains Tk objects. Do not use a non-daemon executor that keeps app exit waiting.
- [x] Load/mutation operations disable conflicting controls until completion. Mutators and subsequent sync/read can share one background job. Replacement/delete must obtain fresh state asynchronously, then show confirmation on main thread; commit still checks expected_revision. Capture plain store/data arguments before dispatch, no worker closures over manager/widgets.
- [x] Refresh only rebuilds list/combobox values when IDs/labels changed. Preserve selection and scroll position. Preview cache key(id,sha) avoids redundant re-rendering after unrelated role changes, but every newly requested preview must still verify current bytes via store.image_bytes. Reserve stable preview height so changing images does not move scrolling layout.
- [x] Retain wheel interception, automatic scrollbars, prior grab restoration, role attention/error UI and explicit unsigned flow. No busy errors may silently change signing choices. Avoid automatic retry loops on errors.

## Task 3: Review and publication (parent)

- [x] Static task/whole-change review (independent requests attempted; if service unavailable, record manual-review scope), resolve material findings, compile without executing modules and diff-check. Update current docs for memory cache/background handling without adding main UI clutter.
- [x] Capture current program/rules/engine/skill/scripts/private byte hashes, build preserving source. Check EXE embedded modules, public resources, protected code, current private tree exact bytes (except process lock) and rules.
- [ ] Guard running program, absolute paths and reparse points; archive old directory, update original release/InvoiceSummary, archive old same-version ZIPs, repackage public Windows/source ZIPs excluding all personal data.
- [ ] Verify ZIP members and checksums; record what was checked and actual interaction/performance still to be tried by user. Commit and repackage source after record.

## Progress

Storage/cache and asynchronous UI implemented. Implementer/parent static review fixed close-during-save and saved-but-refresh-failed states. Independent reviewer requests both failed with service usage limits; no independent review completion is claimed. Static compilation passed for19 application modules; Windows build and saved-artifact checks passed for19 embedded application modules,1336 local files,25 private files and13 rule files. The latest source configuration changed during work; the build matches that latest configuration and unchanged image bytes exactly, with initial fingerprints retained. Publication/archive checks in progress. No runtime timings/GUI tests performed.
