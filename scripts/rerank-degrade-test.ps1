param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default",
    [string]$KnowledgeBaseId = "kb-demo"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[rerank-degrade] $Message"
}

function Fail {
    param([string]$Message)
    throw "[rerank-degrade] $Message"
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

Write-Step "searching with rerank enabled"
$body = @{
    query = "Which request parameters bound the semantic recall candidate set?"
    tenant_id = $TenantId
    knowledge_base_ids = @($KnowledgeBaseId)
    search_mode = "hybrid"
    top_k = 3
    recall_size = 20
    pre_rank_size = 10
    dedup_enabled = $true
    diversity_enabled = $true
    max_chunks_per_document = 2
    rerank_enabled = $true
    rerank_size = 3
} | ConvertTo-Json

$search = Invoke-RestMethod -Uri "$BaseUrl/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $body
if ($search.items.Count -lt 1) {
    Fail "Search returned no items"
}
if ($search.search_plan.rerank_degraded -ne $true) {
    Fail "Expected rerank_degraded=true, got $($search.search_plan.rerank_degraded)"
}

Write-Step "passed"
[pscustomobject]@{
    result_count = $search.items.Count
    rerank_provider = $search.search_plan.rerank_provider
    rerank_enabled = $search.search_plan.rerank_enabled
    rerank_degraded = $search.search_plan.rerank_degraded
} | ConvertTo-Json -Depth 10
