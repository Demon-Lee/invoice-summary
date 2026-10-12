# Usage Guidance Implementation Plan

> Execute inline with executing-plans in the existing dedicated application repository. The user authorized emphasizing these two sections; proceed without another approval gate.

**Goal:** Make execution steps and necessary conditions the first readable information in the default process page and manual.

**Architecture:** Shared short copy in `invoice_desktop/app.py`, two styled guide cards before the existing process form, and clear text headings in help. Existing processing callbacks and portable rules stay in place.

**Tech Stack:** Python/tkinter and the existing PyInstaller environment. No new dependency.

## Constraints

- Change presentation and documentation only; preserve recognition and workbook behavior.
- Preserve the active portable recognition version during build and distribution.
- Do not add or run tests without a user request. Build and perform read-only review; distinguish them from runtime testing.
- Keep source invoices and workbooks untouched.

## Task 1: Prominent guidance

Files: `invoice_desktop/app.py`, `invoice_desktop/__init__.py`.

- [x] Define four numbered execution steps and four necessary conditions, using the existing button names and actual file requirements.
- [x] Place two colored cards in process grid row 0, shift the existing rows by one, keep the table row expanding, and shorten the report to five lines. Use card-width events to update label wrapping. Use a bold section title style and explicit headings so meaning is independent of color.
- [x] Place the original-file mutation notice immediately below the cards. Set the minimum window to 900 × 760.
- [x] Begin HELP with the same steps and requirements; tag its headings with a larger bold font. Preserve detailed template, recovery and rule update information.
- [x] Set `__version__ = "0.1.2"`.

## Task 2: Documentation and distribution

Files: `使用说明.txt`, `README.md`, `docs/release-checks.md`.

- [x] Put numbered execution steps first, necessary conditions second, then recovery, workbook details and rule maintenance. Make the two plain-text headings stand out with separators.
- [x] Update README to the same section order and document the visible guidance.
- [x] Build using `tools/build.ps1 -Python .build-venv\Scripts\python.exe`. Inspect the built manifest and portable rule selection without launching the software.
- [x] Obtain a read-only code review; do not launch the GUI or run tests.
- [x] Publish to the exact release directory after checking resolved paths and running-process state; preserve the old folder as `InvoiceSummary-0.1.1-archive`.
- [x] Record build/review scope, commit source changes, and package `release/InvoiceSummary` using `tools/package_release.py`.

## Coverage

The default page and help cover first-use guidance; the manual and README carry the same instructions to recipients; the release preserves the user's whole-folder update workflow.
