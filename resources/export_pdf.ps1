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

function Select-ExportPrinter($application) {
    # Excel pagination can inherit scaling from third-party virtual drivers.
    # Choose the Windows PDF driver only for this private Excel instance.
    # ActivePrinter needs a workbook and its localised "on" separator.
    $original = [string]$application.ActivePrinter
    $devices = $null
    try {
        $devices = Get-Item -LiteralPath 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Devices' -ErrorAction Stop
        $names = @($devices.GetValueNames())
        $preferred = @($names | Where-Object { $_ -ieq 'Microsoft Print to PDF' } | Select-Object -First 1)
        if ($preferred.Count -eq 0) {
            $registered = @(Get-CimInstance Win32_Printer -Filter "DriverName='Microsoft Print To PDF'" -ErrorAction Stop)
            $preferred = @($registered.Name | Where-Object { $names -contains $_ } | Select-Object -First 1)
        }
        if ($preferred.Count -eq 0) { return $original }
        $preferred = [string]$preferred[0]
        $binding = [string]$devices.GetValue($preferred)
        if ($binding.IndexOf(',') -lt 0) { return $original }
        $port = $binding.Substring($binding.IndexOf(',') + 1)
        if (-not $port.EndsWith(':')) { return $original }
        $separators = @()
        $current = @($names | Sort-Object { $_.Length } -Descending | Where-Object { $original.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) } | Select-Object -First 1)
        if ($current.Count -eq 1) {
            $currentName = [string]$current[0]
            $currentBinding = [string]$devices.GetValue($currentName)
            if ($currentBinding.IndexOf(',') -ge 0) {
                $currentPort = $currentBinding.Substring($currentBinding.IndexOf(',') + 1)
                $length = $original.Length - $currentName.Length - $currentPort.Length
                if ($length -gt 0 -and $original.EndsWith($currentPort, [StringComparison]::OrdinalIgnoreCase)) {
                    $separators += $original.Substring($currentName.Length, $length)
                }
            }
        }
        $separators += ' on '
        foreach ($separator in ($separators | Select-Object -Unique)) {
            try {
                $application.ActivePrinter = $preferred + $separator + $port
                return $original
            } catch { }
        }
        # Keep the original device if the optional Windows PDF driver is absent
        # or unusable. Python still validates the actual PDF paper dimensions.
        return $original
    } catch {
        return $original
    } finally {
        if ($null -ne $devices) { $devices.Dispose() }
    }
}

function Read-NativePageBreaks($worksheet, $geometry) {
    $horizontal = $vertical = $null
    $rows = New-Object 'System.Collections.Generic.List[int]'
    $columns = New-Object 'System.Collections.Generic.List[int]'
    try {
        $horizontal = $worksheet.HPageBreaks
        for ($index = 1; $index -le $horizontal.Count; $index++) {
            $pageBreak = $location = $null
            try {
                $pageBreak = $horizontal.Item($index)
                $location = $pageBreak.Location
                $row = [int]$location.Row
                if ($row -gt 1 -and $row -le [int]$geometry.print_end_row) {
                    $rows.Add($row)
                }
            } finally { Release-Com $location; Release-Com $pageBreak }
        }
        $vertical = $worksheet.VPageBreaks
        for ($index = 1; $index -le $vertical.Count; $index++) {
            $pageBreak = $location = $null
            try {
                $pageBreak = $vertical.Item($index)
                $location = $pageBreak.Location
                $column = [int]$location.Column
                if ($column -gt 1 -and $column -le [int]$geometry.print_end_column) {
                    $columns.Add($column)
                }
            } finally { Release-Com $location; Release-Com $pageBreak }
        }
        return @{ rows = @($rows | Sort-Object -Unique); columns = @($columns | Sort-Object -Unique) }
    } finally { Release-Com $horizontal; Release-Com $vertical }
}

function Refresh-NativePagination($application, $worksheet, $pageSetup, $geometry, [int]$zoom) {
    # Numeric Zoom is essential: Excel ignores manual breaks in FitTo mode.
    $application.PrintCommunication = $false
    try { $pageSetup.Zoom = $zoom }
    finally { $application.PrintCommunication = $true }
    $worksheet.DisplayPageBreaks = $false
    $worksheet.DisplayPageBreaks = $true
    if ([int]$pageSetup.Zoom -ne $zoom) { throw 'Excel did not retain numeric print zoom.' }
    return (Read-NativePageBreaks $worksheet $geometry)
}

