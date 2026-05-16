param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$SampleFile = "samples/documents/smoke.txt",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-delete",
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[document-delete-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[document-delete-test] $Message"
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
$uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$SampleFile"
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

$body = @{
    query = "semantic search recall pre-ranking"
    tenant_id = $TenantId
    knowledge_base_ids = @($KnowledgeBaseId)
    permission_context = @("public")
    search_mode = "hybrid"
    top_k = 5
    recall_size = 20
    pre_rank_size = 10
} | ConvertTo-Json

Write-Step "checking document is searchable before delete"
$beforeSearch = Invoke-RestMethod -Uri "$BaseUrl/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $body
$beforeMatches = @($beforeSearch.items | Where-Object { $_.document_id -eq $upload.document_id })
if ($beforeMatches.Count -lt 1) {
    Fail "Uploaded document was not searchable before delete"
}

Write-Step "deleting document $($upload.document_id)"
$deleteResult = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)?tenant_id=$TenantId" -Method Delete
if ($deleteResult.status -ne "DELETED") {
    Fail "Delete did not return DELETED: $($deleteResult | ConvertTo-Json -Depth 10)"
}

Write-Step "checking deleted document is not searchable"
$afterSearch = Invoke-RestMethod -Uri "$BaseUrl/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $body
$afterMatches = @($afterSearch.items | Where-Object { $_.document_id -eq $upload.document_id })
if ($afterMatches.Count -ne 0) {
    Fail "Deleted document is still searchable"
}

Write-Step "checking idempotent delete"
$secondDelete = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)?tenant_id=$TenantId" -Method Delete
if ($secondDelete.status -ne "DELETED") {
    Fail "Second delete did not return DELETED"
}

$summary = [pscustomobject]@{
    document_id = $upload.document_id
    document_version_id = $upload.document_version_id
    before_match_count = $beforeMatches.Count
    after_match_count = $afterMatches.Count
    deleted_vector_count = $deleteResult.deleted_vector_count
    second_deleted_vector_count = $secondDelete.deleted_vector_count
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
