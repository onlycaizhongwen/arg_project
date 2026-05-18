param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "",
    [string]$ActorId = "header-operator",
    [string]$RequestSource = "header-test",
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[request-context-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[request-context-test] $Message"
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

if ([string]::IsNullOrWhiteSpace($TenantId)) {
    $TenantId = "tenant-ctx-$([guid]::NewGuid().ToString("N").Substring(0, 8))"
}
if ([string]::IsNullOrWhiteSpace($KnowledgeBaseId)) {
    $KnowledgeBaseId = "kb-ctx-$([guid]::NewGuid().ToString("N").Substring(0, 8))"
}

$traceId = "trace-$([guid]::NewGuid().ToString("N").Substring(0, 12))"
$headers = @{
    "X-Tenant-Id" = $TenantId
    "X-Actor-Id" = $ActorId
    "X-Request-Source" = $RequestSource
    "X-Permission-Tags" = "internal"
    "X-Trace-Id" = $traceId
}

Write-Step "checking API health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "ok") {
    Fail "API health check failed: $($health | ConvertTo-Json -Compress)"
}

Write-Step "checking X-Trace-Id response header"
$traceResponse = Invoke-WebRequest -Uri "$BaseUrl/health" -Method Get -Headers @{ "X-Trace-Id" = $traceId }
if ($traceResponse.Headers["X-Trace-Id"] -ne $traceId) {
    Fail "Expected X-Trace-Id response header $traceId, got $($traceResponse.Headers["X-Trace-Id"])"
}

$stamp = [guid]::NewGuid().ToString("N").Substring(0, 12)
$token = "contexttoken$stamp"
$updatedToken = "contextupdate$stamp"
$tempDir = Join-Path $env:TEMP "rag-request-context-test"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$uploadFile = Join-Path $tempDir "context-upload.txt"
$updateFile = Join-Path $tempDir "context-update.txt"
Set-Content -LiteralPath $uploadFile -Encoding UTF8 -Value "$token should be visible only to internal permission context."
Set-Content -LiteralPath $updateFile -Encoding UTF8 -Value "$updatedToken should keep header actor audit context."

Write-Step "uploading with X-Tenant-Id overriding query tenant"
$uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=wrong-tenant&knowledge_base_id=$KnowledgeBaseId&permission_tags=internal" `
    -H "X-Tenant-Id: $TenantId" `
    -F "file=@$uploadFile"
if ($LASTEXITCODE -ne 0) {
    Fail "curl upload failed with exit code $LASTEXITCODE"
}
$upload = $uploadRaw | ConvertFrom-Json
if ($upload.tenant_id -and $upload.tenant_id -ne $TenantId) {
    Fail "Upload returned unexpected tenant_id: $($upload.tenant_id)"
}
Wait-JobSucceeded -JobId $upload.job_id | Out-Null

Write-Step "searching with X-Permission-Tags overriding default public context"
$searchBody = @{
    query = $token
    tenant_id = "wrong-tenant"
    knowledge_base_ids = @($KnowledgeBaseId)
    search_mode = "keyword"
    top_k = 5
    recall_size = 20
    pre_rank_size = 10
} | ConvertTo-Json
$search = Invoke-RestMethod -Uri "$BaseUrl/api/v1/rag/search" -Method Post -Headers $headers -ContentType "application/json" -Body $searchBody
if ($search.items.Count -lt 1) {
    Fail "Header permission context did not return internal document"
}

Write-Step "creating version with header actor/source overriding query actor/source"
$updateRaw = curl.exe -s -X PUT "$BaseUrl/api/v1/documents/$($upload.document_id)/versions?tenant_id=wrong-tenant&actor_id=query-actor&request_source=query-source" `
    -H "X-Tenant-Id: $TenantId" `
    -H "X-Actor-Id: $ActorId" `
    -H "X-Request-Source: $RequestSource" `
    -F "file=@$updateFile"
if ($LASTEXITCODE -ne 0) {
    Fail "curl update failed with exit code $LASTEXITCODE"
}
$update = $updateRaw | ConvertFrom-Json
Wait-JobSucceeded -JobId $update.job_id | Out-Null

Write-Step "checking audit actor/source from headers"
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/audit?tenant_id=wrong-tenant&operation=DOCUMENT_VERSION_CREATED&limit=10" -Method Get -Headers $headers
$createdEvents = @($audit.items | Where-Object { $_.job_id -eq $update.job_id })
if ($createdEvents.Count -lt 1) {
    Fail "Could not find DOCUMENT_VERSION_CREATED audit event for update job"
}
$badEvents = @($createdEvents | Where-Object { $_.actor_id -ne $ActorId -or $_.request_source -ne $RequestSource })
if ($badEvents.Count -gt 0) {
    Fail "Header actor/source was not used in audit event: $($badEvents | ConvertTo-Json -Depth 10)"
}

Write-Step "creating batch with header actor/source overriding request body"
$batchBody = @{
    tenant_id = "wrong-tenant"
    knowledge_base_id = $KnowledgeBaseId
    actor_id = "body-actor"
    request_source = "body-source"
    limit = 10
} | ConvertTo-Json
$batch = Invoke-RestMethod -Uri "$BaseUrl/api/v1/document-batches/rebuild" -Method Post -Headers $headers -ContentType "application/json" -Body $batchBody
if ($batch.actor_id -ne $ActorId -or $batch.request_source -ne $RequestSource) {
    Fail "Batch actor/source did not come from headers: $($batch | ConvertTo-Json -Depth 10)"
}

$summary = [pscustomobject]@{
    tenant_id = $TenantId
    knowledge_base_id = $KnowledgeBaseId
    document_id = $upload.document_id
    update_job_id = $update.job_id
    batch_id = $batch.batch_id
    trace_id = $traceId
    search_result_count = $search.items.Count
    audit_event_count = $createdEvents.Count
    batch_actor_id = $batch.actor_id
    batch_request_source = $batch.request_source
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
