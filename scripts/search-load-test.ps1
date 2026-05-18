param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-load-test",
    [string]$SampleFile = "samples/documents/smoke.txt",
    [int]$UploadCount = 3,
    [int]$SearchCount = 20,
    [int]$Concurrency = 4,
    [int]$TimeoutSeconds = 90,
    [switch]$RerankEnabled,
    [int]$RerankSize = 5,
    [string]$OutputJson = "docs/codex/v1/trace/data-cleaning-rag-load-test-report.json",
    [string]$OutputMarkdown = "docs/codex/v1/trace/data-cleaning-rag-load-test-report.md"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[search-load-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[search-load-test] $Message"
}

function Get-Percentile {
    param(
        [double[]]$Values,
        [double]$Percentile
    )
    if ($Values.Count -eq 0) {
        return $null
    }
    $sorted = @($Values | Sort-Object)
    $index = [Math]::Ceiling(($Percentile / 100.0) * $sorted.Count) - 1
    $index = [Math]::Max(0, [Math]::Min($index, $sorted.Count - 1))
    return [Math]::Round([double]$sorted[$index], 2)
}

function Wait-JobSucceeded {
    param([string]$JobId)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $job = $null
    while ((Get-Date) -lt $deadline) {
        $job = Invoke-RestMethod -Uri "$BaseUrl/api/v1/jobs/$JobId" -Method Get
        if ($job.status -eq "SUCCEEDED") {
            return $job
        }
        if ($job.status -eq "FAILED") {
            Fail "Job failed: $($job.error_message)"
        }
        Start-Sleep -Seconds 2
    }
    Fail "Job did not finish within $TimeoutSeconds seconds. Last status: $($job.status)"
}

function Write-Reports {
    param([pscustomobject]$Report)
    $jsonParent = Split-Path -Parent $OutputJson
    if ($jsonParent -and -not (Test-Path -LiteralPath $jsonParent)) {
        New-Item -ItemType Directory -Path $jsonParent -Force | Out-Null
    }
    $Report | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutputJson -Encoding UTF8

    $lines = @()
    $lines += "# Data Cleaning RAG Load Test Report"
    $lines += ""
    $lines += "- Generated at: $($Report.generated_at)"
    $lines += "- Knowledge base: ``$($Report.knowledge_base_id)``"
    $lines += "- Upload count: $($Report.upload.count)"
    $lines += "- Search count: $($Report.search.count)"
    $lines += "- Search concurrency: $($Report.search.concurrency)"
    $lines += ""
    $lines += "## Summary"
    $lines += ""
    $lines += "| Metric | Value |"
    $lines += "| --- | ---: |"
    $lines += "| Upload throughput docs/sec | $($Report.upload.throughput_docs_per_sec) |"
    $lines += "| Upload P50 ms | $($Report.upload.p50_ms) |"
    $lines += "| Upload P95 ms | $($Report.upload.p95_ms) |"
    $lines += "| Search QPS | $($Report.search.qps) |"
    $lines += "| Search P50 ms | $($Report.search.p50_ms) |"
    $lines += "| Search P95 ms | $($Report.search.p95_ms) |"
    $lines += "| Search P99 ms | $($Report.search.p99_ms) |"
    $lines += "| Search failures | $($Report.search.failure_count) |"
    $lines += "| Rerank enabled | $($Report.rerank.enabled) |"
    $lines += "| Rerank provider | $($Report.rerank.provider) |"
    $lines += "| Rerank degraded count | $($Report.rerank.degraded_count) |"
    $lines += "| Avg rerank score count | $($Report.rerank.average_score_count) |"
    $lines += ""
    $lines += "## Recommendation"
    $lines += ""
    $lines += "- PoC baseline: keep concurrency modest and verify P95 latency with customer sample documents."
    $lines += "- Production sizing should rerun this script with larger documents, realistic query mixes, and the selected embedding/rerank provider."
    $mdParent = Split-Path -Parent $OutputMarkdown
    if ($mdParent -and -not (Test-Path -LiteralPath $mdParent)) {
        New-Item -ItemType Directory -Path $mdParent -Force | Out-Null
    }
    Set-Content -LiteralPath $OutputMarkdown -Encoding UTF8 -Value ($lines -join "`n")
}

if (-not (Test-Path -LiteralPath $SampleFile)) {
    Fail "Sample file not found: $SampleFile"
}

Write-Step "checking API health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "ok") {
    Fail "API health check failed: $($health | ConvertTo-Json -Compress)"
}

$uploads = @()
$uploadLatencies = @()
$uploadTotal = [System.Diagnostics.Stopwatch]::StartNew()
for ($i = 1; $i -le $UploadCount; $i++) {
    Write-Step "uploading sample $i/$UploadCount"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$SampleFile"
    $sw.Stop()
    if ($LASTEXITCODE -ne 0) {
        Fail "curl upload failed with exit code $LASTEXITCODE"
    }
    $upload = $uploadRaw | ConvertFrom-Json
    $uploads += $upload
    $uploadLatencies += $sw.Elapsed.TotalMilliseconds
}
foreach ($upload in $uploads) {
    Wait-JobSucceeded -JobId $upload.job_id | Out-Null
}
$uploadTotal.Stop()

