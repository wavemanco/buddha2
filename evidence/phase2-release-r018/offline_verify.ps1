[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-z0-9-]+$')][string] $Name,
    [switch] $HistoricalSource,
    [switch] $Am1Source,
    [switch] $SeparateChecks,
    [Parameter(Mandatory = $true)][string[]] $Command
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = 'C:\Users\arvik\code\research\Buddha2'
$runsRoot = Join-Path $projectRoot 'runs'
$retainedSource = Join-Path $runsRoot 'phase2-r012\frozen-study\source'
if ($HistoricalSource -and $Am1Source) { throw 'Select one retained historical source' }
if ($Am1Source) { $retainedSource = Join-Path $runsRoot 'phase2-am1-r016\candidate\source' }
$evidenceRoot = Join-Path $projectRoot 'evidence\phase2-release-r018\runtime'
$image = 'sha256:585a5539c6091592258ec19d0bf8e216b189405f95766b167df0d2e88e251366'
foreach ($path in @($projectRoot, $runsRoot, $retainedSource)) {
    $resolved = (Resolve-Path -LiteralPath $path).ProviderPath.TrimEnd('\')
    if (-not [string]::Equals($resolved, $path, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Verification mount differs from its fixed approved path'
    }
    $ancestor = [System.IO.DirectoryInfo]::new($resolved)
    while ($null -ne $ancestor) {
        if (((Get-Item -LiteralPath $ancestor.FullName -Force).Attributes -band
                [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Mount traverses a link' }
        $ancestor = $ancestor.Parent
    }
}
[void][IO.Directory]::CreateDirectory($evidenceRoot)
$prefix = Join-Path $evidenceRoot $Name
if (Test-Path -LiteralPath ($prefix + '.json')) { throw 'Use a new immutable verification name' }
$arguments = @('create', '--platform', 'linux/amd64', '--network', 'none', '--read-only',
    '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '256',
    '--memory', '4g', '--cpus', '2', '--tmpfs', '/tmp:rw,nosuid,nodev,size=536870912',
    '--mount', "type=bind,source=$projectRoot,target=/workspace,readonly",
    '--mount', "type=bind,source=$runsRoot,target=/results",
    '--env', "BUDDHA2_IMAGE_ID=$image", '--entrypoint', 'python')
if ($HistoricalSource -or $Am1Source) {
    $arguments += @('--mount', "type=bind,source=$retainedSource,target=/workspace/src/buddha2,readonly")
}
if ($SeparateChecks) { $arguments += @('--env', 'BUDDHA2_OUTPUT_ROOT=/results/phase2-release-r018/verification') }
$arguments += @($image, '-B') + $Command
$containerId = $null
$exitCode = 1
try {
    $containerId = ((& docker @arguments) -join '').Trim()
    if ($LASTEXITCODE -ne 0 -or $containerId -notmatch '^[a-f0-9]{64}$') { throw 'Cannot create contained verifier' }
    $inspection = @(& docker inspect $containerId | ConvertFrom-Json)[0]
    if ($inspection.Image -ne $image -or $inspection.HostConfig.NetworkMode -ne 'none' -or
            -not $inspection.HostConfig.ReadonlyRootfs) { throw 'Containment differs' }
    $record = [ordered]@{
        image = $inspection.Image; command = $Command; network = $inspection.HostConfig.NetworkMode
        read_only_root = $inspection.HostConfig.ReadonlyRootfs
        cap_drop = @($inspection.HostConfig.CapDrop); security_opt = @($inspection.HostConfig.SecurityOpt)
        mounts = @($inspection.Mounts | Select-Object Source, Destination, RW)
        historical_source_override = [bool]($HistoricalSource -or $Am1Source)
        retained_source = $(if ($HistoricalSource -or $Am1Source) { $retainedSource } else { $null })
        provider_calls = 0; real_credentials_supplied = $false
    }
    $ErrorActionPreference = 'Continue'
    $out = @(& docker start -a $containerId 2> ($prefix + '.stderr.log'))
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    [IO.File]::WriteAllText($prefix + '.stdout.log', ($out -join "`n") + "`n", [Text.UTF8Encoding]::new($false))
    $record.exit_code = $exitCode
    [IO.File]::WriteAllText($prefix + '.json', ($record | ConvertTo-Json -Depth 12) + "`n", [Text.UTF8Encoding]::new($false))
    $out | Select-Object -Last 12 | Write-Output
}
finally {
    if ($null -ne $containerId -and $containerId -match '^[a-f0-9]{64}$') { & docker rm -f $containerId | Out-Null }
}
exit $exitCode
