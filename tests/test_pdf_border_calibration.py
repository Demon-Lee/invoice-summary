import unittest
from types import SimpleNamespace

from invoice_desktop.pdf_layout import _printed_columns, _printed_rows


class PdfBorderCalibrationTests(unittest.TestCase):
    def fixture(self, wrong_header=False):
        native = {'break_rows': [], 'cells': [], 'row_bands': []}
        page = SimpleNamespace(width=842, height=595, chars=[], edges=[])
        for column in range(8):
            text = chr(65 + column)
            native['cells'].append({'address': text + '3', 'page': 1,
                                    'text': text, 'box': [20 + 60 * column, 100, 80 + 60 * column, 120]})
            page.chars.append({'text': 'Z' if wrong_header and column == 4 else text,
                               'x0': 42 + 55 * column, 'x1': 48 + 55 * column,
                               'top': 106, 'bottom': 114, 'doctop': 106, 'upright': True})
        for index in range(9):
            for offset in (-.42, .42):
                x = 30 + 55 * index + offset
                page.edges.append({'x0': x, 'x1': x, 'top': 100, 'bottom': 160, 'height': 60})
        for row in range(3, 6):
            native['row_bands'].append({'row': row, 'page': 1, 'top': 100 + 20 * (row - 3), 'bottom': 120 + 20 * (row - 3)})
        for index in range(4):
            for offset in (-.42, .42):
                y = 100.5 + 20 * index + offset
                page.edges.append({'x0': 30, 'x1': 470, 'top': y, 'bottom': y, 'width': 440})
        sheet = {'name': 'test', 'header_row': 3, 'footer_row': 5, 'repeat_end_row': 3}
        return SimpleNamespace(pages=[page]), sheet, native

    def test_paired_printed_border_paths_map_exact_headers(self):
        pdf, sheet, native = self.fixture()
        transform = _printed_columns(pdf, sheet, native)
        for index in range(9):
            self.assertAlmostEqual(transform(20 + 60 * index), 30 + 55 * index)

    def test_paired_horizontal_paths_keep_all_table_row_bands(self):
        pdf, sheet, native = self.fixture()
        transform = _printed_columns(pdf, sheet, native)
        rows = _printed_rows(pdf, sheet, native, transform)
        self.assertIn(1, rows)
        self.assertEqual(rows[1][0], [100, 120, 140, 160])
        for actual, expected in zip(rows[1][1], [100.5, 120.5, 140.5, 160.5]):
            self.assertAlmostEqual(actual, expected)

    def test_wrong_header_still_prevents_column_calibration(self):
        pdf, sheet, native = self.fixture(wrong_header=True)
        transform = _printed_columns(pdf, sheet, native)
        self.assertEqual(transform(20), 20)

    def test_repeated_border_segments_do_not_bias_the_printed_row_center(self):
        pdf, sheet, native = self.fixture()
        duplicate = next(edge for edge in pdf.pages[0].edges if edge.get('width') == 440)
        pdf.pages[0].edges.extend([dict(duplicate) for _ in range(20)])
        transform = _printed_columns(pdf, sheet, native)
        rows = _printed_rows(pdf, sheet, native, transform)
        self.assertAlmostEqual(rows[1][1][0], 100.5)


if __name__ == '__main__':
    unittest.main()