function Test-TailFits($nativeBreaks, $geometry, $worksheet, [int]$zoom,
    [double]$titleHeight, [double]$availableHeight) {
    $tailPageStart = 1
    foreach ($row in $nativeBreaks.rows) {
        if ($row -gt [int]$geometry.tail_start_row -and $row -le [int]$geometry.tail_end_row) {
            return $false
        }
        if ($row -le [int]$geometry.tail_start_row) { $tailPageStart = [int]$row }
    }
    $flowRange = $null
    try {
        $flowRange = $worksheet.Range([string]$tailPageStart + ':' + [string]$geometry.tail_end_row)
        $flowHeight = [double]$flowRange.Height
        if ($tailPageStart -gt 1) { $flowHeight += $titleHeight }
        return (($flowHeight * $zoom / 100.0) -le ($availableHeight + 0.75))
    } finally { Release-Com $flowRange }
}

function Get-NativeLayout($application, $worksheet, $pageSetup, $geometry) {
    # Points, not pixels. A4 landscape is 297 by 210 mm.
    $paperWidth = 297.0 * 72.0 / 25.4
    $paperHeight = 210.0 * 72.0 / 25.4
    $endRow = [int]$geometry.print_end_row
    $endColumn = [int]$geometry.print_end_column
    $headerRow = [int]$geometry.header_row
    $repeatStart = [int]$geometry.repeat_start_row
    $repeatEnd = [int]$geometry.repeat_end_row
    $tailStart = [int]$geometry.tail_start_row
    $tailEnd = [int]$geometry.tail_end_row
    if ($headerRow -lt 1 -or $headerRow -ge $tailStart -or $tailStart -gt $tailEnd -or
        $tailEnd -ne $endRow -or $endColumn -lt 1 -or @($geometry.content_cells).Count -eq 0 -or
        $repeatStart -lt 1 -or $repeatEnd -lt $repeatStart -or $repeatEnd -gt $headerRow) {
        throw 'Invalid complete-cell geometry or final detail/footer bounds.'
    }
    $printRange = $titleRange = $null
    try {
        $nativeTitles = [string]$pageSetup.PrintTitleRows
        $application.PrintCommunication = $false
        try {
            $pageSetup.PaperSize = 9
            $pageSetup.Orientation = 2
            $pageSetup.Zoom = 100
            $pageSetup.PrintArea = [string]$geometry.print_area
            $pageSetup.PrintTitleColumns = ''
            if ([string]::IsNullOrWhiteSpace($nativeTitles)) {
                $pageSetup.PrintTitleRows = '$1:$' + [string]$headerRow
            }
            $pageSetup.CenterVertically = $false
            $pageSetup.PrintHeadings = $false
        } finally { $application.PrintCommunication = $true }
        $nativeTitles = [string]$pageSetup.PrintTitleRows
        if ($nativeTitles -notmatch '^\$?(\d+):\$?(\d+)$' -or
            [int]$Matches[1] -ne $repeatStart -or [int]$Matches[2] -ne $repeatEnd) {
            throw 'Actual repeated-title rows differ from the geometry plan.'
        }
        [void]$worksheet.ResetAllPageBreaks()
        $printRange = $worksheet.Range([string]$geometry.print_area)
        $titleRange = $worksheet.Range([string]$repeatStart + ':' + [string]$repeatEnd)
        if ([int]$printRange.Row -ne 1 -or [int]$printRange.Column -ne 1) {
            throw 'The print area must begin at A1.'
        }
        $printWidth = [double]$printRange.Width
        $titleHeight = [double]$titleRange.Height
        $titleTop = [double]$titleRange.Top
        $originLeft = [double]$printRange.Left
        $originTop = [double]$printRange.Top
        $leftMargin = [double]$pageSetup.LeftMargin
        $rightMargin = [double]$pageSetup.RightMargin
        $topMargin = [double]$pageSetup.TopMargin
        $bottomMargin = [double]$pageSetup.BottomMargin
        $availableWidth = $paperWidth - $leftMargin - $rightMargin
        $availableHeight = $paperHeight - $topMargin - $bottomMargin
        if ($printWidth -le 0 -or $availableWidth -le 0 -or
            $availableHeight -le 0) {
            throw 'Invalid printable paper dimensions or margins.'
        }
        $baseZoom = [Math]::Min(100, [int][Math]::Floor(100.0 * $availableWidth / $printWidth))
        if ($baseZoom -lt 10) { throw 'All columns cannot fit at Excel minimum 10 percent print zoom.' }
        $nativeBreaks = Refresh-NativePagination $application $worksheet $pageSetup $geometry $baseZoom
        # Printer metrics may make the theoretical width limit one percent too large.
        while (@($nativeBreaks.columns).Count -gt 0 -and $baseZoom -gt 10) {
            $baseZoom--
            $nativeBreaks = Refresh-NativePagination $application $worksheet $pageSetup $geometry $baseZoom
        }
        if (@($nativeBreaks.columns).Count -gt 0) { throw 'Native pagination splits columns across pages.' }
        $zoom = $baseZoom
        $tailFits = Test-TailFits $nativeBreaks $geometry $worksheet $zoom $titleHeight $availableHeight
        $minimumZoom = [Math]::Max(10, [int][Math]::Ceiling($baseZoom * 0.95))
        if (-not $tailFits) {
            for ($candidate = $baseZoom - 1; $candidate -ge $minimumZoom; $candidate--) {
                $nativeBreaks = Refresh-NativePagination $application $worksheet $pageSetup $geometry $candidate
                if (@($nativeBreaks.columns).Count -eq 0 -and
                    (Test-TailFits $nativeBreaks $geometry $worksheet $candidate $titleHeight $availableHeight)) {
                    $zoom = $candidate
                    $tailFits = $true
                    break
                }
            }
        }
        if (-not $tailFits) {
            if ($tailStart -le ($headerRow + 1)) {
                throw 'The final group exceeds one page; moving it would leave a header-only first page.'
            }
            $zoom = $baseZoom
            $nativeBreaks = Refresh-NativePagination $application $worksheet $pageSetup $geometry $zoom
            $breaks = $before = $addedBreak = $null
            try {
                $breaks = $worksheet.HPageBreaks
                $before = $worksheet.Range('A' + [string]$tailStart)
                $addedBreak = $breaks.Add($before)
            } finally { Release-Com $addedBreak; Release-Com $before; Release-Com $breaks }
            $nativeBreaks = Refresh-NativePagination $application $worksheet $pageSetup $geometry $zoom
            if (@($nativeBreaks.rows) -notcontains $tailStart) {
                throw 'Excel did not retain the break before the final detail/footer group.'
            }
        }
        if (@($nativeBreaks.columns).Count -gt 0 -or
            -not (Test-TailFits $nativeBreaks $geometry $worksheet $zoom $titleHeight $availableHeight)) {
            throw 'The final detail/footer group cannot fit on one page at the permitted scale.'
        }
        foreach ($row in $nativeBreaks.rows) {
            if ($row -le ($headerRow + 1)) { throw 'Native pagination creates a header-only first page.' }
        }
        $scale = $zoom / 100.0
        $pageStarts = @(1) + @($nativeBreaks.rows)
        $pageCount = $pageStarts.Count
        $pageTops = @{}
        foreach ($row in $pageStarts) {
            $startCell = $null
            try {
                $startCell = $worksheet.Range('A' + [string]$row)
                $pageTops[[int]$row] = [double]$startCell.Top
            } finally { Release-Com $startCell }
        }
        $horizontalOffset = $leftMargin
        if ([bool]$pageSetup.CenterHorizontally) {
            $horizontalOffset += ($availableWidth - $printWidth * $scale) / 2.0
        }
        $cellProofs = New-Object 'System.Collections.Generic.List[object]'
        $seen = @{}
        foreach ($address in $geometry.content_cells) {
            $cell = $area = $areaRows = $areaColumns = $null
            try {
                $address = [string]$address
                if ($seen.ContainsKey($address)) { throw ('Duplicate content address: ' + $address) }
                $seen[$address] = $true
                $cell = $worksheet.Range($address)
                $area = $cell.MergeArea
                $captionSpan = $null
                if ($null -ne $geometry.caption_spans) { $captionSpan = $geometry.caption_spans.PSObject.Properties[$address] }
                if ($null -ne $captionSpan -and -not [bool]$cell.WrapText) {
                    if (-not [Object]::ReferenceEquals($area, $cell)) { Release-Com $area }
                    $area = $worksheet.Range([string]$captionSpan.Value)
                }
                $areaRows = $area.Rows
                $areaColumns = $area.Columns
                $row = [int]$cell.Row
                $column = [int]$cell.Column
                $lastRow = [int]$area.Row + [int]$areaRows.Count - 1
                $lastColumn = [int]$area.Column + [int]$areaColumns.Count - 1
                if ($row -ne [int]$area.Row -or $column -ne [int]$area.Column -or
                    $row -lt 1 -or $lastRow -gt $endRow -or $column -lt 1 -or $lastColumn -gt $endColumn) {
                    throw ('Content anchor or merged bounds are outside the print area: ' + $address)
                }
                if (($row -lt $repeatStart -and $lastRow -ge $repeatStart) -or
                    ($row -le $repeatEnd -and $lastRow -gt $repeatEnd)) {
                    throw ('A merged content cell crosses the repeated-title boundary: ' + $address)
                }
                foreach ($breakRow in $nativeBreaks.rows) {
                    if ($breakRow -gt $row -and $breakRow -le $lastRow) {
                        throw ('A merged content cell is split across pages: ' + $address)
                    }
                }
                $displayText = [string]$cell.Text
                $value = $cell.Value2
                if ($displayText -match '^#+$' -and $null -ne $value -and $value -is [ValueType]) {
                    throw ('Excel displays numeric overflow hashes in cell ' + $address)
                }
                $orientation = [int]$cell.Orientation
                $left = $horizontalOffset + ([double]$area.Left - $originLeft) * $scale
                $right = $left + [double]$area.Width * $scale
                $height = [double]$area.Height * $scale
                $nativePage = 1
                for ($pageIndex = 1; $pageIndex -lt $pageCount; $pageIndex++) {
                    if ($row -ge [int]$pageStarts[$pageIndex]) { $nativePage = $pageIndex + 1 }
                }
                $targetPages = @($nativePage)
                if ($row -ge $repeatStart -and $row -le $repeatEnd) { $targetPages = @(1..$pageCount) }
                foreach ($pageNumber in $targetPages) {
                    if ($pageNumber -eq 1) {
                        $top = $topMargin + ([double]$area.Top - $originTop) * $scale
                    } elseif ($row -ge $repeatStart -and $row -le $repeatEnd) {
                        $top = $topMargin + ([double]$area.Top - $titleTop) * $scale
                    } else {
                        $startRow = [int]$pageStarts[$pageNumber - 1]
                        $repeatHeight = 0.0
                        if ($pageNumber -gt 1) { $repeatHeight = $titleHeight }
                        $top = $topMargin + ($repeatHeight + [double]$area.Top - $pageTops[$startRow]) * $scale
                    }
                    $bottom = $top + $height
                    # Allow sub-point driver rounding, never an entire clipped row/cell.
                    if ($height -le 0 -or $right -le $left -or $left -lt ($leftMargin - 0.75) -or
                        $top -lt ($topMargin - 0.75) -or $right -gt ($paperWidth - $rightMargin + 0.75) -or
                        $bottom -gt ($paperHeight - $bottomMargin + 0.75)) {
                        throw ('Content cell exceeds the printable page: ' + $address + ', page ' + $pageNumber)
                    }
                    if ($row -ge $tailStart -and $pageNumber -ne $pageCount) {
                        throw ('A final-group cell is not on the final page: ' + $address)
                    }
                    $cellProofs.Add(@{
                        address = $address; page = [int]$pageNumber
                        box = @($left, $top, $right, $bottom)
                        text = $displayText; orientation = $orientation
                    })
                }
            } finally {
                # MergeArea may refer to the same RCW as cell when unmerged.
                Release-Com $areaColumns; Release-Com $areaRows
                if (-not [Object]::ReferenceEquals($area, $cell)) { Release-Com $area }
                Release-Com $cell
            }
        }
        return @{
            name = [string]$geometry.name; zoom = [int]$zoom; base_zoom = [int]$baseZoom
            expected_pages = [int]$pageCount; break_rows = @($nativeBreaks.rows)
            repeat_start_row = $repeatStart; repeat_end_row = $repeatEnd
            tail_start_row = $tailStart; tail_end_row = $tailEnd; cells = @($cellProofs.ToArray())
        }
    } finally { Release-Com $titleRange; Release-Com $printRange }
}

