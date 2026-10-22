"""Carry the selected, validated recognition snapshot into a portable build."""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project))
from invoice_desktop.updates import EngineStore, read_manifest, check_application_contract
from invoice_desktop.policy import snapshot_files
from invoice_desktop.signatures import SignatureStore


def prepare(directory, preserve):
    directory, preserve = Path(directory).resolve(), Path(preserve).resolve()
    if not (directory / "InvoiceSummary.exe").is_file():
        raise ValueError("Build the Windows application before preparing portable rules")
    bundled = directory / "_internal/engine"
    baseline = read_manifest(bundled)
    previous_bundled = preserve / "_internal/engine"
    if not previous_bundled.is_dir():
        previous_bundled = project / "engine"
    source_root = preserve / "recognition"
    origin = "previous portable rules"
    if not (source_root / "active.json").is_file():
        source_root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "InvoiceSummary/recognition"
        origin = "legacy application rules"
    source_store = EngineStore(source_root, previous_bundled) if (source_root / "active.json").is_file() else None
    if source_store is None:
        origin = "bundled rules"
        selected, previous = bundled, None
    else:
        state = source_store._state()
        selected = source_store._path(state["active"])
        previous = source_store._path(state["previous"]) if state.get("previous") else None
    # Read all sources before copying; the preparer never alters the old store.
    snapshots = [(selected, read_manifest(selected))]
    if previous is not None:
        snapshots.append((previous, read_manifest(previous)))
    for _, manifest in snapshots:
        check_application_contract(manifest, baseline)
    target = directory / "recognition"
    engines = target / "engines"
    engines.mkdir(parents=True, exist_ok=True)
    versions = []
    for source, manifest in snapshots:
        version = manifest["version"]
        destination = engines / version
        if not destination.exists():
            with tempfile.TemporaryDirectory(prefix="portable-", dir=engines) as temp:
                stage = Path(temp) / "snapshot"
                stage.mkdir()
                for name in (*snapshot_files(manifest), "manifest.json"):
                    shutil.copyfile(source / name, stage / name)
                read_manifest(stage)
                os.replace(stage, destination)
        else:
            read_manifest(destination)
        versions.append(version)
    old = versions[1] if len(versions) > 1 and versions[1] != versions[0] else None
    store = EngineStore(target, bundled)
    store._activate({"active": versions[0], "previous": old})
    if (preserve / "signatures" / "config.json").is_file():
        SignatureStore(preserve).copy_to(directory)
    return {"version": versions[0], "origin": origin, "directory": str(target), "previous": old}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--preserve", type=Path, default=project / "release/InvoiceSummary")
    arguments = parser.parse_args()
    print(json.dumps(prepare(arguments.directory, arguments.preserve), ensure_ascii=False, indent=2))
