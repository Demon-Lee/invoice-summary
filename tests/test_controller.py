import copy
import tempfile
import unittest
from pathlib import Path
from tests.fixtures import template, payload

try:
    from invoice_desktop.controller import Controller
except ImportError:
    Controller = None


class FakeExcel:
    def check(self, workbook):
        pass

    def apply(self, script, workbook):
        pass


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Controller, "需要实现有保护门槛的处理流程")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf_dir = self.root / "pdf"
        self.pdf_dir.mkdir()
        self.pdf = self.pdf_dir / "原始.pdf"
        self.pdf.write_bytes(b"synthetic invoice")
        self.book = template(self.root / "报销.xlsx")
        self.data = payload()
        self.data["records"][0]["pdf"] = str(self.pdf)
        self.data["rename_plan"] = [dict(source=str(self.pdf), destination=str(self.pdf_dir / "1. 测试器材.pdf"), status="ready", sequence=1)]
        engine = Path(__file__).resolve().parents[1] / "engine"
        self.calls = []
        self.controller = Controller(engine, excel=FakeExcel(), state_dir=self.root / "run-state")
        from invoice_desktop.updates import sha256
        self.controller._fingerprints = lambda directory, workbook: {str(p): sha256(p) for p in [workbook, *sorted(directory.glob('*.pdf'))]}
        def invoke(kind, args, report):
            self.calls.append((kind, args))
            if "preview" in args:
                return copy.deepcopy(self.data)
            if "rename" in args:
                self.pdf.rename(self.pdf_dir / "1. 测试器材.pdf")
                return dict(exceptions=[], rename_plan=[dict(self.data["rename_plan"][0], status="renamed")])
            if "verify" in args:
                return dict(exceptions=[], verification=[dict(status="failed")], batch_verification=dict(status="passed"))
            return dict(sequences={"1": "12.34"}, acceptance_footer_total="12.34", issue_footer_total="12.34")
        self.controller._invoke = invoke

    def test_parser_exception_blocks_apply_and_keeps_all_input_bytes(self):
        self.data["exceptions"] = [dict(pdf=str(self.pdf), field="seller", message="missing seller")]
        before = self.book.read_bytes()
        preview = self.controller.preview(self.pdf_dir, self.book)
        self.assertFalse(preview.clean)
        with self.assertRaisesRegex(ValueError, "异常"):
            self.controller.apply(preview)
        self.assertEqual(self.book.read_bytes(), before)
        self.assertTrue(self.pdf.exists())
        self.assertEqual(len(self.calls), 1)

    def test_cent_mismatch_is_caught_before_any_mutation(self):
        self.data["records"][0]["grand_total"] = "12.35"
        preview = self.controller.preview(self.pdf_dir, self.book)
        self.assertFalse(preview.clean)
        self.assertTrue(any("金额" in error for error in preview.issues))
        self.assertTrue(self.pdf.exists())

    def test_changed_file_requires_fresh_preview(self):
        preview = self.controller.preview(self.pdf_dir, self.book)
        self.assertTrue(preview.clean)
        self.pdf.write_bytes(b"changed after preview")
        with self.assertRaisesRegex(ValueError, "变化"):
            self.controller.apply(preview)
        self.assertTrue(self.pdf.exists())
        self.assertEqual(len(self.calls), 1)

    def test_collision_blocks_even_if_parser_has_no_exception(self):
        self.data["rename_plan"][0]["status"] = "collision"
        preview = self.controller.preview(self.pdf_dir, self.book)
        self.assertFalse(preview.clean)

    def test_zero_exit_failed_verification_is_not_success_and_scratch_is_cleaned(self):
        preview = self.controller.preview(self.pdf_dir, self.book)
        result = self.controller.apply(preview)
        self.assertEqual(result["status"], "failed")
        self.assertIn("逐分", result["error"])
        self.assertEqual(result["cleanup"], "完成")
        self.assertTrue((self.pdf_dir / "1. 测试器材.pdf").exists())
        self.assertIn("写入工作簿", result["completed"])
        self.assertFalse(self.controller.last_scratch.exists())

    def test_incomplete_rename_report_stops_before_workbook_write(self):
        preview = self.controller.preview(self.pdf_dir, self.book)
        before = self.book.read_bytes()
        original = self.controller._invoke
        def invoke(kind, args, report):
            result = original(kind, args, report)
            if "rename" in args:
                result["rename_plan"] = []
            return result
        self.controller._invoke = invoke
        result = self.controller.apply(preview)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.book.read_bytes(), before)

    def test_engine_using_dataclass_has_normal_python_module_context(self):
        from invoice_desktop.controller import load_engine
        path = self.root / "model.py"
        path.write_text("from __future__ import annotations\nfrom dataclasses import dataclass\n@dataclass\nclass Entry:\n    value: int = 1\n", encoding="utf-8")
        module = load_engine(self.root, "model.py")
        self.assertEqual(module.Entry().value, 1)

    def test_failed_excel_run_can_resume_after_application_restart(self):
        class FailingExcel(FakeExcel):
            def apply(self, script, workbook):
                raise ValueError("simulated Excel failure")
        self.controller.excel = FailingExcel()
        failed = self.controller.apply(self.controller.preview(self.pdf_dir, self.book))
        self.assertEqual(failed["status"], "failed")
        renamed = self.pdf_dir / "1. 测试器材.pdf"
        self.data["records"][0]["pdf"] = str(renamed)
        self.data["rename_plan"] = [dict(source=str(renamed), destination=str(renamed), status="unchanged", sequence=1)]
        fresh = Controller(self.controller.engine_dir, excel=FakeExcel(), state_dir=self.root / "run-state")
        fresh._fingerprints = self.controller._fingerprints
        def invoke(kind, args, report):
            self.calls.append((kind, args))
            if "preview" in args:
                return copy.deepcopy(self.data)
            if "rename" in args:
                return dict(exceptions=[], rename_plan=copy.deepcopy(self.data["rename_plan"]))
            if "verify" in args:
                return dict(exceptions=[], verification=[dict(status="passed")], batch_verification=dict(status="passed"))
            return dict(sequences={"1": "12.34"}, acceptance_footer_total="12.34", issue_footer_total="12.34")
        fresh._invoke = invoke
        preview = fresh.preview(self.pdf_dir, self.book)
        self.assertTrue(preview.clean)
        self.assertEqual(preview.rows_to_add, 0)
        self.assertTrue(preview.resume_pending)
        self.assertTrue(preview.has_changes)
        result = fresh.apply(preview)
        self.assertEqual(result["status"], "completed")
        self.assertFalse(fresh.preview(self.pdf_dir, self.book).has_changes)

    def test_pending_run_blocks_changed_invoice_content(self):
        self.controller.apply(self.controller.preview(self.pdf_dir, self.book))
        renamed = self.pdf_dir / "1. 测试器材.pdf"
        self.data["records"][0]["pdf"] = str(renamed)
        self.data["rename_plan"] = [dict(source=str(renamed), destination=str(renamed), status="unchanged", sequence=1)]
        renamed.write_bytes(b"different invoice")
        preview = self.controller.preview(self.pdf_dir, self.book)
        self.assertFalse(preview.clean)
        self.assertTrue(any("未完成" in item for item in preview.issues))


if __name__ == "__main__":
    unittest.main()
