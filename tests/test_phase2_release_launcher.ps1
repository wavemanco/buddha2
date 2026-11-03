#requires -Version 7.2
[CmdletBinding()]
param([string] $Study, [string] $Grant)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
if ($root -ne 'C:\Users\arvik\code\research\Buddha2') { throw 'Tests require the fixed new project root' }
$launcher = Join-Path $root 'phase2-release.ps1'
$pwsh = (Get-Process -Id $PID).Path
$recordsRoot = Join-Path $root 'runs\phase2-release-r018\launcher'

function Assert-That([bool] $Condition, [string] $Message) { if (-not $Condition) { throw $Message } }
function Invoke-Launcher([string] $Script, [string[]] $Arguments) {
    $start = [Diagnostics.ProcessStartInfo]::new($pwsh)
    $start.UseShellExecute = $false; $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true; $start.RedirectStandardError = $true; $start.RedirectStandardInput = $true
    foreach ($argument in @('-NoProfile', '-File', $Script) + $Arguments) { [void]$start.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::Start($start)
    try {
        $process.StandardInput.Close() # Never supply a real secret, even if a guard regresses.
        $stdout = $process.StandardOutput.ReadToEndAsync(); $stderr = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        return [pscustomobject]@{ ExitCode = $process.ExitCode; Stdout = $stdout.GetAwaiter().GetResult(); Stderr = $stderr.GetAwaiter().GetResult() }
    }
    finally { $process.Dispose() }
}

$tokens = $null; $errors = $null
[void][Management.Automation.Language.Parser]::ParseFile($launcher, [ref]$tokens, [ref]$errors)
Assert-That ($errors.Count -eq 0) 'Launcher syntax does not parse'
$before = @(Get-ChildItem -LiteralPath $recordsRoot -Filter '*.json' -ErrorAction SilentlyContinue).Count
foreach ($arguments in @(
    @('provider', '-Study', 'unused.json', '-Grant', 'unused.json'),
    @('mock', '-Live', '-Study', 'unused.json', '-Grant', 'unused.json'),
    @('provider-config', '-Live', '-Study', 'unused.json', '-Grant', 'unused.json'),
    @('provider', '-Live', '-Study', '../escape.json', '-Grant', 'unused.json'),
    @('mock', '-Study', 'a/../../escape.json', '-Grant', 'unused.json'),
    @('mock', '-Study', 'a\..\..\escape.json', '-Grant', 'unused.json'),
    @('mock', '-Study', 'missing.json', '-Grant', 'missing.json')
)) {
    $result = Invoke-Launcher $launcher $arguments
    Assert-That ($result.ExitCode -ne 0) 'Unsafe or absent launch inputs were accepted'
    Assert-That (-not $result.Stdout.Contains('API key')) 'A rejected invocation attempted key entry'
}
$after = @(Get-ChildItem -LiteralPath $recordsRoot -Filter '*.json' -ErrorAction SilentlyContinue).Count
Assert-That ($before -eq $after) 'Rejected arguments created a container record'

$copyRoot = Join-Path $root ('runs\phase2-release-r018\launcher-copy-' + [Guid]::NewGuid().ToString('N'))
$copy = Join-Path $copyRoot 'phase2-release.ps1'
try {
    [void][IO.Directory]::CreateDirectory($copyRoot)
    [IO.File]::Copy($launcher, $copy)
    $result = Invoke-Launcher $copy @('preflight', '-Study', 'unused.json', '-Grant', 'unused.json')
    Assert-That ($result.ExitCode -ne 0) 'A launcher copied outside the approved root was accepted'
}
finally {
    if (Test-Path -LiteralPath $copy) { Remove-Item -LiteralPath $copy }
    if (Test-Path -LiteralPath $copyRoot) { Remove-Item -LiteralPath $copyRoot }
}

# Exercise the exact bounded-cleanup helper against a real, inspected,
# network-disabled container. Extract trusted function definitions only; the
# provider launcher body and masked-key reader are never executed here.
$ast = [Management.Automation.Language.Parser]::ParseFile($launcher, [ref]$tokens, [ref]$errors)
foreach ($definition in $ast.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] }, $false)) {
    Invoke-Expression $definition.Extent.Text
}
$projectRoot = $root
$runsRoot = Join-Path $root 'runs'
$expectedImage = 'sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366'
$image = Docker-Json @('image', 'inspect', $expectedImage)
$ownedInspections = @{}
$Action = 'mock'; $Stage = 'first'
[void][IO.Directory]::CreateDirectory($recordsRoot)
$stopPrefix = Join-Path $recordsRoot ('cancellation-test-' + [Guid]::NewGuid().ToString('N'))
$sleepCommand = @('-B', '-c', "import time`ntime.sleep(60)")
$sleepId = $null
try {
    $sleepId = New-Container (Container-Arguments 'none' 'mock' $sleepCommand $false)
    [void](Inspect-Container $sleepId 'none' 'mock' $sleepCommand $false)
    $started = Invoke-Tool 'docker' @('start', $sleepId) -TimeoutSeconds 10
    Assert-That ($started.ExitCode -eq 0) 'Could not start contained cancellation fixture'
    $rejected = $false
    try { Stop-OwnedContainer $sleepId $stopPrefix } catch { $rejected = $true }
    Assert-That $rejected 'Cleanup accepted an unregistered container handle'
    $stillRunning = Docker-Json @('inspect', $sleepId) 10
    Assert-That $stillRunning.State.Running 'Unregistered-handle rejection signalled the container'
    $ownedInspections[$sleepId] = @{ Network = 'none'; Mode = 'mock'; Command = $sleepCommand; InputOpen = $false }
    Stop-OwnedContainer $sleepId $stopPrefix
    $stopped = Docker-Json @('inspect', $sleepId) 10
    Assert-That (-not $stopped.State.Running) 'Owned inspected container survived bounded stop'
    $termination = Get-Content -LiteralPath ($stopPrefix + '.termination-' + $sleepId + '.json') -Raw -Encoding utf8 | ConvertFrom-Json
    Assert-That ($termination.stop_attempted -and $termination.stop_confirmed -and $termination.requested_stop_seconds -eq 2) 'Bounded stop record is incomplete'
    Assert-That ($termination.journal_intents_preserved -and -not $termination.provider_charge_stopped_proved) 'Cleanup fabricated billing certainty or removed journal state'
}
finally {
    if ($null -ne $sleepId) {
        $last = Docker-Json @('inspect', $sleepId) 10
        if ($last.State.Running -and $ownedInspections.ContainsKey($sleepId)) { Stop-OwnedContainer $sleepId ($stopPrefix + '-cleanup') }
        $last = Docker-Json @('inspect', $sleepId) 10
        if (-not $last.State.Running) { [void](Invoke-Tool 'docker' @('rm', $sleepId) -TimeoutSeconds 10) }
    }
}

