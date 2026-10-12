param([string]$Python = 'python', [switch]$InstallDependencies)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if ($InstallDependencies) {
  & $Python -m pip install -r requirements-build.txt
  if ($LASTEXITCODE -ne 0) { throw 'dependency installation failed' }
}
& $Python -m PyInstaller --noconfirm --clean --windowed --onedir --name InvoiceSummary --add-data 'engine;engine' --add-data 'resources;resources' --collect-all pypdfium2 --copy-metadata pdfplumber --copy-metadata openpyxl --exclude-module matplotlib --exclude-module pandas --exclude-module numpy main.py
if ($LASTEXITCODE -ne 0) { throw 'build failed' }
Copy-Item -LiteralPath '使用说明.txt' -Destination 'dist\InvoiceSummary\使用说明.txt'
Copy-Item -LiteralPath 'THIRD_PARTY_NOTICES.txt' -Destination 'dist\InvoiceSummary\THIRD_PARTY_NOTICES.txt'

