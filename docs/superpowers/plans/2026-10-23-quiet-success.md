# Quiet Success Implementation Plan

> Execute inline using executing-plans; user has specified the requested behavior.

**Goal:** Remove normal completion popups from preview, processing and PDF export, retaining actionable warnings and existing main-page completion feedback.

**Architecture:** App._complete_stage remains the single completion presenter. Add an explicit attention flag for nonblocking skipped-file notices; gate popups by warning/error or attention, preserving stage style independently from popup tone. All normal success callers share the same gate.

**Tech Stack:** Python3.12, Tkinter, PyInstaller, Windows PowerShell.

## Constraints

- V1.1.21, local only; preserve private signatures, recognition, engine/skill and business processing.
- No tests unless requested. Use syntax compilation, static review, build and saved-byte/archive comparison; do not launch GUI/Excel.
- Preserve error-copy snapshots, modal positioning, stage card, metrics, action states and non-invoice skipped-file notices.
- Do not terminate the original app; publish only when it is closed.

## Tasks

- [x] Capture current release EXE, recognition/private trees and protected module/script hashes in ignored .superpowers/quiet-success.
- [x] In invoice_desktop/app.py add attention=False to _complete_stage. Gate with notify and (tone in (warning,error) or attention), derive warning popup tone for attention-only success, and use that popup tone for diagnostic snapshot/call. Pass attention=bool(popup_notice) in the two clean preview and two successful execution branches. Preserve all other completion and error calls, stage updates and actual process state.
- [x] Update README.md and 使用说明.txt to describe successful stages only updating the main page; retain skipped-file and other actionable warnings. Remove obsolete instructions to wait for completion dialogs and success-path/page-count popup descriptions.
- [x] Review every completion branch and compile24modules/main without executing them; build with tools/build.ps1 and compare embedded code/resources/protected bytes and private/rule trees.
- [ ] Commit source, archive old software and packages, publish into release/InvoiceSummary after checking it is closed, package without signatures and verify every archive member. Record actual scope/limitations and repackage committed notes.
