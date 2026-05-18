param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-lock-release",
    [string]$ComposeFile = "infra/docker-compose.yml",
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[document-lock-release-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[document-lock-release-test] $Message"
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

function Invoke-ExpectBusinessError {
    param(
        [string]$Uri,
        [string]$Method,
        [string]$ExpectedCode
    )
    try {
        Invoke-RestMethod -Uri $Uri -Method $Method | Out-Null
    }
    catch {
        $body = $_.ErrorDetails.Message | ConvertFrom-Json
        if ($body.error.code -ne $ExpectedCode) {
            Fail "Expected $ExpectedCode, got $($body.error.code): $($_.ErrorDetails.Message)"
        }
        return $body.error.code
    }
    Fail "Expected error $ExpectedCode but request succeeded"
}

function Invoke-PostgresSql {
    param([string]$Sql)
    $escapedSql = $Sql -replace '"', '\"'
    docker compose -f $ComposeFile exec -T postgres psql -U rag -d rag_cleaning -v ON_ERROR_STOP=1 -c "$escapedSql" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail "PostgreSQL command failed with exit code $LASTEXITCODE"
    }
}

Write-Step "checking API health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "ok") {
    Fail "API health check failed: $($health | ConvertTo-Json -Compress)"
}

Write-Step "ensuring worker is running"
docker compose -f $ComposeFile up -d worker | Out-Null

$stamp = [guid]::NewGuid().ToString("N").Substring(0, 12)
$token = "lockreleasetoken$stamp"
$tempDir = Join-Path $env:TEMP "rag-document-lock-release-test"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$file = Join-Path $tempDir "lock-release.txt"
Set-Content -LiteralPath $file -Encoding UTF8 -Value "$token is used to validate stale lock release."

Write-Step "uploading original document"
$uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$file"
if ($LASTEXITCODE -ne 0) {
    Fail "curl upload failed with exit code $LASTEXITCODE"
}
$upload = $uploadRaw | ConvertFrom-Json
Wait-JobSucceeded -JobId $upload.job_id | Out-Null

Write-Step "creating a fresh synthetic lock and checking it cannot be released"
$freshLockId = [guid]::NewGuid().ToString()
Invoke-PostgresSql -Sql "UPDATE document SET operation_status = 'REBUILD_INDEX', operation_lock_id = '$freshLockId', operation_started_at = now(), updated_at = now() WHERE id = '$($upload.document_id)' AND tenant_id = '$TenantId';"
Invoke-ExpectBusinessError `
    -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/locks/release?tenant_id=$TenantId&stale_lock_minutes=30" `
    -Method Post `
    -ExpectedCode "DOCUMENT_OPERATION_LOCK_NOT_STALE" | Out-Null

Write-Step "creating a stale synthetic lock with active job and checking it is protected"
$activeLockId = [guid]::NewGuid().ToString()
Invoke-PostgresSql -Sql "UPDATE document SET operation_status = 'REBUILD_INDEX', operation_lock_id = '$activeLockId', operation_started_at = now() - interval '120 minutes', updated_at = now() WHERE id = '$($upload.document_id)' AND tenant_id = '$TenantId'; INSERT INTO cleaning_job (id, document_version_id, tenant_id, status) VALUES ('$activeLockId', '$($upload.document_version_id)', '$TenantId', 'PENDING');"
Invoke-ExpectBusinessError `
    -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/locks/release?tenant_id=$TenantId&stale_lock_minutes=30" `
    -Method Post `
    -ExpectedCode "DOCUMENT_OPERATION_LOCK_JOB_ACTIVE" | Out-Null

Write-Step "marking active job failed and releasing stale lock"
Invoke-PostgresSql -Sql "UPDATE cleaning_job SET status = 'FAILED', error_message = 'synthetic stale lock test', finished_at = now() WHERE id = '$activeLockId';"
$release = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/locks/release?tenant_id=$TenantId&stale_lock_minutes=30&actor_id=lock-release-test&request_source=test" -Method Post
if (-not $release.released) {
    Fail "Lock release did not report success: $($release | ConvertTo-Json -Depth 10)"
}
Invoke-PostgresSql -Sql "UPDATE cleaning_job SET status = 'SUCCEEDED', error_message = NULL, finished_at = now() WHERE id = '$activeLockId';"

Write-Step "checking release audit event"
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/audit?tenant_id=$TenantId&operation=DOCUMENT_OPERATION_LOCK_RELEASED&limit=10" -Method Get
$releasedEvents = @($audit.items | Where-Object { $_.metadata.previous_operation_lock_id -eq $activeLockId })
if ($releasedEvents.Count -lt 1) {
    Fail "Expected DOCUMENT_OPERATION_LOCK_RELEASED audit event"
}

Write-Step "checking rebuild is accepted after lock release"
$rebuild = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/rebuild?tenant_id=$TenantId" -Method Post
if ($rebuild.operation -ne "REBUILD_INDEX") {
    Fail "Unexpected rebuild response: $($rebuild | ConvertTo-Json -Depth 10)"
}
Wait-JobSucceeded -JobId $rebuild.job_id | Out-Null

$summary = [pscustomobject]@{
    document_id = $upload.document_id
    fresh_lock_error = "DOCUMENT_OPERATION_LOCK_NOT_STALE"
    active_job_error = "DOCUMENT_OPERATION_LOCK_JOB_ACTIVE"
    released_lock_id = $activeLockId
    rebuild_job_id = $rebuild.job_id
    release_audit_count = $releasedEvents.Count
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
