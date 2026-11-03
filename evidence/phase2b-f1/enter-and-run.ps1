#requires -Version 7.2
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = 'C:\Users\arvik\code\research\Buddha2'
if ((Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).ProviderPath -ne $projectRoot) {
    throw 'This operator command belongs only to the new Buddha2 project'
}
Set-Location -LiteralPath $projectRoot
$authorizationPath = Join-Path $PSScriptRoot 'authorization.json'
$authorization = Get-Content -LiteralPath $authorizationPath -Raw -Encoding utf8 | ConvertFrom-Json
if ($authorization.stage -cne 'first' -or $authorization.cumulative_cap_micro_usd -ne 20000000 -or
        $authorization.expansion_authorized -ne $false -or $authorization.max_request_slots -ne 55) {
    throw 'The recorded authorization differs from P2B-F1/$20/first-stage-only'
}
$attestationPath = Join-Path $PSScriptRoot 'operator-attestation.json'
if (Test-Path -LiteralPath $attestationPath) {
    throw 'This one-time operator entry was already used. Let Codex inspect the saved state before resuming.'
}
Write-Host 'Your $20 first-block authorization is recorded. Expansion is excluded.'
Write-Host 'Confirm the account/profile facts required by the frozen runbook:'
Write-Host 'Both keys are direct Anthropic/OpenAI API keys using public PAYG pricing, standard processing, and no private/premium/custom endpoint overrides.'
Write-Host 'The accounts are intended to provide Sonnet 5.5, Opus 5 and GPT-5.6 Luna; actual access/settings/usage will be observed only in this counted block.'
Write-Host 'Current ordinary input/output USD per million: Sonnet 2/10, Opus 5/25, Luna 0.20/1.20; cache/regional terms are in price-refresh.json and the frozen review.'
if ((Read-Host 'Type YES only if these account/profile facts apply; anything else stops') -cne 'YES') {
    throw 'Account/profile facts were not confirmed. No grant, credential read or provider call was made.'
}
$attestation = [ordered]@{
    kind = 'p2bf1-operator-profile-attestation-v1'
    confirmed_at_utc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    authorization_file_sha256 = (Get-FileHash -LiteralPath $authorizationPath -Algorithm SHA256).Hash.ToLowerInvariant()
    price_refresh_file_sha256 = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'price-refresh.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    study_sha256 = $authorization.study_sha256
    direct_public_payg_standard_profile_confirmed = $true
    current_public_prices_confirmed = $true
    named_models_intended_available = $true
    independent_account_access_verified = $false
    api_keys_stored = $false
    scope = 'first block only; cumulative $20; no expansion or extra probes'
}
New-Item -ItemType File -Path $attestationPath -Value ($attestation | ConvertTo-Json -Depth 8) -ErrorAction Stop | Out-Null
& .\phase0.ps1 run phase2-release grant-template `
    --study /results/phase2-release-r018/release/study.json --stage first `
    --grant-id live-first-001 --cap-micro-usd 20000000 `
    --authorize-live --confirm-public-payg `
    --output /results/phase2-release-r018/grants/live-first-001
if ($LASTEXITCODE -ne 0) { throw 'Grant preparation stopped. Do not enter keys or rerun this operator entry.' }
Write-Host 'The unchanged launcher will verify the actual container before its two masked key prompts.'
Write-Host 'Paste keys only at those prompts. They are not stored in environment variables, files or command history.'
& pwsh -NoProfile -File .\phase2-release.ps1 -Action provider -Live `
    -Study phase2-release-r018/release/study.json `
    -Grant phase2-release-r018/grants/live-first-001/grant.json -Stage first
exit $LASTEXITCODE
