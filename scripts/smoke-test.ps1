param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$SampleFile = "samples/documents/smoke.txt",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-default",
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[smoke] $Message"
}

function Fail {
    param([string]$Message)
    throw "[smoke] $Message"
}

if (-not (Test-Path -LiteralPath $SampleFile)) {
    Fail "Sample file not found: $SampleFile"
}

Write-Step "checking API health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "ok") {
    Fail "API health check failed: $($health | ConvertTo-Json -Compress)"
}

Write-Step "uploading sample document"
$uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId" -F "file=@$SampleFile"
if ($LASTEXITCODE -ne 0) {
    Fail "curl upload failed with exit code $LASTEXITCODE"
}

$upload = $uploadRaw | ConvertFrom-Json
if (-not $upload.job_id) {
    Fail "Upload response does not contain job_id: $uploadRaw"
}

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

Write-Step "running semantic search"
$body = @{
    query = "semantic search recall pre-ranking"
    tenant_id = $TenantId
    knowledge_base_ids = @($KnowledgeBaseId)
    search_mode = "hybrid"
    top_k = 3
    recall_size = 20
    pre_rank_size = 10
} | ConvertTo-Json

$search = Invoke-RestMethod -Uri "$BaseUrl/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $body
if ($search.items.Count -lt 1) {
    Fail "Search returned no items"
}
if ($search.items[0].knowledge_base_id -ne $KnowledgeBaseId) {
    Fail "Search returned unexpected knowledge_base_id: $($search.items[0].knowledge_base_id)"
}

Write-Step "checking knowledge base filter"
$negativeBody = @{
    query = "semantic search recall pre-ranking"
    tenant_id = $TenantId
    knowledge_base_ids = @("kb-does-not-exist")
    search_mode = "hybrid"
    top_k = 3
    recall_size = 20
    pre_rank_size = 10
} | ConvertTo-Json

$negativeSearch = Invoke-RestMethod -Uri "$BaseUrl/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $negativeBody
if ($negativeSearch.items.Count -ne 0) {
    Fail "Knowledge base filter did not exclude unrelated items"
}

$summary = [pscustomobject]@{
    job_id = $upload.job_id
    job_status = $job.status
    document_id = $upload.document_id
    document_version_id = $upload.document_version_id
    knowledge_base_id = $upload.knowledge_base_id
    search_item_count = $search.items.Count
    first_result = $search.items[0].content
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
