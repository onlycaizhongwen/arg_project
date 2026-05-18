param(
    [string]$ApiBaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

function Assert-Equal {
    param(
        [object]$Actual,
        [object]$Expected,
        [string]$Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message. Expected=[$Expected], Actual=[$Actual]"
    }
}

Write-Host "[rerank-runtime-config-test] checking API health"
Invoke-RestMethod -Uri "$ApiBaseUrl/health" -Method Get | Out-Null

$original = Invoke-RestMethod -Uri "$ApiBaseUrl/api/v1/runtime-config/rerank" -Method Get

try {
    Write-Host "[rerank-runtime-config-test] switching to disabled"
    $disabledBody = @{
        provider = "disabled"
        model = "disabled-reranker"
        base_url = ""
        timeout_seconds = 5
    } | ConvertTo-Json
    $disabled = Invoke-RestMethod -Uri "$ApiBaseUrl/api/v1/runtime-config/rerank" -Method Put -ContentType "application/json" -Body $disabledBody
    Assert-Equal $disabled.provider "disabled" "disabled provider mismatch"

    Write-Host "[rerank-runtime-config-test] switching to mock"
    $mockBody = @{
        provider = "mock"
        model = "mock-reranker"
        base_url = ""
        timeout_seconds = 5
    } | ConvertTo-Json
    $mock = Invoke-RestMethod -Uri "$ApiBaseUrl/api/v1/runtime-config/rerank" -Method Put -ContentType "application/json" -Body $mockBody
    Assert-Equal $mock.provider "mock" "mock provider mismatch"

    Write-Host "[rerank-runtime-config-test] switching to external"
    $externalBody = @{
        provider = "external"
        model = "BAAI/bge-reranker-base"
        base_url = "http://reranker:8010/rerank"
        timeout_seconds = 30
    } | ConvertTo-Json
    $external = Invoke-RestMethod -Uri "$ApiBaseUrl/api/v1/runtime-config/rerank" -Method Put -ContentType "application/json" -Body $externalBody
    Assert-Equal $external.provider "external" "external provider mismatch"
    Assert-Equal $external.model "BAAI/bge-reranker-base" "external model mismatch"

    $overview = Invoke-RestMethod -Uri "$ApiBaseUrl/api/v1/diagnostics/overview?tenant_id=default" -Method Get
    Assert-Equal $overview.rerank_metrics.provider "external" "diagnostics provider mismatch"

    Write-Host "[rerank-runtime-config-test] passed"
    $external | ConvertTo-Json -Depth 5
}
finally {
    Write-Host "[rerank-runtime-config-test] restoring original provider"
    $restoreBody = @{
        provider = $original.provider
        model = $original.model
        base_url = $original.base_url
        timeout_seconds = $original.timeout_seconds
    } | ConvertTo-Json
    Invoke-RestMethod -Uri "$ApiBaseUrl/api/v1/runtime-config/rerank" -Method Put -ContentType "application/json" -Body $restoreBody | Out-Null
}
