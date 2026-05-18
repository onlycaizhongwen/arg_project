param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$DocumentsDir = "samples/documents/demo",
    [string]$QueriesFile = "samples/queries/model-eval-queries.json",
    [string]$TenantId = "default",
    [string]$SourceId = "default-file-source",
    [string]$ComposeFile = "infra/docker-compose.yml",
    [string]$OutputJson = "docs/codex/v1/trace/data-cleaning-rag-model-eval-report.json",
    [string]$OutputMarkdown = "docs/codex/v1/trace/data-cleaning-rag-model-eval-report.md",
    [int]$TimeoutSeconds = 90,
    [switch]$SkipMock,
    [switch]$SkipLocalBge,
    [switch]$IncludeDashScope,
    [switch]$IncludeExternalRerank,
    [string]$ExternalRerankBaseUrl = "http://reranker:8010/rerank",
    [string]$ExternalRerankModel = "BAAI/bge-reranker-base",
    [int]$ExternalRerankTimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[model-eval] $Message"
}

function Fail {
    param([string]$Message)
    throw "[model-eval] $Message"
}

function Wait-ApiHealthy {
    $deadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
            if ($health.status -eq "ok") {
                return
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    Fail "API health check failed after waiting"
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

function Get-Percentile {
    param(
        [double[]]$Values,
        [double]$Percentile
    )
    if ($Values.Count -eq 0) {
        return $null
    }
    $sorted = @($Values | Sort-Object)
    $index = [Math]::Ceiling(($Percentile / 100.0) * $sorted.Count) - 1
    $index = [Math]::Max(0, [Math]::Min($index, $sorted.Count - 1))
    return [Math]::Round([double]$sorted[$index], 2)
}

function Get-KeywordMatchRank {
    param(
        [array]$Items,
        [array]$ExpectedKeywords
    )
    for ($index = 0; $index -lt $Items.Count; $index++) {
        $content = [string]$Items[$index].content
        foreach ($keyword in $ExpectedKeywords) {
            if ($content -like "*$keyword*") {
                return $index + 1
            }
        }
    }
    return $null
}

function Set-ComposeModelConfig {
    param([pscustomobject]$Config)
    $env:EMBEDDING_PROVIDER = $Config.embedding_provider
    $env:EMBEDDING_MODEL = $Config.embedding_model
    $env:EMBEDDING_DIMENSION = "$($Config.embedding_dimension)"
    $env:EMBEDDING_BASE_URL = $Config.embedding_base_url
    $env:EMBEDDING_OUTPUT_TYPE = "dense"
    $env:RERANK_PROVIDER = $Config.rerank_provider
    $env:RERANK_MODEL = $Config.rerank_model
    $env:RERANK_BASE_URL = $Config.rerank_base_url
    $env:RERANK_TIMEOUT_SECONDS = "$($Config.rerank_timeout_seconds)"
    docker compose -f $ComposeFile up -d api worker | Out-Null
    Wait-ApiHealthy
}

function Get-RunningConfig {
    $raw = docker compose -f $ComposeFile exec -T api python -c "from app.core.config import settings; print('|'.join([settings.embedding_provider, settings.embedding_model, str(settings.embedding_dimension), settings.rerank_provider, settings.rerank_model]))"
    $parts = $raw.Trim().Split("|")
    return [pscustomobject]@{
        embedding_provider = $parts[0]
        embedding_model = $parts[1]
        embedding_dimension = [int]$parts[2]
        rerank_provider = $parts[3]
        rerank_model = $parts[4]
    }
}

function Invoke-EvalConfig {
    param(
        [pscustomobject]$Config,
        [array]$Documents,
        [array]$Queries
    )
    $queryCases = @($Queries | ForEach-Object { $_ })
    Write-Step "configuring $($Config.name)"
    Set-ComposeModelConfig -Config $Config
    $running = Get-RunningConfig
    $knowledgeBaseId = "kb-model-eval-$($Config.name)-$([guid]::NewGuid().ToString("N").Substring(0, 10))"
    $uploads = @()
    $uploadLatencies = @()

    foreach ($document in $Documents) {
        Write-Step "[$($Config.name)] uploading $($document.Name)"
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $uploadRaw = curl.exe -s -X POST "$BaseUrl/api/v1/ingestions/files?source_id=$SourceId&tenant_id=$TenantId&knowledge_base_id=$knowledgeBaseId" -F "file=@$($document.FullName)"
        $sw.Stop()
        if ($LASTEXITCODE -ne 0) {
            Fail "curl upload failed for $($document.Name) with exit code $LASTEXITCODE"
        }
        $upload = $uploadRaw | ConvertFrom-Json
        $uploads += $upload
        $uploadLatencies += $sw.Elapsed.TotalMilliseconds
    }

    foreach ($upload in $uploads) {
        Wait-JobSucceeded -JobId $upload.job_id | Out-Null
    }

    $searchResults = @()
    foreach ($queryCase in $queryCases) {
        foreach ($mode in @("semantic", "hybrid")) {
            Write-Step "[$($Config.name)] searching $($queryCase.id) mode=$mode"
            $body = @{
                query = $queryCase.query
                tenant_id = $TenantId
                knowledge_base_ids = @($knowledgeBaseId)
                permission_context = @("public")
                search_mode = $mode
                top_k = 5
                recall_size = 30
                pre_rank_size = 10
                dedup_enabled = $true
                diversity_enabled = $true
                max_chunks_per_document = 2
                rerank_enabled = $true
                rerank_size = 5
            } | ConvertTo-Json

            $sw = [System.Diagnostics.Stopwatch]::StartNew()
            $search = Invoke-RestMethod -Uri "$BaseUrl/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $body
            $sw.Stop()
            $combinedContent = (($search.items | ForEach-Object { $_.content }) -join "`n")
            $matchedKeywords = @()
            foreach ($keyword in $queryCase.expected_keywords) {
                if ($combinedContent -like "*$keyword*") {
                    $matchedKeywords += $keyword
                }
            }
            $matchRank = Get-KeywordMatchRank -Items @($search.items) -ExpectedKeywords @($queryCase.expected_keywords)
            $reciprocalRank = if ($null -ne $matchRank) { [Math]::Round(1.0 / [double]$matchRank, 4) } else { 0.0 }
            $firstItem = if ($search.items.Count -gt 0) { $search.items[0] } else { $null }
            $searchResults += [pscustomobject]@{
                id = $queryCase.id
                category = if ($queryCase.PSObject.Properties.Name -contains "category") { $queryCase.category } else { "default" }
                search_mode = $mode
                passed = $matchedKeywords.Count -gt 0
                matched_keywords = $matchedKeywords
                expected_keywords = @($queryCase.expected_keywords)
                first_match_rank = $matchRank
                reciprocal_rank = $reciprocalRank
                recall_at_k = $matchedKeywords.Count -gt 0
                latency_ms = [Math]::Round($sw.Elapsed.TotalMilliseconds, 2)
                result_count = $search.items.Count
                semantic_recall_count = $search.search_plan.semantic_recall_count
                keyword_recall_count = $search.search_plan.keyword_recall_count
                merged_count = $search.search_plan.merged_count
                business_filtered_count = $search.search_plan.business_filtered_count
                rerank_enabled = $search.search_plan.rerank_enabled
                rerank_provider = $search.search_plan.rerank_provider
                rerank_degraded = $search.search_plan.rerank_degraded
                rerank_score_count = @($search.items | Where-Object { $null -ne $_.rerank_score }).Count
                first_result_has_rerank_score = $null -ne $firstItem -and $null -ne $firstItem.rerank_score
                first_result_score = if ($null -ne $firstItem -and $null -ne $firstItem.score) { $firstItem.score } else { $null }
                first_result_rerank_score = if ($null -ne $firstItem -and $null -ne $firstItem.rerank_score) { $firstItem.rerank_score } else { $null }
                first_result = if ($search.items.Count -gt 0) { $search.items[0].content } else { "" }
            }
        }
    }

    $latencies = @($searchResults | ForEach-Object { [double]$_.latency_ms })
    $failed = @($searchResults | Where-Object { -not $_.passed })
    $degraded = @($searchResults | Where-Object { $_.rerank_degraded })
    $mrr = if ($searchResults.Count -gt 0) {
        [Math]::Round((($searchResults | Measure-Object -Property reciprocal_rank -Average).Average), 4)
    } else { 0 }
    $recallAtK = if ($searchResults.Count -gt 0) {
        [Math]::Round(((@($searchResults | Where-Object { $_.recall_at_k }).Count) / $searchResults.Count), 4)
    } else { 0 }
    $categorySummary = @()
    foreach ($categoryGroup in ($searchResults | Group-Object -Property category)) {
        $groupItems = @($categoryGroup.Group)
        $groupFailed = @($groupItems | Where-Object { -not $_.passed })
        $categorySummary += [pscustomobject]@{
            category = $categoryGroup.Name
            check_count = $groupItems.Count
            passed_count = $groupItems.Count - $groupFailed.Count
            hit_rate = if ($groupItems.Count -gt 0) { [Math]::Round((($groupItems.Count - $groupFailed.Count) / $groupItems.Count), 4) } else { 0 }
            mrr = if ($groupItems.Count -gt 0) { [Math]::Round((($groupItems | Measure-Object -Property reciprocal_rank -Average).Average), 4) } else { 0 }
        }
    }
    return [pscustomobject]@{
        name = $Config.name
        knowledge_base_id = $knowledgeBaseId
        requested_config = $Config
        running_config = $running
        uploaded_documents = $Documents.Count
        query_count = $queryCases.Count
        check_count = $searchResults.Count
        passed_count = @($searchResults | Where-Object { $_.passed }).Count
        failed_count = $failed.Count
        hit_rate = if ($searchResults.Count -gt 0) { [Math]::Round((($searchResults.Count - $failed.Count) / $searchResults.Count), 4) } else { 0 }
        mrr = $mrr
        recall_at_k = $recallAtK
        search_latency_p50_ms = Get-Percentile -Values $latencies -Percentile 50
        search_latency_p95_ms = Get-Percentile -Values $latencies -Percentile 95
        search_latency_p99_ms = Get-Percentile -Values $latencies -Percentile 99
        upload_latency_p50_ms = Get-Percentile -Values ([double[]]$uploadLatencies) -Percentile 50
        rerank_degraded_count = $degraded.Count
        category_summary = $categorySummary
        results = $searchResults
    }
}

function Write-MarkdownReport {
    param(
        [pscustomobject]$Report,
        [string]$Path
    )
    $lines = @()
    $lines += "# Data Cleaning RAG Model Evaluation Report"
    $lines += ""
    $lines += "- Generated at: $($Report.generated_at)"
    $lines += "- Documents directory: ``$($Report.documents_dir)``"
    $lines += "- Query file: ``$($Report.queries_file)``"
    $lines += ""
    $lines += "## Summary"
    $lines += ""
    $lines += "| Config | Hit rate | MRR | Recall@K | Passed/Total | P50(ms) | P95(ms) | P99(ms) | Rerank degraded | Embedding | Rerank |"
    $lines += "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |"
    foreach ($item in $Report.configs) {
        $embedding = "$($item.running_config.embedding_provider)/$($item.running_config.embedding_model)"
        $rerank = "$($item.running_config.rerank_provider)/$($item.running_config.rerank_model)"
        $lines += "| $($item.name) | $($item.hit_rate) | $($item.mrr) | $($item.recall_at_k) | $($item.passed_count)/$($item.check_count) | $($item.search_latency_p50_ms) | $($item.search_latency_p95_ms) | $($item.search_latency_p99_ms) | $($item.rerank_degraded_count) | $embedding | $rerank |"
    }
    $lines += ""
    $lines += "## Notes"
    $best = @($Report.configs | Sort-Object -Property @{Expression = "hit_rate"; Descending = $true}, @{Expression = "search_latency_p95_ms"; Descending = $false} | Select-Object -First 1)
    if ($best.Count -gt 0) {
        $lines += "- Best config in this sample set: ``$($best[0].name)`` with hit rate ``$($best[0].hit_rate)``."
    }
    $lines += "- ``mock`` is useful as a development fallback, not as a semantic quality baseline."
    $lines += "- ``local_bge`` is the recommended local demo and offline validation baseline."
    $lines += "- DashScope ``text-embedding-v4`` is included when ``DASHSCOPE_API_KEY`` is configured."
    $lines += "- PoC recommendation: use ``local_bge/bge-m3 + mock rerank`` for offline demo stability; production still needs customer corpus, DashScope quota, and rerank capacity testing."
    $lines += ""
    $lines += "## Details"
    foreach ($item in $Report.configs) {
        $lines += ""
        $lines += "### $($item.name)"
        $lines += ""
        $lines += "#### Category Summary"
        $lines += ""
        $lines += "| Category | Hit rate | MRR | Passed/Total |"
        $lines += "| --- | ---: | ---: | ---: |"
        foreach ($category in $item.category_summary) {
            $lines += "| $($category.category) | $($category.hit_rate) | $($category.mrr) | $($category.passed_count)/$($category.check_count) |"
        }
        $lines += ""
        $lines += "#### Query Details"
        $lines += ""
        $lines += "| Query | Category | Mode | Passed | Rank | RR | Matched keywords | Latency(ms) | Result count | Rerank |"
        $lines += "| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- |"
        foreach ($result in $item.results) {
            $matched = (@($result.matched_keywords) -join ", ")
            $passed = if ($result.passed) { "yes" } else { "no" }
            $rerank = "$($result.rerank_provider), scores=$($result.rerank_score_count), degraded=$($result.rerank_degraded)"
            $lines += "| $($result.id) | $($result.category) | $($result.search_mode) | $passed | $($result.first_match_rank) | $($result.reciprocal_rank) | $matched | $($result.latency_ms) | $($result.result_count) | $rerank |"
        }
    }
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -LiteralPath $Path -Encoding UTF8 -Value ($lines -join "`n")
}

if (-not (Test-Path -LiteralPath $DocumentsDir)) {
    Fail "Documents directory not found: $DocumentsDir"
}
if (-not (Test-Path -LiteralPath $QueriesFile)) {
    Fail "Queries file not found: $QueriesFile"
}

$documents = @(Get-ChildItem -LiteralPath $DocumentsDir -File | Sort-Object Name)
if ($documents.Count -lt 1) {
    Fail "No documents found in $DocumentsDir"
}
$queries = @(Get-Content -LiteralPath $QueriesFile -Raw -Encoding UTF8 | ConvertFrom-Json)

$configs = @()
if (-not $SkipMock) {
    $configs += [pscustomobject]@{
        name = "mock"
        embedding_provider = "mock"
        embedding_model = "mock-embedding"
        embedding_dimension = 1024
        embedding_base_url = ""
        rerank_provider = "mock"
        rerank_model = "mock-reranker"
        rerank_base_url = ""
        rerank_timeout_seconds = 5
    }
}
if (-not $SkipLocalBge) {
    $configs += [pscustomobject]@{
        name = "local_bge"
        embedding_provider = "local_bge"
        embedding_model = "bge-m3"
        embedding_dimension = 1024
        embedding_base_url = "http://host.docker.internal:11434"
        rerank_provider = "mock"
        rerank_model = "mock-reranker"
        rerank_base_url = ""
        rerank_timeout_seconds = 5
    }
}
if ($IncludeExternalRerank) {
    $configs += [pscustomobject]@{
        name = "local_bge_external_rerank"
        embedding_provider = "local_bge"
        embedding_model = "bge-m3"
        embedding_dimension = 1024
        embedding_base_url = "http://host.docker.internal:11434"
        rerank_provider = "external"
        rerank_model = $ExternalRerankModel
        rerank_base_url = $ExternalRerankBaseUrl
        rerank_timeout_seconds = $ExternalRerankTimeoutSeconds
    }
}
if ($IncludeDashScope -or $env:DASHSCOPE_API_KEY) {
    if (-not $env:DASHSCOPE_API_KEY) {
        Fail "DASHSCOPE_API_KEY is required when IncludeDashScope is set"
    }
    $configs += [pscustomobject]@{
        name = "dashscope_text_embedding_v4"
        embedding_provider = "dashscope"
        embedding_model = "text-embedding-v4"
        embedding_dimension = 1024
        embedding_base_url = ""
        rerank_provider = "mock"
        rerank_model = "mock-reranker"
        rerank_base_url = ""
        rerank_timeout_seconds = 5
    }
}

$configReports = @()
foreach ($config in $configs) {
    $configReports += Invoke-EvalConfig -Config $config -Documents $documents -Queries $queries
}

$report = [pscustomobject]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    documents_dir = $DocumentsDir
    queries_file = $QueriesFile
    tenant_id = $TenantId
    configs = $configReports
}

$jsonParent = Split-Path -Parent $OutputJson
if ($jsonParent -and -not (Test-Path -LiteralPath $jsonParent)) {
    New-Item -ItemType Directory -Path $jsonParent -Force | Out-Null
}
$report | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutputJson -Encoding UTF8
Write-MarkdownReport -Report $report -Path $OutputMarkdown

Write-Step "report written"
$report | ConvertTo-Json -Depth 20
