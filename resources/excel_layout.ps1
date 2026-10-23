# Native content fitting library. Dot-sourcing this file only defines functions.
function Release-InvoiceLayoutCom($value) {
    if ($null -ne $value -and [Runtime.InteropServices.Marshal]::IsComObject($value)) {
        # A disconnected server must not replace the primary operation error.
        try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($value) }
        catch [Runtime.InteropServices.COMException] { }
        catch [Runtime.InteropServices.InvalidComObjectException] { }
    }
}

function Get-InvoiceFormulaSnapshot($book, $plan) {
    $snapshots = New-Object 'System.Collections.Generic.List[object]'
    $worksheets = $application = $functions = $null
    try {
        $worksheets = $book.Worksheets
        $application = $book.Application
        $functions = $application.WorksheetFunction
        foreach ($item in @($plan.sheets)) {
            $sheet = $null
            try {
                $sheet = $worksheets.Item([string]$item.name)
                foreach ($address in @($item.content_cells)) {
                    $cell = $null
                    $context = [string]$item.name + '!' + [string]$address
                    try {
                        $cell = $sheet.Range([string]$address)
                        if (-not [bool]$cell.HasFormula) { continue }
                        if ([bool]$functions.IsError($cell)) { throw ($context + ': formula contains an Excel error.') }
                        $value = $cell.Value2
                        if ($value -is [array]) { throw ($context + ': formula anchor did not return a scalar value.') }
                        $valueType = $null
                        if ($null -ne $value) { $valueType = $value.GetType().FullName }
                        # Store the raw scalar as a record property, never as
                        # pipeline output where PowerShell could enumerate it.
                        [void]$snapshots.Add([pscustomobject]@{
                            Sheet = [string]$item.name
                            Address = [string]$address
                            Value = $value
                            ValueType = $valueType
                        })
                    } finally { Release-InvoiceLayoutCom $cell }
                }
            } finally { Release-InvoiceLayoutCom $sheet }
        }
        return ,$snapshots
    } finally {
        Release-InvoiceLayoutCom $functions
        Release-InvoiceLayoutCom $application
        Release-InvoiceLayoutCom $worksheets
    }
}

function Assert-InvoiceFormulaSnapshot($book, $snapshots, [string]$phase) {
    $worksheets = $application = $functions = $null
    try {
        $worksheets = $book.Worksheets
        $application = $book.Application
        $functions = $application.WorksheetFunction
        foreach ($snapshot in $snapshots) {
            $sheet = $cell = $null
            $context = [string]$snapshot.Sheet + '!' + [string]$snapshot.Address
            try {
                $sheet = $worksheets.Item([string]$snapshot.Sheet)
                $cell = $sheet.Range([string]$snapshot.Address)
                if (-not [bool]$cell.HasFormula) { throw ($context + ': formula anchor changed ' + $phase + '.') }
                if ([bool]$functions.IsError($cell)) { throw ($context + ': formula contains an Excel error ' + $phase + '.') }
                $value = $cell.Value2
                if ($value -is [array]) { throw ($context + ': formula anchor did not return a scalar value ' + $phase + '.') }
                $valueType = $null
                if ($null -ne $value) { $valueType = $value.GetType().FullName }
                if (-not [object]::Equals($snapshot.ValueType, $valueType) -or -not [object]::Equals($snapshot.Value, $value)) {
                    throw ($context + ': calculated formula value changed ' + $phase + '; the staged workbook cannot be published.')
                }
            } finally {
                Release-InvoiceLayoutCom $cell
                Release-InvoiceLayoutCom $sheet
            }
        }
    } finally {
        Release-InvoiceLayoutCom $functions
        Release-InvoiceLayoutCom $application
        Release-InvoiceLayoutCom $worksheets
    }
}

function Fit-InvoiceCaptionWidths($sheet, $columns, $item) {
    foreach ($address in @($item.content_cells)) {
        $cell = $span = $column = $measureColumns = $spanColumns = $lastColumn = $font = $null
        try {
            $cell = $sheet.Range([string]$address)
            $row = [int]$cell.Row
            if ($row -ge [int]$item.header_row -and $row -le [int]$item.footer_row) { continue }
            if ([bool]$cell.MergeCells -or [bool]$cell.HasFormula -or $null -eq $cell.Value2) { continue }
            $spanAddress = [string]$address
            if ($null -ne $item.caption_spans) {
                $property = $item.caption_spans.PSObject.Properties[[string]$address]
                if ($null -ne $property) { $spanAddress = [string]$property.Value }
            }
            $span = $sheet.Range($spanAddress)
            $column = $columns.Item([int]$cell.Column)
            $detailWidth = [double]$column.ColumnWidth
            try {
                # Native AutoFit measures the cell's actual font/number format.
                # Restore the detail width before checking the full text span.
                $measureColumns = $cell.Columns
                [void]$measureColumns.AutoFit()
                $required = [double]$column.Width + 2.0
            } finally {
                $column.ColumnWidth = $detailWidth
                Release-InvoiceLayoutCom $measureColumns
                $measureColumns = $null
            }
            $label = ([string]$cell.Value2).Trim()
            if ($row -eq [int]$item.footer_row + 1 -and [int]$cell.Column -in @(1, 4) -and
                $label -match '^(经办人|验收人|保管人|领用人)[:：]?$') {
                $font = $cell.Font
                $required += 3.0 * [double]$font.Size + 4.0
            }
            $spanColumns = $span.Columns
            $lastColumn = $columns.Item([int]$span.Column + [int]$spanColumns.Count - 1)
            for ($attempt = 0; $attempt -lt 3; $attempt++) {
                $deficit = $required - [double]$span.Width
                if ($deficit -le 0.1) { break }
                $units = [double]$lastColumn.ColumnWidth
                $points = [double]$lastColumn.Width
                if ($points -le 0 -or $units -le 0) { throw ('Invalid caption width: ' + $address) }
                $nextWidth = [Math]::Min(255.0, $units + $deficit * $units / $points + 0.25)
                if ($nextWidth -le $units) { break }
                $lastColumn.ColumnWidth = $nextWidth
            }
            if ([double]$span.Width + 0.1 -lt $required) {
                throw ('Caption cannot fit within the native column-width limit: ' + $address)
            }
        } finally {
            Release-InvoiceLayoutCom $font
            Release-InvoiceLayoutCom $lastColumn
            Release-InvoiceLayoutCom $spanColumns
            Release-InvoiceLayoutCom $measureColumns
            Release-InvoiceLayoutCom $column
            Release-InvoiceLayoutCom $span
            Release-InvoiceLayoutCom $cell
        }
    }
}

