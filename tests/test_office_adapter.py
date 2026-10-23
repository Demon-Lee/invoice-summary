import ast
import inspect
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from invoice_desktop.controller import ExcelAdapter


class OfficeAdapterTests(unittest.TestCase):
    def test_backend_names_are_validated_and_normalized(self):
        self.assertEqual(ExcelAdapter().backend, 'Auto')
        self.assertEqual(ExcelAdapter(backend='wps').backend, 'WPS')
        self.assertEqual(ExcelAdapter(backend='excel').backend, 'Excel')
        with self.assertRaises(ValueError):
            ExcelAdapter(backend='other')

    def test_command_passes_selected_backend_and_returns_stdout(self):
        adapter = ExcelAdapter(backend='WPS')
        with patch('invoice_desktop.controller.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'ready-json', '')) as run:
            result = adapter._run(Path('probe.ps1'), ['-WorkbookInput', 'sample.xlsx'])
        self.assertEqual(result, 'ready-json')
        args = run.call_args.args[0]
        self.assertEqual(args[-2:], ['-OfficeBackend', 'WPS'])
        self.assertEqual(run.call_count, 1)

    def test_auto_probe_pins_actual_backend(self):
        adapter = ExcelAdapter()
        adapter._pin_backend(json.dumps({'status':'ready', 'backend':'WPS', 'private_instance':True}))
        self.assertEqual(adapter.backend, 'WPS')
        self.assertEqual(adapter.requested_backend, 'Auto')

    def test_probe_rejects_shared_or_wrong_application(self):
        for record in ({'status':'ready','backend':'WPS','private_instance':False},
                       {'status':'ready','backend':'other','private_instance':True},
                       {'status':'failed','backend':'WPS','private_instance':True}):
            with self.subTest(record=record), self.assertRaises(ValueError):
                ExcelAdapter()._pin_backend(json.dumps(record))
        with self.assertRaises(ValueError):
            ExcelAdapter(backend='Excel')._pin_backend(json.dumps({'status':'ready','backend':'WPS','private_instance':True}))

    def test_invalid_probe_output_is_not_accepted(self):
        for value in ('', 'Excel ready', 'null', '[]'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ExcelAdapter()._pin_backend(value)

    def test_operation_failure_does_not_switch_backend(self):
        adapter = ExcelAdapter(backend='WPS')
        with patch('invoice_desktop.controller.subprocess.run', return_value=subprocess.CompletedProcess([], 1, '', 'native-error')) as run:
            with self.assertRaisesRegex(ValueError, 'WPS'):
                adapter._run(Path('format.ps1'), [])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(adapter.backend, 'WPS')

    def test_ui_export_forwards_the_processing_adapter(self):
        from invoice_desktop.app import App
        import textwrap
        tree = ast.parse(textwrap.dedent(inspect.getsource(App._export_pdf)))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'export_workbook_pdfs']
        self.assertEqual(len(calls), 1)
        keywords = {item.arg: item.value for item in calls[0].keywords}
        self.assertIn('excel', keywords)
        self.assertEqual(ast.unparse(keywords['excel']), 'self.controller.excel')


if __name__ == '__main__':
    unittest.main()
