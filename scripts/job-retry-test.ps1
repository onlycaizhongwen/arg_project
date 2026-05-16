param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-job-retry",
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[job-retry-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[job-retry-test] $Message"
}

function Wait-JobTerminal {
    param([string]$JobId)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $job = $null
    while ((Get-Date) -lt $deadline) {
        $job = Invoke-RestMethod -Uri "$BaseUrl/api/v1/jobs/$JobId" -Method Get
        if ($job.status -in @("SUCCEEDED", "FAILED")) {
            return $job
        }
        Start-Sleep -Seconds 2
    }
    Fail "Job did not reach terminal state within $TimeoutSeconds seconds. Last status: $($job.status)"
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

Write-Step "checking API health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "ok") {
    Fail "API health check failed: $($health | ConvertTo-Json -Compress)"
}

$stamp = [guid]::NewGuid().ToString("N").Substring(0, 12)
$tempDir = Join-Path $env:TEMP "rag-job-retry-test"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$unsupportedFile = Join-Path $tempDir "retry-unsupported-$stamp.bin"
Set-Content -LiteralPath $unsupportedFile -Encoding UTF8 -Value "unsupported retry payload $stamp"

Write-Step "uploading unsupported file to create FAILED job"
$uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$unsupportedFile"
if ($LASTEXITCODE -ne 0) {
    Fail "curl upload failed with exit code $LASTEXITCODE"
}
$upload = $uploadRaw | ConvertFrom-Json
$failedJob = Wait-JobTerminal -JobId $upload.job_id
if ($failedJob.status -ne "FAILED") {
    Fail "Expected source job to fail, got $($failedJob.status)"
}

Write-Step "creating manual retry job"
$retry = Invoke-RestMethod -Uri "$BaseUrl/api/v1/jobs/$($upload.job_id)/retry?tenant_id=$TenantId&actor_id=retry-tester&request_source=job-retry-test" -Method Post
if ($retry.retry_of_job_id -ne $upload.job_id) {
    Fail "Retry response does not reference source job: $($retry | ConvertTo-Json -Depth 10)"
}
if ($retry.job_id -eq $upload.job_id) {
    Fail "Retry reused source job id"
}

Write-Step "waiting for retry job terminal state"
$retryJob = Wait-JobTerminal -JobId $retry.job_id
if ($retryJob.status -ne "FAILED") {
    Fail "Unsupported file retry should fail again, got $($retryJob.status)"
}
if ($retryJob.retry_of_job_id -ne $upload.job_id) {
    Fail "Retry job query missing retry_of_job_id"
}

Write-Step "checking retry audit event"
$audit = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/audit?tenant_id=$TenantId&limit=20" -Method Get
$retryEvents = @($audit.items | Where-Object { $_.operation -eq "JOB_RETRY_REQUESTED" -and $_.job_id -eq $retry.job_id })
if ($retryEvents.Count -lt 1) {
    Fail "Expected JOB_RETRY_REQUESTED audit event"
}
$retryFailedEvents = @($audit.items | Where-Object { $_.operation -eq "JOB_RETRY_FAILED" -and $_.job_id -eq $retry.job_id })
if ($retryFailedEvents.Count -lt 1) {
    Fail "Expected JOB_RETRY_FAILED audit event"
}

Write-Step "checking non-failed retry is rejected"
$supportedFile = Join-Path $tempDir "retry-supported-$stamp.txt"
Set-Content -LiteralPath $supportedFile -Encoding UTF8 -Value "supported retry negative case $stamp"
$supportedUploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$supportedFile"
if ($LASTEXITCODE -ne 0) {
    Fail "curl supported upload failed with exit code $LASTEXITCODE"
}
$supportedUpload = $supportedUploadRaw | ConvertFrom-Json
$supportedJob = Wait-JobTerminal -JobId $supportedUpload.job_id
if ($supportedJob.status -ne "SUCCEEDED") {
    Fail "Expected supported upload to succeed, got $($supportedJob.status)"
}
$notFailedCode = Invoke-ExpectBusinessError `
    -Uri "$BaseUrl/api/v1/jobs/$($supportedUpload.job_id)/retry?tenant_id=$TenantId" `
    -Method Post `
    -ExpectedCode "JOB_NOT_FAILED"

$summary = [pscustomobject]@{
    document_id = $upload.document_id
    source_job_id = $upload.job_id
    retry_job_id = $retry.job_id
    source_status = $failedJob.status
    retry_status = $retryJob.status
    retry_of_job_id = $retryJob.retry_of_job_id
    retry_audit_count = $retryEvents.Count
    retry_failed_audit_count = $retryFailedEvents.Count
    non_failed_retry_error_code = $notFailedCode
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
