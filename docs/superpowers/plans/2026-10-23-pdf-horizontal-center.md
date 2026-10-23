# PDF Horizontal Centering Plan

**Goal:** Center the complete PDF print area horizontally on the page during export.

**Architecture:** In Get-NativeLayout, average the two source horizontal margins before changing PageSetup. Assign that value to both margins and force CenterHorizontally=true in the existing PrintCommunication block. Existing available-width and proof-offset calculations then use equal margins and the unchanged total usable width. No source workbook save.

**Constraints:** Keep1.1.23 locally; no GitHub or business-file writes. Retain grow-only column fitting. No new/run tests requested this turn; use static/syntax/build/saved-artifact inspection and state that limit accurately.

- [x] Capture source/rules/private/portable baselines.
- [x] Apply the native PageSetup change; update policy/generated guide, README, usage and1.1.23notes.
- [x] Inspect the complete diff, parse PowerShell/Python sources, build and compare all embedded modules/resources and protected data.
- [ ] With the software closed, archive/replace the original directory, package public binary/tracked source without signatures, verify saved hashes and record delivery.
