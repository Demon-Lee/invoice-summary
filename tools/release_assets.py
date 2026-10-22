"""Build an application icon and collect license texts for bundled libraries."""
import importlib.metadata as metadata
import json
import shutil
import sys
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from invoice_desktop import __version__
from invoice_desktop.policy import BOUNDARY_GUIDE

(root / "功能归属与更新边界.txt").write_text("发票汇总助手 " + __version__ + "\n\n" + BOUNDARY_GUIDE, encoding="utf-8")
resources = root / "resources"
resources.mkdir(exist_ok=True)
scale = 4
icon = Image.new("RGBA", (256*scale, 256*scale), (0,0,0,0))
draw = ImageDraw.Draw(icon)
draw.rounded_rectangle((12*scale,12*scale,244*scale,244*scale), radius=48*scale, fill="#1761aa")
draw.rounded_rectangle((66*scale,43*scale,194*scale,213*scale), radius=12*scale, fill="white")
for y, right in ((85,168),(112,168),(139,144)):
    draw.rounded_rectangle((88*scale,y*scale,right*scale,(y+9)*scale), radius=4*scale, fill="#98b6d6")
draw.ellipse((143*scale,149*scale,227*scale,233*scale), fill="#21966a", outline="white", width=7*scale)
draw.line((163*scale,190*scale,179*scale,205*scale,209*scale,175*scale), fill="white", width=9*scale, joint="curve")
icon_sizes = (16, 20, 24, 28, 32, 36, 40, 48, 56, 64, 72, 80, 96, 112, 128, 144, 160, 192, 224, 256)
# Render every frame directly from the drawing; avoid a second downsampling pass.
icon_frames = [icon.resize((size, size), Image.Resampling.LANCZOS) for size in icon_sizes]
icon_frames[-1].save(resources / "app.ico", sizes=[frame.size for frame in icon_frames],
                     append_images=icon_frames[:-1])

packages = ("pdfplumber", "pdfminer.six", "Pillow", "pypdfium2", "openpyxl", "lxml", "et_xmlfile", "cryptography", "cffi", "pycparser", "charset-normalizer", "pyinstaller")
collected = []
license_dir = resources / "licenses"
license_dir.mkdir(exist_ok=True)
for name in packages:
    dist = metadata.distribution(name)
    found = []
    for relative in dist.files or []:
        filename = Path(relative).name.lower()
        if not (filename.startswith(("license", "licence", "copying", "notice")) or "licenses" in Path(relative).parts):
            continue
        path = Path(dist.locate_file(relative))
        if not path.is_file() or path.suffix.lower() in (".py", ".pyc", ".dll", ".so"):
            continue
        destination = license_dir / name / Path(relative).name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != path.read_bytes():
            destination = destination.with_name(Path(relative).parent.name + "-" + destination.name)
        shutil.copyfile(path, destination)
        found.append(str(destination.relative_to(root)))
    collected.append({"package": name, "version": dist.version, "license_files": found})
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.is_file():
    shutil.copyfile(python_license, license_dir / "Python-LICENSE.txt")
import tkinter
tcl_root = Path(tkinter.Tcl().eval("info library"))
for directory in (tcl_root, tcl_root.parent / "tk8.6"):
    candidate = directory / "license.terms"
    if candidate.is_file():
        shutil.copyfile(candidate, license_dir / (directory.name + "-license.terms"))
(resources / "bundled-packages.json").write_text(json.dumps(collected, indent=2), encoding="utf-8")
notice = "Third-party notices for InvoiceSummary\n\nThis distribution bundles the following open-source libraries. Full license texts are in _internal/resources/licenses.\n\n"
notice += "\n".join(f"{item['package']} {item['version']} — {', '.join(item['license_files']) or 'see package metadata'}" for item in collected)
notice += "\n\nPython, Tcl/Tk and the PyInstaller bootloader are included. Microsoft Excel is an external user-installed application. OpenAI artifact-tool is not bundled.\n"
(root / "THIRD_PARTY_NOTICES.txt").write_text(notice, encoding="utf-8")
print(json.dumps({"libraries": len(collected), "license_files": len(list(license_dir.rglob('*.*')))}, indent=2))
