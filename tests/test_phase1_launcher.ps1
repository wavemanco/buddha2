#requires -Version 7.2
# Runnable launcher boundaries and a complete synthetic workflow; never launches live.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
if ($projectRoot -ne 'C:\Users\arvik\code\research\Buddha2') { throw 'Test must run from the approved project' }
$launcher = Join-Path $projectRoot 'phase1.ps1'
$pwsh = (Get-Process -Id $PID).Path

function Invoke-Launcher([string] $Script, [string[]] $Arguments) {
    $start = [System.Diagnostics.ProcessStartInfo]::new($pwsh)
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($argument in @('-NoProfile', '-File', $Script) + $Arguments) {
        [void] $start.ArgumentList.Add($argument)
    }
    $process = [System.Diagnostics.Process]::Start($start)
    try {
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            Stdout = $stdout.GetAwaiter().GetResult()
            Stderr = $stderr.GetAwaiter().GetResult()
        }
    }
    finally { $process.Dispose() }
}

function Assert-That([bool] $Condition, [string] $Message) {
    if (-not $Condition) { throw $Message }
}

$tokens = $null
$errors = $null
[void] [System.Management.Automation.Language.Parser]::ParseFile($launcher, [ref] $tokens, [ref] $errors)
Assert-That ($errors.Count -eq 0) 'PowerShell launcher syntax is invalid'
$evidenceRoot = Join-Path $projectRoot 'runs/runtime-phase1'
$before = @(Get-ChildItem -LiteralPath $evidenceRoot -Filter '*.json' -ErrorAction SilentlyContinue).Count
foreach ($case in @(
    @{ Name = 'missing explicit live switch'; Arguments = @('live') },
    @{ Name = 'live switch on offline action'; Arguments = @('offline', '-Live') },
    @{ Name = 'live directory on offline action'; Arguments = @('offline', '-LiveRun', 'unused') },
    @{ Name = 'traversal rejected before dispatch'; Arguments = @('live', '-Live', '-LiveRun', '..', 'judge') },
    @{ Name = 'arbitrary live command rejected before dispatch'; Arguments = @('live', '-Live', '-LiveRun', 'unused', 'fixture') }
)) {
    $result = Invoke-Launcher $launcher $case.Arguments
    Assert-That ($result.ExitCode -ne 0) "Launcher accepted $($case.Name)"
}
$after = @(Get-ChildItem -LiteralPath $evidenceRoot -Filter '*.json' -ErrorAction SilentlyContinue).Count
Assert-That ($before -eq $after) 'A rejected argument invocation created runtime evidence/container'

$copyRoot = Join-Path $projectRoot ('runs/launcher-guard-' + [Guid]::NewGuid().ToString('N'))
$copyPath = Join-Path $copyRoot 'phase1.ps1'
try {
    [void] [System.IO.Directory]::CreateDirectory($copyRoot)
    [System.IO.File]::Copy($launcher, $copyPath)
    $result = Invoke-Launcher $copyPath @('offline', '--help')
    Assert-That ($result.ExitCode -ne 0) 'A launcher copied outside the exact project root was accepted'
}
finally {
    # These exact checked paths are under the project; no recursive deletion is used.
    if (Test-Path -LiteralPath $copyPath) { Remove-Item -LiteralPath $copyPath }
    if (Test-Path -LiteralPath $copyRoot) { Remove-Item -LiteralPath $copyRoot }
}

$result = Invoke-Launcher $launcher @('offline', '--help')
Assert-That ($result.ExitCode -eq 0) ('Offline help failed: ' + $result.Stderr)
Assert-That ($result.Stdout.Contains('prepare,fixture,stage,judge')) 'Offline help did not run the Phase 1 CLI'
$namespace = 'phase1-launcher-fixture-' + [Guid]::NewGuid().ToString('N')
$result = Invoke-Launcher $launcher @('offline', 'fixture', '--output', "/results/$namespace")
Assert-That ($result.ExitCode -eq 0) ('Offline fixture failed: ' + $result.Stderr)
$auditPath = Join-Path $projectRoot "runs/$namespace/evaluator/assessments/audit.json"
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
Assert-That ($audit.fixture -eq $true) 'Fixture result lost its synthetic marker'
Assert-That ($audit.execution.provider_calls -eq 0) 'Offline fixture recorded provider activity'
Assert-That ($audit.human_agreement.successes -eq 12) 'Offline replay did not retain all synthetic prompt outcomes'
$newEvidence = @(Get-ChildItem -LiteralPath $evidenceRoot -Filter '*.json' | Sort-Object LastWriteTime | Select-Object -Last 2)
foreach ($path in $newEvidence) {
    $record = Get-Content -LiteralPath $path.FullName -Raw | ConvertFrom-Json
    Assert-That ($record.ValidationPassed -and $record.ExitCode -eq 0) 'Contained command did not complete successfully'
    Assert-That ($record.Image -eq 'sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366') 'Image pin changed'
    Assert-That ($record.NetworkMode -eq 'none' -and $record.ReadonlyRootfs) 'Offline containment changed'
    Assert-That (@($record.Mounts | Where-Object Type -eq 'bind').Count -eq 2) 'Runtime used extra bind mounts'
    Assert-That ('ANTHROPIC_API_KEY' -notin $record.EnvironmentNames) 'Offline runtime received a provider credential'
    Assert-That ($null -eq $record.PSObject.Properties['Env']) 'Runtime evidence retained environment values'
    foreach ($stream in @(@{ Name = 'Stdout'; File = $record.Streams.StdoutFile }, @{ Name = 'Stderr'; File = $record.Streams.StderrFile })) {
        $actual = (Get-FileHash -LiteralPath (Join-Path $evidenceRoot $stream.File) -Algorithm SHA256).Hash.ToLowerInvariant()
        Assert-That ($actual -eq $record.Streams.($stream.Name + 'Sha256')) 'Captured output hash differs from runtime evidence'
    }
}
Write-Host "Phase 1 launcher checks passed; synthetic artifacts: runs/$namespace"
