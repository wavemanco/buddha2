#requires -Version 7.5
<#
.SYNOPSIS
Rehearse optional late human evidence using synthetic forms and public offline commands.
.DESCRIPTION
All four paths are relative to the new project's runs directory. Run only after
the final all-ten-head fixture matrix and benchmark report exist. No reader is
contacted, no actual human claim is made, and no execution/grant command is used.
.EXAMPLE
pwsh -NoProfile -File evidence/phase2-release-r018/late_human_rehearsal.ps1 `
  -Study phase2-release-r018/frozen-study/study.json `
  -Run phase2-release-r018/STUDY_SHA/mock `
  -Benchmark phase2-release-r018/benchmark `
  -Output phase2-release-r018/late-human-rehearsal
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $Study,
    [Parameter(Mandatory = $true)][string] $Run,
    [Parameter(Mandatory = $true)][string] $Benchmark,
    [Parameter(Mandatory = $true)][string] $Output
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = 'C:\Users\arvik\code\research\Buddha2'
$runsRoot = Join-Path $projectRoot 'runs'
$utf8 = [Text.UTF8Encoding]::new($false)
$commands = [Collections.Generic.List[object]]::new()

function Assert-NoLink([string] $Path) {
    $ancestor = [IO.DirectoryInfo]::new($Path)
    while ($null -ne $ancestor) {
        if ((Test-Path -LiteralPath $ancestor.FullName) -and
            ((Get-Item -LiteralPath $ancestor.FullName -Force).Attributes -band
                [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Approved paths cannot traverse links' }
        $ancestor = $ancestor.Parent
    }
}

function Resolve-RunPath([string] $Relative, [bool] $MustExist = $true) {
    $relativePath = $Relative.Replace('\', '/')
    if ($relativePath -notmatch '^phase2-release-r018/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$' -or
        @($relativePath.Split('/') | Where-Object { $_ -in @('.', '..') }).Count -ne 0) {
        throw 'Supply a runs-relative phase2-release-r018 path without traversal'
    }
    $resolved = [IO.Path]::GetFullPath((Join-Path $runsRoot $relativePath))
    if (-not $resolved.StartsWith($runsRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Path leaves approved run storage'
    }
    Assert-NoLink $resolved
    if ($MustExist -and -not (Test-Path -LiteralPath $resolved)) { throw "Missing input: $relativePath" }
    return $resolved
}

function Read-Json([string] $Path) {
    return [IO.File]::ReadAllText($Path, $utf8) | ConvertFrom-Json -AsHashtable -Depth 100 -DateKind String
}

function Write-TextNew([string] $Path, [string] $Text) {
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path))
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = $utf8.GetBytes($Text + "`n")
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    }
    finally { $stream.Dispose() }
}

function Write-JsonNew([string] $Path, [object] $Value) {
    Write-TextNew $Path (ConvertTo-Json -InputObject $Value -Depth 100)
}

function Assert-True([bool] $Condition, [string] $Message) {
    if (-not $Condition) { throw $Message }
}

function Assert-SameJson([object] $Left, [object] $Right, [string] $Message) {
    Assert-True ((ConvertTo-Json -InputObject $Left -Depth 100 -Compress) -ceq
                (ConvertTo-Json -InputObject $Right -Depth 100 -Compress)) $Message
}

function File-Hash([string] $Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Protected-Hashes {
    $hashes = [ordered]@{}
    foreach ($root in @(@{ Label = 'run'; Path = $runPath }, @{ Label = 'benchmark'; Path = $benchmarkPath })) {
        $pending = [Collections.Generic.Stack[string]]::new()
        $pending.Push($root.Path)
        while ($pending.Count -gt 0) {
            foreach ($item in Get-ChildItem -LiteralPath ($pending.Pop()) -Force | Sort-Object Name) {
                if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                    throw 'Protected evidence contains a link'
                }
                if ($item.PSIsContainer) { $pending.Push($item.FullName) }
                else {
                    $name = $root.Label + '/' + [IO.Path]::GetRelativePath($root.Path, $item.FullName).Replace('\', '/')
                    $hashes.Add($name, (File-Hash $item.FullName))
                }
            }
        }
    }
    $hashes.Add('study.json', (File-Hash $studyPath))
    return $hashes
}

function Invoke-Public(
    [ValidateSet('human-packets', 'human-import', 'human-decide', 'report', 'replay')][string] $Operation,
    [string[]] $Arguments
) {
    $number = $commands.Count + 1
    $argumentsAll = @('-NoProfile', '-File', (Join-Path $projectRoot 'phase0.ps1'), 'run',
        'phase2-release', $Operation, '--study', $containerStudy, '--run', $containerRun, '--fixture') + $Arguments
    $log = Join-Path $outputPath ('commands/{0:d2}-{1}.log' -f $number, $Operation)
    $commandRecord = [ordered]@{
        operation = $Operation; arguments = $argumentsAll; cwd = $projectRoot
        log = [IO.Path]::GetRelativePath($outputPath, $log).Replace('\', '/'); exit_code = $null
    }
    $commands.Add($commandRecord)
    $lines = @(& (Join-Path $PSHOME 'pwsh.exe') @argumentsAll 2>&1)
    $commandRecord.exit_code = $LASTEXITCODE
    Write-TextNew $log (($lines | ForEach-Object { $_.ToString() }) -join "`n")
    Assert-True ($commandRecord.exit_code -eq 0) "Public $Operation failed; inspect $($commandRecord.log)"
}

function UTC([datetime] $Value) { return $Value.ToString('yyyy-MM-ddTHH:mm:ssZ', [Globalization.CultureInfo]::InvariantCulture) }

Assert-NoLink $projectRoot
Assert-True ([string]::Equals((Resolve-Path -LiteralPath $projectRoot).ProviderPath.TrimEnd('\'),
    $projectRoot, [StringComparison]::OrdinalIgnoreCase)) 'New-project root differs'
$studyPath = Resolve-RunPath $Study
$runPath = Resolve-RunPath $Run
$benchmarkPath = Resolve-RunPath $Benchmark
$outputPath = Resolve-RunPath $Output $false
Assert-True (-not (Test-Path -LiteralPath $outputPath)) 'Use a new immutable rehearsal output directory'
foreach ($protected in @($runPath, $benchmarkPath, [IO.Path]::GetDirectoryName($studyPath))) {
    Assert-True (-not ([string]::Equals($outputPath, $protected, [StringComparison]::OrdinalIgnoreCase) -or
        $outputPath.StartsWith($protected + '\', [StringComparison]::OrdinalIgnoreCase) -or
        $protected.StartsWith($outputPath + '\', [StringComparison]::OrdinalIgnoreCase))) 'Rehearsal output overlaps protected inputs'
}
$containerStudy = '/results/' + $Study.Replace('\', '/')
$containerRun = '/results/' + $Run.Replace('\', '/')
$containerBenchmark = '/results/' + $Benchmark.Replace('\', '/')
$containerOutput = '/results/' + $Output.Replace('\', '/')
$benchmarkDecision = Read-Json (Join-Path $benchmarkPath 'decision.json')
$benchmarkSummary = Read-Json (Join-Path $benchmarkPath 'summary.json')
$studyRecord = Read-Json $studyPath
Assert-True ($benchmarkDecision.fixture -eq $true -and $benchmarkSummary.fixture -eq $true -and
    $benchmarkDecision.track -ceq 'benchmark' -and $benchmarkDecision.native_complete -eq $true -and
    $benchmarkDecision.status -ceq 'complete-development' -and
    $benchmarkDecision.human_status -ceq 'not-required' -and $null -eq $benchmarkDecision.human_assessment_sha256 -and
    $benchmarkDecision.policy.human_required -eq $false -and
    $benchmarkDecision.study_sha256 -ceq $studyRecord.study_sha256 -and
    $benchmarkSummary.attempts -eq 1320 -and $benchmarkSummary.orders -eq 72 -and
    $benchmarkSummary.provider_calls -eq 0 -and $benchmarkSummary.reserved_micro_usd -eq 0) `
    'A complete all-ten-head, zero-human fixture benchmark is required'
$before = Protected-Hashes
[void][IO.Directory]::CreateDirectory($outputPath)
Write-JsonNew (Join-Path $outputPath 'before.json') @{ hashes = $before; summary = $benchmarkSummary }
$locationPushed = $false
try {
    Push-Location -LiteralPath $projectRoot
    $locationPushed = $true
    Invoke-Public 'replay' @('--output', "$containerOutput/baseline", '--cutoff', $benchmarkDecision.cutoff)
    Assert-True ((File-Hash (Join-Path $outputPath 'baseline/decision.json')) -ceq
        (File-Hash (Join-Path $benchmarkPath 'decision.json'))) 'Original benchmark does not exactly replay'
    Invoke-Public 'human-packets' @('--output', "$containerOutput/packets", '--cutoff', $benchmarkDecision.cutoff)

    # The chronology is deliberately fabricated after the benchmark cutoff.
    $baseDay = [datetime]::ParseExact($benchmarkDecision.cutoff, 'yyyy-MM-ddTHH:mm:ssZ',
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal).Date.AddDays(1)
    $dueDay = $baseDay.AddDays(1)
    $closedCutoff = UTC ($dueDay.AddDays(1).AddSeconds(-1))
    $lateCutoff = UTC ($dueDay.AddDays(3).AddHours(12))
    $window = [ordered]@{}
    $submissions = @{}
    foreach ($reader in @('fixture-R1', 'fixture-R2')) {
        $form = Read-Json (Join-Path $outputPath "packets/$reader.json")
        Assert-True ($form.fixture -eq $true -and $form.planning_only -eq $false -and
            $form.reader_id -ceq $reader -and $form.study_sha256 -ceq $studyRecord.study_sha256) 'Packet is not the exact execution fixture'
        $form.reader_reference = "synthetic-$reader-no-real-reader"
        foreach ($key in @($form.eligibility.Keys)) { $form.eligibility[$key] = $key -cne 'actual_human' }
        $form.delivered_on = $baseDay.ToString('yyyy-MM-dd')
        $form.due_date = $dueDay.ToString('yyyy-MM-dd')
        foreach ($row in $form.judgments) {
            $row.status = 'acceptable'
            $row.reason = 'Synthetic software example; no actual reader or quality judgment.'
            $row.task_fitness_notes = 'Synthetic fit note; not human evidence.'
            $row.variety_notes = 'Synthetic variety note; not human evidence.'
            $row.duplication_notes = 'Synthetic duplication note; not human evidence.'
            $row.recognition = $false
            $row.missing_context = $false
        }
        $delivered = UTC ($baseDay.AddHours(10))
        $window[$reader] = @{ delivered_at = $delivered; due_date = $form.due_date }
        $submissions[$reader] = @{
            form = $form; delivered_at = $delivered
            first_exposed_at = UTC ($baseDay.AddHours($(if ($reader -ceq 'fixture-R1') { 11 } else { 13 })))
            received_at = UTC ($dueDay.AddDays($(if ($reader -ceq 'fixture-R1') { 0 } else { 2 })).AddHours(12))
        }
    }
    # Fabricate one concern to demonstrate a distinct branch, using only the
    # separate private fixture mapping; reader-facing packet identities stay fixed.
    $mapping = Read-Json (Join-Path $outputPath 'packets/private/unit-mapping.json')
    $concern = @($mapping | Where-Object {
        $_.reader_id -ceq 'fixture-R2' -and $_.method -ceq $benchmarkDecision.synthetic_selected_method
    })[0]
    $concernRow = @($submissions['fixture-R2'].form.judgments | Where-Object unit_id -CEQ $concern.unit_id)[0]
    $concernRow.status = 'substantive concern'
    $concernRow.reason = 'Deliberately fabricated concern to exercise separate selection; no human evidence.'
    Write-JsonNew (Join-Path $outputPath 'inputs/window.json') $window
    Write-JsonNew (Join-Path $outputPath 'inputs/on-time.json') @($submissions['fixture-R1'])
    Write-JsonNew (Join-Path $outputPath 'inputs/late.json') @($submissions['fixture-R2'])

    Invoke-Public 'human-import' @('--submissions', "$containerOutput/inputs/on-time.json", '--window',
        "$containerOutput/inputs/window.json", '--cutoff', $closedCutoff, '--output', "$containerOutput/closed")
    $closedPath = Join-Path $outputPath 'closed/human-assessment.json'
    $closed = Read-Json $closedPath
    $closedHash = File-Hash $closedPath
    Assert-True ($closed.version -eq 1 -and $closed.complete -eq $false -and $closed.selection_inconclusive -eq $true -and
        @($closed.missing_readers).Count -eq 1 -and $closed.missing_readers[0] -ceq 'fixture-R2' -and
        $closed.window_closed_by_reader['fixture-R1'] -eq $true -and
        $closed.window_closed_by_reader['fixture-R2'] -eq $true) 'Closed-window missingness was lost'
    Invoke-Public 'human-decide' @('--human-assessment', "$containerOutput/closed/human-assessment.json",
        '--parent', "$containerBenchmark/decision.json", '--cutoff', (UTC ($dueDay.AddDays(1))),
        '--output', "$containerOutput/pending")
    $pending = Read-Json (Join-Path $outputPath 'pending/decision.json')
    Assert-True ($pending.track -ceq 'human-augmented' -and $pending.status -ceq 'inconclusive' -and
        $pending.human_status -ceq 'inconclusive' -and
        $pending.parent_decision_sha256 -ceq $benchmarkDecision.decision_sha256) 'Missing readers incorrectly produced a human conclusion'

    Invoke-Public 'human-import' @('--submissions', "$containerOutput/inputs/late.json", '--previous',
        "$containerOutput/closed/human-assessment.json", '--cutoff', $lateCutoff, '--output', "$containerOutput/late")
    $late = Read-Json (Join-Path $outputPath 'late/human-assessment.json')
    Assert-True ($late.version -eq 2 -and $late.complete -eq $true -and $late.selection_inconclusive -eq $false -and
        @($late.submissions).Count -eq 2 -and @($late.late_reader_ids).Count -eq 1 -and
        $late.late_reader_ids[0] -ceq 'fixture-R2' -and
        $late.previous_assessment_sha256 -ceq $closed.assessment_sha256 -and
        $benchmarkDecision.synthetic_selected_method -cnotin $late.eligible_methods) 'Late supplement lost predecessor or concern'
    Assert-SameJson $late.previous $closed 'Supplement altered the closed assessment'
    Assert-SameJson $late.submissions[0] $closed.submissions[0] 'Supplement altered the original R1 submission'
    Assert-SameJson $late.window $closed.window 'Supplement changed the original window'
    Assert-True ((File-Hash $closedPath) -ceq $closedHash) 'Closed assessment file changed'
    Invoke-Public 'human-decide' @('--human-assessment', "$containerOutput/late/human-assessment.json",
        '--parent', "$containerBenchmark/decision.json", '--cutoff', (UTC ($dueDay.AddDays(4).AddHours(12))),
        '--output', "$containerOutput/human")
    $human = Read-Json (Join-Path $outputPath 'human/decision.json')
    Assert-True ($human.track -ceq 'human-augmented' -and $human.status -ceq 'complete-development' -and
        $human.human_status -ceq 'complete' -and $human.fixture -eq $true -and $null -eq $human.selected_method -and
        $human.synthetic_selected_method -cne $benchmarkDecision.synthetic_selected_method -and
        $human.parent_decision_sha256 -ceq $benchmarkDecision.decision_sha256 -and
        $human.benchmark_decision_sha256 -ceq $benchmarkDecision.decision_sha256 -and
        $human.execution_sha256 -ceq $benchmarkDecision.execution_sha256 -and
        $human.native_evidence_sha256 -ceq $benchmarkDecision.native_evidence_sha256) 'Late human decision is not a separate compatible fixture branch'

    Invoke-Public 'report' @('--output', "$containerOutput/benchmark-replay", '--cutoff', $benchmarkDecision.cutoff)
    $afterSummary = Read-Json (Join-Path $outputPath 'benchmark-replay/summary.json')
    Assert-SameJson $afterSummary $benchmarkSummary 'Benchmark summary or request count changed'
    Assert-True ((File-Hash (Join-Path $outputPath 'benchmark-replay/decision.json')) -ceq
        (File-Hash (Join-Path $benchmarkPath 'decision.json'))) 'Original zero-human decision changed'
    $after = Protected-Hashes
    Write-JsonNew (Join-Path $outputPath 'after.json') @{ hashes = $after; summary = $afterSummary }
    Assert-SameJson $after $before 'Protected study, journal, portfolios, assessments or benchmark files changed'
    Write-JsonNew (Join-Path $outputPath 'PASS.json') ([ordered]@{
        kind = 'p2r-optional-late-human-public-cli-rehearsal'; status = 'pass'; fixture = $true
        study_sha256 = $studyRecord.study_sha256; source_script_sha256 = File-Hash $PSCommandPath
        benchmark_decision_sha256 = $benchmarkDecision.decision_sha256
        pending_decision_sha256 = $pending.decision_sha256; human_decision_sha256 = $human.decision_sha256
        first_human_assessment_sha256 = $closed.assessment_sha256; supplement_sha256 = $late.assessment_sha256
        attempts_before = $benchmarkSummary.attempts; attempts_after = $afterSummary.attempts
        new_requests = 0; provider_calls = 0; experiment_api_spend_micro_usd = 0; actual_humans = 0
        preserved_file_count = $before.Count; immutable_inputs_unchanged = $true
        closed_window_missingness_preserved = $true; late_original_appended = $true
        separate_human_decision = $true; commands = $commands.ToArray()
        limitations = 'All forms, timings and concern are synthetic; this proves software compatibility, not human validity.'
    })
    Write-Output "PASS: $outputPath (synthetic only; 0 new requests; original benchmark unchanged)"
}
catch {
    Write-JsonNew (Join-Path $outputPath 'FAIL.json') @{
        kind = 'p2r-optional-late-human-public-cli-rehearsal'; status = 'fail'; fixture = $true
        error = $_.Exception.Message; commands = $commands.ToArray()
    }
    throw
}
finally { if ($locationPushed) { Pop-Location } }
