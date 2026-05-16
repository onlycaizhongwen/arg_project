param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$DocumentsDir = "samples/documents/demo",
    [string]$QueriesFile = "samples/queries/demo-queries.json",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-demo",
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[demo-eval] $Message"
}

function Fail {
    param([string]$Message)
    throw "[demo-eval] $Message"
}

if (-not (Test-Path -LiteralPath $DocumentsDir)) {
    Fail "Documents directory not found: $DocumentsDir"
}
if (-not (Test-Path -LiteralPath $QueriesFile)) {
    Fail "Queries file not found: $QueriesFile"
}

Write-Step "checking API health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "ok") {
    Fail "API health check failed: $($health | ConvertTo-Json -Compress)"
}

$documents = Get-ChildItem -LiteralPath $DocumentsDir -File | Sort-Object Name
if ($documents.Count -lt 1) {
    Fail "No demo documents found in $DocumentsDir"
}

$uploads = @()
foreach ($document in $documents) {
    Write-Step "uploading $($document.Name)"
    $uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId" -F "file=@$($document.FullName)"
    if ($LASTEXITCODE -ne 0) {
        Fail "curl upload failed for $($document.Name) with exit code $LASTEXITCODE"
    }
    $upload = $uploadRaw | ConvertFrom-Json
    if (-not $upload.job_id) {
        Fail "Upload response does not contain job_id for $($document.Name): $uploadRaw"
    }
    $uploads += $upload
}

foreach ($upload in $uploads) {
    Write-Step "polling job $($upload.job_id)"
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $job = $null
    while ((Get-Date) -lt $deadline) {
        $job = Invoke-RestMethod -Uri "$BaseUrl/api/v1/jobs/$($upload.job_id)" -Method Get
        if ($job.status -eq "SUCCEEDED") {
            break
        }
        if ($job.status -eq "FAILED") {
            Fail "Job failed: $($job.error_message)"
        }
        Start-Sleep -Seconds 2
    }
    if ($null -eq $job -or $job.status -ne "SUCCEEDED") {
        Fail "Job did not finish within $TimeoutSeconds seconds. Last status: $($job.status)"
    }
}

$queries = Get-Content -LiteralPath $QueriesFile -Raw -Encoding UTF8 | ConvertFrom-Json
$results = @()
foreach ($queryCase in $queries) {
    Write-Step "searching $($queryCase.id)"
    $body = @{
        query = $queryCase.query
        tenant_id = $TenantId
        knowledge_base_ids = @($KnowledgeBaseId)
        search_mode = "hybrid"
        top_k = 5
        recall_size = 30
        pre_rank_size = 10
    } | ConvertTo-Json

    $search = Invoke-RestMethod -Uri "$BaseUrl/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $body
    $combinedContent = (($search.items | ForEach-Object { $_.content }) -join "`n")
    $matchedKeywords = @()
    foreach ($keyword in $queryCase.expected_keywords) {
        if ($combinedContent -like "*$keyword*") {
            $matchedKeywords += $keyword
        }
    }
    $passed = $matchedKeywords.Count -gt 0
    $results += [pscustomobject]@{
        id = $queryCase.id
        passed = $passed
        matched_keywords = $matchedKeywords
        expected_keywords = @($queryCase.expected_keywords)
        result_count = $search.items.Count
        first_result = if ($search.items.Count -gt 0) { $search.items[0].content } else { "" }
    }
}

$passedCount = @($results | Where-Object { $_.passed }).Count
$summary = [pscustomobject]@{
    knowledge_base_id = $KnowledgeBaseId
    uploaded_documents = $documents.Count
    query_count = @($queries).Count
    passed_count = $passedCount
    failed_count = @($queries).Count - $passedCount
    results = $results
}

if ($summary.failed_count -gt 0) {
    $summary | ConvertTo-Json -Depth 10
    Fail "Demo evaluation failed for $($summary.failed_count) query case(s)"
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
