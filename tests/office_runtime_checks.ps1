param([string]$RuntimePath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'resources\office_runtime.ps1'))
$ErrorActionPreference = 'Stop'
. $RuntimePath
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('invoice-office-ast-' + [Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($testRoot)
$checks = 0
function Assert-OfficeTest([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
try {
    $path = Join-Path $testRoot 'fonts.ps1'
    $source = 'param([string]$WorkbookInput)' + "`n" + '$excel = New-Object -ComObject Excel.Application' + "`n" + '$excel.FontName = "Excel.Application is a literal"'
    [IO.File]::WriteAllText($path, $source)
    $adapted = Get-InvoiceAdaptedFontScript -Path $path
    Assert-OfficeTest ($adapted.Contains('$excel = Get-InvoiceFontApplication')) 'Activation was not adapted.'
    Assert-OfficeTest ($adapted.Contains('Excel.Application is a literal')) 'Unrelated source text was changed.'
    $checks++
    foreach ($invalid in @('$excel = New-Object -ComObject $progId',
                           '$a = New-Object -ComObject Excel.Application; $b = New-Object -ComObject Excel.Application',
                           '$excel = New-Object -ComObject Other.Application',
                           '$excel = New-Object -ComObject Excel.Application; $other = New-Object -ComObject $progId',
                           '$excel = New-Object -ComObject Excel.Application; $other = New-Object -Com Excel.Application',
                           '$excel = New-Object -Com Excel.Application',
                           '$excel = New-Object -ComObject:Excel.Application')) {
        [IO.File]::WriteAllText($path, $invalid)
        $rejected = $false
        try { $null = Get-InvoiceAdaptedFontScript -Path $path } catch { $rejected = $true }
        Assert-OfficeTest $rejected 'Unsupported activation did not fail closed.'
        $checks++
    }
    $originalCreator = (Get-Item Function:New-InvoiceOfficeComObject).ScriptBlock
    $script:officeAttempts = New-Object 'System.Collections.Generic.List[string]'
    Set-Item Function:New-InvoiceOfficeComObject -Value {
        param([string]$ProgId)
        [void]$script:officeAttempts.Add($ProgId)
        throw 'Synthetic unavailable automation component.'
    }
    foreach ($backend in @('Auto', 'WPS', 'Excel')) {
        $script:officeAttempts.Clear()
        $rejected = $false
        try { $null = New-InvoiceOfficeContext -Backend $backend } catch { $rejected = $true }
        Assert-OfficeTest $rejected 'Unavailable provider was unexpectedly accepted.'
        $expected = if ($backend -eq 'Auto') { 'KET.Application,Excel.Application' }
                    elseif ($backend -eq 'WPS') { 'KET.Application' } else { 'Excel.Application' }
        Assert-OfficeTest (($script:officeAttempts -join ',') -eq $expected) 'Automatic WPS-first order or explicit provider pinning changed.'
        $checks++
    }
    Set-Item Function:New-InvoiceOfficeComObject -Value $originalCreator
    @{status='passed'; checks=$checks; native_application_started=$false} | ConvertTo-Json -Compress
} finally {
    # The test creates exactly one file; no recursive deletion or computed tree move.
    [IO.File]::Delete((Join-Path $testRoot 'fonts.ps1'))
    [IO.Directory]::Delete($testRoot)
}
