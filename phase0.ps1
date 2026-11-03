[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'test', 'check', 'run')]
    [string] $Action = 'run',

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Rest = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$imageTag = 'buddha2-phase0:local'
$expectedRoot = 'C:\Users\arvik\code\research\Buddha2'

function Assert-NoReparseAncestor([string] $Path) {
    $current = [System.IO.DirectoryInfo]::new([System.IO.Path]::GetFullPath($Path))
    while ($null -ne $current) {
        if (Test-Path -LiteralPath $current.FullName) {
            $item = Get-Item -LiteralPath $current.FullName -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Reparse points are not allowed in approved runtime paths: $($current.FullName)"
            }
        }
        $current = $current.Parent
    }
}

function Invoke-Checked([string] $Program, [string[]] $CommandArguments) {
    & $Program @CommandArguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program exited with status $LASTEXITCODE"
    }
}

function Assert-NoReparseTree([string] $Path) {
    $pending = [System.Collections.Generic.Stack[string]]::new()
    $pending.Push($Path)
    while ($pending.Count -gt 0) {
        foreach ($item in Get-ChildItem -LiteralPath ($pending.Pop()) -Force) {
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Reparse points cannot enter the runtime mounts: $($item.FullName)"
            }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
        }
    }
}

function Save-RuntimeEvidence([string] $Path, $Record) {
    $json = $Record | ConvertTo-Json -Depth 12
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
}

