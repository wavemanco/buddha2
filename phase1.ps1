#requires -Version 7.2
[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Position = 0)]
    [ValidateSet('offline', 'live', 'test')]
    [string] $Action = 'offline',

    [switch] $Live,
    [string] $LiveRun,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Rest = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$expectedRoot = 'C:\Users\arvik\code\research\Buddha2'
$expectedImage = 'sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366'

function Assert-NoReparseAncestor([string] $Path) {
    $current = [System.IO.DirectoryInfo]::new([System.IO.Path]::GetFullPath($Path))
    while ($null -ne $current) {
        if (Test-Path -LiteralPath $current.FullName) {
            $item = Get-Item -LiteralPath $current.FullName -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Reparse points are not permitted in approved runtime paths'
            }
        }
        $current = $current.Parent
    }
}

function Assert-NoReparseTree([string] $Path) {
    $pending = [System.Collections.Generic.Stack[string]]::new()
    $pending.Push($Path)
    while ($pending.Count -gt 0) {
        foreach ($item in Get-ChildItem -LiteralPath ($pending.Pop()) -Force) {
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Reparse points cannot enter runtime mounts'
            }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
        }
    }
}

function Invoke-Docker([string[]] $DockerArguments) {
    $start = [System.Diagnostics.ProcessStartInfo]::new('docker')
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($argument in $DockerArguments) { [void] $start.ArgumentList.Add($argument) }
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

function Get-DockerJson([string[]] $DockerArguments) {
    $result = Invoke-Docker $DockerArguments
    if ($result.ExitCode -ne 0) { throw 'Docker inspection failed; raw error suppressed' }
    return @($result.Stdout | ConvertFrom-Json)[0]
}

function Get-HostMountPath([string] $Source) {
    if ($Source -match '^[A-Za-z]:[/\\]') {
        return [System.IO.Path]::GetFullPath($Source.Replace('/', '\')).TrimEnd('\')
    }
    if ($Source -match '^(?:/run/desktop/mnt/host|/host_mnt)/([A-Za-z])/(.*)$') {
        $windowsPath = $Matches[1].ToUpperInvariant() + ':\' + $Matches[2].Replace('/', '\')
        return [System.IO.Path]::GetFullPath($windowsPath).TrimEnd('\')
    }
    throw 'Docker reported an unsupported bind-source representation'
}

function Save-Evidence([string] $Path, $Record) {
    [System.IO.File]::WriteAllText(
        $Path, ($Record | ConvertTo-Json -Depth 12) + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Get-TextHash([string] $Text) {
    return [System.Convert]::ToHexString(
        [System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes($Text))
    ).ToLowerInvariant()
}

$exitCode = 1
$containerId = $null
$evidencePath = $null
$record = $null
$stage = 'arguments'
try {
    # Reject live switches before any credential forwarding or Docker invocation.
    if ($Action -eq 'live') {
        if (-not $Live.IsPresent) { throw 'live requires the explicit -Live switch' }
        if ([string]::IsNullOrWhiteSpace($LiveRun) -or $LiveRun -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$') {
            throw '-LiveRun must name one approved child directory beneath runs'
        }
        if ($Rest.Count -eq 0 -or $Rest[0] -ne 'judge') {
            throw 'live permits only the bounded judge command'
        }
    }
    elseif ($Live.IsPresent -or -not [string]::IsNullOrEmpty($LiveRun)) {
        throw '-Live and -LiveRun are permitted only with the live action'
    }
    if ($Action -eq 'test' -and $Rest.Count -ne 0) { throw 'test does not accept extra arguments' }

    $stage = 'approved-path validation'
    $projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
    if (-not [string]::Equals($projectRoot, $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'This launcher is outside the approved new project root'
    }
    Assert-NoReparseAncestor $projectRoot
    if (-not [string]::Equals((Resolve-Path -LiteralPath $projectRoot).ProviderPath.TrimEnd('\'), $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Canonical project root differs from the approved location'
    }
    $runsRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot 'runs')).TrimEnd('\')
    Assert-NoReparseAncestor $runsRoot
    [void] [System.IO.Directory]::CreateDirectory($runsRoot)
    Assert-NoReparseAncestor $runsRoot
    $outputRoot = $runsRoot
    $codeRoot = $projectRoot
    $codeDestination = '/workspace'
    $network = 'none'
    if ($Action -eq 'live') {
        $codeRoot = Join-Path $projectRoot 'src'
        $codeDestination = '/workspace/src'
        $outputRoot = [System.IO.Path]::GetFullPath((Join-Path $runsRoot $LiveRun)).TrimEnd('\')
        if (-not $outputRoot.StartsWith($runsRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Live run escapes approved output storage'
        }
        Assert-NoReparseAncestor $outputRoot
        if (-not (Test-Path -LiteralPath $outputRoot -PathType Container)) { throw 'Live run must be staged offline first' }
        $allowedFiles = @('plan.json', 'preparation.json', 'initial-rubric.md', 'bundle.json')
        $allowedDirectories = @('execution', 'controls', 'assessments')
        foreach ($item in Get-ChildItem -LiteralPath $outputRoot -Force) {
            if (($item.PSIsContainer -and $item.Name -notin $allowedDirectories) -or
                (-not $item.PSIsContainer -and $item.Name -notin $allowedFiles)) {
                throw 'Live run contains an undeclared top-level entry; stage only public critic inputs'
            }
        }
        foreach ($name in $allowedFiles) {
            if (-not (Test-Path -LiteralPath (Join-Path $outputRoot $name) -PathType Leaf)) {
                throw 'Live run is missing a required staged public input'
            }
        }
        $network = 'bridge'
    }
    Assert-NoReparseAncestor $codeRoot
    Assert-NoReparseTree $codeRoot
    if ($Action -eq 'live') { Assert-NoReparseTree $outputRoot }

    $stage = 'pinned-image inspection'
    $image = Get-DockerJson @('image', 'inspect', $expectedImage)
    if ($image.Id -ne $expectedImage -or $image.Os -ne 'linux' -or $image.Architecture -ne 'amd64') {
        throw 'The pinned Linux/amd64 image is unavailable or incompatible'
    }
    $arguments = @(
        'create', '--platform', 'linux/amd64', '--network', $network, '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--log-driver', 'none',
        '--pids-limit', '256', '--memory', '4g', '--cpus', '2',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=536870912', '--workdir', '/workspace',
        '--mount', "type=bind,source=$codeRoot,target=$codeDestination,readonly",
        '--mount', "type=bind,source=$outputRoot,target=/results",
        '--env', "BUDDHA2_IMAGE_ID=$expectedImage", '--entrypoint', 'python'
    )
    if ($Action -eq 'live') {
        # Docker receives only this environment variable name, never its value in argv.
        $arguments += @('--env', 'ANTHROPIC_API_KEY', '--env', 'BUDDHA2_OFFLINE=0', '--env', 'BUDDHA2_PHASE1_LIVE=1')
    }
    $arguments += $expectedImage
    if ($Action -eq 'test') {
        $arguments += @('-B', '-m', 'unittest', 'tests.test_pairs', 'tests.test_muce', 'tests.test_phase1_runner', 'tests.test_phase1_cli', '-v')
    }
    else {
        $arguments += @('-B', '-m', 'buddha2.phase1')
        $arguments += $(if ($Rest.Count -gt 0) { $Rest } else { '--help' })
    }
    $stage = 'container creation'
    $created = Invoke-Docker $arguments
    if ($created.ExitCode -ne 0) { throw 'Container creation failed; raw error suppressed' }
    $containerId = $created.Stdout.Trim()
    if ($containerId -notmatch '^[0-9a-f]{64}$') { throw 'Docker returned an invalid container ID' }
    $inspection = Get-DockerJson @('inspect', $containerId)
    $environmentNames = @($inspection.Config.Env | ForEach-Object { ($_ -split '=', 2)[0] })
    $allowedEnvironment = @($image.Config.Env | ForEach-Object { ($_ -split '=', 2)[0] }) + @('BUDDHA2_IMAGE_ID')
    if ($Action -eq 'live') { $allowedEnvironment += @('ANTHROPIC_API_KEY', 'BUDDHA2_PHASE1_LIVE') }
    $evidenceRoot = Join-Path $runsRoot 'runtime-phase1'
    Assert-NoReparseAncestor $evidenceRoot
    [void] [System.IO.Directory]::CreateDirectory($evidenceRoot)
    $evidencePath = Join-Path $evidenceRoot ([Guid]::NewGuid().ToString('N') + '.json')
    $record = [ordered]@{
        SchemaVersion = 1
        Action = $Action
        ExplicitLiveSwitch = $Live.IsPresent
        ContainerId = $containerId
        Image = $inspection.Image
        NetworkMode = $inspection.HostConfig.NetworkMode
        ReadonlyRootfs = $inspection.HostConfig.ReadonlyRootfs
        Mounts = @($inspection.Mounts | Select-Object Type, Source, Destination, RW)
        EnvironmentNames = $environmentNames
        CapDrop = @($inspection.HostConfig.CapDrop)
        SecurityOpt = @($inspection.HostConfig.SecurityOpt)
        PidsLimit = $inspection.HostConfig.PidsLimit
        Memory = $inspection.HostConfig.Memory
        NanoCpus = $inspection.HostConfig.NanoCpus
        Tmpfs = $inspection.HostConfig.Tmpfs
        LoggingDriver = $inspection.HostConfig.LogConfig.Type
        State = $inspection.State.Status
        ExitCode = $null
        ValidationPassed = $false
    }
    Save-Evidence $evidencePath $record
    $stage = 'created-container validation'
    if ($inspection.Image -ne $expectedImage -or $inspection.HostConfig.NetworkMode -ne $network -or
        -not $inspection.HostConfig.ReadonlyRootfs -or 'ALL' -notin $inspection.HostConfig.CapDrop -or
        $inspection.HostConfig.Privileged -or $inspection.HostConfig.PublishAllPorts -or
        -not (@($inspection.HostConfig.SecurityOpt) -match '^no-new-privileges(?::true)?$') -or
        $inspection.HostConfig.PidsLimit -ne 256 -or $inspection.HostConfig.Memory -ne 4294967296 -or
        $inspection.HostConfig.NanoCpus -ne 2000000000 -or $inspection.HostConfig.LogConfig.Type -ne 'none' -or
        @($inspection.HostConfig.Tmpfs.PSObject.Properties).Count -ne 1 -or
        $inspection.HostConfig.Tmpfs.'/tmp' -ne 'rw,nosuid,nodev,size=536870912' -or
        $inspection.Config.WorkingDir -ne '/workspace' -or
        @($inspection.Config.Entrypoint).Count -ne 1 -or $inspection.Config.Entrypoint[0] -ne 'python' -or
        @($environmentNames | Where-Object { $_ -notin $allowedEnvironment }).Count -ne 0 -or
        ($Action -ne 'live' -and 'ANTHROPIC_API_KEY' -in $environmentNames)) {
        throw 'Created container failed containment/environment validation; it was not started'
    }
    $binds = @($inspection.Mounts | Where-Object Type -eq 'bind')
    if ($binds.Count -ne 2 -or @($binds.Destination | Sort-Object -Unique).Count -ne 2 -or
        '/results' -notin $binds.Destination -or $codeDestination -notin $binds.Destination -or
        @($inspection.Mounts | Where-Object {
        $_.Type -ne 'bind' -and -not ($_.Type -eq 'tmpfs' -and $_.Destination -eq '/tmp')
    }).Count -ne 0) { throw 'Unexpected runtime mount; container was not started' }
    foreach ($mount in $binds) {
        $source = Get-HostMountPath $mount.Source
        if ($mount.Destination -eq $codeDestination) {
            if ($mount.RW -or -not [string]::Equals($source, $codeRoot, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Code mount differs from the approved read-only source'
            }
        }
        elseif ($mount.Destination -eq '/results') {
            if (-not $mount.RW -or -not [string]::Equals($source, $outputRoot, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Output mount differs from approved run storage'
            }
        }
        else { throw 'Unexpected bind destination; container was not started' }
    }
    $record.ValidationPassed = $true
    Save-Evidence $evidencePath $record
    $stage = 'bounded execution'
    $attached = Invoke-Docker @('start', '--attach', $containerId)
    $finished = Get-DockerJson @('inspect', $containerId)
    $record.State = $finished.State.Status
    $record.ExitCode = [int] $finished.State.ExitCode
    $record.OOMKilled = $finished.State.OOMKilled
    $record.Streams = [ordered]@{
        StdoutSha256 = Get-TextHash $attached.Stdout
        StderrSha256 = Get-TextHash $attached.Stderr
        StdoutUtf8Bytes = [System.Text.Encoding]::UTF8.GetByteCount($attached.Stdout)
        StderrUtf8Bytes = [System.Text.Encoding]::UTF8.GetByteCount($attached.Stderr)
        ContentRetained = ($Action -ne 'live')
    }
    if ($Action -eq 'live') {
        Write-Host 'Live stdout/stderr suppressed; inspect sanitized structured run artifacts.'
    }
    else {
        $stdoutPath = [System.IO.Path]::ChangeExtension($evidencePath, 'stdout.log')
        $stderrPath = [System.IO.Path]::ChangeExtension($evidencePath, 'stderr.log')
        [System.IO.File]::WriteAllText($stdoutPath, $attached.Stdout, [System.Text.UTF8Encoding]::new($false))
        [System.IO.File]::WriteAllText($stderrPath, $attached.Stderr, [System.Text.UTF8Encoding]::new($false))
        $record.Streams.StdoutFile = [System.IO.Path]::GetFileName($stdoutPath)
        $record.Streams.StderrFile = [System.IO.Path]::GetFileName($stderrPath)
        [Console]::Out.Write($attached.Stdout)
        [Console]::Error.Write($attached.Stderr)
    }
    Save-Evidence $evidencePath $record
    if ($finished.State.Running) { throw 'Attach ended while the container is still running; retain its handle and do not restart' }
    $exitCode = [int] $finished.State.ExitCode
    if ($exitCode -eq 0 -and $attached.ExitCode -ne 0) { $exitCode = $attached.ExitCode }
    Write-Host "Phase 1 runtime evidence: $evidencePath"
}
catch {
    # Even parser/system exception text could contain inspected environment or SDK values.
    Write-Error -Message "Phase 1 launcher failed during $stage; raw error text suppressed" -ErrorAction Continue
    $exitCode = 1
}
finally {
    if ($null -ne $containerId -and $containerId -match '^[0-9a-f]{64}$') {
        try {
            $last = Get-DockerJson @('inspect', $containerId)
            if (-not $last.State.Running) {
                $removed = Invoke-Docker @('rm', $containerId)
                if ($removed.ExitCode -ne 0) { Write-Warning 'Could not remove the stopped Phase 1 container'; $exitCode = 1 }
            }
            else { Write-Warning "Container $containerId remains running; inspect this handle before further execution" }
        }
        catch { Write-Warning 'Container cleanup status is unknown; retain its recorded handle'; $exitCode = 1 }
    }
}
exit $exitCode
