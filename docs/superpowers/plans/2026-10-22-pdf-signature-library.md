# Portable PDF signature library implementation plan

> Execute using subagent-driven-development for the three isolated modules, then integrate and review inline. User approved implementation on 2026-10-22.

**Goal:** A portable named signature library, four role selectors, and consistently sized signatures in exported PDFs only.

**Architecture:** Separate local image/config storage, the Tk manager, and PDF layout/insertion. Export accepts an immutable in-memory snapshot, places images in staged PDFs, validates both, then uses existing pair publication. No changes to workbook writer, skill or recognition.

**Global constraints:** Windows 10/11, existing dependencies only. No tests, GUI launches, Excel operations, diagnostic runs or business processing unless separately requested. Static syntax/resource/archive checks and builds only. Work in the current clean feature checkout; parent handles all commits and release publication. Do not upload this version without request.

## Shared interfaces

`invoice_desktop/signatures.py` exports `SLOTS`: tuples `(key, sheet, label)` in order `acceptance_handler/验收/经办人`, `acceptance_inspector/验收/验收人`, `issue_keeper/领用/保管人`, `issue_recipient/领用/领用人`.

`SignatureStore(application_dir)` owns `application_dir/signatures`. `read()` returns `{version:1, items:[{id,label,file,sha256}], bindings:{slot_key:id_or_None}}`. Methods: `import_image(label, source, item_id=None) -> id`, `rename(item_id,label)`, `delete(item_id)` (clears references), `assign(slot_key,item_id_or_None)`, `image_bytes(item_id) -> bytes`, `snapshot(expected_revision=None) -> {images:{id:PNG_bytes}, labels:{id:label}, bindings:{slot:id}}` (only assigned images), `copy_to(application_dir)` (all items and bindings for local upgrades). IDs remain stable, labels unique, paths relative, saves atomic; reject escaped paths and reparse points.

`signature_ui.open_signature_manager(parent, store)` is a blocking modal with prior grab restoration; list import/name management and four selectors. User actions save immediately. Replacements/deletion show affected roles first. Manager does not change preview/processing eligibility.

`pdf_signatures.add_signatures(stage:Path, plan:dict, snapshot:dict) -> dict` modifies staged PDF files only. Plan sheets contain `signature_slots:[{key,label,row_height,font_size,vertical_alignment}]` and `signature_date_label`. Every PDF role/date label must uniquely locate on a common row for each sheet. Infer printed row scale from matching PDF character font sizes and source font points; constrain usable bands with available PDF row lines and reject collisions with other printed characters. Compute width/height minima across all four roles in PDF points, maintain image aspect ratio, and insert on the signature page using bundled pypdfium2. Return applied role/label/page list and common box dimensions. Reopen output for page/image metadata integrity before releasing stage; no rasterization of the whole page.

## Tasks

- [x] Task 1: Implement `signatures.py` storage, image normalization/blank trimming, stable identity, portable copy and immutable snapshots. No user images in tracked files or fixtures.
- [x] Task 2: Implement `signature_ui.py` against the shared interface: import toolbar, list, selected thumbnail, label operations, four readonly Combobox selectors. Clear disabled/error feedback and responsive modal sizing.
- [x] Task 3: Implement `pdf_signatures.py` with documented official pdfplumber/PDFium APIs. Anchor roles dynamically; all four roles constrain size even when some unassigned. Fail closed for a requested signed export on missing/ambiguous labels, occupied areas or unreadable images. Preserve page dimensions/text and close all PDFium handles.
- [x] Task 4: Parent integrates app and export dialog. Main signature manager is unavailable while busy; export dialog captures checkbox/snapshot and returns directory plus snapshot. `_print_plan` adds signature metadata only when requested; add image pass before final validation and publication, report applied labels. Recheck original workbook fingerprint before publishing. Add a compact main entry without tabs.
- [x] Task 5: Parent integrates portable preservation and packaging. `tools/prepare_portable.py` copies a validated local library; `.gitignore` excludes personal signature files; `tools/package_release.py` excludes distribution `signatures/` without modifying it, and refuses tracked personal signature files.
- [x] Task 6: Static per-task and whole-change reviews; fix all material findings. Bump to 1.1.20, update external guide/policy wording, build, compare saved embedded modules/resources, preserve rules and signature store. Publish locally only after verifying absolute release paths, no reparse points and old executable closed; archive 1.1.19. Package and verify original archives, record actual scope and limitations.

## Review ledger

Tasks 1–5 implemented. Library/UI task review resolved concurrent writes, stale role confirmations, post-save cleanup reporting and corrupted image repair. Whole-feature review resolved displayed-revision export matching, Windows case-insensitive private-file exclusions, explicit busy states and successful-publication-only signature reporting. Final source-only re-reviews found no remaining actionable findings. 18 application modules and changed build scripts compile without executing application code; built embedded module signatures match saved sources. Runtime visual placement is not claimed by static checks.
