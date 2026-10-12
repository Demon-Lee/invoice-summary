# Portable recognition rules

## Approved user workflow

The user approved this change after confirming: update the skill, click “同步本机 skill”, close the application, then ZIP the complete `release/InvoiceSummary` directory and send it to another person. That person extracts the complete directory and runs the EXE with the new rules already selected. No additional approval is required.

## Design

Use the existing immutable recognition store at `<application directory>/recognition` instead of the machine's AppData recognition directory. Its `active.json` and version folders contain only relative version identifiers and the four whitelisted rule files plus their manifest. Synchronization, import and rollback all mutate this same portable store. The fallback bundled engine is already inside the complete application directory. Copying the directory therefore carries the selected version and rollback history.

Keep the maintainer's skill-source path and unfinished business-run records in local AppData, scoped by the absolute application-directory hash. Do not automatically bind to a skill found on the recipient's computer. Keep an explicit binding across restarts only while its saved recognition version matches the portable version. On receiving a new portable version, clear stale bindings so another computer's rules cannot block or replace the delivered rules.

The release builder initializes the portable store from the previous release's portable rules when available. For this first upgrade, preserve the existing compatible legacy AppData recognition version. Normalize selected and previous versions to immutable hash folders in the new release. Copy only whitelisted files and the manifest, never host-specific settings or business records. A changed writer marker requires a main-program update and must not be silently copied into this build.

The delivery stays at `D:/Workspace/发票专题/invoice-desktop/release/InvoiceSummary`. Keep the old application directory under a separate archive name before replacing it. Package the prepared directory and separately deliver Git-tracked sources. Bump the software version to 0.1.1; recognition versions change only when the actual rule files change.

## Errors and scope

- Update checks and atomic activation remain unchanged. Failed synchronization does not activate partial rules.
- The application folder must be writable for a rule update; give the user the affected directory if permission is denied.
- Personal source bindings and run records are not included in a directory copied to another computer.
- Original PDFs, reimbursement workbooks, the skill source and its algorithms are not edited.
- No tests are added or run because the user requested implementation only and the current developer instruction reserves tests for an explicit request. Use successful compilation/build, file inspection and read-only review as the evidence, and state the runtime-verification limit.

## Self-review

The approved workflow maps directly to portable store selection, local binding isolation, release preparation and directory delivery. No absolute machine path enters a portable manifest. The first release preserves the existing active version; subsequent syncs directly update the directory the user will ZIP.
