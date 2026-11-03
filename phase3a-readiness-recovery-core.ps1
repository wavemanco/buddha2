#requires -Version 7.2
[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Position = 0)][ValidateSet('preflight', 'config', 'mock', 'provider')][string] $Action = 'preflight',
    [Parameter(Mandatory = $true)][string] $Study,
    [Parameter(Mandatory = $true)][string] $Grant,
    [ValidateSet('readiness', 'first', 'remaining', 'all')][string] $Stage = 'all',
    [string] $SupervisorAgent,
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
    # P3A-RP2 may replay a full journal twice before hidden key entry. Extend
    # only this local Ready wait; provider HTTP deadlines and frozen bytes stay bound.
    $oldReadyWait = '$readyTask.Wait(120000)'
    $providerText = ($definitions | Where-Object Name -CEQ 'Invoke-ProviderExecution').Extent.Text
    if ([regex]::Matches($providerText, [regex]::Escape($oldReadyWait)).Count -ne 1) { throw 'Frozen Ready-wait token differs' }
    # Retain the complete source/inventory check, but install the local equivalent
    # native-metadata guard instead of executing the old cmdlet-heavy definition.
    $imports = @($definitions | Where-Object Name -CNE 'Assert-NoReparse' | ForEach-Object {
        if ($_.Name -ceq 'Invoke-ProviderExecution') { $_.Extent.Text.Replace($oldReadyWait, '$readyTask.Wait(600000)') }
        else { $_.Extent.Text }
    })
    return [ScriptBlock]::Create(($imports -join "`n"))
}

function Assert-NoReparse([string] $Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $parts = $full.Substring([IO.Path]::GetPathRoot($full).Length).Split([IO.Path]::DirectorySeparatorChar)
    foreach ($part in $parts) {
        if ($part -match '(?i)(?:stdout|stderr)' -or $part.ToLowerInvariant() -in @('credential-binding.json', '.writer.lock', '.env', 'auth.json', 'credentials.json')) { throw 'Private path rejected before metadata' }
    }
    $current = [IO.Path]::GetPathRoot($full)
    foreach ($part in $parts) {
        if ($part -eq '') { continue }
        $current = Join-Path $current $part
        try { $attributes = [IO.File]::GetAttributes($current) }
        catch [IO.FileNotFoundException] { break }
        catch [IO.DirectoryNotFoundException] { break }
        if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'A launch path traverses a reparse point' }
    }
}

