param([string]$WorkbookInput)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$invoiceExcel = $null
try {
  $invoiceExcel = New-Object -ComObject Excel.Application
  $invoiceExcel.Visible = $false
  $invoiceExcel.DisplayAlerts = $false
  [Console]::WriteLine('Excel ready')
} finally {
  if ($null -ne $invoiceExcel) {
    $invoiceExcel.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($invoiceExcel)
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
  }
}

