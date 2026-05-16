param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[diagnostics-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[diagnostics-test] $Message"
}

Write-Step "checking API health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "ok") {
    Fail "API health check failed: $($health | ConvertTo-Json -Compress)"
}

Write-Step "checking diagnostics overview"
$overview = Invoke-RestMethod -Uri "$BaseUrl/api/v1/diagnostics/overview?tenant_id=$TenantId&window_minutes=120&stale_lock_minutes=30" -Method Get
if (-not $overview.status) {
    Fail "Diagnostics response does not contain status"
}
if ($overview.tenant_id -ne $TenantId) {
    Fail "Unexpected tenant_id: $($overview.tenant_id)"
}
if ($null -eq $overview.job_metrics.by_status) {
    Fail "Missing job status metrics"
}
if ($null -eq $overview.queue_metrics.available) {
    Fail "Missing queue availability metric"
}
if ($null -eq $overview.lock_metrics.active_count) {
    Fail "Missing lock metrics"
}
if ($null -eq $overview.rerank_metrics.degraded_recent_count) {
    Fail "Missing rerank degradation metric"
}
if ($null -eq $overview.signals) {
    Fail "Missing signals array"
}

Write-Step "passed"
$overview | ConvertTo-Json -Depth 10
