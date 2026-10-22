param([string]$EngineScript, [string]$WorkbookInput, [string]$LayoutPlanFile)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
& $EngineScript -WorkbookInput $WorkbookInput
if (-not $?) { throw 'Shared font processing failed.' }
& (Join-Path $PSScriptRoot 'format_workbook.ps1') -WorkbookInput $WorkbookInput -PlanFile $LayoutPlanFile
if (-not $?) { throw 'Workbook content fitting failed.' }

