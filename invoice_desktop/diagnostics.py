"""Release smoke checks use newly generated files or temporary source copies."""
import shutil
import tempfile
import json
import hashlib
import zipfile
from pathlib import Path
from openpyxl import Workbook

from .controller import Controller
from .updates import sha256, EngineStore, read_manifest, _snapshot_version


def update_smoke(engine_dir):
    with tempfile.TemporaryDirectory(prefix="invoice-update-check-") as tmp:
        root = Path(tmp)
        candidate = root / "candidate"
        candidate.mkdir()
        manifest = read_manifest(engine_dir)
        files = tuple(manifest["files"])
        for name in files:
            shutil.copyfile(Path(engine_dir) / name, candidate / name)
        with (candidate / "invoice_pipeline.py").open("a", encoding="utf-8") as stream:
            stream.write("\n# release update compatibility check\n")
        manifest["files"] = {name: sha256(candidate / name) for name in files}
        manifest["version"] = _snapshot_version(manifest)
        archive = root / "update.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            for name in files:
                zipped.write(candidate / name, name)
            zipped.writestr("manifest.json", json.dumps(manifest))
        store = EngineStore(root / "state", engine_dir)
        old = store.version()
        store.install(archive)
        if store.version() == old:
            raise ValueError("更新检查未切换版本")
        store.rollback()
        if store.version() != old:
            raise ValueError("回退检查未恢复原版本")
        return {"install": "passed", "interfaces": "passed", "rollback": "passed"}


def pipeline_smoke(source_pdf, engine_dir):
    source = Path(source_pdf).resolve()
    original_hash = sha256(source)
    with tempfile.TemporaryDirectory(prefix="invoice-smoke-") as tmp:
        root = Path(tmp)
        directory = root / "invoices"
        directory.mkdir()
        shutil.copyfile(source, directory / "sample.pdf")
        book = root / "test.xlsx"
        wb = Workbook()
        wb.remove(wb.active)
        for name, primary, secondary in (("验收", "经办人", "验收人"), ("领用", "保管人", "领用人")):
            ws = wb.create_sheet(name)
            headers = ["序号", "产品名称", "规格型号", "单位", "数量", "单价", "金额"]
            if name == "验收":
                headers.append("生产厂家")
            for col, value in enumerate(headers, 1):
                ws.cell(3, col, value)
            ws.cell(8, 1, "合计")
            ws.cell(8, 5, "=SUM(E4:E7)")
            ws.cell(8, 7, "=SUM(G4:G7)")
            ws.cell(9, 1, primary + "：")
            ws.cell(9, 4, secondary + "：")
            ws.cell(9, 7, "验收日期：" if name == "验收" else "领用日期：")
            ws.cell(9, 8, "2026.1.1")
            ws.cell(10, 1, "说明：测试模板")
        wb.save(book)
        wb.close()
        controller = Controller(engine_dir, state_dir=root / "run-state")
        preview = controller.preview(directory, book)
        if not preview.clean:
            raise ValueError("临时输入预览失败：" + "；".join(preview.issues))
        result = controller.apply(preview)
        if result["status"] != "completed":
            raise ValueError(result.get("error", "完整流程测试未完成"))
        if source.exists() and sha256(source) != original_hash:
            raise ValueError("源 PDF 指纹变化")
        return {"status": result["status"], "completed": result["completed"], "total": result["total"],
                "cleanup": result["cleanup"], "original_unchanged": True, "engine_version": preview.engine_version}

