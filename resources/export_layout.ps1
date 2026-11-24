# Export-only layout. Regular workbook formatting remains grow-only.
function Get-InvoicePrintWidths($Columns, [double]$AvailableWidth, $Reservations = @()) {
    if ($AvailableWidth -le 0) { throw 'Invalid printable width.' }
    $items = @()
    $used = 0.0
    foreach ($column in $Columns) {
        $width = [double]$column.natural_width
        $maximum = $width
        if ([bool]$column.wrap) {
            if ([double]$column.weight -le 0 -or [double]$column.min_width -le 0) { throw 'Invalid text column weight/minimum.' }
            $width = [double]$column.min_width
            $maximum = [Math]::Max($width, $maximum)
        }
        if ($width -le 0 -or [double]::IsNaN($width) -or [double]::IsInfinity($width)) { throw 'Invalid native column width.' }
        $items += [pscustomobject]@{ index = [int]$column.index; width = $width; maximum = $maximum;
                                    weight = [double]$column.weight; wrap = [bool]$column.wrap }
        $used += $width
    }
    # A signature/date span is a floor across its columns, not a new column.
    # Apply these floors before giving the remaining budget to body text.
    foreach ($reservation in $Reservations) {
        $start = [int]$reservation.start_column
        $end = [int]$reservation.end_column
        $minimum = [double]$reservation.minimum_width
        $span = @($items | Where-Object { $_.index -ge $start -and $_.index -le $end })
        if ($start -lt 1 -or $end -lt $start -or $span.Count -ne ($end - $start + 1) -or
            $minimum -le 0 -or [double]::IsNaN($minimum) -or [double]::IsInfinity($minimum)) {
            throw 'Invalid footer width reservation.'
        }
        $current = [double](($span | Measure-Object -Property width -Sum).Sum)
        $extra = [Math]::Max(0.0, $minimum - $current)
        foreach ($item in $span) {
            $item.width += $extra / $span.Count
            $item.maximum = [Math]::Max($item.maximum, $item.width)
        }
        $used += $extra
    }
    $remaining = [Math]::Max(0.0, $AvailableWidth - $used)
    for ($round = 0; $round -le $items.Count -and $remaining -gt 0.01; $round++) {
        $active = @($items | Where-Object { $_.wrap -and ($_.maximum - $_.width) -gt 0.01 })
        if ($active.Count -eq 0) { break }
        $totalWeight = [double](($active | Measure-Object -Property weight -Sum).Sum)
        $distributed = 0.0
        foreach ($item in $active) {
            $addition = [Math]::Min($item.maximum - $item.width, $remaining * $item.weight / $totalWeight)
            $item.width += $addition
            $distributed += $addition
        }
        if ($distributed -le 0.001) { break }
        $remaining -= $distributed
    }
    foreach ($item in $items) {
        [pscustomobject]@{ index = $item.index; width = [double]$item.width; wrap = $item.wrap }
    }
}

function Set-InvoicePrintColumnWidth($column, [double]$points) {
    # ColumnWidth uses font-relative units while Width is measured in points.
    # A few native measurements handle font/DPI rounding without text probes.
    for ($attempt = 0; $attempt -lt 4; $attempt++) {
        $current = [double]$column.Width
        if ($current -le 0) { throw 'A print column has zero width.' }
        if ([Math]::Abs($current - $points) -le 0.5) { break }
        $units = [double]$column.ColumnWidth * $points / $current
        $column.ColumnWidth = [Math]::Max(0.5, [Math]::Min(255.0, $units))
    }
}

function Get-InvoicePrintRowHeight([double]$AutoHeight, [double]$MinimumHeight) {
    # WPS screen AutoFit can underestimate the PDF printer's line leading.
    # Preserve source minima and reserve space for the printed glyph bounds.
    return [Math]::Max($MinimumHeight, $AutoHeight + 3.0)
}

