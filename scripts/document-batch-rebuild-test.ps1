param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-batch-rebuild",
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[document-batch-rebuild-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[document-batch-rebuild-test] $Message"
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
    Fail "Batch did not finish within $TimeoutSeconds seconds. Last status: $($batch.status)"
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
$tokenA = "batchrebuilda$stamp"
$tokenB = "batchrebuildb$stamp"
$tempDir = Join-Path $env:TEMP "rag-document-batch-rebuild-test"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$fileA = Join-Path $tempDir "batch-a.txt"
$fileB = Join-Path $tempDir "batch-b.txt"
Set-Content -LiteralPath $fileA -Encoding UTF8 -Value "$tokenA should remain searchable after batch rebuild."
Set-Content -LiteralPath $fileB -Encoding UTF8 -Value "$tokenB should remain searchable after batch rebuild."

Write-Step "uploading documents"
$uploadRawA = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$fileA"
if ($LASTEXITCODE -ne 0) {
    Fail "curl upload A failed with exit code $LASTEXITCODE"
}
$uploadA = $uploadRawA | ConvertFrom-Json
$uploadRawB = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=public" -F "file=@$fileB"
if ($LASTEXITCODE -ne 0) {
    Fail "curl upload B failed with exit code $LASTEXITCODE"
}
$uploadB = $uploadRawB | ConvertFrom-Json
Wait-JobSucceeded -JobId $uploadA.job_id | Out-Null
Wait-JobSucceeded -JobId $uploadB.job_id | Out-Null

Write-Step "creating batch rebuild"
$body = @{
    tenant_id = $TenantId
    knowledge_base_id = $KnowledgeBaseId
    actor_id = "batch-test"
    request_source = "script"
    limit = 10
} | ConvertTo-Json
$batchCreated = Invoke-RestMethod -Uri "$BaseUrl/api/v1/document-batches/rebuild" -Method Post -ContentType "application/json" -Body $body
if (-not $batchCreated.batch_id) {
    Fail "Batch response did not include batch_id: $($batchCreated | ConvertTo-Json -Depth 10)"
}
if ($batchCreated.summary.total_count -lt 2) {
    Fail "Expected at least 2 batch items, got $($batchCreated.summary.total_count)"
}

Write-Step "waiting for batch jobs"
$batch = Wait-BatchFinished -BatchId $batchCreated.batch_id
if ($batch.status -ne "SUCCEEDED") {
    Fail "Expected batch SUCCEEDED, got $($batch.status): $($batch | ConvertTo-Json -Depth 10)"
}
if ($batch.summary.succeeded_count -lt 2) {
    Fail "Expected at least 2 succeeded items, got $($batch.summary.succeeded_count)"
}

Write-Step "checking batch items"
$items = Invoke-RestMethod -Uri "$BaseUrl/api/v1/document-batches/$($batch.batch_id)/items?tenant_id=$TenantId&limit=20" -Method Get
$documentIds = @($items.items | ForEach-Object { $_.document_id })
if ($documentIds -notcontains $uploadA.document_id -or $documentIds -notcontains $uploadB.document_id) {
    Fail "Batch items do not contain both uploaded documents: $($items | ConvertTo-Json -Depth 10)"
}
$nonSucceeded = @($items.items | Where-Object { $_.status -ne "SUCCEEDED" })
if ($nonSucceeded.Count -gt 0) {
    Fail "Expected all batch items to succeed: $($nonSucceeded | ConvertTo-Json -Depth 10)"
}

Write-Step "checking documents remain searchable"
$searchA = Search-Keyword -Query $tokenA
$searchB = Search-Keyword -Query $tokenB
$matchA = @($searchA.items | Where-Object { $_.document_id -eq $uploadA.document_id })
$matchB = @($searchB.items | Where-Object { $_.document_id -eq $uploadB.document_id })
if ($matchA.Count -lt 1 -or $matchB.Count -lt 1) {
    Fail "Expected both documents to remain searchable after batch rebuild"
}

$summary = [pscustomobject]@{
    batch_id = $batch.batch_id
    status = $batch.status
    total_count = $batch.summary.total_count
    succeeded_count = $batch.summary.succeeded_count
    document_ids = @($uploadA.document_id, $uploadB.document_id)
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
