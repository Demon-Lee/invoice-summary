# Stage Notifications Implementation Plan

> Execute inline with executing-plans in the existing application project. The user has authorized clearer stage completion feedback; routine UX implementation and packaging need no additional approval.

**Goal:** Make the end and outcome of invoice preview and execution clearly visible.

**Architecture:** Add a persistent colored banner in the processing tab. Track the optional invoice operation in the existing worker queue; render stage outcomes and one completion dialog for preview or execution on the main thread. Correction checks update the banner without success dialogs. Leave controller and skill logic unchanged.

**Tech Stack:** Existing Python/tkinter and PyInstaller; no additional dependencies.

## Global Constraints

- Distinguish processing, passed, blocked, failed, cleanup warning and no-change outcomes with explicit text.
- Clear stale completion feedback on input/rule changes and at new operation start.
- No business file processing, GUI runs, added tests or test runs. Use read-only review, build and release file inspection.
- Preserve portable recognition snapshots and distribute the full application directory.

## Task 1: Interface and guidance

Files: `invoice_desktop/app.py`, `invoice_desktop/__init__.py`, `README.md`, `使用说明.txt`.

- [x] Add a responsive, prominent stage banner below the action buttons and keep the details table flexible. Merge the existing summary into the card and increase the default window height.
- [x] Add optional operation tracking to the background runner; update progress and display stage-specific failure feedback on raised errors.
- [x] Render and notify preview and execution outcomes. Keep manual correction completion free of extra dialogs. Reset feedback, footer status and batch summary when inputs/rules change.
- [x] Update guidance and bump version to 0.1.5.

## Task 2: Review and release

Files: `docs/release-checks.md`, this plan, `release/InvoiceSummary` and release ZIPs.

- [x] Obtain independent read-only review through requesting-code-review and address substantive findings. Final review found no remaining Critical / Important; both Minor findings addressed.
- [x] Build, confirm portable engine/version and required files, and commit source changes.
- [ ] Safely publish to the existing application path, retaining any previous release directory or existing ZIP, and package from the actual published directory.
- [ ] Record evidence and runtime limitations, commit documentation, and regenerate final source package.
