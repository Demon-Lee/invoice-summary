import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook
from tests.fixtures import template
from invoice_desktop.pdf_export import _sheet_plan

ROOT=Path(__file__).resolve().parents[1]
LIBRARY=ROOT/'resources/export_layout.ps1'


class PrintWidthTests(unittest.TestCase):
    def allocate(self,columns,available=700,reservations=None):
        self.assertTrue(LIBRARY.is_file(),'需要导出专用列宽分配，不能把长文字整行撑宽')
        with tempfile.TemporaryDirectory() as temp:
            script=Path(temp)/'widths.ps1'
            data=json.dumps(dict(columns=columns,available=available,reservations=reservations or []))
            source=". '"+str(LIBRARY).replace("'","''")+"'\n$caseInput = ConvertFrom-Json @'\n"+data+"\n'@\n"
            source+="$widths = @(Get-InvoicePrintWidths -Columns $caseInput.columns -AvailableWidth $caseInput.available -Reservations $caseInput.reservations)\nConvertTo-Json -InputObject $widths -Compress\n"
            script.write_text(source,encoding='utf-8-sig')
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            return json.loads(result.stdout)

    def column(self,index,natural,minimum=0,weight=0,wrap=False):
        return dict(index=index,natural_width=natural,min_width=minimum,weight=weight,wrap=wrap)

    def test_long_text_uses_page_budget_and_numeric_width_stays_complete(self):
        widths=self.allocate([self.column(1,80),self.column(2,1200,100,3,True),self.column(3,600,70,2,True)])
        self.assertEqual(widths[0]['width'],80)
        self.assertLessEqual(sum(c['width'] for c in widths),700.01)
        self.assertLess(widths[1]['width'],1200)
        self.assertGreater(widths[1]['width'],widths[2]['width'])

    def test_short_columns_do_not_consume_unused_text_space(self):
        widths=self.allocate([self.column(1,60),self.column(2,110,100,3,True),self.column(3,500,70,2,True)])
        self.assertAlmostEqual(widths[1]['width'],110)
        self.assertAlmostEqual(widths[2]['width'],500)

    def test_minima_are_preserved_if_a_page_requires_some_scaling(self):
        widths=self.allocate([self.column(1,80),self.column(2,400,100,3,True)],available=120)
        self.assertEqual(widths[0]['width'],80)
        self.assertEqual(widths[1]['width'],100)

    def test_zero_weight_fixed_side_column_does_not_expand(self):
        widths=self.allocate([self.column(1,14),self.column(2,2000,100,3,True)])
        self.assertEqual(widths[0]['width'],14)
        self.assertAlmostEqual(widths[1]['width'],686)

    def test_native_wrapped_row_gets_printing_leading(self):
        self.assertTrue(LIBRARY.is_file())
        with tempfile.TemporaryDirectory() as temp:
            script=Path(temp)/'rows.ps1'
            source="$ErrorActionPreference = 'Stop'\n. '"+str(LIBRARY).replace("'","''")+"'\n"
            source+="@( (Get-InvoicePrintRowHeight 30 23.1), (Get-InvoicePrintRowHeight 14.25 22.5), (Get-InvoicePrintRowHeight 15 23.1 $true), (Get-InvoicePrintRowHeight 43.5 23.1 $true) ) | ConvertTo-Json -Compress"
            script.write_text(source,encoding='utf-8-sig')
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            rows=json.loads(result.stdout)
            self.assertGreaterEqual(rows[0],33)
            self.assertEqual(rows[1],22.5)
            self.assertGreater(rows[2],15)
            self.assertLess(rows[2],18)
            self.assertGreater(rows[3],43.5)

    def test_signer_span_gets_space_before_long_text_columns(self):
        columns=[self.column(1,40),self.column(2,900,100,3,True),self.column(3,600,72,2,True),
                 self.column(4,32,28,.25,True),self.column(5,54),self.column(6,80)]
        widths=self.allocate(columns,reservations=[dict(start_column=4,end_column=5,minimum_width=190)])
        self.assertGreaterEqual(widths[3]['width']+widths[4]['width'],189.99)
        self.assertLessEqual(sum(w['width'] for w in widths),700.01)
        self.assertEqual(widths[5]['width'],80)

    def test_date_value_span_is_preserved_even_beyond_table_headers(self):
        columns=[self.column(1,40),self.column(2,900,100,3,True),self.column(3,25),self.column(4,16)]
        widths=self.allocate(columns,reservations=[dict(start_column=3,end_column=4,minimum_width=90)])
        self.assertGreaterEqual(widths[2]['width']+widths[3]['width'],89.99)
        self.assertLessEqual(sum(w['width'] for w in widths),700.01)


