import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from invoice_desktop.controller import Controller


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("batch_rename_engine", ROOT / "engine/invoice_pipeline.py")
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


class BatchRenameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def source(self, name, content=None):
        path = self.root / name
        path.write_bytes((content or name).encode("utf-8"))
        return path

    def contents(self):
        return {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}

    def test_chain_can_reuse_names_vacated_in_same_batch(self):
        earlier = self.source("14. 螺母.pdf", "invoice A")
        later = self.source("15. 螺母.pdf", "invoice B")
        # Deliberately put the dependent move first.
        plan = pipeline.build_rename_plan([(later, "螺母"), (earlier, "螺母")], [14, 13])
        self.assertEqual([e["status"] for e in plan], ["ready", "ready"])
        self.assertEqual(pipeline._apply_rename_entries(plan), [])
        self.assertEqual(self.contents(), {"13. 螺母.pdf": b"invoice A", "14. 螺母.pdf": b"invoice B"})

    def test_four_electronic_wire_files_keep_their_individual_contents(self):
        files = [self.source(f"{n}. 电子线.pdf") for n in range(30, 34)]
        before = [p.read_bytes() for p in files]
        plan = pipeline.build_rename_plan([(p, "电子线") for p in files], range(29, 33))
        self.assertTrue(all(e["status"] == "ready" for e in plan))
        self.assertEqual(pipeline._apply_rename_entries(plan), [])
        self.assertEqual([(self.root / f"{n}. 电子线.pdf").read_bytes() for n in range(29, 33)], before)
        self.assertEqual(len(list(self.root.iterdir())), 4)

    def test_cycle_can_swap_names_without_replacing_contents(self):
        a, b = self.source("1. A.pdf"), self.source("2. B.pdf")
        first, second = a.read_bytes(), b.read_bytes()
        plan = pipeline.build_rename_plan([(a, "B"), (b, "A")], [2, 1])
        self.assertTrue(all(e["status"] == "ready" for e in plan))
        self.assertEqual(pipeline._apply_rename_entries(plan), [])
        self.assertEqual(a.read_bytes(), second)
        self.assertEqual(b.read_bytes(), first)

    def test_external_occupant_blocks_entire_batch(self):
        source = self.source("original.pdf")
        self.source("1. A.pdf", "external file")
        other = self.source("other.pdf")
        before = self.contents()
        plan = pipeline.build_rename_plan([(source, "A"), (other, "B")])
        self.assertEqual(plan[0]["status"], "collision")
        self.assertTrue(pipeline._apply_rename_entries(plan))
        self.assertEqual(self.contents(), before)

    def test_blocked_occupant_propagates_to_dependent_moves(self):
        a, b = self.source("1. A.pdf"), self.source("2. B.pdf")
        self.source("3. C.pdf", "not in batch")
        plan = pipeline.build_rename_plan([(a, "B"), (b, "C")], [2, 3])
        self.assertEqual([e["status"] for e in plan], ["collision", "collision"])

    def test_duplicate_final_names_block_without_moving_any_file(self):
        a, b = self.source("first.pdf"), self.source("second.pdf")
        before = self.contents()
        plan = pipeline.build_rename_plan([(a, "A"), (b, "A")], [1, 1])
        self.assertTrue(pipeline._apply_rename_entries(plan))
        self.assertEqual(self.contents(), before)

    def test_unchanged_file_stays_in_place(self):
        a = self.source("1. A.pdf")
        plan = pipeline.build_rename_plan([(a, "A")])
        with patch.object(Path, "rename", side_effect=AssertionError("unchanged file moved")):
            self.assertEqual(pipeline._apply_rename_entries(plan), [])
        self.assertEqual(plan[0]["status"], "unchanged")

    def test_apply_rechecks_a_destination_created_after_preview(self):
        source = self.source("original.pdf")
        plan = pipeline.build_rename_plan([(source, "A")])
        self.source("1. A.pdf", "new external file")
        before = self.contents()
        self.assertTrue(pipeline._apply_rename_entries(plan))
        self.assertEqual(self.contents(), before)

    def test_failed_publish_rolls_back_all_original_names_and_bytes(self):
        a, b = self.source("original A.pdf"), self.source("original B.pdf")
        before = self.contents()
        plan = pipeline.build_rename_plan([(a, "A"), (b, "B")])
        original = Path.rename
        failed = False

        def rename(path, target):
            nonlocal failed
            if Path(target).name == "2. B.pdf" and not failed:
                failed = True
                raise PermissionError("simulated locked file")
            return original(path, target)

        with patch.object(Path, "rename", rename):
            result = pipeline._apply_rename_entries(plan)
        self.assertTrue(result)
        self.assertEqual(self.contents(), before)
        self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_incomplete_recovery_directory_blocks_preview_plan(self):
        source = self.source("original.pdf")
        recovery = self.root / ".invoice-rename-interrupted"
        recovery.mkdir()
        (recovery / "recovery.json").write_text("{}", encoding="utf-8")
        plan = pipeline.build_rename_plan([(source, "A")])
        self.assertEqual(plan[0]["status"], "collision")

    def test_new_target_created_during_publish_is_never_overwritten(self):
        source = self.source("original.pdf", "invoice")
        plan = pipeline.build_rename_plan([(source, "A")])
        original = Path.rename

        def rename(path, target):
            if Path(target).name == "1. A.pdf":
                Path(target).write_bytes(b"external file")
            return original(path, target)

        with patch.object(Path, "rename", rename):
            self.assertTrue(pipeline._apply_rename_entries(plan))
        self.assertEqual(source.read_bytes(), b"invoice")
        self.assertEqual((self.root / "1. A.pdf").read_bytes(), b"external file")
        self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_failed_rollback_preserves_manifest_and_every_invoice(self):
        a, b = self.source("original A.pdf"), self.source("original B.pdf")
        before = sorted(self.contents().values())
        plan = pipeline.build_rename_plan([(a, "A"), (b, "B")])
        original = Path.rename

        def rename(path, target):
            if Path(target).name == "2. B.pdf" or path.name == "1. A.pdf":
                raise PermissionError("simulated lock during publish/rollback")
            return original(path, target)

        with patch.object(Path, "rename", rename):
            errors = pipeline._apply_rename_entries(plan)
        self.assertTrue(any("恢复未完成" in e["message"] for e in errors))
        self.assertEqual(sorted(p.read_bytes() for p in self.root.rglob("*.pdf")), before)
        self.assertEqual(len(list(self.root.glob(".invoice-rename-*/recovery.json"))), 1)

    def test_empty_pdf_directory_reports_interrupted_rename(self):
        import contextlib
        import io
        import json
        recovery = self.root / ".invoice-rename-interrupted"
        recovery.mkdir()
        (recovery / "recovery.json").write_text("[]", encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            pipeline.main(["preview", "--pdf-dir", str(self.root)])
        self.assertTrue(any("恢复未完成" in e["message"] for e in json.loads(output.getvalue())["exceptions"]))


class DesktopRenameVerificationTests(unittest.TestCase):
    def test_source_path_can_be_reused_by_another_invoice(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, second = root / "30. 电子线.pdf", root / "31. 电子线.pdf"
            plan = [dict(source=str(first), destination=str(root / "29. 电子线.pdf"), status="ready"),
                    dict(source=str(second), destination=str(first), status="ready")]
            fingerprints = {str(first): hashlib.sha256(b"A").hexdigest(),
                            str(second): hashlib.sha256(b"B").hexdigest()}
            (root / "29. 电子线.pdf").write_bytes(b"A")
            first.write_bytes(b"B")
            preview = SimpleNamespace(payload={"rename_plan": plan}, fingerprints=fingerprints)
            actual = Controller.__new__(Controller)._actual_rename_plan(preview)
            self.assertEqual([e["status"] for e in actual], ["renamed", "renamed"])

    def test_existing_destination_with_wrong_contents_is_not_completed(self):
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp) / "old.pdf", Path(temp) / "new.pdf"
            target.write_bytes(b"different invoice")
            preview = SimpleNamespace(payload={"rename_plan": [dict(source=str(source), destination=str(target))]},
                                      fingerprints={str(source): hashlib.sha256(b"expected invoice").hexdigest()})
            actual = Controller.__new__(Controller)._actual_rename_plan(preview)
            self.assertEqual(actual[0]["status"], "not_completed")


if __name__ == "__main__":
    unittest.main()
