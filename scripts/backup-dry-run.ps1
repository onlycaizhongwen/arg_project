param(
    [string]$ComposeFile = "infra/docker-compose.yml",
    [string]$OutputDir = "backups/poc",
    [string]$ReportPath = "docs/codex/v1/trace/data-cleaning-rag-backup-dry-run-report.md"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[backup-dry-run] $Message"
}

function Fail {
    param([string]$Message)
    throw "[backup-dry-run] $Message"
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
Ensure-Directory -Path $OutputDir

Write-Step "checking compose services"
docker compose -f $ComposeFile ps | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail "docker compose ps failed"
}

$postgresBackup = Join-Path $OutputDir "rag_cleaning_$stamp.sql"
Write-Step "exporting PostgreSQL backup to $postgresBackup"
docker compose -f $ComposeFile exec -T postgres pg_dump -U rag -d rag_cleaning > $postgresBackup
if ($LASTEXITCODE -ne 0) {
    Fail "pg_dump failed"
}
$postgresBackupItem = Get-Item -LiteralPath $postgresBackup

Write-Step "checking MinIO bucket"
$minioRaw = docker compose -f $ComposeFile exec -T minio sh -c "mc alias set local http://localhost:9000 rag rag_password >/dev/null && mc ls local/rag-documents --recursive --summarize"
$minioStatus = if ($LASTEXITCODE -eq 0) { "ok" } else { "failed" }
$minioText = ($minioRaw -join "`n")
$minioTotalObjects = if ($minioText -match "Total Objects:\s+(\d+)") { $Matches[1] } else { "unknown" }
$minioTotalSize = if ($minioText -match "Total Size:\s+(.+)") { $Matches[1].Trim() } else { "unknown" }

Write-Step "checking Qdrant collections"
try {
    $qdrantResponse = Invoke-RestMethod -Uri "http://localhost:6333/collections" -Method Get
    $qdrantRaw = $qdrantResponse | ConvertTo-Json -Depth 10
    $qdrantStatus = "ok"
} catch {
    $qdrantRaw = $_.Exception.Message
    $qdrantStatus = "failed"
}

$reportParent = Split-Path -Parent $ReportPath
if ($reportParent) {
    Ensure-Directory -Path $reportParent
}

$lines = @()
$lines += "# Data Cleaning RAG Backup Dry Run Report"
$lines += ""
$lines += "- Generated at: $((Get-Date).ToUniversalTime().ToString("o"))"
$lines += "- Compose file: ``$ComposeFile``"
$lines += "- Output dir: ``$OutputDir``"
$lines += ""
$lines += "## PostgreSQL"
$lines += ""
$lines += "- Backup file: ``$postgresBackup``"
$lines += "- Size bytes: $($postgresBackupItem.Length)"
$lines += "- Status: ok"
$lines += ""
$lines += "## MinIO"
$lines += ""
$lines += "- Status: $minioStatus"
$lines += "- Bucket: ``rag-documents``"
$lines += "- Total objects: $minioTotalObjects"
$lines += "- Total size: $minioTotalSize"
$lines += ""
$lines += "## Qdrant"
$lines += ""
$lines += "- Status: $qdrantStatus"
$lines += ""
$lines += '```json'
$lines += ($qdrantRaw -join "`n")
$lines += '```'
$lines += ""
$lines += "## Notes"
$lines += ""
$lines += "- This script is a non-destructive dry run."
$lines += "- PostgreSQL restore must be performed in an isolated environment before production use."
$lines += "- MinIO and Qdrant production backup should use customer-approved object storage snapshots or Qdrant snapshots."

Set-Content -LiteralPath $ReportPath -Encoding UTF8 -Value ($lines -join "`n")

Write-Step "report written"
[pscustomobject]@{
    postgres_backup = $postgresBackup
    postgres_backup_bytes = $postgresBackupItem.Length
    minio_status = $minioStatus
    qdrant_status = $qdrantStatus
    report_path = $ReportPath
} | ConvertTo-Json -Depth 5
