param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[metrics-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[metrics-test] $Message"
}

Write-Step "checking API health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "ok") {
    Fail "API health check failed: $($health | ConvertTo-Json -Compress)"
}

Write-Step "checking Prometheus metrics"
$metrics = Invoke-RestMethod -Uri "$BaseUrl/api/v1/metrics?tenant_id=$TenantId&window_minutes=120&stale_lock_minutes=30" -Method Get
$requiredNames = @(
    "rag_cleaning_job_status_count",
    "rag_cleaning_job_recent_total",
    "rag_cleaning_job_recent_failed",
    "rag_cleaning_job_failure_rate",
    "rag_cleaning_queue_available",
    "rag_cleaning_queue_ready_count",
    "rag_cleaning_queue_consumer_count",
    "rag_cleaning_document_lock_active_count",
    "rag_cleaning_document_lock_stale_count",
    "rag_cleaning_rerank_degraded_recent_count",
    "rag_api_request_total",
    "rag_api_request_error_total"
)

foreach ($name in $requiredNames) {
    if ($metrics -notmatch [regex]::Escape($name)) {
        Fail "Missing metric: $name"
    }
}

if ($metrics -notmatch "tenant_id=`"$([regex]::Escape($TenantId))`"") {
    Fail "Missing tenant_id label for $TenantId"
}

Write-Step "passed"
$metrics
