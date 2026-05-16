param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-rebuild",
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[document-rebuild-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[document-rebuild-test] $Message"
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
$token = "rebuildtoken$stamp"
$tempDir = Join-Path $env:TEMP "rag-document-rebuild-test"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$filePath = Join-Path $tempDir "rebuild-source.txt"
Set-Content -LiteralPath $filePath -Encoding UTF8 -Value "$token must remain searchable after rebuilding the same document index."

Write-Step "uploading document"
$uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$filePath"
if ($LASTEXITCODE -ne 0) {
    Fail "curl upload failed with exit code $LASTEXITCODE"
}
$upload = $uploadRaw | ConvertFrom-Json
Wait-JobSucceeded -JobId $upload.job_id | Out-Null

Write-Step "checking document is searchable before rebuild"
$before = Search-Keyword -Query $token
$beforeMatches = @($before.items | Where-Object {
    $_.document_id -eq $upload.document_id -and $_.document_version_id -eq $upload.document_version_id
})
if ($beforeMatches.Count -lt 1) {
    Fail "Document was not searchable before rebuild"
}

Write-Step "rebuilding document index"
$rebuild = Invoke-RestMethod -Uri "$BaseUrl/api/v1/documents/$($upload.document_id)/rebuild?tenant_id=$TenantId" -Method Post
if ($rebuild.operation -ne "REBUILD_INDEX") {
    Fail "Unexpected rebuild operation: $($rebuild | ConvertTo-Json -Depth 10)"
}
if ($rebuild.document_version_id -ne $upload.document_version_id) {
    Fail "Rebuild should reuse current version. upload=$($upload.document_version_id), rebuild=$($rebuild.document_version_id)"
}
Wait-JobSucceeded -JobId $rebuild.job_id | Out-Null

Write-Step "checking document is searchable after rebuild"
$after = Search-Keyword -Query $token
$afterMatches = @($after.items | Where-Object {
    $_.document_id -eq $upload.document_id -and $_.document_version_id -eq $upload.document_version_id
})
if ($afterMatches.Count -lt 1) {
    Fail "Document was not searchable after rebuild"
}

$summary = [pscustomobject]@{
    document_id = $upload.document_id
    document_version_id = $upload.document_version_id
    upload_job_id = $upload.job_id
    rebuild_job_id = $rebuild.job_id
    before_match_count = $beforeMatches.Count
    after_match_count = $afterMatches.Count
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
