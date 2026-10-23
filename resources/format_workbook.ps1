param(
    [Parameter(Mandatory=$true)][string]$WorkbookInput,
    [Parameter(Mandatory=$true)][string]$PlanFile
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
. (Join-Path $PSScriptRoot 'excel_layout.ps1')

# The timer runs managed C# only; no PowerShell callback uses a worker thread.
Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
public sealed class InvoiceFormatWatchdog : IDisposable {
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
    private readonly int processId;
    private readonly long startTicks;
    private readonly Timer timer;
    private int timedOut;
    public bool TimedOut { get { return Interlocked.CompareExchange(ref timedOut, 0, 0) != 0; } }
    public InvoiceFormatWatchdog(int id, long ticks) {
        processId = id; startTicks = ticks;
        timer = new Timer(OnTimeout, null, 210000, Timeout.Infinite);
    }
    private void OnTimeout(object state) {
        Interlocked.Exchange(ref timedOut, 1);
        StopOwned();
    }
    public void StopOwned() {
        try {
            using (Process process = Process.GetProcessById(processId)) {
                if (String.Equals(process.ProcessName, "EXCEL", StringComparison.OrdinalIgnoreCase)
                    && process.StartTime.ToUniversalTime().Ticks == startTicks) {
                    process.Kill();
                    process.WaitForExit(5000);
                }
            }
        } catch (ArgumentException) { }
          catch (InvalidOperationException) { }
          catch (System.ComponentModel.Win32Exception) { }
    }
    public void Dispose() { timer.Dispose(); }
}
'@

$excel = $books = $book = $guard = $excelProcess = $null
$owned = $false
$priorCalculateBeforeSave = $null
$stage = 'open'
$sheetName = ''
$elapsed = [Diagnostics.Stopwatch]::StartNew()
try {
    $plan = Get-Content -LiteralPath $PlanFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([int]$plan.schema_version -ne 1 -or @($plan.sheets).Count -ne 2) {
        throw 'Expected schema version 1 and exactly two formatting worksheets.'
    }
    $helperStarted = [Diagnostics.Process]::GetCurrentProcess().StartTime.ToUniversalTime()
    $excel = New-Object -ComObject Excel.Application
    $excelProcessId = [uint32]0
    [void][InvoiceFormatWatchdog]::GetWindowThreadProcessId([IntPtr]$excel.Hwnd, [ref]$excelProcessId)
    $excelProcess = Get-Process -Id $excelProcessId -ErrorAction Stop
    $excelStarted = $excelProcess.StartTime.ToUniversalTime()
    if ($excelProcess.ProcessName -ine 'EXCEL' -or $excelStarted -lt $helperStarted) {
        throw 'Cannot confirm a private Excel instance. Close Excel and retry.'
    }
    $books = $excel.Workbooks
    if ($books.Count -ne 0) { throw 'Excel instance already has workbooks. Close Excel and retry.' }
    $owned = $true
    $guard = [InvoiceFormatWatchdog]::new([int]$excelProcessId, [long]$excelStarted.Ticks)
    $excelProcess.Dispose()
    $excelProcess = $null
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $false
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 3
    $book = $books.Open($WorkbookInput, 0, $false)
    if ([bool]$book.ReadOnly) { throw 'The staged workbook cannot be opened for editing.' }
    $priorCalculateBeforeSave = [bool]$excel.CalculateBeforeSave
    $excel.CalculateBeforeSave = $false
    $stage = 'initial'
    foreach ($item in @($plan.sheets)) {
        $sheetName = [string]$item.name
        Fit-InvoiceContent $book $item
        if ($guard.TimedOut) { throw 'Workbook formatting timed out.' }
    }
    # Calculate only after both sheets pass fitting. Re-fit the final formula
    # displays before saving. Every probe belongs to a scratch workbook, so
    # the source sheet count and calculation mode remain unchanged throughout.
    $stage = 'calculate'
    $sheetName = ''
    [void]$excel.Calculate()
    $formulaSnapshot = Get-InvoiceFormulaSnapshot $book $plan
    $stage = 'final'
    foreach ($item in @($plan.sheets)) {
        $sheetName = [string]$item.name
        Fit-InvoiceContent $book $item $formulaSnapshot
        if ($guard.TimedOut) { throw 'Workbook formatting timed out.' }
    }
    # Scratch edits can recalculate volatile source formulas in this private
    # application. The final probes use captured values, and these checks
    # require the source to equal that same baseline before publication.
    Assert-InvoiceFormulaSnapshot $book $formulaSnapshot 'after final fitting'
    if ($guard.TimedOut) { throw 'Workbook formatting timed out.' }
    $stage = 'save'
    $sheetName = ''
    [void]$book.Save()
    Assert-InvoiceFormulaSnapshot $book $formulaSnapshot 'after saving'
    if ($guard.TimedOut) { throw 'Workbook formatting timed out while saving.' }
    @{ status = 'completed' } | ConvertTo-Json -Compress | Write-Output
} catch {
    if ($null -ne $guard -and $guard.TimedOut) {
        throw ([string]::Format([Globalization.CultureInfo]::InvariantCulture,
            'INVOICE_FORMAT_TIMEOUT stage={0} elapsed={1:0.0}s sheet={2}',
            @($stage, $elapsed.Elapsed.TotalSeconds, $sheetName)))
    }
    throw
} finally {
    try {
        if ($owned -and $null -ne $excel -and $null -ne $priorCalculateBeforeSave) {
            $excel.CalculateBeforeSave = $priorCalculateBeforeSave
        }
    } catch { }
    try { if ($null -ne $book) { [void]$book.Close($false) } } catch { }
    Release-InvoiceLayoutCom $book
    Release-InvoiceLayoutCom $books
    try { if ($owned -and $null -ne $excel) { [void]$excel.Quit() } } catch { }
    Release-InvoiceLayoutCom $excel
    $book = $books = $excel = $null
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    if ($null -ne $excelProcess) { $excelProcess.Dispose() }
    if ($null -ne $guard) {
        $guard.StopOwned()
        $guard.Dispose()
    }
}
