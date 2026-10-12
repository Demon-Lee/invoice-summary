# Portable Rules Implementation Plan

> Execute inline with executing-plans on the existing `feat/desktop-app` branch. The user already approved the design. No new worktree or further approval is needed.

**Goal:** A complete copy of InvoiceSummary carries the recognition version chosen after skill synchronization.

**Architecture:** Reuse EngineStore in a sibling `recognition` directory. Keep source binding and recovery records in local per-directory AppData. Prepare the portable store during build, then publish the complete folder.

**Tech Stack:** Existing Python/tkinter, JSON manifests and PyInstaller. No new dependency.

## Global constraints

- Preserve existing parser, workbook and Excel behavior.
- Preserve atomic update checks and rollback.
- Copy only whitelisted engine files; exclude host settings and business files.
- Respect the developer instruction: no added or executed tests without a user request.

## Task 1: Application locations and binding

Files: `invoice_desktop/controller.py`, `invoice_desktop/app.py`, `main.py`, `.gitignore`.

- [x] Add the application-directory resolver, independent of the current working directory:

```python
def application_root():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
```

- [x] App accepts `application_dir=None`, uses `EngineStore(application_dir / "recognition", resource_root() / "engine")`, and derives the local state directory from the application path:

```python
identity = hashlib.sha256(str(self.application_dir).casefold().encode("utf-8")).hexdigest()[:16]
local = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "InvoiceSummary/instances" / identity
```

- [x] Persist both `skill_source` and `recognition_version`; restore a binding only if its version equals the current portable store. Default to no binding. Save the new version after synchronization and clear mismatching bindings after import.
- [x] Update help and successful-sync feedback to explain whole-directory distribution, show the software directory, and add “打开软件文件夹”. Isolate diagnostic-mode application directory in its existing temporary context.
- [x] Ignore source-mode `recognition/` artifacts.

## Task 2: Release preparation and delivery

Files: `tools/prepare_portable.py`, `tools/build.ps1`, `tools/package_release.py`, `invoice_desktop/__init__.py`.

- [x] Add `prepare(directory, preserve)` to populate `directory/recognition` from the previous portable store, otherwise compatible legacy AppData, otherwise bundled engine. Read and validate every manifest; resolve selected/previous hashes through EngineStore; copy only FILES plus manifest into immutable directories and atomically write the normalized active pointer.
- [x] Invoke preparation after PyInstaller builds the directory:

```powershell
& $Python tools/prepare_portable.py --directory 'dist\InvoiceSummary' --preserve 'release\InvoiceSummary'
if ($LASTEXITCODE -ne 0) { throw 'portable recognition preparation failed' }
```

- [x] Bump version to 0.1.1, document the exact user workflow, and build with the existing environment.
- [x] Inspect the built portable pointer and required files. Request read-only code review, fixing substantive issues without adding/running tests.
- [x] Commit sources and package the built directory. Replace the specified release folder only after checking exact resolved targets stay in release; keep the existing directory under an archive name. Do not delete input files.

## Task 3: User documentation

Files: `README.md`, `使用说明.txt`, `docs/release-checks.md`.

- [x] State: sync → wait for success → close software → ZIP the entire folder → recipient extracts and runs. Include `recognition` and `_internal`.
- [x] Describe remaining compatibility limits and writable-folder requirement. Preserve the optional ZIP import/export route.
- [x] Report successful build and read-only review separately from unperformed runtime/regression tests.

## Coverage

Task 1 supplies portable selection and host isolation; Task 2 ensures the exact distributable folder includes the selected rules; Task 3 gives the approved operating steps and accurate evidence.
