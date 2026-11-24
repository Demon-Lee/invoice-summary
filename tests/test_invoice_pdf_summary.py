import hashlib
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pypdfium2 as pdfium

from invoice_desktop import pdf_export
from invoice_desktop.updates import sha256

try:
    from invoice_desktop import invoice_pdf_summary as summary
except ImportError:
    summary = None


def make_pdf(path, pages, feature=None):
    """Small independent vector PDF fixture: (text, width, height, rotation)."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    resources = ""
    annots = ""
    prefix = b""
    if feature == "form":
        appearance=b"0 0 1 rg 0 0 90 35 re f BT /F1 12 Tf 5 10 Td (WIDGET) Tj ET"
        objects[0]=b"<< /Type /Catalog /Pages 2 0 R /AcroForm << /Fields [4 0 R] /NeedAppearances false >> >>"
        objects.extend([b"<< /Type /Annot /Subtype /Widget /FT /Tx /T (Field) /V (WIDGET) /Rect [80 80 170 115] /F 4 /AP << /N 5 0 R >> >>",
                        f"<< /Type /XObject /Subtype /Form /BBox [0 0 90 35] /Resources << /Font << /F1 3 0 R >> >> /Length {len(appearance)} >>\nstream\n".encode()+appearance+b"\nendstream"])
        annots="/Annots [4 0 R]"
    elif feature == "layer":
        objects[0]=b"<< /Type /Catalog /Pages 2 0 R /OCProperties << /OCGs [4 0 R] /D << /BaseState /OFF /OFF [4 0 R] >> >> >>"
        objects.append(b"<< /Type /OCG /Name (Hidden layer) >>")
        resources="/Properties << /HiddenLayer 4 0 R >>"
        prefix=b"/OC /HiddenLayer BDC 1 0 0 rg 10 100 70 40 re f EMC\n"
    kids = []
    for text, width, height, rotation in pages:
        page_id = len(objects) + 1
        kids.append(f"{page_id} 0 R")
        content = prefix + f"BT /F1 14 Tf 20 40 Td ({text}) Tj ET".encode("ascii")
        objects.extend([
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Rotate {rotation} /Resources << /Font << /F1 3 0 R >> {resources} >> {annots} /Contents {page_id+1} 0 R >>".encode("ascii"),
            f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream",
        ])
    objects[1] = f"<< /Type /Pages /Count {len(kids)} /Kids [{' '.join(kids)}] >>".encode("ascii")
    result = bytearray(b"%PDF-1.7\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = len(result)
    result.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    result.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    path.write_bytes(result)
    return path


class InvoiceSummaryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(summary, "需要实现与本批处理结果绑定的发票汇总")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inputs = self.root / "invoices"
        self.inputs.mkdir()
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()
        self.output = self.root / "export"
        self.output.mkdir()

    def invoice(self, name, sequence, pages=None):
        path = make_pdf(self.inputs / name, pages or [(f"invoice {sequence}", 420, 300, 0)])
        return dict(sequence=sequence, path=str(path), sha256=sha256(path))

    def test_processing_manifest_includes_each_invoice_once_with_final_path(self):
        first, second = self.invoice("1. A.pdf", 1), self.invoice("2. B.pdf", 2)
        old_a, old_b = str(self.inputs / "old A.pdf"), str(self.inputs / "old B.pdf")
        result = dict(status="completed", payload={"records": [dict(sequence=1, pdf=old_a, rows=[{}, {}]),
                                                               dict(sequence=2, pdf=old_b, rows=[{}])]},
                      rename_plan=[dict(source=old_a, destination=first["path"], status="renamed"),
                                   dict(source=old_b, destination=second["path"], status="renamed")])
        self.assertEqual(summary.sources_from_processing(result, {old_a:first["sha256"],old_b:second["sha256"]}), [first,second])

    def test_failed_processing_cannot_supply_invoice_manifest(self):
        with self.assertRaises(ValueError):
            summary.sources_from_processing(dict(status="failed"), {})

    def test_merge_orders_by_sequence_and_preserves_all_pages(self):
        first = self.invoice("10. A.pdf", 1, [("A page 1",420,300,0),("A page 2",300,420,90)])
        second = self.invoice("2. B.pdf", 2, [("B page 1",600,400,0)])
        snapshots = summary.snapshot_invoices([second,first], self.scratch, self.output)
        report = summary.merge_invoice_pdfs(snapshots, self.output / summary.FILENAME)
        self.assertEqual((report["invoices"],report["pages"]), (2,3))
        with pdfium.PdfDocument(self.output / summary.FILENAME) as pdf:
            texts=[]
            for page in pdf:
                with closing(page), closing(page.get_textpage()) as text:
                    texts.append(text.get_text_bounded().strip())
            self.assertEqual(texts,["A page 1","A page 2","B page 1"])
            with closing(pdf[1]) as page:
                self.assertEqual(page.get_rotation(),90)
                self.assertEqual(tuple(page.get_size()),(420,300))

    def test_later_unlisted_files_do_not_enter_summary(self):
        first = self.invoice("1. A.pdf",1)
        self.invoice("new invoice.pdf",2)
        snapshots=summary.snapshot_invoices([first],self.scratch,self.output)
        result=summary.merge_invoice_pdfs(snapshots,self.output / summary.FILENAME)
        self.assertEqual(result["invoices"],1)

    def test_modified_invoice_blocks_snapshot(self):
        source=self.invoice("1. A.pdf",1)
        Path(source["path"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError,"变化"):
            summary.snapshot_invoices([source],self.scratch,self.output)

    def test_missing_invoice_is_not_silently_skipped(self):
        source=self.invoice("1. A.pdf",1)
        Path(source["path"]).unlink()
        with self.assertRaises(ValueError):
            summary.snapshot_invoices([source],self.scratch,self.output)

    def test_duplicate_file_or_gapped_sequence_is_rejected(self):
        source=self.invoice("1. A.pdf",1)
        for sources in ([source,dict(source,sequence=2)],[dict(source,sequence=2)],[]):
            with self.subTest(sources=sources),self.assertRaises(ValueError):
                summary.snapshot_invoices(sources,self.scratch,self.output)

    def test_cannot_write_summary_into_invoice_input_directory(self):
        source=self.invoice("1. A.pdf",1)
        with self.assertRaisesRegex(ValueError,"文件夹"):
            summary.snapshot_invoices([source],self.scratch,self.inputs)

    def test_unreadable_invoice_stops_merge(self):
        path=self.inputs/'1. bad.pdf'
        path.write_bytes(b"not a PDF")
        source=dict(sequence=1,path=str(path),sha256=sha256(path))
        snapshots=summary.snapshot_invoices([source],self.scratch,self.output)
        with self.assertRaisesRegex(ValueError,"读取"):
            summary.merge_invoice_pdfs(snapshots,self.output / summary.FILENAME)

    def test_interactive_form_cannot_silently_disappear_from_summary(self):
        path=make_pdf(self.inputs/'1. form.pdf',[("page content",420,300,0)],feature='form')
        source=dict(sequence=1,path=str(path),sha256=sha256(path))
        snapshots=summary.snapshot_invoices([source],self.scratch,self.output)
        with self.assertRaisesRegex(ValueError,'交互表单'):
            summary.merge_invoice_pdfs(snapshots,self.output / summary.FILENAME)
        self.assertFalse((self.output / summary.FILENAME).exists())

    def test_hidden_layer_cannot_silently_become_visible_in_summary(self):
        path=make_pdf(self.inputs/'1. layer.pdf',[("page content",420,300,0)],feature='layer')
        source=dict(sequence=1,path=str(path),sha256=sha256(path))
        snapshots=summary.snapshot_invoices([source],self.scratch,self.output)
        with self.assertRaisesRegex(ValueError,'可选图层'):
            summary.merge_invoice_pdfs(snapshots,self.output / summary.FILENAME)
        self.assertFalse((self.output / summary.FILENAME).exists())

    def test_mutation_after_snapshot_is_detected_before_publication(self):
        source=self.invoice("1. A.pdf",1)
        summary.snapshot_invoices([source],self.scratch,self.output)
        Path(source['path']).write_bytes(b"changed during Office export")
        with self.assertRaisesRegex(ValueError,"变化"):
            summary.verify_sources([source])


class OutputPublicationTests(unittest.TestCase):
    def test_three_outputs_are_fingerprinted_only_when_requested(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            self.assertEqual(set(pdf_export.output_fingerprints(folder)),{'验收单.pdf','领用单.pdf'})
            self.assertEqual(set(pdf_export.output_fingerprints(folder,include_invoice_summary=True)),
                             {'验收单.pdf','领用单.pdf','发票汇总.pdf'})

    def test_third_publish_failure_restores_all_previous_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            stage=folder/'stage'
            stage.mkdir()
            names=('验收单.pdf','领用单.pdf','发票汇总.pdf')
            for name in names:
                (folder/name).write_bytes(('old '+name).encode())
                (stage/name).write_bytes(('new '+name).encode())
            before={name:(folder/name).read_bytes() for name in names}
            approved={name:sha256(folder/name) for name in names}
            original=pdf_export.os.replace
            def replace(source,target):
                if Path(source)==stage/'发票汇总.pdf':
                    raise PermissionError('simulated third PDF is open')
                return original(source,target)
            self.assertTrue(hasattr(pdf_export,'_publish_outputs'),'需要支持三份文件一起发布')
            installed={}
            with patch.object(pdf_export.os,'replace',replace),self.assertRaises(ValueError):
                pdf_export._publish_outputs(stage,folder,approved,installed)
            self.assertEqual({name:(folder/name).read_bytes() for name in names},before)
            self.assertEqual(installed,{})


class ExportFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.book=self.root/'filled.xlsx'
        self.book.write_bytes(b'workbook snapshot fixture')
        self.inputs=self.root/'invoices'
        self.inputs.mkdir()
        source=make_pdf(self.inputs/'1. invoice.pdf',[("invoice page",420,300,0)])
        self.sources=[dict(sequence=1,path=str(source),sha256=sha256(source))]
        self.output=self.root/'output'
        self.output.mkdir()
        self.plan={'schema_version':1,'sheets':[dict(name='验收',file_name='验收单.pdf'),dict(name='领用',file_name='领用单.pdf')]}

    def export(self,include=True,during_office=None):
        calls=[]
        test=self
        class FakeOffice:
            def export_pdf(self,book,plan_file,stage,report_file):
                calls.append('Office')
                for item in test.plan['sheets']:
                    make_pdf(stage/item['file_name'],[("table page",842,595,0)])
                report_file.write_text(json.dumps(dict(status='completed',sheets=test.plan['sheets'])),encoding='utf-8')
                if during_office:
                    during_office()
        files=[dict(sheet=s['name'],name=s['file_name'],pages=1) for s in self.plan['sheets']]
        approved=pdf_export.output_fingerprints(self.output,include_invoice_summary=include)
        with patch.object(pdf_export,'_print_plan',return_value=self.plan),patch.object(pdf_export,'_validate_pdfs',return_value=files):
            result=pdf_export.export_workbook_pdfs(self.book,self.output,approved,excel=FakeOffice(),
                expected_workbook_sha256=sha256(self.book),invoice_sources=self.sources if include else None)
        return result,calls

    def test_summary_is_published_with_two_tables(self):
        before=self.book.read_bytes()
        result,calls=self.export()
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(len(result['files']),3)
        self.assertEqual(result['files'][-1]['invoices'],1)
        self.assertEqual(result['cleanup'],'完成')
        self.assertEqual(self.book.read_bytes(),before)
        self.assertEqual(calls,['Office'])

    def test_table_only_export_ignores_invoice_sources_and_keeps_old_summary(self):
        (self.output/'发票汇总.pdf').write_bytes(b'old summary')
        Path(self.sources[0]['path']).unlink()
        result,_=self.export(include=False)
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(len(result['files']),2)
        self.assertEqual((self.output/'发票汇总.pdf').read_bytes(),b'old summary')

    def test_missing_invoice_blocks_before_office_or_any_publication(self):
        Path(self.sources[0]['path']).unlink()
        result,calls=self.export()
        self.assertEqual(result['status'],'failed')
        self.assertEqual(calls,[])
        self.assertEqual(list(self.output.iterdir()),[])

    def test_invoice_mutation_during_office_keeps_all_prior_outputs(self):
        for name in ('验收单.pdf','领用单.pdf','发票汇总.pdf'):
            (self.output/name).write_bytes(('old '+name).encode())
        before={p.name:p.read_bytes() for p in self.output.iterdir()}
        result,_=self.export(during_office=lambda:Path(self.sources[0]['path']).write_bytes(b'changed'))
        self.assertEqual(result['status'],'failed')
        self.assertEqual({p.name:p.read_bytes() for p in self.output.iterdir()},before)


if __name__=='__main__':
    unittest.main()
