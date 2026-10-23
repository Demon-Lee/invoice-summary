# Signature Library Style and 1.1.22 Publication Plan

> Continue the already-authorized release task inline. Request read-only static UI review; do not run tests or GUI.

**Goal:** Refine the signature-library presentation before publishing version1.1.22 source and Windows package to GitHub.

**Architecture:** Retain all library controls and callbacks; split the existing library body into heading, responsive top tools, list/preview cards, responsive selected-item tools and notice. Existing Canvas and Listbox objects keep their state/task semantics.

## Tasks

- [ ] Record the scope extension in .superpowers/release-v1.1.22/baseline.json, retaining the former protected signature_ui hash as evidence and all other original protected/private/rule hashes.
- [ ] In signature_ui.py reparent the top three tools to a gray ttk.Frame, put the remaining three in a separate bottom bar, and retain toolbar_buttons plus existing control attributes. Use a red foreground style inheriting the existing rounded export-action button for Delete.
- [ ] Put the existing Listbox/AutoHideScrollbar into a titled white list card and existing preview Label into a titled white preview card. Use weighted side-by-side columns by default; switch to stacked cards below640px and keep preview geometry independent of image size. Wrap each toolbar by max requested button width and available host width, with cached column geometry; no new data calls.
- [ ] Bind preview-label wrapping to its own allocated width and notice wrapping to body width. Preserve all warnings, focus, tab/scroll handlers, tasks, caches and role-saving methods.
- [ ] Update release/readme/user docs, statically review the UI diff, compile24modules/main, rebuild1.1.22 and compare saved code/resources plus protected/private/rule bytes. Publish local directory only after the app is closed; do not terminate it.
- [ ] Commit local release evidence, package source and Windows ZIP without signatures, scan archive/history blobs against private content and paths, fast-forward GitHub refs/tag and publish v1.1.22 with checksums. Verify assets/downloads and preserve historical releases.
