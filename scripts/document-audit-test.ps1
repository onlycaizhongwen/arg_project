param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-audit",
    [string]$ActorId = "audit-tester",
    [string]$RequestSource = "script",
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[document-audit-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[document-audit-test] $Message"
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

Write-Step "checking API health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "ok") {
    Fail "API health check failed: $($health | ConvertTo-Json -Compress)"
}

$stamp = [guid]::NewGuid().ToString("N").Substring(0, 12)
$tempDir = Join-Path $env:TEMP "rag-document-audit-test"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$initialFile = Join-Path $tempDir "audit-initial.txt"
$updateFile = Join-Path $tempDir "audit-update.txt"
Set-Content -LiteralPath $initialFile -Encoding UTF8 -Value "auditinitial$stamp should be indexed before audit operations."
Set-Content -LiteralPath $updateFile -Encoding UTF8 -Value "auditupdate$stamp should be indexed after version update."

Write-Step "uploading initial document"
$uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$initialFile"
if ($LASTEXITCODE -ne 0) {
    Fail "curl upload failed with exit code $LASTEXITCODE"
}
$upload = $uploadRaw | ConvertFrom-Json
Wait-JobSucceeded -JobId $upload.job_id | Out-Null

Write-Step "creating audited document version"
$updateUrl = "$BaseUrl/api/v1/documents/$($upload.document_id)/versions?tenant_id=$TenantId&actor_id=$ActorId&request_source=$RequestSource"
$updateRaw = curl.exe -s -X PUT $updateUrl -F "file=@$updateFile"
if ($LASTEXITCODE -ne 0) {
    Fail "curl update failed with exit code $LASTEXITCODE"
}
$update = $updateRaw | ConvertFrom-Json
Wait-JobSucceeded -JobId $update.job_id | Out-Null

Write-Step "creating audited rebuild request"
$rebuild = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/rebuild?tenant_id=$TenantId&actor_id=$ActorId&request_source=$RequestSource" -Method Post
Wait-JobSucceeded -JobId $rebuild.job_id | Out-Null

Write-Step "creating audited delete request"
$deleteResult = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)?tenant_id=$TenantId&actor_id=$ActorId&request_source=$RequestSource" -Method Delete
if ($deleteResult.status -ne "DELETED") {
    Fail "Delete did not return DELETED"
}

Write-Step "checking audit events"
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/audit?tenant_id=$TenantId&limit=10" -Method Get
$operations = @($audit.items | ForEach-Object { $_.operation })
$expectedOperations = @(
    "DOCUMENT_VERSION_CREATED",
    "DOCUMENT_VERSION_INDEXED",
    "DOCUMENT_INDEX_REBUILD_REQUESTED",
    "DOCUMENT_INDEX_REBUILD_SUCCEEDED",
    "DOCUMENT_DELETED",
    "DOCUMENT_DELETE_SUCCEEDED"
)
foreach ($operation in $expectedOperations) {
    if ($operations -notcontains $operation) {
        Fail "Missing audit operation: $operation. Actual: $($operations -join ',')"
    }
}

$badActorEvents = @($audit.items | Where-Object {
    $_.operation -in @("DOCUMENT_VERSION_CREATED", "DOCUMENT_INDEX_REBUILD_REQUESTED", "DOCUMENT_DELETED", "DOCUMENT_DELETE_SUCCEEDED") -and (
        $_.actor_id -ne $ActorId -or $_.request_source -ne $RequestSource
    )
})
if ($badActorEvents.Count -gt 0) {
    Fail "Audit actor/source mismatch: $($badActorEvents | ConvertTo-Json -Depth 10)"
}

$workerEvents = @($audit.items | Where-Object {
    $_.operation -in @("DOCUMENT_VERSION_INDEXED", "DOCUMENT_INDEX_REBUILD_SUCCEEDED") -and (
        $_.actor_id -ne "worker" -or $_.request_source -ne "worker"
    )
})
if ($workerEvents.Count -gt 0) {
    Fail "Worker audit actor/source mismatch: $($workerEvents | ConvertTo-Json -Depth 10)"
}

Write-Step "checking audit operation filter"
$filteredAudit = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/audit?tenant_id=$TenantId&operation=DOCUMENT_INDEX_REBUILD_SUCCEEDED&limit=10" -Method Get
$filteredOperations = @($filteredAudit.items | ForEach-Object { $_.operation })
if ($filteredOperations.Count -lt 1) {
    Fail "Expected filtered audit result for DOCUMENT_INDEX_REBUILD_SUCCEEDED"
}
if (@($filteredOperations | Where-Object { $_ -ne "DOCUMENT_INDEX_REBUILD_SUCCEEDED" }).Count -gt 0) {
    Fail "Audit operation filter returned unexpected operations: $($filteredOperations -join ',')"
}

$summary = [pscustomobject]@{
    document_id = $upload.document_id
    update_job_id = $update.job_id
    rebuild_job_id = $rebuild.job_id
    audit_event_count = $audit.items.Count
    filtered_audit_count = $filteredAudit.items.Count
    operations = $operations
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
