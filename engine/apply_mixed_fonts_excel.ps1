param(
  [Parameter(Mandatory = $true)]
  [string]$WorkbookInput
)

$workbookPath = (Resolve-Path -LiteralPath $WorkbookInput).Path
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false

try {
  $workbook = $excel.Workbooks.Open($workbookPath, 0, $false)
  $sequenceHeader = ([string][char]0x5e8f) + ([string][char]0x53f7)
  $songti = ([string][char]0x5b8b) + ([string][char]0x4f53)

  foreach ($worksheet in @($workbook.Worksheets)) {
    $lastRow = $worksheet.UsedRange.Rows.Count + $worksheet.UsedRange.Row - 1
    $headerRow = $null
    for ($row = 1; $row -le $lastRow; $row++) {
      if ([string]$worksheet.Cells.Item($row, 1).Value2 -eq $sequenceHeader) {
        $headerRow = $row
        break
      }
    }
    if ($null -eq $headerRow) { throw "sequence header not found" }

    $lastColumn = if ($worksheet.UsedRange.Columns.Count -ge 8) { 8 } else { 7 }
    for ($row = $headerRow + 1; $row -le $lastRow; $row++) {
      if ($worksheet.Cells.Item($row, 1).Value2 -isnot [ValueType]) { continue }
      for ($column = 1; $column -le $lastColumn; $column++) {
        $cell = $worksheet.Cells.Item($row, $column)
        $value = $cell.Value2
        if ($null -eq $value -or [string]$value -eq '') { continue }
        $cell.Font.Name = 'Times New Roman'
        $cell.Font.Size = 11
        $text = [string]$value
        $start = 0
        while ($start -lt $text.Length) {
          $isAscii = [int][char]$text[$start] -lt 128
          $end = $start + 1
          while ($end -lt $text.Length -and (([int][char]$text[$end] -lt 128) -eq $isAscii)) { $end++ }
          if (-not $isAscii) { $cell.Characters($start + 1, $end - $start).Font.Name = $songti }
          $start = $end
        }
      }
    }
  }
  $excel.CalculateFullRebuild()
  $workbook.Save()
  $workbook.Close($true)
} finally {
  if ($workbook) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($workbook) }
  $excel.Quit()
  [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}