$searchBody = @{
    query = "recall pre-ranking rerank candidate set"
    tenant_id = $TenantId
    knowledge_base_ids = @($KnowledgeBaseId)
    permission_context = @("public")
    search_mode = "hybrid"
    top_k = 5
    recall_size = 30
    pre_rank_size = 10
    dedup_enabled = $true
    diversity_enabled = $true
    rerank_enabled = [bool]$RerankEnabled
    rerank_size = $RerankSize
} | ConvertTo-Json

$searchLatencies = @()
$failureCount = 0
$rerankProviders = @()
$rerankDegradedCount = 0
$rerankScoreCounts = @()
$searchTotal = [System.Diagnostics.Stopwatch]::StartNew()
$remaining = $SearchCount
while ($remaining -gt 0) {
    $batchSize = [Math]::Min($Concurrency, $remaining)
    $jobs = @()
    for ($i = 0; $i -lt $batchSize; $i++) {
        $jobs += Start-Job -ArgumentList $BaseUrl, $searchBody -ScriptBlock {
            param($JobBaseUrl, $JobSearchBody)
            $sw = [System.Diagnostics.Stopwatch]::StartNew()
            try {
                $search = Invoke-RestMethod -Uri "$JobBaseUrl/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $JobSearchBody
                $ok = $true
                $errorMessage = $null
                $rerankProvider = $search.search_plan.rerank_provider
                $rerankDegraded = [bool]$search.search_plan.rerank_degraded
                $rerankScoreCount = @($search.items | Where-Object { $null -ne $_.rerank_score }).Count
            } catch {
                $ok = $false
                $errorMessage = $_.Exception.Message
                $rerankProvider = $null
                $rerankDegraded = $false
                $rerankScoreCount = 0
            }
            $sw.Stop()
            [pscustomobject]@{
                ok = $ok
                latency_ms = [Math]::Round($sw.Elapsed.TotalMilliseconds, 2)
                error = $errorMessage
                rerank_provider = $rerankProvider
                rerank_degraded = $rerankDegraded
                rerank_score_count = $rerankScoreCount
            }
        }
    }
    Wait-Job -Job $jobs | Out-Null
    foreach ($job in $jobs) {
        $result = Receive-Job -Job $job
        Remove-Job -Job $job
        $searchLatencies += [double]$result.latency_ms
        if (-not $result.ok) {
            $failureCount += 1
        }
        if ($result.rerank_provider) {
            $rerankProviders += [string]$result.rerank_provider
        }
        if ($result.rerank_degraded) {
            $rerankDegradedCount += 1
        }
        $rerankScoreCounts += [double]$result.rerank_score_count
    }
    $remaining -= $batchSize
}
$searchTotal.Stop()

$report = [pscustomobject]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    tenant_id = $TenantId
    knowledge_base_id = $KnowledgeBaseId
    upload = [pscustomobject]@{
        count = $UploadCount
        total_seconds = [Math]::Round($uploadTotal.Elapsed.TotalSeconds, 2)
        throughput_docs_per_sec = if ($uploadTotal.Elapsed.TotalSeconds -gt 0) { [Math]::Round($UploadCount / $uploadTotal.Elapsed.TotalSeconds, 4) } else { 0 }
        p50_ms = Get-Percentile -Values ([double[]]$uploadLatencies) -Percentile 50
        p95_ms = Get-Percentile -Values ([double[]]$uploadLatencies) -Percentile 95
        p99_ms = Get-Percentile -Values ([double[]]$uploadLatencies) -Percentile 99
    }
    search = [pscustomobject]@{
        count = $SearchCount
        concurrency = $Concurrency
        total_seconds = [Math]::Round($searchTotal.Elapsed.TotalSeconds, 2)
        qps = if ($searchTotal.Elapsed.TotalSeconds -gt 0) { [Math]::Round($SearchCount / $searchTotal.Elapsed.TotalSeconds, 4) } else { 0 }
        failure_count = $failureCount
        p50_ms = Get-Percentile -Values ([double[]]$searchLatencies) -Percentile 50
        p95_ms = Get-Percentile -Values ([double[]]$searchLatencies) -Percentile 95
        p99_ms = Get-Percentile -Values ([double[]]$searchLatencies) -Percentile 99
    }
    rerank = [pscustomobject]@{
        enabled = [bool]$RerankEnabled
        size = $RerankSize
        provider = if ($rerankProviders.Count -gt 0) { (@($rerankProviders | Select-Object -First 1)[0]) } else { "" }
        degraded_count = $rerankDegradedCount
        average_score_count = if ($rerankScoreCounts.Count -gt 0) { [Math]::Round((($rerankScoreCounts | Measure-Object -Average).Average), 2) } else { 0 }
    }
}

Write-Reports -Report $report
Write-Step "report written"
$report | ConvertTo-Json -Depth 10
