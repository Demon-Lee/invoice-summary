import unittest
from pathlib import Path
from unittest.mock import patch

from invoice_desktop.controller import load_engine


ENGINE = Path(__file__).resolve().parents[1] / "engine"


class MultiPageEngineTests(unittest.TestCase):
    def test_desktop_engine_reads_all_pages_and_checks_total(self):
        engine = load_engine(ENGINE, "invoice_pipeline.py")

        def word(text, x, y, width=30):
            return {"text": text, "x0": x, "x1": x + width, "top": y, "bottom": y + 9}

        header = "电子发票（普通发票）\n发票号码：00000000000000000001\n名称：测试采购单位\n名称：测试供货单位\n项目名称 规格型号 单位 数量 单价 金额 税率 税额\n"

        class Page:
            chars = []
            def __init__(self, text, words): self.text, self.words = text, words
            def extract_text(self): return self.text
            def extract_words(self): return self.words
            def extract_tables(self): return [[]]

        class Pdf:
            def __init__(self, total):
                self.pages = [
                    Page(header + "*金属制品*长螺 A 份 1 10 10.00 13% 1.30\n丝\n小 计 ¥10.00 ¥1.30\n合 计\n", [word("项目名称", 12, 100), word("*金属制品*长螺", 12, 120, 90), word("丝", 12, 135), word("小", 58, 150, 9), word("计", 103, 150, 9), word("¥10.00", 401, 150), word("¥1.30", 553, 150)]),
                    Page(header + "续行\n*金属制品*垫片 B 份 1 5 5.00 13% 0.65\n合 计\n价税合计（小写）¥" + total, [word("项目名称", 12, 100), word("续行", 12, 112), word("*金属制品*垫片", 12, 130, 90), word("合计", 58, 150, 40)]),
                ]
            def __enter__(self): return self
            def __exit__(self, *_): return False

        with patch.object(engine.pdfplumber, "open", return_value=Pdf("16.95")):
            record, errors = engine.extract_pdf_record("invoice.pdf", 1)
        self.assertEqual(errors, [])
        self.assertEqual([row["product_name"] for row in record["rows"]], ["长螺丝续行", "垫片"])
        self.assertEqual(record["detail_total"], "16.95")
        with patch.object(engine.pdfplumber, "open", return_value=Pdf("99.99")):
            record, errors = engine.extract_pdf_record("invoice.pdf", 1)
        self.assertIsNone(record)
        self.assertTrue(any(error["field"] == "detail_total" for error in errors))


if __name__ == "__main__":
    unittest.main()
