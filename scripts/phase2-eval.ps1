param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$DocumentsDir = "samples/documents/demo",
    [string]$QueriesFile = "samples/queries/demo-queries.json",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-phase2",
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[phase2-eval] $Message"
}

function Fail {
    param([string]$Message)
    throw "[phase2-eval] $Message"
}

if (-not (Test-Path -LiteralPath $DocumentsDir)) {
    Fail "Documents directory not found: $DocumentsDir"
}
if (-not (Test-Path -LiteralPath $QueriesFile)) {
    Fail "Queries file not found: $QueriesFile"
}

Write-Step "checking API health"
$healthDeadline = (Get-Date).AddSeconds(30)
$health = $null
while ((Get-Date) -lt $healthDeadline) {
    try {
        $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
        if ($health.status -eq "ok") {
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}
if ($null -eq $health -or $health.status -ne "ok") {
    Fail "API health check failed after waiting"
}

if ($KnowledgeBaseId -eq "kb-phase2") {
    $KnowledgeBaseId = "kb-phase2-$([guid]::NewGuid().ToString("N").Substring(0, 12))"
}

$documents = Get-ChildItem -LiteralPath $DocumentsDir -File | Sort-Object Name
foreach ($document in $documents) {
    Write-Step "uploading $($document.Name)"
    $uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId" -F "file=@$($document.FullName)"
    if ($LASTEXITCODE -ne 0) {
        Fail "curl upload failed for $($document.Name) with exit code $LASTEXITCODE"
    }
    $upload = $uploadRaw | ConvertFrom-Json
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $job = $null
    while ((Get-Date) -lt $deadline) {
        $job = Invoke-RestMethod -Uri "$BaseUrl/api/v1/jobs/$($upload.job_id)" -Method Get
        if ($job.status -eq "SUCCEEDED") {
            break
        }
        if ($job.status -eq "FAILED") {
            Fail "Job failed for $($document.Name): $($job.error_message)"
        }
        Start-Sleep -Seconds 2
    }
    if ($null -eq $job -or $job.status -ne "SUCCEEDED") {
        Fail "Job did not finish within $TimeoutSeconds seconds for $($document.Name)"
    }
}

$queries = Get-Content -LiteralPath $QueriesFile -Raw -Encoding UTF8 | ConvertFrom-Json
$modes = @("semantic", "keyword", "hybrid")
$results = @()

foreach ($queryCase in $queries) {
    foreach ($mode in $modes) {
        Write-Step "searching $($queryCase.id) mode=$mode"
        $body = @{
            query = $queryCase.query
            tenant_id = $TenantId
            knowledge_base_ids = @($KnowledgeBaseId)
            search_mode = $mode
            top_k = 5
            recall_size = 30
            pre_rank_size = 10
            dedup_enabled = $true
            diversity_enabled = $true
            max_chunks_per_document = 2
            rerank_enabled = $true
            rerank_size = 5
        } | ConvertTo-Json

        $search = Invoke-RestMethod -Uri "$BaseUrl/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $body
        $combinedContent = (($search.items | ForEach-Object { $_.content }) -join "`n")
        $matchedKeywords = @()
        foreach ($keyword in $queryCase.expected_keywords) {
            if ($combinedContent -like "*$keyword*") {
                $matchedKeywords += $keyword
            }
        }
        $recallSources = @($search.items | ForEach-Object { $_.recall_sources } | ForEach-Object { $_ } | Sort-Object -Unique)
        $results += [pscustomobject]@{
            id = $queryCase.id
            search_mode = $mode
            passed = $matchedKeywords.Count -gt 0
            matched_keywords = $matchedKeywords
            result_count = $search.items.Count
            recall_sources = $recallSources
            semantic_recall_count = $search.search_plan.semantic_recall_count
            keyword_recall_count = $search.search_plan.keyword_recall_count
            merged_count = $search.search_plan.merged_count
            business_filtered_count = $search.search_plan.business_filtered_count
            dedup_removed_count = $search.search_plan.dedup_removed_count
            document_limit_removed_count = $search.search_plan.document_limit_removed_count
            rerank_enabled = $search.search_plan.rerank_enabled
            rerank_degraded = $search.search_plan.rerank_degraded
            rerank_score_count = @($search.items | Where-Object { $null -ne $_.rerank_score }).Count
            max_document_result_count = @(
                $search.items |
                    Group-Object -Property document_version_id |
                    ForEach-Object { $_.Count } |
                    Sort-Object -Descending |
                    Select-Object -First 1
            )[0]
            first_result = if ($search.items.Count -gt 0) { $search.items[0].content } else { "" }
        }
    }
}

$failed = @($results | Where-Object { -not $_.passed })
$hybridWithoutKeyword = @(
    $results | Where-Object {
        $_.search_mode -eq "hybrid" -and $_.recall_sources -notcontains "keyword"
    }
)
$documentLimitViolations = @(
    $results | Where-Object {
        $_.max_document_result_count -gt 2
    }
)
$rerankMissing = @(
    $results | Where-Object {
        -not $_.rerank_enabled -or $_.rerank_degraded -or $_.rerank_score_count -lt 1
    }
)

$summary = [pscustomobject]@{
    knowledge_base_id = $KnowledgeBaseId
    uploaded_documents = $documents.Count
    query_count = @($queries).Count
    mode_count = $modes.Count
    check_count = $results.Count
    passed_count = @($results | Where-Object { $_.passed }).Count
    failed_count = $failed.Count
    hybrid_without_keyword_count = $hybridWithoutKeyword.Count
    document_limit_violation_count = $documentLimitViolations.Count
    rerank_missing_count = $rerankMissing.Count
    results = $results
}

if ($failed.Count -gt 0) {
    $summary | ConvertTo-Json -Depth 10
    Fail "Phase 2 evaluation failed for $($failed.Count) mode/query case(s)"
}
if ($hybridWithoutKeyword.Count -gt 0) {
    $summary | ConvertTo-Json -Depth 10
    Fail "Hybrid search did not include keyword recall for $($hybridWithoutKeyword.Count) query case(s)"
}
if ($documentLimitViolations.Count -gt 0) {
    $summary | ConvertTo-Json -Depth 10
    Fail "Document limit failed for $($documentLimitViolations.Count) mode/query case(s)"
}
if ($rerankMissing.Count -gt 0) {
    $summary | ConvertTo-Json -Depth 10
    Fail "Rerank did not produce scores for $($rerankMissing.Count) mode/query case(s)"
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
