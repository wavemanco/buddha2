#requires -Version 7.2
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
if ($root -ne 'C:\Users\arvik\code\research\Buddha2') { throw 'Handshake checks require the research checkout' }
$target = Join-Path $root 'phase3b-seq2-core.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($target, [ref]$tokens, [ref]$errors)
if ($errors.Count -ne 0) { throw 'Current launcher does not parse' }
$names = @('Assert-NoReparse', 'Get-ProviderHandshake', 'Get-FrozenHelperBlock')
$functions = @($ast.EndBlock.Statements | Where-Object {
    $_ -is [Management.Automation.Language.FunctionDefinitionAst] -and $_.Name -cin $names
})
if ($functions.Count -ne $names.Count) { throw 'Shared host function inventory differs' }
. ([ScriptBlock]::Create((($functions | ForEach-Object { $_.Extent.Text }) -join "`n")))

$script:forbiddenCalls = 0
function Read-MaskedKey { $script:forbiddenCalls++; throw 'Credential access forbidden in handshake checks' }
function Read-Host { $script:forbiddenCalls++; throw 'Credential access forbidden in handshake checks' }
function Invoke-ProviderExecution { $script:forbiddenCalls++; throw 'Provider startup forbidden in handshake checks' }
function Invoke-Tool { $script:forbiddenCalls++; throw 'Process dispatch forbidden in handshake checks' }
function Assert-That([bool] $Condition, [string] $Message) { if (-not $Condition) { throw $Message } }
function Assert-Rejected([scriptblock] $Case, [string] $Pattern) {
    $caught = $false
    try { & $Case | Out-Null }
    catch { $caught = $_.Exception.Message -match $Pattern }
    Assert-That $caught 'Expected shared-consumer rejection did not occur'
}

