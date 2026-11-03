#requires -Version 7.2
[CmdletBinding()]
param([string] $Study, [string] $Grant)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = 'C:\Users\arvik\code\research\Buddha2'
$script = Join-Path $root 'rank-format.ps1'
$pwsh = (Get-Process -Id $PID).Path
function Assert-That([bool] $Value, [string] $Message) { if (-not $Value) { throw $Message } }
function Invoke-Launch([string[]] $Arguments) {
    $start = [Diagnostics.ProcessStartInfo]::new($pwsh)
    $start.UseShellExecute = $false; $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true; $start.RedirectStandardError = $true; $start.RedirectStandardInput = $true
    foreach ($arg in @('-NoProfile', '-File', $script) + $Arguments) { [void]$start.ArgumentList.Add($arg) }
    $process = [Diagnostics.Process]::Start($start)
    try {
        $process.StandardInput.Close()
        $stdout = $process.StandardOutput.ReadToEndAsync(); $stderr = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        return [pscustomobject]@{ ExitCode=$process.ExitCode; Stdout=$stdout.GetAwaiter().GetResult(); Stderr=$stderr.GetAwaiter().GetResult() }
    }
    finally { $process.Dispose() }
}
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($script, [ref]$tokens, [ref]$errors)
Assert-That ($errors.Count -eq 0) 'PowerShell launcher syntax failed'
$loader = @($ast.EndBlock.Statements | Where-Object { $_ -is [Management.Automation.Language.FunctionDefinitionAst] -and $_.Name -eq 'Get-FrozenHelperBlock' })
Assert-That ($loader.Count -eq 1) 'Missing exact-source helper loader'
. ([ScriptBlock]::Create($loader[0].Extent.Text))
$block = Get-FrozenHelperBlock (Join-Path $root 'phase2-release.ps1')
Assert-That ($block.Ast.EndBlock.Statements.Count -eq 13) 'Unexpected imported top-level inventory'
Assert-That (@($block.Ast.EndBlock.Statements | Where-Object { $_ -isnot [Management.Automation.Language.FunctionDefinitionAst] }).Count -eq 0) 'Frozen main body was imported'
# Definitions alone may be evaluated; the retained main body never runs.
. $block
$ownedInspections = @{}
$rejected = $false
try { Stop-OwnedContainer ('0' * 64) 'unused' } catch { $rejected = $true }
Assert-That $rejected 'Cleanup accepted an unowned handle'
$temporary = Join-Path $root ('runs\rank-launch-helper-test-' + [Guid]::NewGuid().ToString('N') + '.ps1')
try {
    [IO.File]::WriteAllText($temporary, ([IO.File]::ReadAllText((Join-Path $root 'phase2-release.ps1')) + "`nthrow 'must never run'"), [Text.UTF8Encoding]::new($false))
    $rejected = $false
    try { [void](Get-FrozenHelperBlock $temporary) } catch { $rejected = $true }
    Assert-That $rejected 'Changed helper source was accepted'
}
finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary } }
foreach ($arguments in @(
    @('provider', '-Study', 'unused.json', '-Grant', 'unused.json'),
    @('mock', '-Live', '-Study', 'unused.json', '-Grant', 'unused.json'),
    @('config', '-Live', '-Study', 'unused.json', '-Grant', 'unused.json'),
    @('mock', '-Study', '../escape.json', '-Grant', 'unused.json'),
    @('mock', '-Study', 'missing.json', '-Grant', 'missing.json')
)) {
    $result = Invoke-Launch $arguments
    Assert-That ($result.ExitCode -ne 0 -and -not $result.Stdout.Contains('API key')) 'Unsafe input reached credential entry'
}
if (-not $Study -and -not $Grant) { Write-Host 'Launcher parser, frozen helper hash/main-body exclusion, ownership and argument checks PASS'; exit 0 }
Assert-That (-not [string]::IsNullOrWhiteSpace($Study) -and -not [string]::IsNullOrWhiteSpace($Grant)) 'Supply both fixture paths'
$records = Join-Path $root 'runs\phase2b-rank-format-v1\launcher'
$before = @(Get-ChildItem -LiteralPath $records -Filter '*.json' -ErrorAction SilentlyContinue | ForEach-Object FullName)
foreach ($mode in @('preflight', 'mock', 'mock', 'config')) {
    $result = Invoke-Launch @($mode, '-Study', $Study, '-Grant', $Grant)
    Assert-That ($result.ExitCode -eq 0) ("Contained $mode failed: " + $result.Stderr)
    Assert-That (-not $result.Stdout.Contains('fixture-not-a-secret')) 'Dummy key appeared in output'
}
$new = @(Get-ChildItem -LiteralPath $records -Filter '*.json' | Where-Object FullName -notin $before)
$inspections = @($new | Where-Object Name -like '*.inspection.json' | ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw -Encoding utf8 | ConvertFrom-Json })
Assert-That ($inspections.Count -eq 3) 'Missing actual mock/resume/config inspections'
Assert-That (@($inspections | Where-Object { $_.preflight.configuration_only -and $_.container.network_mode -eq 'bridge' -and $_.container.state_at_inspection -eq 'created' }).Count -eq 1) 'Configuration was not create-only'
$executions = @($new | Where-Object Name -like '*.result.json')
Assert-That ($executions.Count -eq 2) 'Configuration unexpectedly executed'
$calls = @($executions | ForEach-Object {
    $lines = (Get-Content -LiteralPath ($_.FullName.Replace('.result.json', '.stdout.log')) -Encoding utf8)
    ($lines[-1] | ConvertFrom-Json).new_mock_http_calls
})
Assert-That (0 -in $calls -and ($calls | Measure-Object -Sum).Sum -gt 0) 'Unchanged resume dispatched or initial mock did not run'
$result = Invoke-Launch @('provider', '-Live', '-Study', $Study, '-Grant', $Grant)
Assert-That ($result.ExitCode -ne 0 -and $result.Stderr.Contains('source scope and authority preflight')) 'Fixture authority reached provider credential entry'
Write-Host 'Actual launcher image/mounts, fake-stdin mock/resume, create-only configuration and fixture-before-key rejection PASS'
