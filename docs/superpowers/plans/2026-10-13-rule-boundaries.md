# Rule Boundaries Implementation Plan

> Execute inline with executing-plans in the existing application project. The user approved the three ownership categories and requested implementation; no new approval is needed.

**Goal:** Define and enforce the shared skill update boundary while retaining application-owned corrections and full refill.

**Architecture:** A compiled application policy defines supported shared files and contracts. Manifest format 2 explicitly describes the shared scope; legacy format 1 remains accepted under existing checks and the bundled writer fingerprint. The UI uses the same policy text and update labels, and a generated distribution guide documents the boundary.

**Tech Stack:** Existing Python/tkinter, JSON, ZIP, SHA-256, PyInstaller.

## Global Constraints

- Preserve parser, correction, workbook refill and execution behavior. Do not modify the source skill or bundled scripts.
- Skill packages contain only the four shared files and manifest; never application policy or application code.
- Reject unsupported scope/contracts and writer fingerprint changes before activation; pin compatibility to bundled application support for activation, rollback and portable preservation.
- Read both legacy and new manifests without silently rewriting old recognition snapshots.
- No added/running tests, GUI, diagnostics, skill update interface checks or business processing during development. Use static review, build and file inspection only.

## Task 1: Policy and compatible snapshots

Files: `invoice_desktop/policy.py`, `invoice_desktop/updates.py`, `tools/prepare_portable.py`.

- [x] Centralize ownership text, shared whitelist, update labels and supported version declarations.
- [x] Produce format 2 manifests with scope metadata in the hash; read and validate formats 1/2 and preserve documentation-only adaptation checks. Legacy support is limited to the originally supported version 1 contracts.
- [x] Enforce application-pinned shared workbook compatibility on active/sync/import/rollback and portable rule preservation; keep atomic activation.
- [x] Return before/after and changed-file information for clear update reports.

## Task 2: User guidance

Files: `invoice_desktop/app.py`, `invoice_desktop/__init__.py`, `README.md`, `使用说明.txt`, `tools/release_assets.py`, `tools/build.ps1`, generated `功能归属与更新边界.txt`.

- [x] Add ownership, current update result and source skill reference tabs within rules; show human-readable changed domains and retained software features.
- [x] Clearly distinguish source skill workflow from application interaction and full-refill policy; use the policy as the guide source.
- [x] Bump to 0.1.6, generate/copy the boundary guide and document update/recovery compatibility limits.

## Task 3: Review and publication

Files: this plan and `docs/release-checks.md`; release directory and archives.

- [x] Obtain independent read-only review and address substantive findings. Final review of `23ba1fc → dcbfc30` found no remaining Critical / Important / Minor.
- [x] Build and inspect retained recognition/version and all portable assets; commit implementation. Final rebuild exited 0 and retained `42334e9f238e`.
- [x] Publish safely to original portable folder, preserve old release ZIP/directory, package actual folder. Previous folder retained as `release/InvoiceSummary-0.1.5-archive`; existing ZIP also remains.
- [x] Record evidence and unverified runtime aspects, commit final records and regenerate source package.