function Assert-PublicProjectTree([string] $Root) {
    # Exclude private names before any attribute/stat/content access.
    $private = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($name in @('credential-binding.json', '.writer.lock', '.env', 'auth.json', 'credentials.json')) { [void]$private.Add($name) }
    $canonical = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar)
    Assert-NoReparse $canonical
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($canonical)
    while ($pending.Count -gt 0) {
        foreach ($entry in [IO.Directory]::EnumerateFileSystemEntries($pending.Pop())) {
            if ($private.Contains([IO.Path]::GetFileName($entry)) -or [IO.Path]::GetFileName($entry) -match '(?i)(?:stdout|stderr)') { continue }
            $full = [IO.Path]::GetFullPath($entry)
            if (-not $full.StartsWith($canonical + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Public tree escaped the approved root' }
            Assert-NoReparse $full
            $attributes = [IO.File]::GetAttributes($full)
            if (($attributes -band [IO.FileAttributes]::Directory) -ne 0) { $pending.Push($full) }
        }
    }
}

function Assert-PublicCompletionInput([string] $Relative) {
    # Lexical checks precede the frozen helper's attribute/path inspection.
    $relativePath = $Relative.Replace('\', '/')
    if (-not $relativePath.StartsWith('phase3a-readiness-recovery-v1/', [StringComparison]::Ordinal) -or
            $relativePath -cnotmatch '^[A-Za-z0-9][A-Za-z0-9_./-]{0,250}$') { throw 'Input is outside the new public completion scope' }
    $private = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($name in @('credential-binding.json', '.writer.lock', '.env', 'auth.json', 'credentials.json')) { [void]$private.Add($name) }
    foreach ($part in $relativePath.Split('/')) {
        if ($part -match '(?i)(?:stdout|stderr)' -or $part -cin @('', '.', '..') -or $private.Contains($part)) { throw 'Input is not a public ordinary completion path' }
    }
}

$expectedRoot = 'C:\Users\arvik\code\research\Buddha2'
$expectedImage = 'sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800'
$containerIds = [Collections.Generic.List[string]]::new()
$ownedInspections = @{}
$prefix = $null
$step = 'arguments'
$exitCode = 1
try {
    $Action = $Action.ToLowerInvariant()
    if (($Action -in @('mock', 'provider') -or $SupervisorAgent) -and $SupervisorAgent -cnotmatch '^/root(?:/[a-z0-9_]+)+$') { throw 'Dedicated supervisor agent required' }
    if (($Action -eq 'provider') -ne $Live.IsPresent) { throw 'Only explicit provider execution requires -Live' }
    if ($Action -eq 'provider') {
        [Console]::Title = 'Buddha2 P3A-RP2 - validation then hidden keys'
        Write-Host 'Buddha2 P3A-RP2: validating public paths, source, authority and containment before hidden key entry.'
        Write-Host 'Validation is active. The two masked prompts appear only after the controller confirms its exact release.'
    }
    $projectRoot = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
    if (-not [string]::Equals($projectRoot, $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Launcher outside approved new root' }
    $step = 'approved paths'
    Assert-NoReparse $projectRoot
    $helperSource = Join-Path $projectRoot 'phase2-release.ps1'
    Assert-NoReparse $helperSource
    . (Get-FrozenHelperBlock $helperSource)
    if (-not [string]::Equals((Resolve-Path -LiteralPath $projectRoot).ProviderPath.TrimEnd('\'), $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Canonical project root differs' }
    $runsRoot = Join-Path $projectRoot 'runs'
    Assert-PublicCompletionInput $Study
    Assert-PublicCompletionInput $Grant
    $studyInput = Get-RunPath $Study
    $grantInput = Get-RunPath $Grant
    Assert-PublicProjectTree $projectRoot
    $runtimeRoot = Join-Path $runsRoot 'phase3a-readiness-recovery-v1\launcher'
    Assert-NoReparse $runtimeRoot
    [void][IO.Directory]::CreateDirectory($runtimeRoot)
    $nonce = [Guid]::NewGuid().ToString('N')
    $prefix = Join-Path $runtimeRoot $nonce
    $containerPrefix = '/results/phase3a-readiness-recovery-v1/launcher/' + $nonce
    $mode = $(if ($Action -eq 'config') { 'provider-config' } else { $Action })
    $step = 'pinned image'
    $image = Docker-Json @('image', 'inspect', $expectedImage)
    if ($image.Id -ne $expectedImage -or $image.Os -ne 'linux' -or $image.Architecture -ne 'amd64') { throw 'Pinned image differs' }
    $step = 'source scope and authority preflight'
    $checkCommand = @('-B', '-m', 'followups.phase3a_readiness_recovery_v1.launch', '--command', 'preflight',
        '--study', $studyInput.ContainerPath, '--grant', $grantInput.ContainerPath, '--stage', $Stage, '--mode', $mode,
        '--record', ($containerPrefix + '.preflight.json'))
    if ($SupervisorAgent) { $checkCommand += @('--supervisor-agent', $SupervisorAgent) }
    $checkId = New-Container (Container-Arguments 'none' 'preflight' $checkCommand $false)
    $containerIds.Add($checkId)
    $checkInspection = Inspect-Container $checkId 'none' 'preflight' $checkCommand $false
    $ownedInspections[$checkId] = @{ Network = 'none'; Mode = 'preflight'; Command = $checkCommand; InputOpen = $false }
    Save-Json ($prefix + '.preflight-container.json') $checkInspection
    $checkResult = Invoke-Tool 'docker' @('start', '--attach', $checkId)
    if ($checkResult.ExitCode -ne 0) { throw 'P3A-RP2 authority or source preflight rejected' }
    $checked = Get-Content -LiteralPath ($prefix + '.preflight.json') -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
    if ($Action -eq 'preflight') {
        [Console]::Out.WriteLine(($checked | ConvertTo-Json -Depth 30))
        $exitCode = 0
    }
    else {
        $step = 'inspected execution configuration'
        $network = $(if ($Action -in @('provider', 'config')) { 'bridge' } else { 'none' })
        $executionCommand = @('-B', '-m', 'followups.phase3a_readiness_recovery_v1.launch', '--command', 'execute',
            '--study', $studyInput.ContainerPath, '--grant', $grantInput.ContainerPath, '--stage', $Stage, '--mode', $mode,
            '--inspection', ($containerPrefix + '.inspection.json'))
        if ($SupervisorAgent) { $executionCommand += @('--supervisor-agent', $SupervisorAgent) }
        $executionId = New-Container (Container-Arguments $network $mode $executionCommand $true)
        $containerIds.Add($executionId)
        $inspection = Inspect-Container $executionId $network $mode $executionCommand $true
        $ownedInspections[$executionId] = @{ Network = $network; Mode = $mode; Command = $executionCommand; InputOpen = $true }
        Save-Json ($prefix + '.inspection-draft.json') ([ordered]@{ kind = 'phase3a-rp2-host-inspection-v1'; preflight = $checked; container = $inspection })
        $sealCode = 'import hashlib,json,pathlib,sys; v=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")); v["inspection_sha256"]=hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest(); p=pathlib.Path(sys.argv[2]); p.open("x",encoding="utf-8").write(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+"\n")'
        $sealed = Invoke-Tool 'python' @('-I', '-B', '-c', $sealCode, ($prefix + '.inspection-draft.json'), ($prefix + '.inspection.json'))
        if ($sealed.ExitCode -ne 0) { throw 'Could not seal the actual inspected configuration' }
        if ($Action -eq 'config') {
            Write-Host 'P3A-RP2 provider configuration inspected without startup or credential entry.'
            $exitCode = 0
        }
        else {
            $step = 'validated execution and credential handshake'
            if ($Action -eq 'provider') {
                $bound = Get-Content -LiteralPath ($prefix + '.inspection.json') -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
                Write-Host 'Entering keys confirms the same previously declared Anthropic/OpenAI accounts and public-PAYG billing profile; stop if those accounts or terms have changed.'
                Write-Host 'This one controller retains keys only in RAM through supervised startup, readiness, first-pair review and remaining work. Approved cap: $190.00 total, included $50.86 first checkpoint and $20 readiness cell.'
                Write-Host 'After key entry, paid work waits for the named keyless supervisor to attach (at most 30 minutes). No extra key prompt is required.'
                Write-Host 'Validating the frozen release before hidden key entry; this may take a few minutes. Wait for the masked prompts.'
                $result = Invoke-ProviderExecution $executionId $checked $bound.inspection_sha256
            }
            else {
                $dummy = '{"anthropic_api_key":"fixture-not-a-secret","openai_api_key":"fixture-not-a-secret"}' + "`n"
                $result = Invoke-Tool 'docker' @('start', '--attach', '--interactive', $executionId) $dummy
            }
            $finished = Docker-Json @('inspect', $executionId)
            Save-Json ($prefix + '.result.json') ([ordered]@{ kind = 'phase3a-host-result-v1'; action = $Action;
                preflight = $checked; inspection_file = ($nonce + '.inspection.json'); state = $finished.State.Status;
                started_at_utc = $finished.State.StartedAt; finished_at_utc = $finished.State.FinishedAt;
                elapsed_wall_seconds = $(if (-not $finished.State.Running) {
                    ([DateTimeOffset]::Parse($finished.State.FinishedAt) - [DateTimeOffset]::Parse($finished.State.StartedAt)).TotalSeconds
                } else { $null });
                wall_time_basis = 'Docker container lifetime, including credential entry and execution';
                exit_code = $finished.State.ExitCode; actual_credentials_supplied = ($Action -eq 'provider');
                stdout_bytes = [Text.Encoding]::UTF8.GetByteCount($result.Stdout); stderr_bytes = [Text.Encoding]::UTF8.GetByteCount($result.Stderr);
                stream_content_retained = ($Action -ne 'provider') })
            if ($Action -eq 'provider') { Write-Host 'Provider streams suppressed. Inspect the P3A-RP2 artifacts and journal.' }
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
    Write-Host "P3A-RP2 launch records: $prefix.*"
}
catch {
    Write-Error -Message "P3A-RP2 launcher failed during $step; raw error suppressed" -ErrorAction Continue
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
