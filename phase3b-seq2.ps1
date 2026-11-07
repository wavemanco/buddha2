#requires -Version 5.1
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

function Assert-PublicHIInput([string] $Relative) {
    # Reject private/escaped input names before any filesystem operation.
    $value = $Relative.Replace('\', '/')
    if (-not $value.StartsWith('phase3b-seq2-v1/', [StringComparison]::Ordinal) -or
        $value -cnotmatch '^[A-Za-z0-9][A-Za-z0-9_./-]{0,250}$') { throw 'Input is outside P3B-S2' }
    foreach ($part in $value.Split('/')) {
        if ($part -match '(?i)(?:stdout|stderr)' -or $part -cin @('', '.', '..') -or $part.ToLowerInvariant() -in @('credential-binding.json', '.writer.lock', '.env', 'auth.json', 'credentials.json')) {
            throw 'Input is not a public ordinary P3B-S2 path'
        }
    }
}

function Assert-OrdinaryHIPath([string] $Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $current = [IO.Path]::GetPathRoot($full)
    foreach ($part in $full.Substring($current.Length).Split([IO.Path]::DirectorySeparatorChar)) {
        if ($part -eq '') { continue }
        if ($part -match '(?i)(?:stdout|stderr)' -or $part.ToLowerInvariant() -in @('credential-binding.json', '.writer.lock', '.env', 'auth.json', 'credentials.json')) { throw 'Private path rejected' }
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
    if (($Action -in @('mock', 'provider') -or $SupervisorAgent) -and $SupervisorAgent -cnotmatch '^/root(?:/[a-z0-9_]+)+$') { throw 'Dedicated supervisor agent required' }
    Assert-PublicHIInput $Study
    Assert-PublicHIInput $Grant
    $expectedRoot = 'C:\Users\arvik\code\research\Buddha2'
    if (-not [string]::Equals([IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\'), $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Bootstrap outside approved research root' }
    $runtime = 'C:\Users\arvik\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
    $core = Join-Path $expectedRoot 'phase3b-seq2-core.ps1'
    Assert-OrdinaryHIPath $runtime
    Assert-OrdinaryHIPath $core
    if ((Get-HISHA256 $runtime) -cne '2a6769a3330dc1084d0154bfde7d164ab750ca7f700f313f9d417c1be78b2233' -or
        (Get-HISHA256 $core) -cne '21c6e1ce64e96ced7e086ff347994dd5a6e812ebe7b79538436cbe52c97b6408') { throw 'Pinned bootstrap executable or core source differs' }
    $arguments = @('-NoProfile', '-File', $core, '-Action', $Action.ToLowerInvariant(), '-Study', $Study, '-Grant', $Grant, '-Stage', $Stage.ToLowerInvariant())
    if ($SupervisorAgent) { $arguments += @('-SupervisorAgent', $SupervisorAgent) }
    if ($Live.IsPresent) { $arguments += '-Live' }
    # Native argv only; credentials never enter bootstrap arguments or environment.
    & $runtime @arguments
    exit $LASTEXITCODE
}
catch {
    Write-Error -Message 'P3B-S2 bootstrap rejected input, runtime or child source; raw error suppressed' -ErrorAction Continue
    exit 1
}
