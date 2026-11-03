#requires -Version 7.2
[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Position = 0)][ValidateSet('preflight', 'config', 'mock', 'provider')][string] $Action = 'preflight',
    [Parameter(Mandatory = $true)][string] $Study,
    [Parameter(Mandatory = $true)][string] $Grant,
    [switch] $Live
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-FrozenHelperBlock([string] $Path) {
    # Import only known top-level functions from the exact retained launcher.
    # Its main body is never evaluated; both launchers remain independently bound.
    $bytes = [IO.File]::ReadAllBytes($Path)
    $hash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
    if ($hash -cne '489e7df6edf0bbd610e60c99b5bd6a17b38c78bd86d97cd58fed2bff02e4c479') { throw 'Frozen helper source differs' }
    $tokens = $null; $errors = $null
    $ast = [Management.Automation.Language.Parser]::ParseInput([Text.UTF8Encoding]::new($false, $true).GetString($bytes), [ref]$tokens, [ref]$errors)
    $names = @('Assert-NoReparse', 'Assert-NoReparseTree', 'Get-RunPath', 'Invoke-Tool', 'Docker-Json',
        'Save-Json', 'Get-HostPath', 'Container-Arguments', 'Inspect-Container', 'New-Container',
        'Read-MaskedKey', 'Stop-OwnedContainer', 'Invoke-ProviderExecution')
    $definitions = @($ast.EndBlock.Statements | Where-Object {
        $_ -is [Management.Automation.Language.FunctionDefinitionAst] -and $_.Name -cin $names
    })
    if ($errors.Count -ne 0 -or $definitions.Count -ne $names.Count -or
            @($definitions.Name | Sort-Object -Unique).Count -ne $names.Count) { throw 'Frozen helper inventory differs' }
    return [ScriptBlock]::Create(($definitions.Extent.Text -join "`n"))
}

