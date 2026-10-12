"""Export a trusted, complete skill snapshot as an offline recognition update."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from invoice_desktop.updates import export_update, read_manifest

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest = export_update(args.skill, args.output, read_manifest(Path(__file__).resolve().parents[1] / "engine"))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
