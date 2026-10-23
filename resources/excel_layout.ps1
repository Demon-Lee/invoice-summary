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

function Fit-InvoiceContent($book, $item, $formulaSnapshot = $null) {
    $sheets = $sheet = $rows = $columns = $band = $bandRows = $bandColumns = $null
    $widthBand = $null
    $application = $functions = $null
    $columnMinima = @{}
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
        # Include column headings, not the merged title or the three footer
        # rows. Keep existing minimum widths so fixed footer labels still fit.
        for ($index = 1; $index -le $lastColumn; $index++) {
            $column = $null
            try {
                $column = $columns.Item($index)
                $columnMinima[$index] = [double]$column.ColumnWidth
            } finally { Release-InvoiceLayoutCom $column }
        }
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
        for ($index = 1; $index -le $lastColumn; $index++) {
            $column = $null
            try {
                $column = $columns.Item($index)
                if ([double]$column.ColumnWidth -lt [double]$columnMinima[$index]) {
                    $column.ColumnWidth = [double]$columnMinima[$index]
                }
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