if ([string]::IsNullOrEmpty($Study) -and [string]::IsNullOrEmpty($Grant)) {
    Write-Host 'Argument/path and actual bounded-cancellation checks passed. Supply -Study and -Grant fixture paths for complete launch integration.'
    exit 0
}
Assert-That (-not [string]::IsNullOrWhiteSpace($Study) -and -not [string]::IsNullOrWhiteSpace($Grant)) 'Both fixture input paths are required'
$baselineRecords = @(Get-ChildItem -LiteralPath $recordsRoot -Filter '*.json' -ErrorAction SilentlyContinue | ForEach-Object FullName)
foreach ($action in @('preflight', 'mock', 'mock', 'provider-config')) {
    $result = Invoke-Launcher $launcher @($action, '-Study', $Study, '-Grant', $Grant, '-Stage', 'first')
    Assert-That ($result.ExitCode -eq 0) ("Contained $action failed: " + $result.Stderr)
    Assert-That (-not $result.Stdout.Contains('fixture-not-a-secret') -and -not $result.Stderr.Contains('fixture-not-a-secret')) 'Dummy secret leaked into launcher streams'
}
$new = @(Get-ChildItem -LiteralPath $recordsRoot -Filter '*.json' | Where-Object FullName -notin $baselineRecords)
$inspections = @($new | Where-Object Name -like '*.inspection.json' | ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw -Encoding utf8 | ConvertFrom-Json })
Assert-That ($inspections.Count -eq 3) 'Mock/resume/configuration did not retain three inspected launch records'
Assert-That (@($inspections | Where-Object { $_.preflight.configuration_only -and $_.container.network_mode -eq 'bridge' -and $_.container.state_at_inspection -eq 'created' }).Count -eq 1) 'Provider configuration was not inspected without startup'
foreach ($inspection in $inspections) {
    Assert-That ($inspection.container.image -eq 'sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366') 'Image identity differs'
    Assert-That ($inspection.container.read_only_rootfs -and $inspection.container.mounts.Count -eq 2) 'Mount/root containment differs'
    Assert-That ('ANTHROPIC_API_KEY' -notin $inspection.container.environment_names -and 'OPENAI_API_KEY' -notin $inspection.container.environment_names) 'A credential was forwarded through the Docker environment'
}
$results = @($new | Where-Object Name -like '*.result.json' | ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw -Encoding utf8 | ConvertFrom-Json })
Assert-That ($results.Count -eq 2) 'Only the two mock invocations may execute'
foreach ($record in $results) {
    Assert-That ($record.action -eq 'mock' -and $record.exit_code -eq 0 -and -not $record.actual_credentials_supplied) 'Mock launch result differs'
}
$streamFiles = @($new | Where-Object Name -like '*.result.json' | ForEach-Object { $_.FullName.Replace('.result.json', '.stdout.log') })
$summaries = @($streamFiles | ForEach-Object { (Get-Content -LiteralPath $_ -Raw -Encoding utf8).Trim() | ConvertFrom-Json })
Assert-That (@($summaries | Where-Object new_mock_http_calls -eq 0).Count -ge 1) 'Unchanged host-launch resume made additional HTTP attempts'

# Invalid grants must fail in contained preflight before the host reaches key entry.
$invalidRoot = Join-Path $root ('runs\phase2-release-r018\launcher-invalid-' + [Guid]::NewGuid().ToString('N'))
$invalidGrant = Join-Path $invalidRoot 'grant.json'
try {
    [void][IO.Directory]::CreateDirectory($invalidRoot)
    [IO.File]::WriteAllText($invalidGrant, '{}', [Text.UTF8Encoding]::new($false))
    $relative = $invalidGrant.Substring((Join-Path $root 'runs').Length + 1).Replace('\', '/')
    $result = Invoke-Launcher $launcher @('provider', '-Live', '-Study', $Study, '-Grant', $relative)
    Assert-That ($result.ExitCode -ne 0 -and $result.Stderr.Contains('grant and source preflight')) 'An invalid grant reached credential entry or provider launch'
}
finally {
    if (Test-Path -LiteralPath $invalidGrant) { Remove-Item -LiteralPath $invalidGrant }
    if (Test-Path -LiteralPath $invalidRoot) { Remove-Item -LiteralPath $invalidRoot }
}
Write-Host 'P2-R launcher integration checks passed: actual image/mounts, mock first block/resume, provider configuration without startup and invalid-grant-before-key rejection.'