$excel = $books = $book = $sheet = $setup = $sheets = $guard = $null
$owned = $false
$originalPrinter = $null
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
    $originalPrinter = Select-ExportPrinter $excel
    $sheets = $book.Worksheets
    $layoutReports = New-Object 'System.Collections.Generic.List[object]'
    foreach ($item in $plan.sheets) {
        try {
            $sheet = $sheets.Item([string]$item.name)
            $sheet.Visible = -1
            [void]$sheet.Select($true)
            $setup = $sheet.PageSetup
            $layout = Get-NativeLayout $excel $sheet $setup $item
            $output = Join-Path $OutputDirectory ([string]$item.file_name)
            [void]$sheet.ExportAsFixedFormat(0, $output, 0, $false, $false, [Type]::Missing, [Type]::Missing, $false)
            if ($guard.TimedOut) { throw 'PDF export timed out. Retry after closing the workbook.' }
            $layoutReports.Add($layout)
        } catch {
            throw ('Worksheet "' + [string]$item.name + '": ' + $_.Exception.Message)
        } finally {
            Release-Com $setup
            Release-Com $sheet
            $setup = $sheet = $null
        }
    }
    # No workbook Save: all pagination settings belong to the temporary copy.
    @{ status = 'completed'; sheets = @($plan.sheets); layout = @($layoutReports.ToArray()) } |
        ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ReportFile -Encoding UTF8
} finally {
    # Restore while the temporary workbook is still open: Excel may reject
    # ActivePrinter changes when its Workbooks collection is empty.
    try { if ($owned -and $null -ne $book -and $originalPrinter) { $excel.ActivePrinter = $originalPrinter } } catch { }
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
