param([string]$WorkbookInput, [ValidateSet('Auto', 'Excel', 'WPS')][string]$OfficeBackend = 'Auto')
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
. (Join-Path $PSScriptRoot 'office_runtime.ps1')
$context = $null
try {
  $context = New-InvoiceOfficeContext -Backend $OfficeBackend
  @{status='ready'; backend=$context.Backend; private_instance=$true} | ConvertTo-Json -Compress | Write-Output
} finally {
  if ($null -ne $context) {
    Close-InvoiceOfficeContext $context
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
  }
}

