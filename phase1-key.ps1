#requires -Version 7.2
[CmdletBinding()]
param(
    [ValidateSet('set', 'run', 'status', 'clear')]
    [string] $Action = 'set',
    [ValidateSet('calibration', 'audit')]
    [string] $Stage = 'calibration'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$credentialName = 'BUDDHA2_PHASE1_ANTHROPIC_DPAPI'
$expectedRoot = 'C:\Users\arvik\code\research\Buddha2'
$secure = $null
$pointer = [IntPtr]::Zero
$child = $null
$start = $null
$plain = $null
$exitCode = 1

function Assert-SafePath([string] $Path) {
    $absolute = [System.IO.Path]::GetFullPath($Path)
    if (Test-Path -LiteralPath $absolute) {
        if (((Get-Item -LiteralPath $absolute -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Linked paths are unsupported'
        }
    }
    $directory = [System.IO.DirectoryInfo]::new([System.IO.Path]::GetDirectoryName($absolute))
    while ($null -ne $directory) {
        if (Test-Path -LiteralPath $directory.FullName) {
            if (((Get-Item -LiteralPath $directory.FullName -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Linked ancestors are unsupported'
            }
        }
        $directory = $directory.Parent
    }
}

try {
    if (-not $IsWindows) { throw 'Windows DPAPI is required' }
    $projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
    if (-not [string]::Equals($projectRoot, $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'This helper is outside the approved project'
    }
    Assert-SafePath $PSCommandPath
    $encrypted = [Environment]::GetEnvironmentVariable($credentialName, 'User')

    switch ($Action) {
        'status' {
            Write-Output ('EncryptedCredentialAvailable=' + (-not [string]::IsNullOrWhiteSpace($encrypted)))
            $exitCode = 0
        }
        'set' {
            if (-not [string]::IsNullOrWhiteSpace($encrypted)) {
                throw 'A credential is already saved; clear explicitly before replacement'
            }
            Write-Host 'Paste your Anthropic API key at the masked prompt, then press Enter.'
            Write-Host 'This saves it encrypted for your Windows account. No API call is made here.'
            $secure = Read-Host -Prompt 'Anthropic API key (characters hidden)' -AsSecureString
            if ($secure.Length -lt 20 -or $secure.Length -gt 4096) { throw 'Invalid key length' }
            $encrypted = ConvertFrom-SecureString -SecureString $secure
            [Environment]::SetEnvironmentVariable($credentialName, $encrypted, 'User')
            Write-Host 'Encrypted key saved. Return to Codex and say Ready.'
            $exitCode = 0
        }
        'clear' {
            [Environment]::SetEnvironmentVariable($credentialName, $null, 'User')
            Write-Host 'Temporary encrypted Phase 1 credential cleared.'
            $exitCode = 0
        }
        'run' {
            $grantPath = Join-Path $projectRoot 'runs\phase1-live-r05\controls\authorization.json'
            $launcher = Join-Path $projectRoot 'phase1.ps1'
            Assert-SafePath $grantPath
            Assert-SafePath $launcher
            $grant = Get-Content -LiteralPath $grantPath -Raw | ConvertFrom-Json
            if ($grant.authorization_micro_usd -ne 5000000 -or $grant.scheduled_presentations -ne 48 -or
                $grant.generation_attempt_ceiling -ne 52 -or $grant.staged_run -ne 'runs/phase1-live-r05') {
                throw 'The frozen spending grant is incompatible'
            }
            if ([string]::IsNullOrWhiteSpace($encrypted)) { throw 'Set the encrypted credential first' }
            $secure = ConvertTo-SecureString -String $encrypted
            $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
            $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
            if ([string]::IsNullOrWhiteSpace($plain) -or $plain.Contains("`r") -or $plain.Contains("`n")) {
                throw 'Invalid credential'
            }
            $start = [System.Diagnostics.ProcessStartInfo]::new((Get-Process -Id $PID).Path)
            $start.UseShellExecute = $false
            $start.CreateNoWindow = $true
            $start.RedirectStandardOutput = $true
            $start.RedirectStandardError = $true
            foreach ($argument in @('-NoProfile', '-File', $launcher, 'live', '-Live', '-LiveRun',
                'phase1-live-r05', 'judge', '--run', '/results', '--stage', $Stage,
                '--cap-micro-usd', '5000000')) {
                [void] $start.ArgumentList.Add($argument)
            }
            $start.WorkingDirectory = $projectRoot
            $start.Environment['ANTHROPIC_API_KEY'] = $plain
            [void] $start.Environment.Remove($credentialName)
            $child = [System.Diagnostics.Process]::Start($start)
            Write-Host ('Phase 1 launcher process ID: ' + $child.Id)
            [void] $start.Environment.Remove('ANTHROPIC_API_KEY')
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
            $pointer = [IntPtr]::Zero
            $secure.Dispose()
            $secure = $null
            $plain = $null
            $stdout = $child.StandardOutput.ReadToEndAsync()
            $stderr = $child.StandardError.ReadToEndAsync()
            $child.WaitForExit()
            [void] $stdout.GetAwaiter().GetResult()
            [void] $stderr.GetAwaiter().GetResult()
            $exitCode = $child.ExitCode
            Write-Host "Phase 1 launcher exited with status $exitCode; inspect the structured run artifacts."
        }
    }
}
catch {
    # System/crypto/parser errors can include input; never display their raw messages.
    Write-Error -Message "Phase 1 credential action '$Action' could not finish; no secret details displayed." -ErrorAction Continue
    $exitCode = 1
}
finally {
    if ($null -ne $start) { [void] $start.Environment.Remove('ANTHROPIC_API_KEY') }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $secure) { $secure.Dispose() }
    if ($null -ne $child) {
        if (-not $child.HasExited) {
            Write-Warning ('Launcher process ' + $child.Id + ' remains running. Inspect that PID and runs/runtime-phase1 before retrying.')
        }
        $child.Dispose()
    }
    $plain = $null
    $encrypted = $null
}
exit $exitCode