class ExportPlanWidthTests(unittest.TestCase):
    def test_only_filled_detail_rows_can_shrink_below_template_height(self):
        with tempfile.TemporaryDirectory() as temp:
            wb = load_workbook(template(Path(temp) / 'sample.xlsx'))
            ws = wb['领用']
            ws['A4'] = 1
            ws['B4'] = '器材'
            ws['A6'] = 2
            ws['B6'] = '带换行的名称'
            plan = _sheet_plan(ws, '领用单.pdf')
            self.assertEqual(plan['print_detail_rows'], [4, 6])
            wb.close()

    def test_date_value_keeps_its_merged_span(self):
        with tempfile.TemporaryDirectory() as temp:
            wb=load_workbook(template(Path(temp)/'sample.xlsx'))
            ws=wb['领用'];ws['A4']=1;ws['B4']='器材'
            ws['F8']='领用日期：';ws['G8']='2026.11.24';ws['H8']=None
            ws.merge_cells('G8:H8')
            value=_sheet_plan(ws,'领用单.pdf')['print_footer_spans'][-1]
            self.assertEqual((value['start_column'],value['end_column']),(7,8))
            wb.close()

    def test_footer_declares_two_signature_spaces_and_both_date_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            wb=load_workbook(template(Path(temp)/'sample.xlsx'))
            ws=wb['领用'];ws['A4']=1;ws['B4']='器材'
            ws['F8']='领用日期：';ws['G8']='2026.11.24';ws['H8']=None
            plan=_sheet_plan(ws,'领用单.pdf')
            self.assertIn('print_footer_spans',plan)
            fields=plan['print_footer_spans']
            self.assertEqual([f['kind'] for f in fields],['signature','signature','date_label','date_value'])
            self.assertEqual((fields[1]['start_column'],fields[1]['end_column']),(4,5))
            self.assertGreaterEqual(fields[1]['blank_width'],100)
            self.assertEqual(fields[2]['anchor'],'F8')
            self.assertEqual(fields[3]['anchor'],'G8')
            wb.close()
    def test_date_beyond_last_table_header_has_a_width_minimum(self):
        with tempfile.TemporaryDirectory() as temp:
            wb=load_workbook(template(Path(temp)/'sample.xlsx'))
            ws=wb['领用']
            ws['A4']=1;ws['B4']='器材'
            plan=_sheet_plan(ws,'领用单.pdf')
            self.assertIn('H8',plan['print_minimum_cells'])
            wb.close()

    def test_only_export_plan_declares_text_wrapping_roles(self):
        with tempfile.TemporaryDirectory() as temp:
            path=template(Path(temp)/'sample.xlsx')
            wb=load_workbook(path)
            for ws in wb:
                for col,value in enumerate([1,'长名称','长规格','个',1,12.34,12.34,'供应商'],1):
                    ws.cell(4,col,value)
            before=[(name,dict((k,v.width) for k,v in wb[name].column_dimensions.items())) for name in wb.sheetnames]
            plan=_sheet_plan(wb['验收'],'验收单.pdf')
            self.assertIn('print_columns',plan)
            columns={c['index']:c for c in plan['print_columns']}
            self.assertTrue(columns[2]['wrap'])
            self.assertTrue(columns[3]['wrap'])
            self.assertTrue(columns[8]['wrap'])
            for index in (1,5,6,7):self.assertFalse(columns[index]['wrap'])
            self.assertEqual(before,[(name,dict((k,v.width) for k,v in wb[name].column_dimensions.items())) for name in wb.sheetnames])
            wb.close()


if __name__=='__main__':unittest.main()
