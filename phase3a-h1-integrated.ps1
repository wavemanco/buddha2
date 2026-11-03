#requires -Version 5.1
[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Position = 0)][ValidateSet('preflight', 'config', 'mock', 'provider')][string] $Action = 'preflight',
    [Parameter(Mandatory = $true)][string] $Study,
    [Parameter(Mandatory = $true)][string] $Grant,
    [ValidateSet('readiness', 'first', 'remaining', 'all')][string] $Stage = 'all',
    [switch] $Live
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-PublicHIInput([string] $Relative) {
    # Reject private/escaped input names before any filesystem operation.
    $value = $Relative.Replace('\', '/')
    if (-not $value.StartsWith('phase3a-h1-integrated-v1/', [StringComparison]::Ordinal) -or
        $value -cnotmatch '^[A-Za-z0-9][A-Za-z0-9_./-]{0,250}$') { throw 'Input is outside P3A-HI' }
    foreach ($part in $value.Split('/')) {
        if ($part -cin @('', '.', '..') -or $part.ToLowerInvariant() -in @('credential-binding.json', '.writer.lock', '.env', 'auth.json', 'credentials.json')) {
            throw 'Input is not a public ordinary P3A-HI path'
        }
    }
}

function Assert-OrdinaryHIPath([string] $Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $current = [IO.Path]::GetPathRoot($full)
    foreach ($part in $full.Substring($current.Length).Split([IO.Path]::DirectorySeparatorChar)) {
        if ($part -eq '') { continue }
        if ($part.ToLowerInvariant() -in @('credential-binding.json', '.writer.lock', '.env', 'auth.json', 'credentials.json')) { throw 'Private path rejected' }
        $current = Join-Path $current $part
        $attributes = [IO.File]::GetAttributes($current)
        if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Bootstrap path traverses a reparse point' }
    }
}

function Get-HISHA256([string] $Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($Path))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

try {
    Assert-PublicHIInput $Study
    Assert-PublicHIInput $Grant
    $expectedRoot = 'C:\Users\arvik\code\research\Buddha2'
    if (-not [string]::Equals([IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\'), $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Bootstrap outside approved research root' }
    $runtime = 'C:\Users\arvik\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
    $core = Join-Path $expectedRoot 'phase3a-h1-integrated-core.ps1'
    Assert-OrdinaryHIPath $runtime
    Assert-OrdinaryHIPath $core
    if ((Get-HISHA256 $runtime) -cne '362a356ce7f0940ec74f73a8fc2c990a2cc24a38a11c90bbd8eca947110ad139' -or
        (Get-HISHA256 $core) -cne '80e538653554ac8af6fa33e7031aeb2798dca284e9238bf84ea3ce27096c593a') { throw 'Pinned bootstrap executable or core source differs' }
    $arguments = @('-NoProfile', '-File', $core, '-Action', $Action.ToLowerInvariant(), '-Study', $Study, '-Grant', $Grant, '-Stage', $Stage.ToLowerInvariant())
    if ($Live.IsPresent) { $arguments += '-Live' }
    # Native argv only; credentials never enter bootstrap arguments or environment.
    & $runtime @arguments
    exit $LASTEXITCODE
}
catch {
    Write-Error -Message 'P3A-HI bootstrap rejected input, runtime or child source; raw error suppressed' -ErrorAction Continue
    exit 1
}