$output = Join-Path $root ('runs\phase3b-seq2-v1\remaining-pairs-v1\host-handshake-tests\' + [Guid]::NewGuid().ToString('N'))
Assert-NoReparse $output
[void][IO.Directory]::CreateDirectory($output)
$inspection = Join-Path $output 'inspection.fixture.json'
$expected = 'a' * 64
[IO.File]::WriteAllText($inspection, ('{"inspection_sha256":"' + $expected + '"}'), [Text.UTF8Encoding]::new($false))
$legacy = @{ cap_micro_usd = 146435242; first_pair_cap_micro_usd = 26094077; readiness_included_micro_usd = 35000000 }
$remaining = @{ cap_micro_usd = 350000000; first_pair_cap_micro_usd = 350000000; readiness_included_micro_usd = 50000000 }
$checkedProfiles = @($legacy, $remaining,
    @{ cap_micro_usd = 15011727; first_pair_cap_micro_usd = 15011727; readiness_included_micro_usd = 0 })
foreach ($checkedProfile in $checkedProfiles) {
    Assert-That ((Get-ProviderHandshake $checkedProfile $inspection) -ceq $expected) 'Valid profile did not consume the inspection identity'
}
foreach ($field in @('cap_micro_usd', 'first_pair_cap_micro_usd', 'readiness_included_micro_usd')) {
    $missing = $remaining.Clone()
    $missing.Remove($field)
    Assert-Rejected { Get-ProviderHandshake $missing $inspection } 'preflight field'
}
foreach ($invalid in @('350000000', -1, $null, $true, 1.5)) {
    $wrong = $remaining.Clone()
    $wrong.cap_micro_usd = $invalid
    Assert-Rejected { Get-ProviderHandshake $wrong $inspection } 'preflight field'
}
Assert-Rejected { Get-ProviderHandshake $remaining (Join-Path $output 'auth.json') } 'Private path'
[IO.File]::WriteAllText($inspection, '{"inspection_sha256":"invalid"}', [Text.UTF8Encoding]::new($false))
Assert-Rejected { Get-ProviderHandshake $remaining $inspection } 'inspection identity'
Assert-That ($script:forbiddenCalls -eq 0) 'Pre-credential checks reached forbidden activity'

# Replace only OS process creation in the actual retained READY consumer, never its validation.
$retained = Get-FrozenHelperBlock (Join-Path $root 'phase2-release.ps1')
$readyFunction = @($retained.Ast.EndBlock.Statements | Where-Object {
    $_ -is [Management.Automation.Language.FunctionDefinitionAst] -and $_.Name -ceq 'Invoke-ProviderExecution'
})
Assert-That ($readyFunction.Count -eq 1) 'Retained READY consumer is not unique'
$readySource = $readyFunction[0].Extent.Text
$startLine = '$process = [Diagnostics.Process]::Start($start)'
Assert-That ([regex]::Matches($readySource, [regex]::Escape($startLine)).Count -eq 1) 'READY process-start boundary changed'
. ([ScriptBlock]::Create($readySource.Replace($startLine, '$process = $script:readyFixtureProcess')))
$script:readyKeyCalls = 0
$script:readyDisposed = 0
function Read-MaskedKey { $script:readyKeyCalls++; throw 'READY_CREDENTIAL_SENTINEL' }
function Set-ReadyFixture([string] $Frame) {
    $script:readyKeyCalls = 0
    $script:readyDisposed = 0
    $script:readyFixtureProcess = [pscustomobject]@{
        StandardOutput = [IO.StringReader]::new($Frame + "`n")
        StandardError = [IO.StringReader]::new('')
        StandardInput = [IO.StringWriter]::new()
    }
    $script:readyFixtureProcess | Add-Member -MemberType ScriptMethod -Name Dispose -Value { $script:readyDisposed++ }
}
$checkedReady = @{ study_sha256 = '1' * 64; grant_sha256 = '2' * 64 }
$inspectionReady = '3' * 64
$goodReady = @{ credential_input_ready = $true; study_sha256 = $checkedReady.study_sha256;
    grant_sha256 = $checkedReady.grant_sha256; host_inspection_sha256 = $inspectionReady }
Set-ReadyFixture ($goodReady | ConvertTo-Json -Compress)
Assert-Rejected { Invoke-ProviderExecution 'fixture-owned-process' $checkedReady $inspectionReady } 'READY_CREDENTIAL_SENTINEL'
Assert-That ($script:readyKeyCalls -eq 1 -and $script:readyDisposed -eq 1) 'Valid READY did not reach only the credential sentinel and cleanup'
$invalidReadyFrames = [Collections.Generic.List[string]]::new()
foreach ($field in @('study_sha256', 'grant_sha256', 'host_inspection_sha256')) {
    $badReady = $goodReady.Clone()
    $badReady[$field] = '0' * 64
    $invalidReadyFrames.Add(($badReady | ConvertTo-Json -Compress))
}
$badReady = $goodReady.Clone(); $badReady.credential_input_ready = $false
$invalidReadyFrames.Add(($badReady | ConvertTo-Json -Compress))
$badReady = $goodReady.Clone(); $badReady.Remove('grant_sha256')
$invalidReadyFrames.Add(($badReady | ConvertTo-Json -Compress))
foreach ($unexpected in @('runtime_sha256', 'request_sha256')) {
    $badReady = $goodReady.Clone(); $badReady[$unexpected] = '0' * 64
    $invalidReadyFrames.Add(($badReady | ConvertTo-Json -Compress))
}
$invalidReadyFrames.Add('{"credential_input_ready":')
foreach ($frame in $invalidReadyFrames) {
    Set-ReadyFixture $frame
    Assert-Rejected { Invoke-ProviderExecution 'fixture-owned-process' $checkedReady $inspectionReady } '.'
    Assert-That ($script:readyKeyCalls -eq 0 -and $script:readyDisposed -eq 1) 'Invalid READY reached credentials or skipped cleanup'
}
$result = [ordered]@{ kind = 'phase3b-shared-provider-handshake-component-check-v1'; passed = $true;
    positive_profiles = $checkedProfiles.Count; rejected_cases = 10; credential_or_dispatch_calls = $script:forbiddenCalls;
    valid_ready_reached_credential_sentinel = $true; invalid_ready_frames_rejected_before_credentials = $invalidReadyFrames.Count;
    ready_process_start_boundary_substituted = $true; real_keys_read = 0;
    fixture_only = $true; actual_prepared_kit_acceptance = $false }
[IO.File]::WriteAllText((Join-Path $output 'result.json'), (($result | ConvertTo-Json) + "`n"), [Text.UTF8Encoding]::new($false))
[Console]::Out.WriteLine(($result | ConvertTo-Json -Compress))
[Console]::Out.WriteLine(('Check record: ' + (Join-Path $output 'result.json')))
