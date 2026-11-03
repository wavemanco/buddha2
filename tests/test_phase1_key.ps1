#requires -Version 7.2
# Uses a disposable synthetic value; never starts a live container or reads a real key.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
if ($projectRoot -ne 'C:\Users\arvik\code\research\Buddha2') { throw 'Wrong test root' }
$helper = Join-Path $projectRoot 'phase1-key.ps1'
$pwsh = (Get-Process -Id $PID).Path
$name = 'BUDDHA2_PHASE1_ANTHROPIC_DPAPI'
if (-not [string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($name, 'User'))) {
    throw 'Refusing to test over an existing saved credential'
}
$fixture = 'fixture-not-an-api-key-' + [Guid]::NewGuid().ToString('N')
$fixtureBlob = $null
$pointer = [IntPtr]::Zero
$secure = $null

function Invoke-Child([string[]] $Arguments) {
    $info = [System.Diagnostics.ProcessStartInfo]::new($pwsh)
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    foreach ($argument in @('-NoProfile') + $Arguments) { [void] $info.ArgumentList.Add($argument) }
    $process = [System.Diagnostics.Process]::Start($info)
    try {
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $result = [pscustomobject]@{ ExitCode = $process.ExitCode; Out = $stdout.GetAwaiter().GetResult(); Err = $stderr.GetAwaiter().GetResult() }
        if ($result.Out.Contains($fixture) -or $result.Err.Contains($fixture)) { throw 'Fixture plaintext was exposed' }
        return $result
    }
    finally { $process.Dispose() }
}

function Assert-That([bool] $Condition, [string] $Message) {
    if (-not $Condition) { throw $Message }
}

try {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($helper, [ref]$tokens, [ref]$errors)
    Assert-That ($errors.Count -eq 0) 'Helper has syntax errors'
    $runtime = Join-Path $projectRoot 'runs/runtime-phase1'
    $before = @(Get-ChildItem -LiteralPath $runtime -Filter '*.json').Count
    $missing = Invoke-Child @('-File', $helper, '-Action', 'run')
    Assert-That ($missing.ExitCode -ne 0) 'Missing credential allowed dispatch'
    Assert-That (@(Get-ChildItem -LiteralPath $runtime -Filter '*.json').Count -eq $before) 'Missing-key check started a container'

    $body = @'
$global:phase1Fixture = 'FIXTURE_VALUE'
function global:Read-Host {
    param([string] $Prompt, [switch] $AsSecureString)
    if (-not $AsSecureString.IsPresent) { throw 'Prompt does not request hidden SecureString input' }
    ConvertTo-SecureString -String $global:phase1Fixture -AsPlainText -Force
}
& 'HELPER_PATH' -Action set
'@
    $body = $body.Replace('FIXTURE_VALUE', $fixture).Replace('HELPER_PATH', $helper.Replace("'", "''"))
    $created = Invoke-Child @('-Command', $body)
    Assert-That ($created.ExitCode -eq 0) 'Synthetic hidden-input save failed'
    $fixtureBlob = [Environment]::GetEnvironmentVariable($name, 'User')
    Assert-That (-not [string]::IsNullOrWhiteSpace($fixtureBlob) -and -not $fixtureBlob.Contains($fixture)) 'Storage is absent or exposes plaintext'
    $secure = ConvertTo-SecureString -String $fixtureBlob
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    Assert-That ([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) -eq $fixture) 'Windows DPAPI roundtrip failed'
    $status = Invoke-Child @('-File', $helper, '-Action', 'status')
    Assert-That ($status.ExitCode -eq 0 -and $status.Out.Contains('EncryptedCredentialAvailable=True')) 'Saved-key status failed'
    $duplicate = Invoke-Child @('-File', $helper, '-Action', 'set')
    Assert-That ($duplicate.ExitCode -ne 0) 'Existing key was silently overwritten'
    Assert-That ([Environment]::GetEnvironmentVariable($name, 'User') -eq $fixtureBlob) 'Saved value changed on refused replacement'
    $clear = Invoke-Child @('-File', $helper, '-Action', 'clear')
    Assert-That ($clear.ExitCode -eq 0 -and [string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($name, 'User'))) 'Clear did not remove its exact entry'
    Assert-That (@(Get-ChildItem -LiteralPath $runtime -Filter '*.json').Count -eq $before) 'Credential tests started a runtime'
    Write-Host 'Credential checks passed: masked-input contract, encrypted roundtrip, no plaintext output, no overwrite, missing-key refusal, exact cleanup; zero live calls.'
}
finally {
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($null -ne $secure) { $secure.Dispose() }
    $current = [Environment]::GetEnvironmentVariable($name, 'User')
    if ($null -ne $fixtureBlob -and $current -eq $fixtureBlob) { [Environment]::SetEnvironmentVariable($name, $null, 'User') }
}
