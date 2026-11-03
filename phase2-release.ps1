#requires -Version 7.2
[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Position = 0)][ValidateSet('preflight', 'mock', 'provider-config', 'provider')]
    [string] $Action = 'preflight',
    [Parameter(Mandatory = $true)][string] $Study,
    [Parameter(Mandatory = $true)][string] $Grant,
    [ValidateSet('first', 'expansion')][string] $Stage = 'first',
    [switch] $Live
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$expectedRoot = 'C:\Users\arvik\code\research\Buddha2'
$expectedImage = 'sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366'

function Assert-NoReparse([string] $Path) {
    $current = [IO.DirectoryInfo]::new([IO.Path]::GetFullPath($Path))
    while ($null -ne $current) {
        if (Test-Path -LiteralPath $current.FullName) {
            if (((Get-Item -LiteralPath $current.FullName -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'A launch path traverses a reparse point'
            }
        }
        $current = $current.Parent
    }
}

function Assert-NoReparseTree([string] $Path) {
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($Path)
    while ($pending.Count -gt 0) {
        foreach ($item in Get-ChildItem -LiteralPath ($pending.Pop()) -Force) {
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'A runtime tree contains a reparse point' }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
        }
    }
}

function Get-RunPath([string] $Relative) {
    $Relative = $Relative.Replace('\', '/')
    if ($Relative -notmatch '^[A-Za-z0-9][A-Za-z0-9_./-]{0,250}$' -or
            @($Relative.Split('/') | Where-Object { $_ -in @('', '.', '..') }).Count -ne 0) {
        throw 'Inputs must be ordinary relative paths beneath the new project runs directory'
    }
    $path = [IO.Path]::GetFullPath((Join-Path $runsRoot $Relative.Replace('/', '\')))
    if (-not $path.StartsWith($runsRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Input escapes approved run storage' }
    Assert-NoReparse $path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Required input file is absent' }
    return [pscustomobject]@{ HostPath = $path; ContainerPath = '/results/' + $Relative }
}

function Invoke-Tool([string] $Program, [string[]] $Arguments, [AllowNull()][string] $InputText = $null,
        [int] $TimeoutSeconds = 0) {
    $start = [Diagnostics.ProcessStartInfo]::new($Program)
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.RedirectStandardInput = $null -ne $InputText
    foreach ($argument in $Arguments) { [void]$start.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::Start($start)
    try {
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if ($null -ne $InputText) {
            $process.StandardInput.Write($InputText)
            $process.StandardInput.Close()
        }
        if ($TimeoutSeconds -gt 0) {
            if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
                try { $process.Kill($true); $process.WaitForExit() } catch { }
                throw 'A controlled helper exceeded its bounded timeout'
            }
        }
        else { $process.WaitForExit() }
        return [pscustomobject]@{ ExitCode = $process.ExitCode; Stdout = $stdout.GetAwaiter().GetResult(); Stderr = $stderr.GetAwaiter().GetResult() }
    }
    finally { $process.Dispose() }
}

function Docker-Json([string[]] $Arguments, [int] $TimeoutSeconds = 30) {
    $result = Invoke-Tool 'docker' $Arguments -TimeoutSeconds $TimeoutSeconds
    if ($result.ExitCode -ne 0) { throw 'Docker operation failed; raw output suppressed' }
    return @($result.Stdout | ConvertFrom-Json -Depth 30)[0]
}

function Save-Json([string] $Path, $Value) {
    if (Test-Path -LiteralPath $Path) { throw 'Refusing to overwrite a launch record' }
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 30) + "`n", [Text.UTF8Encoding]::new($false))
}

function Get-HostPath([string] $Source) {
    if ($Source -match '^[A-Za-z]:[/\\]') { return [IO.Path]::GetFullPath($Source.Replace('/', '\')).TrimEnd('\') }
    if ($Source -match '^(?:/run/desktop/mnt/host|/host_mnt)/([A-Za-z])/(.*)$') {
        return [IO.Path]::GetFullPath($Matches[1].ToUpperInvariant() + ':\' + $Matches[2].Replace('/', '\')).TrimEnd('\')
    }
    throw 'Unsupported inspected host mount path'
}

function Container-Arguments([string] $Network, [string] $Mode, [string[]] $Command, [bool] $InputOpen) {
    $args = @('create', '--platform', 'linux/amd64', '--network', $Network, '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--log-driver', 'none',
        '--pids-limit', '256', '--memory', '4g', '--cpus', '2',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=536870912', '--workdir', '/workspace',
        '--mount', "type=bind,source=$projectRoot,target=/workspace,readonly",
        '--mount', "type=bind,source=$runsRoot,target=/results",
        '--env', "BUDDHA2_IMAGE_ID=$expectedImage", '--env', "BUDDHA2_RELEASE_LAUNCH_MODE=$Mode",
        '--env', $(if ($Mode -in @('provider', 'provider-config')) { 'BUDDHA2_OFFLINE=0' } else { 'BUDDHA2_OFFLINE=1' }),
        '--entrypoint', 'python')
    if ($InputOpen) { $args += '-i' }
    return $args + @($expectedImage) + $Command
}

function Inspect-Container([string] $Id, [string] $Network, [string] $Mode, [string[]] $Command, [bool] $InputOpen,
        [int] $TimeoutSeconds = 30) {
    $actual = Docker-Json @('inspect', $Id) $TimeoutSeconds
    $expectedEnvironment = @{}
    foreach ($item in $image.Config.Env) { $parts = $item.Split('=', 2); $expectedEnvironment[$parts[0]] = $parts[1] }
    $expectedEnvironment['BUDDHA2_IMAGE_ID'] = $expectedImage
    $expectedEnvironment['BUDDHA2_RELEASE_LAUNCH_MODE'] = $Mode
    $expectedEnvironment['BUDDHA2_OFFLINE'] = $(if ($Mode -in @('provider', 'provider-config')) { '0' } else { '1' })
    $seenEnvironment = @{}
    foreach ($item in $actual.Config.Env) {
        $parts = $item.Split('=', 2)
        if ($seenEnvironment.ContainsKey($parts[0]) -or -not $expectedEnvironment.ContainsKey($parts[0]) -or
                $parts[1] -cne $expectedEnvironment[$parts[0]]) { throw 'Unexpected container environment; values suppressed' }
        $seenEnvironment[$parts[0]] = $true
    }
    if ($seenEnvironment.Count -ne $expectedEnvironment.Count) { throw 'Missing container environment controls' }
    if ($actual.Image -ne $expectedImage -or $actual.HostConfig.NetworkMode -ne $Network -or
            -not $actual.HostConfig.ReadonlyRootfs -or $actual.HostConfig.Privileged -or $actual.HostConfig.PublishAllPorts -or
            @($actual.HostConfig.CapDrop).Count -ne 1 -or $actual.HostConfig.CapDrop[0] -ne 'ALL' -or
            -not (@($actual.HostConfig.SecurityOpt) -match '^no-new-privileges(?::true)?$') -or
            $actual.HostConfig.PidsLimit -ne 256 -or $actual.HostConfig.Memory -ne 4294967296 -or
            $actual.HostConfig.NanoCpus -ne 2000000000 -or $actual.HostConfig.LogConfig.Type -ne 'none' -or
            @($actual.HostConfig.Tmpfs.PSObject.Properties).Count -ne 1 -or
            $actual.HostConfig.Tmpfs.'/tmp' -ne 'rw,nosuid,nodev,size=536870912' -or
            $actual.Config.WorkingDir -ne '/workspace' -or $actual.Config.OpenStdin -ne $InputOpen -or $actual.Config.Tty -or
            @($actual.Config.Entrypoint).Count -ne 1 -or $actual.Config.Entrypoint[0] -ne 'python' -or
            ($actual.Config.Cmd | ConvertTo-Json -Compress) -cne ($Command | ConvertTo-Json -Compress)) {
        throw 'Created container differs from the supported launch contract'
    }
    if ($null -ne $actual.HostConfig.PortBindings -and @($actual.HostConfig.PortBindings.PSObject.Properties).Count -ne 0) {
        throw 'Published ports are unsupported'
    }
    $binds = @($actual.Mounts | Where-Object Type -eq 'bind')
    if ($binds.Count -ne 2 -or @($binds.Destination | Sort-Object -Unique).Count -ne 2 -or
            @($actual.Mounts | Where-Object { $_.Type -ne 'bind' -and -not ($_.Type -eq 'tmpfs' -and $_.Destination -eq '/tmp') }).Count -ne 0) {
        throw 'Unexpected created-container mount'
    }
    foreach ($mount in $binds) {
        $hostPath = Get-HostPath $mount.Source
        if ($mount.Destination -eq '/workspace') {
            if ($mount.RW -or -not [string]::Equals($hostPath, $projectRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Code mount differs' }
        }
        elseif ($mount.Destination -eq '/results') {
            if (-not $mount.RW -or -not [string]::Equals($hostPath, $runsRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Result mount differs' }
        }
        else { throw 'Unexpected mount destination' }
    }
    return [ordered]@{
        container_id = $Id; image = $actual.Image; image_os = $image.Os; image_architecture = $image.Architecture
        network_mode = $actual.HostConfig.NetworkMode; read_only_rootfs = $actual.HostConfig.ReadonlyRootfs
        privileged = $actual.HostConfig.Privileged; publish_all_ports = $actual.HostConfig.PublishAllPorts
        cap_drop = @($actual.HostConfig.CapDrop); security_opt = @($actual.HostConfig.SecurityOpt)
        pids_limit = $actual.HostConfig.PidsLimit; memory = $actual.HostConfig.Memory; nano_cpus = $actual.HostConfig.NanoCpus
        tmpfs = @{ '/tmp' = $actual.HostConfig.Tmpfs.'/tmp' }; log_driver = $actual.HostConfig.LogConfig.Type
        working_dir = $actual.Config.WorkingDir; entrypoint = @($actual.Config.Entrypoint)
        open_stdin = $actual.Config.OpenStdin; tty = $actual.Config.Tty; command = @($actual.Config.Cmd)
        state_at_inspection = $actual.State.Status
        port_bindings = @{}; environment_names = @($seenEnvironment.Keys | Sort-Object)
        mounts = @($binds | ForEach-Object { @{ type = $_.Type; source = $_.Source; destination = $_.Destination; rw = $_.RW } })
    }
}

function New-Container([string[]] $Arguments) {
    $result = Invoke-Tool 'docker' $Arguments
    if ($result.ExitCode -ne 0 -or $result.Stdout.Trim() -notmatch '^[0-9a-f]{64}$') { throw 'Could not create contained launch' }
    return $result.Stdout.Trim()
}

function Read-MaskedKey([string] $Prompt) {
    $secure = Read-Host -Prompt $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer); $secure.Dispose() }
}

function Stop-OwnedContainer([string] $Id, [string] $Prefix) {
    if (-not $ownedInspections.ContainsKey($Id)) { throw 'Refusing to stop a container without its owned inspected contract' }
    $contract = $ownedInspections[$Id]
    $record = [ordered]@{
        kind = 'phase2-release-bounded-termination-v1'; container_id = $Id; owned_inspected = $true
        action = $Action; stage = $Stage; requested_stop_seconds = 2; helper_timeout_seconds = 10
        state_before = 'unknown'; state_after = 'unknown'; stop_attempted = $false; stop_confirmed = $false
        journal_intents_preserved = $true; provider_charge_stopped_proved = $false
        reason = 'host_failure_or_interruption'; raw_error_suppressed = $true
    }
    try {
        # Revalidate the immutable image/mount/command/environment contract before
        # signalling this exact handle. No arbitrary container is ever stopped.
        $current = Inspect-Container $Id $contract.Network $contract.Mode $contract.Command $contract.InputOpen 10
        $record.state_before = $current.state_at_inspection
        if ($record.state_before -eq 'running') {
            $record.stop_attempted = $true
            $stopped = Invoke-Tool 'docker' @('stop', '--time', '2', $Id) -TimeoutSeconds 10
            if ($stopped.ExitCode -ne 0) { throw 'Bounded stop could not be confirmed' }
        }
        $last = Docker-Json @('inspect', $Id) 10
        $record.state_after = $last.State.Status
        $record.stop_confirmed = -not $last.State.Running
    }
    catch { $record.stop_confirmed = $false }
    Save-Json ($Prefix + '.termination-' + $Id + '.json') $record
    if (-not $record.stop_confirmed) { throw 'Owned-container cleanup is unconfirmed; retain its handle and do not relaunch' }
}

function Invoke-ProviderExecution([string] $Id, $Checked, [string] $InspectionHash) {
    $start = [Diagnostics.ProcessStartInfo]::new('docker')
    $start.UseShellExecute = $false; $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true; $start.RedirectStandardError = $true; $start.RedirectStandardInput = $true
    foreach ($argument in @('start', '--attach', '--interactive', $Id)) { [void]$start.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::Start($start)
    $keys = $null; $payload = $null
    try {
        $stderr = $process.StandardError.ReadToEndAsync()
        $readyTask = $process.StandardOutput.ReadLineAsync()
        if (-not $readyTask.Wait(120000)) { throw 'Timed out before credential-ready handshake' }
        $readyLine = $readyTask.GetAwaiter().GetResult()
        $ready = $readyLine | ConvertFrom-Json -AsHashtable
        if ($ready.Count -ne 4 -or $ready.credential_input_ready -ne $true -or
                $ready.study_sha256 -ne $Checked.study_sha256 -or $ready.grant_sha256 -ne $Checked.grant_sha256 -or
                $ready.host_inspection_sha256 -ne $InspectionHash) { throw 'Container did not validate the expected launch before credentials' }
        # The created container has now independently revalidated the release,
        # grant and inspection. Only at this point may the operator enter keys.
        $keys = @{ anthropic_api_key = Read-MaskedKey 'Anthropic API key (hidden)'; openai_api_key = Read-MaskedKey 'OpenAI API key (hidden)' }
        $payload = ($keys | ConvertTo-Json -Compress) + "`n"
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $process.StandardInput.Write($payload); $process.StandardInput.Close()
        $process.WaitForExit()
        return [pscustomobject]@{ ExitCode = $process.ExitCode; Stdout = $readyLine + "`n" + $stdout.GetAwaiter().GetResult(); Stderr = $stderr.GetAwaiter().GetResult() }
    }
    finally {
        $payload = $null
        if ($null -ne $keys) { $keys.Clear(); $keys = $null }
        try { $process.StandardInput.Close() } catch { }
        $process.Dispose()
    }
}

$containerIds = [Collections.Generic.List[string]]::new()
$ownedInspections = @{}
$exitCode = 1
$step = 'arguments'
$payload = $null
$keys = $null
$prefix = $null
try {
    if (($Action -eq 'provider') -ne $Live.IsPresent) { throw 'Only provider execution requires the explicit -Live switch' }
    $step = 'approved paths'
    $projectRoot = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
    if (-not [string]::Equals($projectRoot, $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Launcher outside approved root' }
    Assert-NoReparse $projectRoot
    if (-not [string]::Equals((Resolve-Path -LiteralPath $projectRoot).ProviderPath.TrimEnd('\'), $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Canonical project root differs' }
    $runsRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'runs')).TrimEnd('\')
    Assert-NoReparse $runsRoot
    $studyInput = Get-RunPath $Study
    $grantInput = Get-RunPath $Grant
    Assert-NoReparseTree $projectRoot
    $runtimeRoot = Join-Path $runsRoot 'phase2-release-r018\launcher'
    Assert-NoReparse $runtimeRoot
    [void][IO.Directory]::CreateDirectory($runtimeRoot)
    $nonce = [Guid]::NewGuid().ToString('N')
    $prefix = Join-Path $runtimeRoot $nonce
    $containerPrefix = '/results/phase2-release-r018/launcher/' + $nonce
    $step = 'pinned image'
    $image = Docker-Json @('image', 'inspect', $expectedImage)
    if ($image.Id -ne $expectedImage -or $image.Os -ne 'linux' -or $image.Architecture -ne 'amd64') { throw 'Pinned image differs' }
    $step = 'grant and source preflight'
    $checkCommand = @('-B', '-m', 'buddha2.phase2_release_launch', 'check', '--study', $studyInput.ContainerPath,
        '--grant', $grantInput.ContainerPath, '--stage', $Stage, '--mode', $Action, '--record', ($containerPrefix + '.preflight.json'))
    $checkId = New-Container (Container-Arguments 'none' 'preflight' $checkCommand $false)
    $containerIds.Add($checkId)
    $checkInspection = Inspect-Container $checkId 'none' 'preflight' $checkCommand $false
    $ownedInspections[$checkId] = @{ Network = 'none'; Mode = 'preflight'; Command = $checkCommand; InputOpen = $false }
    Save-Json ($prefix + '.preflight-container.json') $checkInspection
    $checkResult = Invoke-Tool 'docker' @('start', '--attach', $checkId)
    if ($checkResult.ExitCode -ne 0) { throw 'Release or grant preflight rejected the invocation' }
    $checked = Get-Content -LiteralPath ($prefix + '.preflight.json') -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
    if ($Action -eq 'preflight') {
        [Console]::Out.WriteLine(($checked | ConvertTo-Json -Depth 20))
        $exitCode = 0
    }
    else {
        $step = 'created execution container'
        $network = $(if ($Action -in @('provider', 'provider-config')) { 'bridge' } else { 'none' })
        $executionCommand = @('-B', '-m', 'buddha2.phase2_release_launch', 'execute', '--study', $studyInput.ContainerPath,
            '--grant', $grantInput.ContainerPath, '--stage', $Stage, '--mode', $Action,
            '--inspection', ($containerPrefix + '.inspection.json'))
        $executionId = New-Container (Container-Arguments $network $Action $executionCommand $true)
        $containerIds.Add($executionId)
        $inspection = Inspect-Container $executionId $network $Action $executionCommand $true
        $ownedInspections[$executionId] = @{ Network = $network; Mode = $Action; Command = $executionCommand; InputOpen = $true }
        $draft = [ordered]@{ kind = 'phase2-release-host-inspection-v1'; preflight = $checked; container = $inspection }
        Save-Json ($prefix + '.inspection-draft.json') $draft
        # Host Python performs only isolated stdlib canonical JSON/hash work.
        # No credential is present or read during this operation.
        $sealCode = 'import hashlib,json,pathlib,sys; v=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")); v["inspection_sha256"]=hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest(); p=pathlib.Path(sys.argv[2]); p.open("x",encoding="utf-8").write(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+"\n")'
        $sealed = Invoke-Tool 'python' @('-I', '-B', '-c', $sealCode, ($prefix + '.inspection-draft.json'), ($prefix + '.inspection.json'))
        if ($sealed.ExitCode -ne 0) { throw 'Could not bind the inspected container record' }
        if ($Action -eq 'provider-config') {
            Write-Host 'Provider-mode container configuration inspected. It was not started; no credentials were requested.'
            $exitCode = 0
        }
        else {
            $step = 'validated execution and credential handshake'
            if ($Action -eq 'provider') {
                $sealedRecord = Get-Content -LiteralPath ($prefix + '.inspection.json') -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
                $result = Invoke-ProviderExecution $executionId $checked $sealedRecord.inspection_sha256
            }
            else { $result = Invoke-Tool 'docker' @('start', '--attach', '--interactive', $executionId) '' }
            $step = 'bounded execution result'
            $finished = Docker-Json @('inspect', $executionId)
            $record = [ordered]@{ kind = 'phase2-release-host-result-v1'; action = $Action; stage = $Stage;
                preflight = $checked; inspection_file = ($nonce + '.inspection.json'); state = $finished.State.Status;
                exit_code = $finished.State.ExitCode; actual_credentials_supplied = ($Action -eq 'provider');
                stdout_bytes = [Text.Encoding]::UTF8.GetByteCount($result.Stdout); stderr_bytes = [Text.Encoding]::UTF8.GetByteCount($result.Stderr);
                stream_content_retained = ($Action -ne 'provider') }
            Save-Json ($prefix + '.result.json') $record
            if ($Action -eq 'provider') { Write-Host 'Provider streams suppressed. Inspect sanitized phase artifacts and the retained journal.' }
            else {
                [IO.File]::WriteAllText($prefix + '.stdout.log', $result.Stdout, [Text.UTF8Encoding]::new($false))
                [IO.File]::WriteAllText($prefix + '.stderr.log', $result.Stderr, [Text.UTF8Encoding]::new($false))
                [Console]::Out.Write($result.Stdout); [Console]::Error.Write($result.Stderr)
            }
            if ($finished.State.Running) { throw 'Container still running; use its recorded handle rather than relaunching' }
            $exitCode = [int]$finished.State.ExitCode
            if ($exitCode -eq 0 -and $result.ExitCode -ne 0) { $exitCode = $result.ExitCode }
        }
    }
    Write-Host "Phase 2 release launch records: $prefix.*"
}
catch {
    Write-Error -Message "Phase 2 release launcher failed during $step; raw error suppressed" -ErrorAction Continue
    $exitCode = 1
}
finally {
    $payload = $null
    if ($null -ne $keys) { $keys.Clear(); $keys = $null }
    foreach ($id in $containerIds) {
        try {
            $state = Docker-Json @('inspect', $id) 10
            if ($state.State.Running) {
                Stop-OwnedContainer $id $prefix
                $state = Docker-Json @('inspect', $id) 10
                Write-Warning "Stopped owned container $id after host failure/interruption; reconcile its journal before further execution"
            }
            if (-not $state.State.Running) {
                $removed = Invoke-Tool 'docker' @('rm', $id) -TimeoutSeconds 10
                if ($removed.ExitCode -ne 0) { Write-Warning 'Could not remove a stopped launch container'; $exitCode = 1 }
            }
        }
        catch { Write-Warning 'Container cleanup state is unknown; retain the launch record'; $exitCode = 1 }
    }
}
exit $exitCode