function Measure-InvoicePrintCaption($sheet, $columns, [string]$address) {
    $cell = $captionColumns = $column = $font = $application = $functions = $null
    try {
        $cell = $sheet.Range($address)
        # A wrapped caption otherwise reports its narrow, already wrapped size.
        $cell.WrapText = $false
        $cell.ShrinkToFit = $false
        if ([Object]::Equals($cell.MergeCells, $false)) {
            $captionColumns = $cell.Columns
            [void]$captionColumns.AutoFit()
            $column = $columns.Item([int]$cell.Column)
            $width = [double]$column.Width
        } else {
            # Native AutoFit cannot measure a merged caption. Use a generous
            # one-line estimate without moving cells or altering their merges.
            $font = $cell.Font
            $display = [string]$cell.Text
            if ($display -match '^#+$' -and $cell.Value2 -is [ValueType] -and $cell.Value2 -isnot [bool]) {
                # Column AutoFit above can temporarily narrow a merged date.
                # Measure its formatted date, never the overflow hash marks.
                $application = $sheet.Application
                $functions = $application.WorksheetFunction
                $display = [string]$functions.Text($cell.Value2, [string]$cell.NumberFormat)
            }
            $units = 0.0
            foreach ($character in $display.ToCharArray()) {
                if ([int]$character -ge 0x2E80) { $units += 1.0 } else { $units += 0.65 }
            }
            $width = $units * [double]$font.Size + 6.0
        }
        return $width / 0.85 + 4.0
    } finally {
        Release-InvoiceLayoutCom $functions; Release-InvoiceLayoutCom $application
        Release-InvoiceLayoutCom $font; Release-InvoiceLayoutCom $column
        Release-InvoiceLayoutCom $captionColumns; Release-InvoiceLayoutCom $cell
    }
}

