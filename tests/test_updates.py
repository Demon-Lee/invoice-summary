import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

try:
    from invoice_desktop.updates import EngineStore, export_update
except ImportError:
    EngineStore = export_update = None


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(EngineStore, "需要实现版本化的 skill 更新管理")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.skill = self.root / "skill"
        (self.skill / "scripts").mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("rules v1", encoding="utf-8")
        for name in ("invoice_pipeline.py", "collect_excel_totals.py"):
            shutil.copyfile(Path(__file__).resolve().parents[1] / "engine" / name, self.skill / "scripts" / name)
        (self.skill / "scripts/apply_mixed_fonts_excel.ps1").write_text("# fonts", encoding="utf-8")
        (self.skill / "scripts/write_summary.mjs").write_text("// workbook v1", encoding="utf-8")
        archive = self.root / "base.zip"
        export_update(self.skill, archive)
        self.bundled = self.root / "bundled"
        with zipfile.ZipFile(archive) as z:
            z.extractall(self.bundled)
        self.store = EngineStore(self.root / "store", self.bundled)

    def test_compatible_recognition_change_is_installed_and_can_be_rolled_back(self):
        old = self.store.version()
        file = self.skill / "scripts/invoice_pipeline.py"
        file.write_text(file.read_text() + "\n# corrected recognition\n", encoding="utf-8")
        self.store.sync(self.skill)
        self.assertNotEqual(self.store.version(), old)
        self.assertEqual(self.store.active().joinpath(file.name).read_text(), file.read_text())
        self.store.rollback()
        self.assertEqual(self.store.version(), old)

    def test_policy_only_change_requires_script_adaptation(self):
        (self.skill / "SKILL.md").write_text("new business rule", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "规则说明"):
            self.store.sync(self.skill)
        self.assertEqual(self.store.active(), self.bundled)

    def test_changed_writer_requires_main_app_update(self):
        (self.skill / "scripts/write_summary.mjs").write_text("// new writer rule", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "写表"):
            self.store.sync(self.skill)

    def test_hash_mismatch_never_switches_active_engine(self):
        bad = self.root / "bad.zip"
        with zipfile.ZipFile(self.root / "base.zip") as z, zipfile.ZipFile(bad, "w") as out:
            for name in z.namelist():
                out.writestr(name, b"corrupted" if name == "invoice_pipeline.py" else z.read(name))
        with self.assertRaisesRegex(ValueError, "完整性"):
            self.store.install(bad)
        self.assertEqual(self.store.active(), self.bundled)

    def test_zip_traversal_is_rejected(self):
        bad = self.root / "bad.zip"
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("../outside.py", "bad")
        with self.assertRaises(ValueError):
            self.store.install(bad)
        self.assertFalse((self.root / "outside.py").exists())

    def test_incompatible_main_signature_never_activates(self):
        parser = self.skill / "scripts/invoice_pipeline.py"
        parser.write_text("def main():\n    return 0\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "接口"):
            self.store.sync(self.skill)
        self.assertEqual(self.store.active(), self.bundled)

    def test_missing_required_helper_never_activates(self):
        parser = self.skill / "scripts/invoice_pipeline.py"
        parser.write_text(parser.read_text(encoding="utf-8").replace("def is_verification_report_pdf(", "def removed_helper("), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "接口"):
            self.store.sync(self.skill)
        self.assertEqual(self.store.active(), self.bundled)

    def test_incompatible_preview_output_never_activates(self):
        parser = self.skill / "scripts/invoice_pipeline.py"
        parser.write_text(parser.read_text(encoding="utf-8") + '\ndef main(argv=None):\n    Path(argv[argv.index("--report") + 1]).write_text("{}", encoding="utf-8")\n    return 0\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "接口"):
            self.store.sync(self.skill)
        self.assertEqual(self.store.active(), self.bundled)


if __name__ == "__main__":
    unittest.main()
