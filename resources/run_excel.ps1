param([string]$EngineScript, [string]$WorkbookInput, [string]$LayoutPlanFile,
      [ValidateSet('Auto', 'Excel', 'WPS')][string]$OfficeBackend = 'Auto')
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
. (Join-Path $PSScriptRoot 'office_runtime.ps1')
$selectedBackend = Invoke-InvoiceSharedFonts -EngineScript $EngineScript -WorkbookInput $WorkbookInput -OfficeBackend $OfficeBackend
if (-not $?) { throw 'Shared font processing failed.' }
& (Join-Path $PSScriptRoot 'format_workbook.ps1') -WorkbookInput $WorkbookInput -PlanFile $LayoutPlanFile -OfficeBackend $selectedBackend
if (-not $?) { throw 'Workbook content fitting failed.' }

