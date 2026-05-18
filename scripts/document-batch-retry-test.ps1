param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-batch-retry",
    [string]$ComposeFile = "infra/docker-compose.yml",
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[document-batch-retry-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[document-batch-retry-test] $Message"
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
$tokenA = "batchretrya$stamp"
$tokenB = "batchretryb$stamp"
$tempDir = Join-Path $env:TEMP "rag-document-batch-retry-test"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$fileA = Join-Path $tempDir "retry-a.txt"
$fileB = Join-Path $tempDir "retry-b.txt"
Set-Content -LiteralPath $fileA -Encoding UTF8 -Value "$tokenA is used to retry a failed batch item."
Set-Content -LiteralPath $fileB -Encoding UTF8 -Value "$tokenB is used to keep a succeeded batch item untouched."

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

Write-Step "creating synthetic partial failed batch"
$retryBatchId = [guid]::NewGuid().ToString()
$failedItemId = [guid]::NewGuid().ToString()
$succeededItemId = [guid]::NewGuid().ToString()
Invoke-PostgresSql -Sql "INSERT INTO document_operation_batch (id, tenant_id, operation, status, filters, total_count, actor_id, request_source) VALUES ('$retryBatchId', '$TenantId', 'REBUILD_INDEX', 'PARTIAL_SUCCEEDED', '{""synthetic"":true}'::jsonb, 2, 'batch-retry-test', 'script'); INSERT INTO document_operation_batch_item (id, batch_id, tenant_id, document_id, document_version_id, status, error_code, error_message) VALUES ('$failedItemId', '$retryBatchId', '$TenantId', '$($uploadA.document_id)', '$($uploadA.document_version_id)', 'FAILED', 'SYNTHETIC_FAILURE', 'synthetic failed item'), ('$succeededItemId', '$retryBatchId', '$TenantId', '$($uploadB.document_id)', '$($uploadB.document_version_id)', 'SUCCEEDED', NULL, NULL);"

Write-Step "retrying failed items"
$retry = Invoke-RestMethod -Uri "$BaseUrl/api/v1/document-batches/$retryBatchId/retry-failed?tenant_id=$TenantId&actor_id=batch-retry-test&request_source=script" -Method Post
if ($retry.retried_count -ne 1) {
    Fail "Expected retried_count 1, got $($retry.retried_count): $($retry | ConvertTo-Json -Depth 10)"
}
$retryItems = Invoke-RestMethod -Uri "$BaseUrl/api/v1/document-batches/$retryBatchId/items?tenant_id=$TenantId&limit=20" -Method Get
$retriedItem = $retryItems.items | Where-Object { $_.item_id -eq $failedItemId } | Select-Object -First 1
$untouchedItem = $retryItems.items | Where-Object { $_.item_id -eq $succeededItemId } | Select-Object -First 1
if (-not $retriedItem.job_id) {
    Fail "Retried item does not contain new job_id: $($retryItems | ConvertTo-Json -Depth 10)"
}
if ($untouchedItem.job_id) {
    Fail "Succeeded item should not be resubmitted: $($untouchedItem | ConvertTo-Json -Depth 10)"
}
Wait-JobSucceeded -JobId $retriedItem.job_id | Out-Null
$retryFinished = Invoke-RestMethod -Uri "$BaseUrl/api/v1/document-batches/$retryBatchId`?tenant_id=$TenantId" -Method Get
if ($retryFinished.status -ne "SUCCEEDED") {
    Fail "Expected retried batch to become SUCCEEDED, got $($retryFinished.status): $($retryFinished | ConvertTo-Json -Depth 10)"
}

Write-Step "creating synthetic cancelable batch"
$cancelBatchId = [guid]::NewGuid().ToString()
$pendingItemId = [guid]::NewGuid().ToString()
$doneItemId = [guid]::NewGuid().ToString()
Invoke-PostgresSql -Sql "INSERT INTO document_operation_batch (id, tenant_id, operation, status, filters, total_count, actor_id, request_source) VALUES ('$cancelBatchId', '$TenantId', 'REBUILD_INDEX', 'RUNNING', '{""synthetic"":true}'::jsonb, 2, 'batch-retry-test', 'script'); INSERT INTO document_operation_batch_item (id, batch_id, tenant_id, document_id, document_version_id, status) VALUES ('$pendingItemId', '$cancelBatchId', '$TenantId', '$($uploadA.document_id)', '$($uploadA.document_version_id)', 'PENDING'), ('$doneItemId', '$cancelBatchId', '$TenantId', '$($uploadB.document_id)', '$($uploadB.document_version_id)', 'SUCCEEDED');"

Write-Step "canceling pending batch items"
$cancel = Invoke-RestMethod -Uri "$BaseUrl/api/v1/document-batches/$cancelBatchId/cancel?tenant_id=$TenantId&actor_id=batch-retry-test&request_source=script" -Method Post
if ($cancel.canceled_items -ne 1) {
    Fail "Expected canceled_items 1, got $($cancel.canceled_items): $($cancel | ConvertTo-Json -Depth 10)"
}
$cancelItems = Invoke-RestMethod -Uri "$BaseUrl/api/v1/document-batches/$cancelBatchId/items?tenant_id=$TenantId&limit=20" -Method Get
$pendingItem = $cancelItems.items | Where-Object { $_.item_id -eq $pendingItemId } | Select-Object -First 1
$doneItem = $cancelItems.items | Where-Object { $_.item_id -eq $doneItemId } | Select-Object -First 1
if ($pendingItem.status -ne "CANCELED") {
    Fail "Expected pending item to become CANCELED: $($pendingItem | ConvertTo-Json -Depth 10)"
}
if ($doneItem.status -ne "SUCCEEDED") {
    Fail "Expected succeeded item to remain SUCCEEDED: $($doneItem | ConvertTo-Json -Depth 10)"
}
$canceledOnly = Invoke-RestMethod -Uri "$BaseUrl/api/v1/document-batches/$cancelBatchId/items?tenant_id=$TenantId&status=CANCELED&limit=20" -Method Get
if ($canceledOnly.total_count -ne 1 -or $canceledOnly.items.Count -ne 1) {
    Fail "Status filter did not return the canceled item: $($canceledOnly | ConvertTo-Json -Depth 10)"
}

$summary = [pscustomobject]@{
    retry_batch_id = $retryBatchId
    retry_status = $retryFinished.status
    retried_job_id = $retriedItem.job_id
    cancel_batch_id = $cancelBatchId
    canceled_items = $cancel.canceled_items
    canceled_filter_count = $canceledOnly.total_count
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