function Fit-InvoiceContent($book, $item, $formulaSnapshot = $null) {
    $sheets = $sheet = $rows = $columns = $band = $bandRows = $bandColumns = $null
    $widthBand = $null
    $application = $functions = $null
    $rowMinima = @{}
    $name = [string]$item.name
    try {
        $first = [int]$item.header_row
        $last = [int]$item.footer_row - 1
        $lastColumn = [int]$item.print_end_column
        if ($first -lt 1 -or $last -lt $first -or $lastColumn -lt 1) { throw 'Invalid detail AutoFit bounds.' }
        $sheets = $book.Worksheets
        $sheet = $sheets.Item($name)
        $application = $book.Application
        $functions = $application.WorksheetFunction
        $rows = $sheet.Rows
        $columns = $sheet.Columns
        # Column widths follow current contents; row heights keep their floor.
        for ($index = $first; $index -le $last; $index++) {
            $row = $null
            try {
                $row = $rows.Item($index)
                $rowMinima[$index] = [double]$row.RowHeight
            } finally { Release-InvoiceLayoutCom $row }
        }
        $edge = $null
        try {
            $edge = $columns.Item($lastColumn)
            $letter = ([string]$edge.Address($false, $false)).Split(':')[0]
            $band = $sheet.Range('A' + $first + ':' + $letter + $last)
        } finally { Release-InvoiceLayoutCom $edge }
        if (-not [Object]::Equals($band.MergeCells, $false)) {
            throw 'The detail/header area contains merged cells; use the standard unmerged detail template.'
        }
        $band.WrapText = $false
        $band.ShrinkToFit = $false
        # Totals may use a wider bold/grouped numeric format. Include that
        # row for column width only; its merged label is ignored by AutoFit.
        $widthBand = $sheet.Range('A' + $first + ':' + $letter + [int]$item.footer_row)
        $bandColumns = $widthBand.Columns
        [void]$bandColumns.AutoFit()
        Fit-InvoiceCaptionWidths $sheet $columns $item
        for ($index = 1; $index -le $lastColumn; $index++) {
            $column = $null
            try {
                $column = $columns.Item($index)
                # Excel's hard column limit: use native wrapping only for a
                # column that cannot grow further. Ordinary details stay flat.
                if ([double]$column.ColumnWidth -ge 254.9) {
                    $columnLetter = ([string]$column.Address($false, $false)).Split(':')[0]
                    $wrapped = $null
                    try {
                        $wrapped = $sheet.Range($columnLetter + $first + ':' + $columnLetter + $last)
                        $wrapped.WrapText = $true
                    } finally { Release-InvoiceLayoutCom $wrapped }
                }
            } finally { Release-InvoiceLayoutCom $column }
        }
        $bandRows = $band.Rows
        [void]$bandRows.AutoFit()
        for ($index = $first; $index -le $last; $index++) {
            $row = $null
            try {
                $row = $rows.Item($index)
                $height = [double]$row.RowHeight
                if ($height -ge 408.0) { throw ('Row ' + $index + ' exceeds the safe Excel AutoFit height; shorten the detail text.') }
                if ($height -lt [double]$rowMinima[$index]) { $row.RowHeight = [double]$rowMinima[$index] }
            } finally { Release-InvoiceLayoutCom $row }
        }
        # Lightweight validation remains; no clipboard copies or text probes.
        foreach ($address in @($item.content_cells)) {
            $cell = $null
            try {
                $cell = $sheet.Range([string]$address)
                if ([bool]$functions.IsError($cell)) { throw ([string]$address + ': cell contains an Excel error.') }
                $value = $cell.Value2
                if ($null -ne $value -and $value -is [ValueType] -and $value -isnot [bool] -and [string]$cell.Text -match '^#+$') {
                    throw ([string]$address + ': formatted numeric value is hidden by hashes.')
                }
            } finally { Release-InvoiceLayoutCom $cell }
        }
    } catch {
        throw ($name + ': detail AutoFit failed. ' + $_.Exception.Message)
    } finally {
        Release-InvoiceLayoutCom $bandRows
        Release-InvoiceLayoutCom $bandColumns
        Release-InvoiceLayoutCom $band
        Release-InvoiceLayoutCom $widthBand
        Release-InvoiceLayoutCom $columns
        Release-InvoiceLayoutCom $rows
        Release-InvoiceLayoutCom $sheet
        Release-InvoiceLayoutCom $sheets
        Release-InvoiceLayoutCom $functions
        Release-InvoiceLayoutCom $application
    }
}
