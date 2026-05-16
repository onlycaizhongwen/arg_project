param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-operation-lock",
    [string]$ComposeFile = "infra/docker-compose.yml",
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[document-operation-lock-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[document-operation-lock-test] $Message"
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

$workerStopped = $false
try {
    Write-Step "checking API health"
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
    if ($health.status -ne "ok") {
        Fail "API health check failed: $($health | ConvertTo-Json -Compress)"
    }

    Write-Step "ensuring worker is running"
    docker compose -f $ComposeFile up -d worker | Out-Null

    $stamp = [guid]::NewGuid().ToString("N").Substring(0, 12)
    $oldToken = "lockoldtoken$stamp"
    $newToken = "locknewtoken$stamp"
    $tempDir = Join-Path $env:TEMP "rag-document-operation-lock-test"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    $oldFile = Join-Path $tempDir "lock-old.txt"
    $newFile = Join-Path $tempDir "lock-new.txt"
    Set-Content -LiteralPath $oldFile -Encoding UTF8 -Value "$oldToken is the original indexed document."
    Set-Content -LiteralPath $newFile -Encoding UTF8 -Value "$newToken is the pending updated document."

    Write-Step "uploading original document"
    $uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$oldFile"
    if ($LASTEXITCODE -ne 0) {
        Fail "curl upload failed with exit code $LASTEXITCODE"
    }
    $upload = $uploadRaw | ConvertFrom-Json
    Wait-JobSucceeded -JobId $upload.job_id | Out-Null

    Write-Step "stopping worker to keep update job pending"
    docker compose -f $ComposeFile stop worker | Out-Null
    $workerStopped = $true

    Write-Step "creating updated version while worker is stopped"
    $updateRaw = curl.exe -s -X PUT "$BaseUrl/api/v1/documents/$($upload.document_id)/versions?tenant_id=$TenantId" -F "file=@$newFile"
    if ($LASTEXITCODE -ne 0) {
        Fail "curl update failed with exit code $LASTEXITCODE"
    }
    $update = $updateRaw | ConvertFrom-Json
    if (-not $update.job_id) {
        Fail "Update did not return job_id: $updateRaw"
    }

    Write-Step "checking concurrent rebuild is rejected"
    $errorCode = Invoke-ExpectBusinessError `
        -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/rebuild?tenant_id=$TenantId" `
        -Method Post `
        -ExpectedCode "DOCUMENT_OPERATION_IN_PROGRESS"

    Write-Step "checking rejected operation audit event"
    $auditAfterReject = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/audit?tenant_id=$TenantId&limit=20" -Method Get
    $rejectedEvents = @($auditAfterReject.items | Where-Object { $_.operation -eq "DOCUMENT_OPERATION_REJECTED" })
    if ($rejectedEvents.Count -lt 1) {
        Fail "Expected DOCUMENT_OPERATION_REJECTED audit event"
    }

    Write-Step "restarting worker and waiting for update lock release"
    docker compose -f $ComposeFile up -d worker | Out-Null
    $workerStopped = $false
    Wait-JobSucceeded -JobId $update.job_id | Out-Null

    Write-Step "checking rebuild is accepted after update finishes"
    $rebuild = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/rebuild?tenant_id=$TenantId" -Method Post
    if ($rebuild.operation -ne "REBUILD_INDEX") {
        Fail "Unexpected rebuild response: $($rebuild | ConvertTo-Json -Depth 10)"
    }
    Wait-JobSucceeded -JobId $rebuild.job_id | Out-Null

    $summary = [pscustomobject]@{
        document_id = $upload.document_id
        update_job_id = $update.job_id
        rebuild_job_id = $rebuild.job_id
        rejected_error_code = $errorCode
        rejected_audit_count = $rejectedEvents.Count
    }

    Write-Step "passed"
    $summary | ConvertTo-Json -Depth 10
}
finally {
    if ($workerStopped) {
        Write-Step "restarting worker after test cleanup"
        docker compose -f $ComposeFile up -d worker | Out-Null
    }
}
