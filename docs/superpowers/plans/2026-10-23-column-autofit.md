# Native Column AutoFit Implementation Plan

**Goal:** Let native column fitting grow or shrink with current contents while keeping captions/signing space readable.

**Architecture:** Update the existing application-owned excel_layout.ps1 helper shared by formatting and export. Remove old template column minima, retain native header/detail/total AutoFit and row minima, then fit nonmerged captions using their existing validated spans and native single-cell width measurement. No engine or workbook-data changes.

**Tech Stack:** PowerShell5, WPS/Excel COM, existing Python layout/PDF proof and portable build.

## Constraints

Keep1.1.23 locally, no GitHub. Tests use only copied inputs and dummy signatures, never personal files. Office process ownership and all content/formula/PDF proof gates stay unchanged. Row heights retain their old minima. Signature fields reserve three font ems plus padding after the label. Caption expansion is limited to the native255column-width capacity; no whole-column legacy minima.

## Task

- [x] Capture current application/rules/private/engine/source baselines and preserve old packages.
- [x] Record red native cases: existing library cannot shrink wide columns; removing only column minima causes the actual standard-template date labelF15 PDF proof to fail.
- [x] In resources/excel_layout.ps1 remove columnMinima and restoration loop. Add a caption-width helper that measures an unmerged cell with Columns.AutoFit, restores its detail width, and expands only its existing span's last column when the measured text plus signer writing reserve will not fit. Call it after header/detail/total column AutoFit and before row AutoFit. Retain column limits and row minima.
- [x] Update policy.py, generated boundary guide, README, 使用说明 and1.1.23release notes to describe content-based column fitting and caption requirements.
- [x] Run native temporary standard templates and actual batch through current production helpers, with simulated signatures, source/content/formula/PDF checks; compare narrowed and expanded widths. Review code independently, inspect syntax and saved build bytes/resources/private/rules.
- [ ] Replace closed portable directory with guarded archive/rollback, package tracked source/public binary excluding signatures, verify member hashes, record results and provide local trial.