$expectedRoot = 'C:\Users\arvik\code\research\Buddha2'
$expectedImage = 'sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366'
$Stage = 'rank-format-v1'
$containerIds = [Collections.Generic.List[string]]::new()
$ownedInspections = @{}
$prefix = $null
$step = 'arguments'
$exitCode = 1
try {
    $Action = $Action.ToLowerInvariant()
    if (($Action -eq 'provider') -ne $Live.IsPresent) { throw 'Only explicit provider execution requires -Live' }
    $projectRoot = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
    if (-not [string]::Equals($projectRoot, $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Launcher outside approved new root' }
    . (Get-FrozenHelperBlock (Join-Path $projectRoot 'phase2-release.ps1'))
    $step = 'approved paths'
    Assert-NoReparse $projectRoot
    if (-not [string]::Equals((Resolve-Path -LiteralPath $projectRoot).ProviderPath.TrimEnd('\'), $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Canonical project root differs' }
    $runsRoot = Join-Path $projectRoot 'runs'
    $studyInput = Get-RunPath $Study
    $grantInput = Get-RunPath $Grant
    Assert-NoReparseTree $projectRoot
    $runtimeRoot = Join-Path $runsRoot 'phase2b-rank-format-v1\launcher'
    Assert-NoReparse $runtimeRoot
    [void][IO.Directory]::CreateDirectory($runtimeRoot)
    $nonce = [Guid]::NewGuid().ToString('N')
    $prefix = Join-Path $runtimeRoot $nonce
    $containerPrefix = '/results/phase2b-rank-format-v1/launcher/' + $nonce
    $mode = $(if ($Action -eq 'config') { 'provider-config' } else { $Action })
    $step = 'pinned image'
    $image = Docker-Json @('image', 'inspect', $expectedImage)
    if ($image.Id -ne $expectedImage -or $image.Os -ne 'linux' -or $image.Architecture -ne 'amd64') { throw 'Pinned image differs' }
    $step = 'source scope and authority preflight'
    $checkCommand = @('-B', '-m', 'followups.rank_format_v1.launch', '--command', 'preflight',
        '--study', $studyInput.ContainerPath, '--grant', $grantInput.ContainerPath, '--mode', $mode,
        '--record', ($containerPrefix + '.preflight.json'))
    $checkId = New-Container (Container-Arguments 'none' 'preflight' $checkCommand $false)
    $containerIds.Add($checkId)
    $checkInspection = Inspect-Container $checkId 'none' 'preflight' $checkCommand $false
    $ownedInspections[$checkId] = @{ Network = 'none'; Mode = 'preflight'; Command = $checkCommand; InputOpen = $false }
    Save-Json ($prefix + '.preflight-container.json') $checkInspection
    $checkResult = Invoke-Tool 'docker' @('start', '--attach', $checkId)
    if ($checkResult.ExitCode -ne 0) { throw 'Follow-up authority or source preflight rejected' }
    $checked = Get-Content -LiteralPath ($prefix + '.preflight.json') -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
    if ($Action -eq 'preflight') {
        [Console]::Out.WriteLine(($checked | ConvertTo-Json -Depth 30))
        $exitCode = 0
    }
    else {
        $step = 'inspected execution configuration'
        $network = $(if ($Action -in @('provider', 'config')) { 'bridge' } else { 'none' })
        $executionCommand = @('-B', '-m', 'followups.rank_format_v1.launch', '--command', 'execute',
            '--study', $studyInput.ContainerPath, '--grant', $grantInput.ContainerPath, '--mode', $mode,
            '--inspection', ($containerPrefix + '.inspection.json'))
        $executionId = New-Container (Container-Arguments $network $mode $executionCommand $true)
        $containerIds.Add($executionId)
        $inspection = Inspect-Container $executionId $network $mode $executionCommand $true
        $ownedInspections[$executionId] = @{ Network = $network; Mode = $mode; Command = $executionCommand; InputOpen = $true }
        Save-Json ($prefix + '.inspection-draft.json') ([ordered]@{ kind = 'rank-format-host-inspection-v1'; preflight = $checked; container = $inspection })
        $sealCode = 'import hashlib,json,pathlib,sys; v=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")); v["inspection_sha256"]=hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest(); p=pathlib.Path(sys.argv[2]); p.open("x",encoding="utf-8").write(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+"\n")'
        $sealed = Invoke-Tool 'python' @('-I', '-B', '-c', $sealCode, ($prefix + '.inspection-draft.json'), ($prefix + '.inspection.json'))
        if ($sealed.ExitCode -ne 0) { throw 'Could not seal the actual inspected configuration' }
        if ($Action -eq 'config') {
            Write-Host 'Follow-up provider configuration inspected without startup or credential entry.'
            $exitCode = 0
        }
        else {
            $step = 'validated execution and credential handshake'
            if ($Action -eq 'provider') {
                $bound = Get-Content -LiteralPath ($prefix + '.inspection.json') -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
                $result = Invoke-ProviderExecution $executionId $checked $bound.inspection_sha256
            }
            else {
                $dummy = '{"anthropic_api_key":"fixture-not-a-secret","openai_api_key":"fixture-not-a-secret"}' + "`n"
                $result = Invoke-Tool 'docker' @('start', '--attach', '--interactive', $executionId) $dummy
            }
            $finished = Docker-Json @('inspect', $executionId)
            Save-Json ($prefix + '.result.json') ([ordered]@{ kind = 'rank-format-host-result-v1'; action = $Action;
                preflight = $checked; inspection_file = ($nonce + '.inspection.json'); state = $finished.State.Status;
                exit_code = $finished.State.ExitCode; actual_credentials_supplied = ($Action -eq 'provider');
                stdout_bytes = [Text.Encoding]::UTF8.GetByteCount($result.Stdout); stderr_bytes = [Text.Encoding]::UTF8.GetByteCount($result.Stderr);
                stream_content_retained = ($Action -ne 'provider') })
            if ($Action -eq 'provider') { Write-Host 'Provider streams suppressed. Inspect the follow-up artifacts and journal.' }
            else {
                [IO.File]::WriteAllText($prefix + '.stdout.log', $result.Stdout, [Text.UTF8Encoding]::new($false))
                [IO.File]::WriteAllText($prefix + '.stderr.log', $result.Stderr, [Text.UTF8Encoding]::new($false))
                [Console]::Out.Write($result.Stdout); [Console]::Error.Write($result.Stderr)
            }
            if ($finished.State.Running) { throw 'Execution remains running; preserve its handle and do not relaunch' }
            $exitCode = [int]$finished.State.ExitCode
            if ($exitCode -eq 0 -and $result.ExitCode -ne 0) { $exitCode = $result.ExitCode }
        }
    }
    Write-Host "Follow-up launch records: $prefix.*"
}
catch {
    Write-Error -Message "Rank-format launcher failed during $step; raw error suppressed" -ErrorAction Continue
    $exitCode = 1
}
finally {
    foreach ($id in $containerIds) {
        try {
            $state = Docker-Json @('inspect', $id) 10
            if ($state.State.Running) { Stop-OwnedContainer $id $prefix; $state = Docker-Json @('inspect', $id) 10 }
            if (-not $state.State.Running) {
                $removed = Invoke-Tool 'docker' @('rm', $id) -TimeoutSeconds 10
                if ($removed.ExitCode -ne 0) { Write-Warning 'Could not remove a stopped owned container'; $exitCode = 1 }
            }
        }
        catch { Write-Warning 'Owned-container cleanup is unconfirmed; preserve its handle and reconcile the journal'; $exitCode = 1 }
    }
}
exit $exitCode
