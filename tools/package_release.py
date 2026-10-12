"""Package the built directory and Git-tracked sources without business data."""
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from invoice_desktop import __version__

release = root / "release"
release.mkdir(exist_ok=True)
distribution = root / "dist/InvoiceSummary"
if not (distribution / "InvoiceSummary.exe").is_file():
    raise SystemExit("Build the Windows application first")
outputs = []
binary_zip = release / f"发票汇总助手-{__version__}-Windows.zip"
with zipfile.ZipFile(binary_zip, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
    for file in sorted(distribution.rglob("*")):
        if not file.is_file():
            continue
        if file.suffix.lower() in (".pdf", ".xlsx", ".xls") or "node_modules" in file.parts:
            raise ValueError(f"Distribution contains an unexpected business file: {file.name}")
        zipped.write(file, Path("InvoiceSummary") / file.relative_to(distribution))
outputs.append(binary_zip)
tracked = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout.decode("utf-8").split("\0")
source_zip = release / f"发票汇总助手-{__version__}-源码.zip"
with zipfile.ZipFile(source_zip, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
    for name in tracked:
        if name:
            zipped.write(root / name, Path("invoice-desktop") / name)
outputs.append(source_zip)
checksums = {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in outputs}
(release / "SHA256.json").write_text(json.dumps(checksums, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps([{"path": str(file), "bytes": file.stat().st_size} for file in outputs], ensure_ascii=False, indent=2))
