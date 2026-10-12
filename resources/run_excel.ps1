param([string]$EngineScript, [string]$WorkbookInput)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
& $EngineScript -WorkbookInput $WorkbookInput