function Fit-InvoicePrintContent($book, $item, $pageSetup) {
    $sheets = $sheet = $columns = $rows = $band = $widthBand = $bandColumns = $bandRows = $null
    $application = $functions = $null
    try {
        $first = [int]$item.header_row
        $last = [int]$item.footer_row - 1
        $lastColumn = [int]$item.print_end_column
        if ($last -lt $first -or @($item.print_columns).Count -ne $lastColumn) { throw 'Invalid export column plan.' }
        $sheets = $book.Worksheets
        $sheet = $sheets.Item([string]$item.name)
        $columns = $sheet.Columns
        $rows = $sheet.Rows
        $application = $book.Application
        $functions = $application.WorksheetFunction
        $rowMinima = @{}
        for ($index = $first; $index -le $last; $index++) {
            $row = $null
            try { $row = $rows.Item($index); $rowMinima[$index] = [double]$row.RowHeight }
            finally { Release-InvoiceLayoutCom $row }
        }
        $edge = $null
        try { $edge = $columns.Item($lastColumn); $letter = ([string]$edge.Address($false, $false)).Split(':')[0] }
        finally { Release-InvoiceLayoutCom $edge }
        $band = $sheet.Range('A' + $first + ':' + $letter + $last)
        if (-not [Object]::Equals($band.MergeCells, $false)) { throw 'The detail/header area must be unmerged.' }
        $band.WrapText = $false
        $band.ShrinkToFit = $false
        $widthBand = $sheet.Range('A' + $first + ':' + $letter + [int]$item.footer_row)
        $bandColumns = $widthBand.Columns
        [void]$bandColumns.AutoFit()
        $naturalWidths = @{}
        $minimumWidths = @{}
        foreach ($descriptor in @($item.print_columns)) {
            $column = $null
            $index = [int]$descriptor.index
            try {
                $column = $columns.Item($index)
                if (@($item.numeric_columns) -contains $index) {
                    $column.ColumnWidth = [Math]::Min(255.0, [double]$column.ColumnWidth + 2.0)
                }
                $naturalWidths[$index] = [double]$column.Width
                $minimumWidths[$index] = [double]$descriptor.min_width
            } finally { Release-InvoiceLayoutCom $column }
        }
        # Labels with no empty spill area (e.g. a date caption beside its date)
        # need enough space even if their detail column is numeric.
        $captionWidths = @{}
        foreach ($address in @($item.print_minimum_cells)) {
            $cell = $null
            try {
                $cell = $sheet.Range([string]$address)
                $index = [int]$cell.Column
                $captionWidths[[string]$address] = Measure-InvoicePrintCaption $sheet $columns ([string]$address)
                $minimumWidths[$index] = [Math]::Max([double]$minimumWidths[$index], [double]$captionWidths[[string]$address])
            } finally {
                Release-InvoiceLayoutCom $cell
            }
        }
        $reservations = foreach ($span in @($item.print_footer_spans)) {
            $address = [string]$span.anchor
            if (-not $captionWidths.ContainsKey($address)) {
                $captionWidths[$address] = Measure-InvoicePrintCaption $sheet $columns $address
            }
            [pscustomobject]@{ start_column = [int]$span.start_column; end_column = [int]$span.end_column;
                minimum_width = [double]$captionWidths[$address] + [double]$span.blank_width }
        }
        $measured = foreach ($descriptor in @($item.print_columns)) {
            $index = [int]$descriptor.index
            [pscustomobject]@{ index = $index; wrap = [bool]$descriptor.wrap;
                natural_width = [Math]::Max([double]$naturalWidths[$index], [double]$minimumWidths[$index]);
                min_width = [double]$minimumWidths[$index]; weight = [double]$descriptor.weight }
        }
        # A modest 90-percent print scale gives dense tables useful text space
        # while keeping ordinary 11pt body text near 10pt on paper.
        $available = (297.0 * 72.0 / 25.4 - [double]$pageSetup.LeftMargin - [double]$pageSetup.RightMargin - 8.0) / 0.9
        $widths = @(Get-InvoicePrintWidths -Columns @($measured) -AvailableWidth $available -Reservations @($reservations))
        foreach ($width in $widths) {
            $column = $wrapped = $null
            try {
                $column = $columns.Item([int]$width.index)
                Set-InvoicePrintColumnWidth $column ([double]$width.width)
                if ($width.wrap) {
                    $columnLetter = ([string]$column.Address($false, $false)).Split(':')[0]
                    $wrapped = $sheet.Range($columnLetter + $first + ':' + $columnLetter + $last)
                    $wrapped.WrapText = $true
                }
                $width | Add-Member -NotePropertyName actual_width -NotePropertyValue ([double]$column.Width)
            } finally { Release-InvoiceLayoutCom $wrapped; Release-InvoiceLayoutCom $column }
        }
        # The PDF printer can wrap CJK text one line earlier than WPS's screen
        # metrics. Measure row heights with narrower text columns, then restore
        # the actual print widths before applying the captured heights.
        foreach ($width in $widths) {
            if (-not $width.wrap) { continue }
            $column = $null
            try {
                $column = $columns.Item([int]$width.index)
                Set-InvoicePrintColumnWidth $column ([double]$width.actual_width * 0.85)
            } finally { Release-InvoiceLayoutCom $column }
        }
        $bandRows = $band.Rows
        [void]$bandRows.AutoFit()
        $autoHeights = @{}
        for ($index = $first; $index -le $last; $index++) {
            $row = $null
            try { $row = $rows.Item($index); $autoHeights[$index] = [double]$row.RowHeight }
            finally { Release-InvoiceLayoutCom $row }
        }
        foreach ($width in $widths) {
            if (-not $width.wrap) { continue }
            $column = $null
            try {
                $column = $columns.Item([int]$width.index)
                Set-InvoicePrintColumnWidth $column ([double]$width.width)
                $width.actual_width = [double]$column.Width
            } finally { Release-InvoiceLayoutCom $column }
        }
        $fittedRows = New-Object 'System.Collections.Generic.List[object]'
        for ($index = $first; $index -le $last; $index++) {
            $row = $null
            try {
                $row = $rows.Item($index)
                $autoHeight = [double]$autoHeights[$index]
                $height = Get-InvoicePrintRowHeight $autoHeight ([double]$rowMinima[$index])
                if ($height -ge 408.0) { throw ('Row ' + $index + ': wrapped text exceeds the safe row-height limit.') }
                if ([double]$row.RowHeight -lt $height) { $row.RowHeight = $height }
                [void]$fittedRows.Add(@{ row = $index; auto_height = $autoHeight;
                    minimum_height = [double]$rowMinima[$index]; actual_height = [double]$row.RowHeight })
            } finally { Release-InvoiceLayoutCom $row }
        }
        foreach ($address in @($item.content_cells)) {
            $cell = $null
            try {
                $cell = $sheet.Range([string]$address)
                if ([bool]$functions.IsError($cell)) { throw ([string]$address + ': cell contains an Excel error.') }
                $value = $cell.Value2
                if ($null -ne $value -and $value -is [ValueType] -and $value -isnot [bool] -and [string]$cell.Text -match '^#+$') {
                    throw ([string]$address + ': formatted print value is hidden by hashes.')
                }
            } finally { Release-InvoiceLayoutCom $cell }
        }
        return @{ available_width = $available; columns = $widths; rows = @($fittedRows.ToArray()) }
    } catch {
        throw ([string]$item.name + ': print wrapping failed. ' + $_.Exception.Message)
    } finally {
        Release-InvoiceLayoutCom $bandRows; Release-InvoiceLayoutCom $bandColumns
        Release-InvoiceLayoutCom $widthBand; Release-InvoiceLayoutCom $band
        Release-InvoiceLayoutCom $functions; Release-InvoiceLayoutCom $application
        Release-InvoiceLayoutCom $columns; Release-InvoiceLayoutCom $rows
        Release-InvoiceLayoutCom $sheet; Release-InvoiceLayoutCom $sheets
    }
}
