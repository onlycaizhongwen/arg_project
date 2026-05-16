param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-update",
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[document-update-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[document-update-test] $Message"
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

function Search-Keyword {
    param([string]$Query)
    $body = @{
        query = $Query
        tenant_id = $TenantId
        knowledge_base_ids = @($KnowledgeBaseId)
        permission_context = @("public")
        search_mode = "keyword"
        top_k = 5
        recall_size = 20
        pre_rank_size = 10
    } | ConvertTo-Json
    return Invoke-RestMethod -Uri "$BaseUrl/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $body
}

Write-Step "checking API health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "ok") {
    Fail "API health check failed: $($health | ConvertTo-Json -Compress)"
}

$stamp = [guid]::NewGuid().ToString("N").Substring(0, 12)
$oldToken = "oldversiontoken$stamp"
$newToken = "newversiontoken$stamp"
$tempDir = Join-Path $env:TEMP "rag-document-update-test"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$oldFile = Join-Path $tempDir "old-version.txt"
$newFile = Join-Path $tempDir "new-version.txt"
Set-Content -LiteralPath $oldFile -Encoding UTF8 -Value "$oldToken is visible in the first indexed document version."
Set-Content -LiteralPath $newFile -Encoding UTF8 -Value "$newToken is visible in the second indexed document version."

Write-Step "uploading original document"
$uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$oldFile"
if ($LASTEXITCODE -ne 0) {
    Fail "curl upload failed with exit code $LASTEXITCODE"
}
$upload = $uploadRaw | ConvertFrom-Json
Wait-JobSucceeded -JobId $upload.job_id | Out-Null

Write-Step "checking original version is searchable"
$oldBefore = Search-Keyword -Query $oldToken
$oldBeforeMatches = @($oldBefore.items | Where-Object { $_.document_id -eq $upload.document_id })
if ($oldBeforeMatches.Count -lt 1) {
    Fail "Original version was not searchable before update"
}

Write-Step "creating updated version"
$updateRaw = curl.exe -s -X PUT "$BaseUrl/api/v1/documents/$($upload.document_id)/versions?tenant_id=$TenantId" -F "file=@$newFile"
if ($LASTEXITCODE -ne 0) {
    Fail "curl update failed with exit code $LASTEXITCODE"
}
$update = $updateRaw | ConvertFrom-Json
if ($update.document_id -ne $upload.document_id) {
    Fail "Update returned unexpected document_id: $updateRaw"
}
if ($update.document_version_id -eq $upload.document_version_id) {
    Fail "Update reused the old document_version_id"
}
Wait-JobSucceeded -JobId $update.job_id | Out-Null

Write-Step "checking old version is no longer searchable"
$oldAfter = Search-Keyword -Query $oldToken
$oldAfterMatches = @($oldAfter.items | Where-Object { $_.document_id -eq $upload.document_id })
if ($oldAfterMatches.Count -ne 0) {
    Fail "Old document version is still searchable after update"
}

Write-Step "checking new version is searchable"
$newAfter = Search-Keyword -Query $newToken
$newAfterMatches = @($newAfter.items | Where-Object {
    $_.document_id -eq $upload.document_id -and $_.document_version_id -eq $update.document_version_id
})
if ($newAfterMatches.Count -lt 1) {
    Fail "New document version is not searchable after update"
}

$summary = [pscustomobject]@{
    document_id = $upload.document_id
    old_document_version_id = $upload.document_version_id
    new_document_version_id = $update.document_version_id
    old_before_match_count = $oldBeforeMatches.Count
    old_after_match_count = $oldAfterMatches.Count
    new_after_match_count = $newAfterMatches.Count
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
