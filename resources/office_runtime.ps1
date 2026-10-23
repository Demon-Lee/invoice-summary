# Software-owned activation and lifecycle; shared invoice scripts stay unchanged.
if (-not ('InvoiceOfficeWatchdog' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
public sealed class InvoiceOfficeWatchdog : IDisposable {
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint id);
    private readonly int id;
    private readonly long ticks;
    private readonly string name;
    private readonly Timer timer;
    private int timedOut;
    public bool TimedOut { get { return Interlocked.CompareExchange(ref timedOut, 0, 0) != 0; } }
    public InvoiceOfficeWatchdog(int processId, long startTicks, string processName) {
        id = processId; ticks = startTicks; name = processName;
        timer = new Timer(OnTimeout, null, 210000, Timeout.Infinite);
    }
    private void OnTimeout(object state) {
        Interlocked.Exchange(ref timedOut, 1);
        try {
            using (Process process = Process.GetProcessById(id)) {
                if (String.Equals(process.ProcessName, name, StringComparison.OrdinalIgnoreCase)
                    && process.StartTime.ToUniversalTime().Ticks == ticks) {
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
}

function Release-InvoiceOfficeCom($Value) {
    try {
        if (-not [Object]::ReferenceEquals($null, $Value)) {
            if ([Runtime.InteropServices.Marshal]::IsComObject($Value)) {
                [void][Runtime.InteropServices.Marshal]::ReleaseComObject($Value)
            }
        }
    } catch { }
}

function New-InvoiceOfficeComObject([string]$ProgId) {
    return ,(New-Object -ComObject $ProgId)
}

function New-InvoiceOfficeContext {
    param([ValidateSet('Auto', 'Excel', 'WPS')][string]$Backend = 'Auto')
    $candidates = if ($Backend -eq 'WPS') { @('KET.Application') }
                  elseif ($Backend -eq 'Excel') { @('Excel.Application') }
                  else { @('KET.Application', 'Excel.Application') }
    $failures = New-Object 'System.Collections.Generic.List[string]'
    foreach ($progId in $candidates) {
        $before = @(Get-Process -Name EXCEL,wps,et -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
        $helperStart = [Diagnostics.Process]::GetCurrentProcess().StartTime.ToUniversalTime()
        $application = $books = $process = $null
        $owned = $false
        try {
            $application = New-InvoiceOfficeComObject $progId
            $processId = [uint32]0
            [void][InvoiceOfficeWatchdog]::GetWindowThreadProcessId([IntPtr][long]$application.Hwnd, [ref]$processId)
            if ($processId -eq 0) { throw 'The application has no identifiable native window.' }
            $process = Get-Process -Id $processId -ErrorAction Stop
            $actual = if ($process.ProcessName -ieq 'EXCEL') { 'Excel' }
                      elseif ($process.ProcessName -in @('et', 'wps')) { 'WPS' }
                      else { throw 'The activated process is not a supported spreadsheet application.' }
            $books = $application.Workbooks
            if ($processId -in $before -or $process.StartTime.ToUniversalTime() -lt $helperStart -or [int]$books.Count -ne 0) {
                throw 'Cannot confirm a new empty private spreadsheet instance; existing documents were not changed.'
            }
            $owned = $true
            if ($Backend -ne 'Auto' -and $actual -ne $Backend) { throw 'The registered component started a different spreadsheet application.' }
            return [pscustomobject]@{
                Application=$application; Backend=$actual; ProgId=$progId
                ProcessId=[int]$processId; ProcessName=[string]$process.ProcessName
                StartTicks=[long]$process.StartTime.ToUniversalTime().Ticks
            }
        } catch {
            [void]$failures.Add($progId + ': ' + $_.Exception.Message)
            if ($null -ne $application) {
                if ($owned) { try { $application.Quit() } catch { } }
                Release-InvoiceOfficeCom $application
            }
        } finally {
            Release-InvoiceOfficeCom $books
            if ($null -ne $process) { $process.Dispose() }
        }
    }
    $label = if ($Backend -eq 'Auto') { 'WPS 或 Excel' } else { $Backend }
    throw ($label + ' 自动化组件不可用，或无法创建独立实例；请确认已安装桌面版并关闭目标文件。' + "`n" + ($failures -join "`n"))
}

function Close-InvoiceOfficeContext($Context) {
    if ($null -eq $Context) { return }
    try { $Context.Application.Quit() } catch { }
    Release-InvoiceOfficeCom $Context.Application
}

function Get-InvoiceAdaptedFontScript {
    param([Parameter(Mandatory=$true)][string]$Path)
    $source = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $Path).Path)
    $tokens = $parseErrors = $null
    $ast = [Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$parseErrors)
    if (@($parseErrors).Count) { throw '识别规则字体脚本无法解析，请联系维护者。' }
    $factories = @($ast.FindAll({ param($node)
        if ($node -isnot [Management.Automation.Language.CommandAst] -or $node.GetCommandName() -ine 'New-Object') { return $false }
        return @($node.CommandElements | Where-Object {
            $_ -is [Management.Automation.Language.CommandParameterAst] -and
            'ComObject'.StartsWith($_.ParameterName, [StringComparison]::OrdinalIgnoreCase)
        }).Count -gt 0
    }, $true))
    if ($factories.Count -ne 1) { throw '识别规则字体脚本的自动化创建入口不受支持，请联系维护者。' }
    $parts = $factories[0].CommandElements
    if ($parts.Count -ne 3 -or $parts[1] -isnot [Management.Automation.Language.CommandParameterAst] -or
        $parts[1].ParameterName -ine 'ComObject' -or $null -ne $parts[1].Argument -or
        $parts[2] -isnot [Management.Automation.Language.StringConstantExpressionAst] -or $parts[2].Value -ine 'Excel.Application') {
        throw '识别规则字体脚本的自动化创建入口不受支持，请联系维护者。'
    }
    $extent = $factories[0].Extent
    return $source.Substring(0, $extent.StartOffset) + 'Get-InvoiceFontApplication' + $source.Substring($extent.EndOffset)
}

function Invoke-InvoiceSharedFonts {
    param([string]$EngineScript, [string]$WorkbookInput,
          [ValidateSet('Auto', 'Excel', 'WPS')][string]$OfficeBackend = 'Auto')
    $adapted = Get-InvoiceAdaptedFontScript -Path $EngineScript
    $context = New-InvoiceOfficeContext -Backend $OfficeBackend
    $guard = [InvoiceOfficeWatchdog]::new($context.ProcessId, $context.StartTicks, $context.ProcessName)
    function Get-InvoiceFontApplication { return ,$context.Application }
    try {
        & ([scriptblock]::Create($adapted)) -WorkbookInput $WorkbookInput | Out-Null
        if ($guard.TimedOut) { throw '表格软件字体排版超时，请关闭目标文件后重试。' }
    } catch {
        if ($guard.TimedOut) { throw '表格软件字体排版超时，请关闭目标文件后重试。' }
        throw
    } finally {
        $guard.Dispose()
        Close-InvoiceOfficeContext $context
    }
    return $context.Backend
}
