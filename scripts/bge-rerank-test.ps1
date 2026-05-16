param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$DocumentsDir = "samples/documents/demo",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-bge-rerank",
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[bge-rerank-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[bge-rerank-test] $Message"
}

if (-not (Test-Path -LiteralPath $DocumentsDir)) {
    Fail "Documents directory not found: $DocumentsDir"
}

Write-Step "checking API health"
$healthDeadline = (Get-Date).AddSeconds(60)
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

Write-Step "checking reranker health through host port"
$rerankerHealth = Invoke-RestMethod -Uri "http://localhost:8010/health" -Method Get
if ($rerankerHealth.status -ne "ok") {
    Fail "Reranker health check failed: $($rerankerHealth | ConvertTo-Json -Compress)"
}

$documents = Get-ChildItem -LiteralPath $DocumentsDir -File | Sort-Object Name
foreach ($document in $documents) {
    Write-Step "uploading $($document.Name)"
    $uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$($document.FullName)"
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

Write-Step "searching with BGE rerank"
$body = @{
    query = "Which request parameters bound the semantic recall candidate set?"
    tenant_id = $TenantId
    knowledge_base_ids = @($KnowledgeBaseId)
    permission_context = @("public")
    search_mode = "hybrid"
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
if ($search.items.Count -lt 1) {
    Fail "Search returned no items"
}
if ($search.search_plan.rerank_provider -ne "external") {
    Fail "Expected rerank_provider=external, got $($search.search_plan.rerank_provider)"
}
if ($search.search_plan.rerank_degraded -ne $false) {
    Fail "Expected rerank_degraded=false, got $($search.search_plan.rerank_degraded)"
}
$rerankScoreCount = @($search.items | Where-Object { $null -ne $_.rerank_score }).Count
if ($rerankScoreCount -lt 1) {
    Fail "Expected at least one rerank_score"
}

$summary = [pscustomobject]@{
    knowledge_base_id = $KnowledgeBaseId
    reranker_model = $rerankerHealth.model
    result_count = $search.items.Count
    rerank_provider = $search.search_plan.rerank_provider
    rerank_degraded = $search.search_plan.rerank_degraded
    rerank_score_count = $rerankScoreCount
    first_rerank_score = $search.items[0].rerank_score
    first_result = $search.items[0].content
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
