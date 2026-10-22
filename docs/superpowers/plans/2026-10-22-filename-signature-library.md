# Filename signature library implementation plan

> Execute storage using subagent-driven-development, integrate UI and publication in this session. User approved implementation. Parent owns commits/publication.

**Goal:** Human-readable signature filenames and automatic discovery without silent role substitution.

**Architecture:** SignatureStore owns scanning, v1 migration, v2 configuration and immutable export snapshots. Image/path helpers may be a small separate module. Existing PDF insertion remains unchanged. UI displays storage issues and role attention; build copies before migrating.

**Tech Stack:** Existing Python3.12, Tk8.6, Pillow, PyInstaller; Windows10/11.

## Global constraints

- Keep V1.1.20, existing dependencies, current feature checkout. No cloud upload.
- No tests, GUI/Excel launches or business processing. Static syntax, source review, saved-file/archive checks and builds only.
- Never silently replace a selected person's image. Retain stable IDs for internal changes; external changes require role confirmation.
- Preserve all original personal files during migration and build; no private images in Git or public packages.
- Parent handles Git commits and release changes; implementer edits only assigned storage modules.

## Task 1: Storage and migration

Files: `invoice_desktop/signatures.py`, optionally new `invoice_desktop/signature_files.py`.

Interfaces: existing SLOTS/SignatureStore method signatures retained; `image_dir:Path` is the active `signatures/签名图片` directory. `read()` synchronizes under lock and returns version2 with items/bindings/`issues:list[str]`/`attention:dict[slot,str]`. Each item retains id,label,file,sha256. All mutators accept expected_revision. `snapshot()` returns the existing deeply immutable PNG snapshot but refuses outstanding attention. `copy_to()` copies private files without mutating source, then migrates/synchronizes destination.

- [x] Validate Windows-compatible filename labels, unique case-insensitive stems across extensions; read ordinary files only, preserve source bytes. Reuse `_png(...,normalize=True)` in memory for snapshot/preview.
- [x] Split raw config loading from synchronized read to avoid reentering OS lock. Update stored revision after own saves. Keep atomic writes and expected_revision.
- [x] Migrate v1 by backing up config and copying old images to label filenames, preserving IDs/roles and original image bytes. Refuse conflicts without overwriting. Keep backup source images out of active scan. Handle invalid legacy labels with a unique safe filename and visible issue.
- [x] Scan nonrecursive PNG/JPEG files, reject duplicates/invalid images individually with issues. New valid paths get IDs. Missing/renamed/replaced records clear affected roles into persistent attention. No identity inference by image content. Assigning a role, including None, clears that role's attention.
- [x] Internal rename/replacement/deletion preserve expected-revision confirmations and rollback/recovery on config save failure; avoid silently re-discovering old files after a successful operation. Do not modify source images outside the active directory.
- [x] copy_to copies all private files, including unrecognized images and backups, to an empty destination under source/destination locks; destination.read migrates. Source config/images unchanged.
- [x] Compile edited modules without executing them, inspect diff; write implementation report for parent. No tests or commits.

## Task 2: UI and export integration (parent)

Files: signature_ui.py, pdf_export_ui.py, 使用说明.txt, current signature spec.

- [x] Add open-folder and refresh actions with existing rounded styles; label defaults to Path(source).stem. Directory created by storage read, open via os.startfile. Refresh preserves current list selection.
- [x] Render issues/attention visibly, wrap to dialog width. Mark affected role labels. Assignment passes revision(self.data) so stale dropdown cannot confirm a newly replaced image unseen.
- [x] Export summary includes issues/attention, keeps unsigned option. Snapshot errors refresh dialog for deliberate confirmation. Existing export/PDF code and processing gates remain unchanged.
- [x] Update user instructions and signed-feature specification for canonical directory, direct-file discovery, migration/backups, conflicts and external-edit confirmation.
- [x] Static task/whole-change review; resolve material findings, compile modules, diff check.

## Task 3: Build and local publication (parent)

- [x] Capture old private-directory byte hashes and full config in ignored baseline, rules/engine/skill/protected code fingerprints. Do not print personal names/images.
- [x] Build using tools/build.ps1. Check original private files unchanged by build; check built v2 ID/role mapping and each migrated original image byte hash, preserved legacy backup/other user files, saved embedded modules/resources/rules.
- [x] Archive old folder, guard running program and absolute paths/reparse points, then replace original release/InvoiceSummary. Preserve old same-version packages before repackaging.
- [x] Package Windows/source ZIP, exclude entire personal directory, compare every member, record hashes/counts/review/runtime limitations, commit docs and repackage source.

## Progress

Storage and UI implemented; independent task/whole-change reviews resolved signed-intent loss on failed or successful-empty refresh. Final review found no remaining actionable findings. Static compilation and Windows build passed; saved build migration preserves 12 IDs, labels, roles and original byte hashes, legacy backups and source directory unchanged. Local publication and Windows/source archive member/hash checks passed; 1338 local files, 27 private files, 1311 public Windows ZIP members. Final release record committed and source repackaged. No GUI/business runtime validation is claimed.
