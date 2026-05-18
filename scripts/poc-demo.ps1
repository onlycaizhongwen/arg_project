param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "",
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[poc-demo] $Message"
}

function Fail {
    param([string]$Message)
    throw "[poc-demo] $Message"
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
            Fail "Job $JobId failed: $($job.error_message)"
        }
        Start-Sleep -Seconds 2
    }
    Fail "Job $JobId did not finish within $TimeoutSeconds seconds. Last status: $($job.status)"
}

function Wait-BatchFinished {
    param([string]$BatchId)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $batch = $null
    while ((Get-Date) -lt $deadline) {
        $batch = Invoke-RestMethod -Uri "$BaseUrl/api/v1/document-batches/$BatchId`?tenant_id=$TenantId" -Method Get
        if ($batch.status -in @("SUCCEEDED", "PARTIAL_SUCCEEDED", "FAILED")) {
            return $batch
        }
        Start-Sleep -Seconds 2
    }
    Fail "Batch $BatchId did not finish within $TimeoutSeconds seconds. Last status: $($batch.status)"
}

function Invoke-HybridSearch {
    param([string]$Query)
    $body = @{
        query = $Query
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
    return Invoke-RestMethod -Uri "$BaseUrl/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $body
}

if ([string]::IsNullOrWhiteSpace($KnowledgeBaseId)) {
    $KnowledgeBaseId = "kb-poc-$([guid]::NewGuid().ToString("N").Substring(0, 10))"
}

Write-Step "checking API health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "ok") {
    Fail "API health check failed: $($health | ConvertTo-Json -Compress)"
}

$stamp = [guid]::NewGuid().ToString("N").Substring(0, 12)
$uploadToken = "pocupload$stamp"
$updateToken = "pocupdate$stamp"
$batchToken = "pocbatch$stamp"
$tempDir = Join-Path $env:TEMP "rag-poc-demo"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$uploadFile = Join-Path $tempDir "poc-upload.txt"
$updateFile = Join-Path $tempDir "poc-update.txt"
$batchFile = Join-Path $tempDir "poc-batch.txt"
Set-Content -LiteralPath $uploadFile -Encoding UTF8 -Value "$uploadToken verifies upload, cleaning, embedding, Qdrant indexing, and hybrid retrieval."
Set-Content -LiteralPath $updateFile -Encoding UTF8 -Value "$updateToken verifies document version update and new index visibility."
Set-Content -LiteralPath $batchFile -Encoding UTF8 -Value "$batchToken verifies batch rebuild governance for a knowledge base."

Write-Step "uploading primary demo document"
$uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$uploadFile"
if ($LASTEXITCODE -ne 0) {
    Fail "curl upload failed with exit code $LASTEXITCODE"
}
$upload = $uploadRaw | ConvertFrom-Json
Wait-JobSucceeded -JobId $upload.job_id | Out-Null

Write-Step "checking hybrid retrieval after upload"
$searchAfterUpload = Invoke-HybridSearch -Query $uploadToken
$uploadMatches = @($searchAfterUpload.items | Where-Object { $_.document_id -eq $upload.document_id })
if ($uploadMatches.Count -lt 1) {
    Fail "Uploaded document was not found by hybrid search"
}

Write-Step "creating updated document version"
$updateRaw = curl.exe -s -X PUT "$BaseUrl/api/v1/documents/$($upload.document_id)/versions?tenant_id=$TenantId&actor_id=poc-operator&request_source=poc-demo" -F "file=@$updateFile"
if ($LASTEXITCODE -ne 0) {
    Fail "curl update failed with exit code $LASTEXITCODE"
}
$update = $updateRaw | ConvertFrom-Json
Wait-JobSucceeded -JobId $update.job_id | Out-Null

Write-Step "checking updated version retrieval"
$searchAfterUpdate = Invoke-HybridSearch -Query $updateToken
$updateMatches = @($searchAfterUpdate.items | Where-Object {
    $_.document_id -eq $upload.document_id -and $_.document_version_id -eq $update.document_version_id
})
if ($updateMatches.Count -lt 1) {
    Fail "Updated document version was not found by hybrid search"
}

Write-Step "rebuilding document index"
$rebuild = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/rebuild?tenant_id=$TenantId&actor_id=poc-operator&request_source=poc-demo" -Method Post
Wait-JobSucceeded -JobId $rebuild.job_id | Out-Null

Write-Step "uploading second document for batch rebuild"
$batchUploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$batchFile"
if ($LASTEXITCODE -ne 0) {
    Fail "curl batch upload failed with exit code $LASTEXITCODE"
}
$batchUpload = $batchUploadRaw | ConvertFrom-Json
Wait-JobSucceeded -JobId $batchUpload.job_id | Out-Null

Write-Step "creating knowledge-base batch rebuild"
$batchBody = @{
    tenant_id = $TenantId
    knowledge_base_id = $KnowledgeBaseId
    actor_id = "poc-operator"
    request_source = "poc-demo"
    limit = 20
} | ConvertTo-Json
$batchCreated = Invoke-RestMethod -Uri "$BaseUrl/api/v1/document-batches/rebuild" -Method Post -ContentType "application/json" -Body $batchBody
$batch = Wait-BatchFinished -BatchId $batchCreated.batch_id
if ($batch.status -ne "SUCCEEDED") {
    Fail "Expected batch rebuild to succeed, got $($batch.status)"
}

Write-Step "checking diagnostics overview"
$diagnostics = Invoke-RestMethod -Uri "$BaseUrl/api/v1/diagnostics/overview?tenant_id=$TenantId&window_minutes=120&stale_lock_minutes=30" -Method Get
if (-not $diagnostics.status) {
    Fail "Diagnostics overview did not return status"
}

$summary = [pscustomobject]@{
    knowledge_base_id = $KnowledgeBaseId
    document_id = $upload.document_id
    original_job_id = $upload.job_id
    update_job_id = $update.job_id
    rebuild_job_id = $rebuild.job_id
    batch_document_id = $batchUpload.document_id
    batch_id = $batch.batch_id
    batch_status = $batch.status
    batch_total_count = $batch.summary.total_count
    batch_succeeded_count = $batch.summary.succeeded_count
    upload_match_count = $uploadMatches.Count
    update_match_count = $updateMatches.Count
    diagnostics_status = $diagnostics.status
    queue_ready_count = $diagnostics.queue_metrics.ready_count
    active_lock_count = $diagnostics.lock_metrics.active_count
    rerank_provider = $diagnostics.rerank_metrics.provider
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
