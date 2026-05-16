param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$KnowledgeBaseId = "kb-permission",
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[permission-test] $Message"
}

function Fail {
    param([string]$Message)
    throw "[permission-test] $Message"
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

function Upload-Document {
    param(
        [string]$FilePath,
        [string]$PermissionTags
    )
    $uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$KnowledgeBaseId&permission_tags=$PermissionTags" -F "file=@$FilePath"
    if ($LASTEXITCODE -ne 0) {
        Fail "curl upload failed with exit code $LASTEXITCODE"
    }
    $upload = $uploadRaw | ConvertFrom-Json
    if (-not $upload.job_id) {
        Fail "Upload response does not contain job_id: $uploadRaw"
    }
    Wait-JobSucceeded -JobId $upload.job_id | Out-Null
    return $upload
}

function Search-Keyword {
    param(
        [string]$Query,
        [object[]]$PermissionContext,
        [bool]$IncludePermissionContext = $true
    )
    $body = @{
        query = $Query
        tenant_id = $TenantId
        knowledge_base_ids = @($KnowledgeBaseId)
        search_mode = "keyword"
        top_k = 5
        recall_size = 20
        pre_rank_size = 10
    }
    if ($IncludePermissionContext) {
        $body.permission_context = $PermissionContext
    }
    $json = $body | ConvertTo-Json
    return Invoke-RestMethod -Uri "$BaseUrl/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $json
}

Write-Step "checking API health"
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "ok") {
    Fail "API health check failed: $($health | ConvertTo-Json -Compress)"
}

$tempDir = Join-Path $env:TEMP "rag-permission-test"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$publicFile = Join-Path $tempDir "public.txt"
$internalFile = Join-Path $tempDir "internal.txt"
Set-Content -LiteralPath $publicFile -Encoding UTF8 -Value "publicalpha content is visible to public permission context."
Set-Content -LiteralPath $internalFile -Encoding UTF8 -Value "privatebeta content is visible only to internal permission context."

Write-Step "uploading public document"
$publicUpload = Upload-Document -FilePath $publicFile -PermissionTags "public"
Write-Step "uploading internal document"
$internalUpload = Upload-Document -FilePath $internalFile -PermissionTags "internal"

Write-Step "checking default public context"
$defaultSearch = Search-Keyword -Query "privatebeta" -PermissionContext @() -IncludePermissionContext $false
if ($defaultSearch.items.Count -ne 0) {
    Fail "Default permission context returned internal content"
}

Write-Step "checking explicit public context"
$publicSearch = Search-Keyword -Query "privatebeta" -PermissionContext @("public")
if ($publicSearch.items.Count -ne 0) {
    Fail "Public permission context returned internal content"
}

Write-Step "checking internal context"
$internalSearch = Search-Keyword -Query "privatebeta" -PermissionContext @("internal")
if ($internalSearch.items.Count -lt 1) {
    Fail "Internal permission context did not return internal content"
}
$combinedInternalContent = (($internalSearch.items | ForEach-Object { $_.content }) -join "`n")
if ($combinedInternalContent -notlike "*privatebeta*") {
    Fail "Internal permission context returned results without privatebeta marker"
}

$summary = [pscustomobject]@{
    knowledge_base_id = $KnowledgeBaseId
    public_document_id = $publicUpload.document_id
    internal_document_id = $internalUpload.document_id
    default_result_count = $defaultSearch.items.Count
    public_result_count = $publicSearch.items.Count
    internal_result_count = $internalSearch.items.Count
    internal_permission_tags = $internalSearch.items[0].permission_tags
}

Write-Step "passed"
$summary | ConvertTo-Json -Depth 10