function Get-HostMountPath([string] $Source) {
    if ($Source -match '^[A-Za-z]:[/\\]') {
        return [System.IO.Path]::GetFullPath($Source.Replace('/', '\')).TrimEnd('\')
    }
    if ($Source -match '^(?:/run/desktop/mnt/host|/host_mnt)/([A-Za-z])/(.*)$') {
        $windowsPath = $Matches[1].ToUpperInvariant() + ':\' + $Matches[2].Replace('/', '\')
        return [System.IO.Path]::GetFullPath($windowsPath).TrimEnd('\')
    }
    throw "Docker reported an unsupported bind source representation: $Source"
}

$exitCode = 1
$containerId = $null
$runtimeRecord = $null
$evidencePath = $null
$locationPushed = $false
try {
    $projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
    if (-not [string]::Equals($projectRoot, $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "This launcher is restricted to $expectedRoot"
    }
    Assert-NoReparseAncestor $projectRoot
    $resolvedRoot = (Resolve-Path -LiteralPath $projectRoot).ProviderPath.TrimEnd('\')
    if (-not [string]::Equals($resolvedRoot, $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The canonical project root is outside the approved location'
    }
    $runsRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot 'runs')).TrimEnd('\')
    if (-not $runsRoot.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Run storage escapes the approved project root'
    }
    Assert-NoReparseAncestor $runsRoot
    [void] [System.IO.Directory]::CreateDirectory($runsRoot)
    Assert-NoReparseAncestor $runsRoot
    Assert-NoReparseTree $projectRoot
    Push-Location -LiteralPath $projectRoot
    $locationPushed = $true

    if ($Action -eq 'setup') {
        if ($Rest.Count -ne 0) { throw 'setup does not accept additional arguments' }
        Invoke-Checked 'python' @('-B', 'tools/sources.py', '--fetch')
        Invoke-Checked 'docker' @('build', '--platform', 'linux/amd64', '--tag', $imageTag, $projectRoot)
        $exitCode = 0
    }
    else {
        if ($Action -ne 'run' -and $Rest.Count -ne 0) {
            throw "$Action does not accept additional arguments"
        }
        $imageId = ((Invoke-Checked 'docker' @('image', 'inspect', '--format', '{{.Id}}', $imageTag)) -join '').Trim()
        if ($imageId -notmatch '^sha256:[0-9a-f]{64}$') { throw 'Docker did not return a valid immutable image ID' }
        $arguments = @(
            'create', '--platform', 'linux/amd64', '--network', 'none', '--read-only',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--pids-limit', '256', '--memory', '4g', '--cpus', '2',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=536870912',
            '--mount', "type=bind,source=$projectRoot,target=/workspace,readonly",
            '--mount', "type=bind,source=$runsRoot,target=/results",
            '--env', "BUDDHA2_IMAGE_ID=$imageId"
        )
        if ($Action -eq 'test' -or $Action -eq 'check') { $arguments += @('--entrypoint', 'python') }
        $arguments += $imageId
        if ($Action -eq 'test') {
            $arguments += @('-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v')
        }
        elseif ($Action -eq 'check') { $arguments += @('-B', 'tools/checks.py') }
        elseif ($Rest.Count -gt 0) { $arguments += $Rest }
        else { $arguments += '--help' }
        $containerId = ((Invoke-Checked 'docker' $arguments) -join '').Trim()
        if ($containerId -notmatch '^[0-9a-f]{64}$') { throw 'Docker did not return a valid container ID' }
        $inspection = @(Invoke-Checked 'docker' @('inspect', $containerId) | ConvertFrom-Json)[0]
        $sensitiveEnvironment = @($inspection.Config.Env | Where-Object {
            ($_ -split '=', 2)[0] -match '(?i)(API_?KEY|ACCESS_KEY_ID|SECRET_ACCESS_KEY|TOKEN|SECRET|PASSWORD|CREDENTIALS?)$'
        })
        $runtimeRecord = [ordered]@{
            ContainerId = $containerId
            Image = $inspection.Image
            Command = @($inspection.Config.Entrypoint) + @($inspection.Config.Cmd)
            Mounts = @($inspection.Mounts | Select-Object Type, Source, Destination, RW)
            NetworkMode = $inspection.HostConfig.NetworkMode
            ReadonlyRootfs = $inspection.HostConfig.ReadonlyRootfs
            CapDrop = @($inspection.HostConfig.CapDrop)
            SecurityOpt = @($inspection.HostConfig.SecurityOpt)
            Env = @($inspection.Config.Env | Where-Object { $_ -notin $sensitiveEnvironment })
            OmittedEnvironmentNames = @($sensitiveEnvironment | ForEach-Object { ($_ -split '=', 2)[0] })
            PidsLimit = $inspection.HostConfig.PidsLimit
            Memory = $inspection.HostConfig.Memory
            NanoCpus = $inspection.HostConfig.NanoCpus
            Tmpfs = $inspection.HostConfig.Tmpfs
            ExitCode = $null
        }
        $evidenceRoot = Join-Path $runsRoot 'runtime'
        Assert-NoReparseAncestor $evidenceRoot
        [void] [System.IO.Directory]::CreateDirectory($evidenceRoot)
        $evidencePath = Join-Path $evidenceRoot ([Guid]::NewGuid().ToString('N') + '.json')
        Save-RuntimeEvidence $evidencePath $runtimeRecord

        if ($inspection.Image -ne $imageId -or $inspection.HostConfig.NetworkMode -ne 'none' -or
            -not $inspection.HostConfig.ReadonlyRootfs -or 'ALL' -notin $inspection.HostConfig.CapDrop -or
            -not (@($inspection.HostConfig.SecurityOpt) -match '^no-new-privileges(?::true)?$') -or
            $sensitiveEnvironment.Count -ne 0) {
            throw 'Created container failed offline security validation; it was not started'
        }
        $binds = @($inspection.Mounts | Where-Object Type -eq 'bind')
        if ($binds.Count -ne 2 -or @($inspection.Mounts | Where-Object {
            $_.Type -ne 'bind' -and -not ($_.Type -eq 'tmpfs' -and $_.Destination -eq '/tmp')
        }).Count -ne 0) { throw 'Unexpected runtime mount; container was not started' }
        foreach ($mount in $binds) {
            $hostPath = Get-HostMountPath $mount.Source
            if ($mount.Destination -eq '/workspace') {
                if ($mount.RW -or -not [string]::Equals($hostPath, $projectRoot, [StringComparison]::OrdinalIgnoreCase)) {
                    throw 'Code mount differs from the approved read-only root'
                }
            }
            elseif ($mount.Destination -eq '/results') {
                if (-not $mount.RW -or -not [string]::Equals($hostPath, $runsRoot, [StringComparison]::OrdinalIgnoreCase)) {
                    throw 'Output mount differs from the approved writable run root'
                }
            }
            else { throw 'Unexpected bind destination; container was not started' }
        }
        & docker start --attach $containerId
        $attachExit = $LASTEXITCODE
        $finished = @(Invoke-Checked 'docker' @('inspect', $containerId) | ConvertFrom-Json)[0]
        $runtimeRecord.ExitCode = [int] $finished.State.ExitCode
        $runtimeRecord.State = $finished.State.Status
        $runtimeRecord.OOMKilled = $finished.State.OOMKilled
        $stdoutPath = [System.IO.Path]::ChangeExtension($evidencePath, 'stdout.log')
        $stderrPath = [System.IO.Path]::ChangeExtension($evidencePath, 'stderr.log')
        $logs = Start-Process -FilePath 'docker' -ArgumentList @('logs', $containerId) -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        if ($logs.ExitCode -ne 0) { throw 'Could not retain runtime logs' }
        $runtimeRecord.Logs = [ordered]@{
            Stdout = [System.IO.Path]::GetFileName($stdoutPath)
            Stderr = [System.IO.Path]::GetFileName($stderrPath)
            StdoutSha256 = (Get-FileHash -LiteralPath $stdoutPath -Algorithm SHA256).Hash.ToLowerInvariant()
            StderrSha256 = (Get-FileHash -LiteralPath $stderrPath -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        Save-RuntimeEvidence $evidencePath $runtimeRecord
        if ($finished.State.Running) { throw 'Attached invocation returned while its container was still running' }
        $exitCode = [int] $finished.State.ExitCode
        if ($exitCode -eq 0 -and $attachExit -ne 0) { $exitCode = $attachExit }
        Write-Host "Runtime evidence: $evidencePath"
    }
}
catch {
    Write-Error -Message $_.Exception.Message -ErrorAction Continue
    $exitCode = 1
}
finally {
    if ($null -ne $containerId -and $containerId -match '^[0-9a-f]{64}$') {
        & docker rm --force $containerId | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Could not remove fixture container $containerId"
            $exitCode = 1
        }
    }
    if ($locationPushed) { Pop-Location }
}
exit $exitCode
