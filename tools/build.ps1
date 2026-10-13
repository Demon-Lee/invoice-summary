param([string]$Python = 'python', [switch]$InstallDependencies)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if ($InstallDependencies) {
  & $Python -m pip install -r requirements-build.txt
  if ($LASTEXITCODE -ne 0) { throw 'dependency installation failed' }
}
& $Python tools/release_assets.py
if ($LASTEXITCODE -ne 0) { throw 'release assets failed' }
& $Python -m PyInstaller --noconfirm --clean --windowed --onedir --name InvoiceSummary --icon 'resources\app.ico' --add-data 'engine;engine' --add-data 'resources;resources' --collect-all pypdfium2 --copy-metadata pdfplumber --copy-metadata openpyxl --exclude-module matplotlib --exclude-module pandas --exclude-module numpy main.py
if ($LASTEXITCODE -ne 0) { throw 'build failed' }
& $Python tools/prepare_portable.py --directory 'dist\InvoiceSummary' --preserve 'release\InvoiceSummary'
if ($LASTEXITCODE -ne 0) { throw 'portable recognition preparation failed' }
$invoiceGuideName = -join @([char]0x4f7f, [char]0x7528, [char]0x8bf4, [char]0x660e, '.txt')
Copy-Item -LiteralPath $invoiceGuideName -Destination ('dist\InvoiceSummary\' + $invoiceGuideName)
$invoiceBoundaryName = -join @([char]0x529f, [char]0x80fd, [char]0x5f52, [char]0x5c5e, [char]0x4e0e, [char]0x66f4, [char]0x65b0, [char]0x8fb9, [char]0x754c, '.txt')
Copy-Item -LiteralPath $invoiceBoundaryName -Destination ('dist\InvoiceSummary\' + $invoiceBoundaryName)
Copy-Item -LiteralPath 'THIRD_PARTY_NOTICES.txt' -Destination 'dist\InvoiceSummary\THIRD_PARTY_NOTICES.txt'

