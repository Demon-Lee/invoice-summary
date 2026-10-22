# Native content fitting library. Dot-sourcing this file only defines functions.
function Release-InvoiceLayoutCom($value) {
    if ($null -ne $value -and [Runtime.InteropServices.Marshal]::IsComObject($value)) {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($value)
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

function Set-InvoiceColumnPoints($column, [double]$points, [string]$context) {
    # ColumnWidth uses font character units; Width uses points. Search the
    # actual Excel geometry, always rounding toward a wider measurement cell.
    if ($points -le 0) { throw ($context + ': invalid column width.') }
    $column.ColumnWidth = 255
    if ([double]$column.Width + 0.05 -lt $points) {
        throw ($context + ': required column width exceeds the Excel limit.')
    }
    $low = 0.0
    $high = 255.0
    for ($step = 0; $step -lt 18; $step++) {
        $middle = ($low + $high) / 2.0
        $column.ColumnWidth = $middle
        if ([double]$column.Width -lt $points) { $low = $middle } else { $high = $middle }
    }
    $column.ColumnWidth = $high
    if ([double]$column.Width + 0.05 -lt $points) {
        throw ($context + ': Excel could not apply the required column width.')
    }
}

function Copy-InvoiceProbe($source, $probe) {
    $used = $target = $copied = $null
    try {
        $used = $probe.UsedRange
        [void]$used.UnMerge()
        [void]$used.Clear()
        $target = $probe.Range('A1')
        # Copying the source range, then unmerging ONLY the probe, retains rich
        # text runs, number formats, indentation, and orientation for AutoFit.
        [void]$source.Copy($target)
        $copied = $probe.UsedRange
        [void]$copied.UnMerge()
        return ,$target
    } catch {
        Release-InvoiceLayoutCom $target
        throw
    } finally {
        Release-InvoiceLayoutCom $used
        Release-InvoiceLayoutCom $copied
    }
}

function Set-InvoiceProbeValue($target, $value, [string]$context) {
    # Formula results can themselves begin with '='. Write strings as literal
    # text, then restore the copied display format before measuring them.
    $format = $target.NumberFormat
    try {
        if ($value -is [string]) { $target.NumberFormat = '@' }
        $target.Value2 = $value
    } finally {
        if ($value -is [string]) { $target.NumberFormat = $format }
    }
    if ([bool]$target.HasFormula) { throw ($context + ': probe value was interpreted as a formula.') }
    $actual = $target.Value2
    # Excel may store a zero-length string as a genuinely empty cell.
    $empty = $value -is [string] -and $value.Length -eq 0 -and
        ($null -eq $actual -or [Object]::Equals($actual, ''))
    if (-not $empty -and -not [Object]::Equals($value, $actual)) {
        throw ($context + ': probe did not retain the calculated scalar value.')
    }
}

function Measure-InvoiceCell($cell, $area, $probe, [double]$width, [bool]$measureWidth, [string]$context, [bool]$useCapturedValue = $false, $capturedValue = $null) {
    $target = $probeColumn = $probeRow = $null
    try {
        $target = Copy-InvoiceProbe $area $probe
        # A copied formula can acquire relative references on the probe. Its
        # current value is enough to measure the unchanged source display.
        if ($useCapturedValue) {
            Set-InvoiceProbeValue $target $capturedValue $context
        } elseif ([bool]$cell.HasFormula) {
            Set-InvoiceProbeValue $target $cell.Value2 $context
        }
        $target.ShrinkToFit = $false
        $probeColumn = $target.EntireColumn
        $probeRow = $target.EntireRow
        if ($measureWidth) {
            $target.WrapText = $false
            [void]$probeColumn.AutoFit()
            return [double]$probeColumn.Width
        }
        # A slightly narrower probe and extra row padding cover Excel pixel
        # rounding without changing any source font or rich text run.
        Set-InvoiceColumnPoints $probeColumn ([Math]::Max(1.0, $width - 1.0)) $context
        $target.WrapText = $true
        $probeRow.RowHeight = 15
        [void]$probeRow.AutoFit()
        $height = [double]$probeRow.RowHeight
        if ($height -ge 409.0) {
            throw ($context + ': required text height reaches the Excel 409 pt limit.')
        }
        return ($height + 2.0)
    } catch {
        throw ($context + ': native measurement failed. ' + $_.Exception.Message)
    } finally {
        Release-InvoiceLayoutCom $probeRow
        Release-InvoiceLayoutCom $probeColumn
        Release-InvoiceLayoutCom $target
    }
}

function Fit-InvoiceContent($book, $item, $formulaSnapshot = $null) {
    $sheet = $worksheets = $probe = $scope = $scopeRows = $scopeColumns = $null
    $application = $worksheetFunctions = $sheetRows = $sheetColumns = $null
    $probeBooks = $probeBook = $probeSheets = $null
    $rowMinima = @{}
    $columnMinima = @{}
    $numericColumns = @{}
    $formulaValues = @{}
    $sheetName = [string]$item.name
    foreach ($snapshot in $formulaSnapshot) {
        if ([string]$snapshot.Sheet -eq $sheetName) { $formulaValues[[string]$snapshot.Address] = $snapshot }
    }
    try {
        if ([string]::IsNullOrWhiteSpace($sheetName)) { throw 'Layout sheet name is missing.' }
        if ([int]$item.print_end_row -lt 1 -or [int]$item.print_end_column -lt 1) {
            throw ($sheetName + ': invalid print bounds.')
        }
        $worksheets = $book.Worksheets
        $sheet = $worksheets.Item($sheetName)
        $application = $book.Application
        $worksheetFunctions = $application.WorksheetFunction
        $sheetRows = $sheet.Rows
        $sheetColumns = $sheet.Columns
        $scope = $sheet.Range([string]$item.print_area)
        $scopeRows = $scope.EntireRow
        $scopeColumns = $scope.EntireColumn
        $scopeRows.Hidden = $false
        $scopeColumns.Hidden = $false
        foreach ($index in @($item.numeric_columns)) { $numericColumns[[int]$index] = $true }
        for ($index = 1; $index -le [int]$item.print_end_row; $index++) {
            $row = $null
            try {
                $row = $sheetRows.Item($index)
                $rowMinima[$index] = [double]$row.RowHeight
            } finally { Release-InvoiceLayoutCom $row }
        }
        foreach ($index in $numericColumns.Keys) {
            $column = $null
            try {
                $column = $sheetColumns.Item([int]$index)
                $columnMinima[$index] = [double]$column.Width
            } finally { Release-InvoiceLayoutCom $column }
        }
        # Keep the source worksheet collection unchanged. Adding a source
        # probe would change SHEETS() while fitting its calculated display.
        # A scratch workbook also leaves Application.Calculation untouched.
        $probeBooks = $application.Workbooks
        $probeBook = $probeBooks.Add(-4167)
        $probeBook.Date1904 = [bool]$book.Date1904
        $probeSheets = $probeBook.Worksheets
        $probe = $probeSheets.Item(1)
        [void]$sheet.Activate()

        # Measure individual numeric cells, never entire template columns:
        # merged titles and footer labels must not inflate numeric widths.
        foreach ($address in @($item.content_cells)) {
            $cell = $area = $columns = $column = $null
            $context = $sheetName + '!' + [string]$address
            try {
                $cell = $sheet.Range([string]$address)
                $area = $cell.MergeArea
                $area.WrapText = $true
                $area.ShrinkToFit = $false
                if ([bool]$worksheetFunctions.IsError($cell)) { throw ($context + ': cell contains an Excel error.') }
                $value = $cell.Value2
                $useCapturedValue = $formulaValues.ContainsKey([string]$address)
                if ($useCapturedValue) {
                    $value = $formulaValues[[string]$address].Value
                } elseif ($null -ne $formulaSnapshot -and [bool]$cell.HasFormula) {
                    throw ($context + ': formula is missing from the calculated value snapshot.')
                }
                $isNumber = $null -ne $value -and $value -isnot [string] -and $value -isnot [bool]
                if (-not $isNumber) { continue }
                $columns = $area.Columns
                $firstColumn = [int]$area.Column
                $lastColumn = $firstColumn + [int]$columns.Count - 1
                $expandIndex = 0
                for ($index = $firstColumn; $index -le $lastColumn; $index++) {
                    if ($numericColumns.ContainsKey($index)) { $expandIndex = $index }
                }
                if ($expandIndex -eq 0) { continue }
                $required = (Measure-InvoiceCell $cell $area $probe 0.0 $true $context $useCapturedValue $value) + 2.0
                $missing = $required - [double]$area.Width
                if ($missing -gt 0.05) {
                    $column = $sheetColumns.Item($expandIndex)
                    Set-InvoiceColumnPoints $column ([double]$column.Width + $missing) $context
                }
            } finally {
                Release-InvoiceLayoutCom $column
                Release-InvoiceLayoutCom $columns
                Release-InvoiceLayoutCom $area
                Release-InvoiceLayoutCom $cell
            }
        }

        # Native AutoFit handles unmerged cells. Restore every original row
        # minimum, including retained blank rows and side content rows.
        [void]$scopeRows.AutoFit()
        for ($index = 1; $index -le [int]$item.print_end_row; $index++) {
            $row = $null
            try {
                $row = $sheetRows.Item($index)
                $height = [double]$row.RowHeight
                $row.RowHeight = [Math]::Max($height, [double]$rowMinima[$index])
            } finally { Release-InvoiceLayoutCom $row }
        }

        # Check every anchor, including ordinary cells, through the same native
        # probe so long unmerged text and merged text share the height proof.
        foreach ($address in @($item.content_cells)) {
            $cell = $area = $areaRows = $row = $null
            $context = $sheetName + '!' + [string]$address
            try {
                $cell = $sheet.Range([string]$address)
                $area = $cell.MergeArea
                $useCapturedValue = $formulaValues.ContainsKey([string]$address)
                $value = $cell.Value2
                if ($useCapturedValue) {
                    $value = $formulaValues[[string]$address].Value
                } elseif ($null -ne $formulaSnapshot -and [bool]$cell.HasFormula) {
                    throw ($context + ': formula is missing from the calculated value snapshot.')
                }
                $required = Measure-InvoiceCell $cell $area $probe ([double]$area.Width) $false $context $useCapturedValue $value
                $areaRows = $area.Rows
                $firstRow = [int]$area.Row
                $count = [int]$areaRows.Count
                $missing = $required - [double]$area.Height
                # A vertical merge can share its required height across rows.
                # Grow only as necessary; never shrink a previously fitted row.
                for ($offset = $count - 1; $offset -ge 0 -and $missing -gt 0.05; $offset--) {
                    $row = $sheetRows.Item($firstRow + $offset)
                    $height = [double]$row.RowHeight
                    $added = [Math]::Min($missing, 409.0 - $height)
                    if ($added -gt 0) { $row.RowHeight = [Math]::Min(409.0, $height + $added) }
                    $missing = $required - [double]$area.Height
                    Release-InvoiceLayoutCom $row
                    $row = $null
                }
                if ($missing -gt 0.05) { throw ($context + ': content cannot fit within the Excel 409 pt row limit.') }
                if ([bool]$worksheetFunctions.IsError($cell)) { throw ($context + ': cell contains an Excel error.') }
                $value = $cell.Value2
                if ($null -ne $value -and $value -isnot [string] -and $value -isnot [bool] -and [string]$cell.Text -match '^#+$') {
                    throw ($context + ': formatted numeric value is hidden by hashes.')
                }
            } finally {
                Release-InvoiceLayoutCom $row
                Release-InvoiceLayoutCom $areaRows
                Release-InvoiceLayoutCom $area
                Release-InvoiceLayoutCom $cell
            }
        }
        foreach ($index in $numericColumns.Keys) {
            $column = $null
            try {
                $column = $sheetColumns.Item([int]$index)
                if ([double]$column.Width + 0.05 -lt [double]$columnMinima[$index]) {
                    throw ($sheetName + ': numeric column became narrower than the template.')
                }
            } finally { Release-InvoiceLayoutCom $column }
        }
    } catch {
        throw ($sheetName + ': content fitting failed. ' + $_.Exception.Message)
    } finally {
        # The scratch workbook is discarded on success and failure. There is
        # never a probe sheet to add/delete in the source workbook.
        try {
            if ($null -ne $probeBook) { [void]$probeBook.Close($false) }
        } finally {
            try { if ($null -ne $application) { $application.CutCopyMode = $false } } catch { }
            Release-InvoiceLayoutCom $probe
            Release-InvoiceLayoutCom $probeSheets
            Release-InvoiceLayoutCom $probeBook
            Release-InvoiceLayoutCom $probeBooks
            Release-InvoiceLayoutCom $scopeRows
            Release-InvoiceLayoutCom $scopeColumns
            Release-InvoiceLayoutCom $scope
            Release-InvoiceLayoutCom $sheetRows
            Release-InvoiceLayoutCom $sheetColumns
            Release-InvoiceLayoutCom $worksheetFunctions
            Release-InvoiceLayoutCom $application
            Release-InvoiceLayoutCom $sheet
            Release-InvoiceLayoutCom $worksheets
        }
    }
}
