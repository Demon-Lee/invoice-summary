param(
    [Parameter(Mandatory=$true)][string]$WorkbookInput,
    [Parameter(Mandatory=$true)][string]$PlanFile,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$ReportFile
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

# No PowerShell callbacks on worker threads: the watchdog is entirely managed C#.
Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
public sealed class InvoicePdfWatchdog : IDisposable {
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
    private readonly int processId;
    private readonly long startTicks;
    private readonly Timer timer;
    private int timedOut;
    public bool TimedOut { get { return Interlocked.CompareExchange(ref timedOut, 0, 0) != 0; } }
    public InvoicePdfWatchdog(int id, long ticks) {
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

function Release-Com($value) {
    if ($null -ne $value -and [Runtime.InteropServices.Marshal]::IsComObject($value)) {
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($value)
    }
}

$excel = $books = $book = $sheet = $setup = $sheets = $guard = $null
$owned = $false
try {
    $plan = Get-Content -LiteralPath $PlanFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if (@($plan.sheets).Count -ne 2) { throw 'Expected exactly two export worksheets.' }
    $helperStarted = [Diagnostics.Process]::GetCurrentProcess().StartTime.ToUniversalTime()
    $excel = New-Object -ComObject Excel.Application
    $excelProcessId = [uint32]0
    [void][InvoicePdfWatchdog]::GetWindowThreadProcessId([IntPtr]$excel.Hwnd, [ref]$excelProcessId)
    $excelProcess = Get-Process -Id $excelProcessId -ErrorAction Stop
    $excelStarted = $excelProcess.StartTime.ToUniversalTime()
    if ($excelProcess.ProcessName -ine 'EXCEL' -or $excelStarted -lt $helperStarted) {
        throw 'Cannot confirm a private Excel instance. Close Excel and retry.'
    }
    $books = $excel.Workbooks
    if ($books.Count -ne 0) { throw 'Excel instance already has workbooks. Close Excel and retry.' }
    $owned = $true
    $guard = [InvoicePdfWatchdog]::new([int]$excelProcessId, [long]$excelStarted.Ticks)
    $excelProcess.Dispose()
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $false
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 3
    $book = $books.Open($WorkbookInput, 0, $true)
    $sheets = $book.Worksheets
    foreach ($item in $plan.sheets) {
        try {
            $sheet = $sheets.Item([string]$item.name)
            $sheet.Visible = -1
            [void]$sheet.Select($true)
            [void]$sheet.ResetAllPageBreaks()
            $setup = $sheet.PageSetup
            $setup.PaperSize = 9
            $setup.Orientation = 2
            $setup.Zoom = $false
            $setup.FitToPagesWide = 1
            $setup.FitToPagesTall = $false
            $setup.PrintArea = [string]$item.print_area
            $setup.PrintTitleColumns = ''
            if ([string]::IsNullOrWhiteSpace([string]$setup.PrintTitleRows)) {
                $setup.PrintTitleRows = '$1:$' + [string]$item.header_row
            }
            $output = Join-Path $OutputDirectory ([string]$item.file_name)
            [void]$sheet.ExportAsFixedFormat(0, $output, 0, $false, $false, [Type]::Missing, [Type]::Missing, $false)
            if ($guard.TimedOut) { throw 'PDF export timed out. Retry after closing the workbook.' }
        } finally {
            Release-Com $setup
            Release-Com $sheet
            $setup = $sheet = $null
        }
    }
    # No workbook Save: all pagination settings belong to the temporary copy.
    @{ status = 'completed'; sheets = @($plan.sheets) } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportFile -Encoding UTF8
} finally {
    try { if ($null -ne $book) { [void]$book.Close($false) } } catch { }
    Release-Com $setup
    Release-Com $sheet
    Release-Com $sheets
    Release-Com $book
    Release-Com $books
    try { if ($owned -and $null -ne $excel) { [void]$excel.Quit() } } catch { }
    Release-Com $excel
    $setup = $sheet = $sheets = $book = $books = $excel = $null
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    if ($null -ne $guard) {
        $guard.StopOwned()
        $guard.Dispose()
    }
}
