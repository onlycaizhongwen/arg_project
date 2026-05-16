param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-failure",
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[failure-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[failure-test] $Message"
}

function Invoke-ExpectError {
    param(
        [string]$Method,
        [string]$Uri,
        [string]$Body = "",
        [int]$ExpectedStatus,
        [string]$ExpectedCode
    )
    $args = @("-s", "-w", "`n%{http_code}", "-X", $Method, $Uri)
    if ($Body) {
        $args += @("-H", "Content-Type: application/json", "-d", $Body)
    }
    $raw = & curl.exe @args
    if ($LASTEXITCODE -ne 0) {
        Fail "curl request failed with exit code $LASTEXITCODE"
    }
    $lines = @($raw -split "`n")
    $status = [int]$lines[-1]
    $bodyText = ($lines[0..($lines.Count - 2)] -join "`n")
    if ($status -ne $ExpectedStatus) {
        Fail "Expected HTTP $ExpectedStatus, got $status. Body: $bodyText"
    }
    $parsed = $bodyText | ConvertFrom-Json
    if ($parsed.error.code -ne $ExpectedCode) {
        Fail "Expected error code $ExpectedCode, got $($parsed.error.code). Body: $bodyText"
    }
    return $parsed
}

function Invoke-CurlUpload {
    param(
        [string]$FilePath,
        [string]$KnowledgeBase
    )
    $raw = curl.exe -s -w "`n%{http_code}" -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBase" -F "file=@$FilePath"
    if ($LASTEXITCODE -ne 0) {
        Fail "curl upload failed with exit code $LASTEXITCODE"
    }
    $lines = @($raw -split "`n")
    $status = [int]$lines[-1]
    $bodyText = ($lines[0..($lines.Count - 2)] -join "`n")
    return [pscustomobject]@{
        status = $status
        body_text = $bodyText
        body = if ($bodyText.Trim()) { $bodyText | ConvertFrom-Json } else { $null }
    }
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
    Fail "Job $JobId did not reach terminal status within $TimeoutSeconds seconds. Last status: $($job.status)"
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

Write-Step "checking JOB_NOT_FOUND"
$null = Invoke-ExpectError `
    -Method "GET" `
    -Uri "$BaseUrl/api/v1/jobs/00000000-0000-0000-0000-000000000000" `
    -ExpectedStatus 404 `
    -ExpectedCode "JOB_NOT_FOUND"

Write-Step "checking VALIDATION_ERROR"
$badSearchBody = @{
    query = "bad request"
    top_k = "not-a-number"
} | ConvertTo-Json -Compress
$null = Invoke-ExpectError `
    -Method "POST" `
    -Uri "$BaseUrl/api/v1/rag/search" `
    -Body $badSearchBody `
    -ExpectedStatus 422 `
    -ExpectedCode "VALIDATION_ERROR"

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("rag-failure-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempDir | Out-Null
try {
    Write-Step "checking EMPTY_FILE"
    $emptyFile = Join-Path $tempDir "empty.txt"
    New-Item -ItemType File -Path $emptyFile | Out-Null
    $emptyUpload = Invoke-CurlUpload -FilePath $emptyFile -KnowledgeBase $KnowledgeBaseId
    if ($emptyUpload.status -ne 400) {
        Fail "Expected empty upload HTTP 400, got $($emptyUpload.status). Body: $($emptyUpload.body_text)"
    }
    if ($emptyUpload.body.error.code -ne "EMPTY_FILE") {
        Fail "Expected EMPTY_FILE, got $($emptyUpload.body.error.code). Body: $($emptyUpload.body_text)"
    }

    Write-Step "checking unsupported file async failure"
    $unsupportedFile = Join-Path $tempDir "unsupported.bin"
    Set-Content -LiteralPath $unsupportedFile -Value "unsupported file extension for parser failure" -Encoding UTF8
    $upload = Invoke-CurlUpload -FilePath $unsupportedFile -KnowledgeBase $KnowledgeBaseId
    if ($upload.status -ne 200) {
        Fail "Expected unsupported upload to create async job, got HTTP $($upload.status). Body: $($upload.body_text)"
    }
    $job = Wait-JobTerminal -JobId $upload.body.job_id
    if ($job.status -ne "FAILED") {
        Fail "Expected unsupported file job to fail, got $($job.status)"
    }
    if ($job.error_message -notlike "*Unsupported document extension*") {
        Fail "Unexpected unsupported file error: $($job.error_message)"
    }

    $summary = [pscustomobject]@{
        job_not_found = "passed"
        validation_error = "passed"
        empty_file = "passed"
        unsupported_file_job_id = $upload.body.job_id
        unsupported_file_status = $job.status
        unsupported_file_retry_count = $job.retry_count
    }
    Write-Step "passed"
    $summary | ConvertTo-Json -Depth 10
} finally {
    if (Test-Path -LiteralPath $tempDir) {
        Remove-Item -LiteralPath $tempDir -Recurse -Force
    }
}
