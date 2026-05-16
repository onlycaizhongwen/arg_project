# MVP local infrastructure

This directory starts the local MVP stack:

- PostgreSQL
- RabbitMQ
- MinIO
- Qdrant
- FastAPI API
- Python Worker

Default images use `docker.m.daocloud.io` to avoid Docker Hub pull failures in
mainland China. Override them with environment variables when another registry
is preferred.

## Start

```powershell
docker compose -f infra/docker-compose.yml build api worker
docker compose -f infra/docker-compose.yml up -d
.\scripts\db-migrate.ps1
docker compose -f infra/docker-compose.yml ps
```

`infra/db/init.sql` bootstraps a fresh PostgreSQL volume. Alembic migrations in
`services/api/migrations` are the ongoing schema-change mechanism.

## Smoke Test

The preferred smoke test is:

```powershell
.\scripts\smoke-test.ps1
```

## Demo Evaluation

The demo evaluation uploads the documents in `samples/documents/demo`, searches
the query set in `samples/queries/demo-queries.json`, and checks whether returned
chunks contain the expected keywords.

```powershell
.\scripts\demo-eval.ps1
```

The default demo knowledge base is `kb-demo`, so the evaluation does not mix with
the smoke-test knowledge base `kb-default`.

## Failure Test

The failure test validates the MVP error envelope and async failure path:

```powershell
.\scripts\failure-test.ps1
```

Manual commands are listed below for debugging.

```powershell
curl.exe -s -X POST "http://localhost:8000/api/v1/ingestions/files?source_id=default-file-source&tenant_id=default" -F "file=@samples/documents/smoke.txt"
```

Use the returned `job_id`:

```powershell
curl.exe -s http://localhost:8000/api/v1/jobs/<job_id>
```

Search after the job status becomes `SUCCEEDED`:

```powershell
$body = @{
  query = 'semantic search recall pre-ranking'
  tenant_id = 'default'
  top_k = 3
  recall_size = 20
  pre_rank_size = 10
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/api/v1/rag/search -Method Post -ContentType 'application/json' -Body $body
```

## Local URLs

- API: `http://localhost:8000/health`
- API contract: `../docs/codex/v1/plans/data-cleaning-rag-api-contract.md`
- RabbitMQ console: `http://localhost:15672`
- MinIO console: `http://localhost:9001`
- Qdrant dashboard: `http://localhost:6333/dashboard`

Default local credentials are listed in `../.env.example`.

## Embedding Providers

Default local runs use deterministic `mock` embeddings. To validate the active
provider:

```powershell
.\scripts\embedding-check.ps1
```

DashScope example:

```powershell
$env:EMBEDDING_PROVIDER = "dashscope"
$env:EMBEDDING_MODEL = "text-embedding-v4"
$env:EMBEDDING_DIMENSION = "1024"
$env:EMBEDDING_OUTPUT_TYPE = "dense"
$env:DASHSCOPE_API_KEY = "<your-key>"

docker compose -f infra/docker-compose.yml up -d api worker
.\scripts\embedding-check.ps1
```

Local BGE example with Ollama's OpenAI-compatible endpoint:

```powershell
$env:EMBEDDING_PROVIDER = "local_bge"
$env:EMBEDDING_MODEL = "bge-m3"
$env:EMBEDDING_DIMENSION = "1024"
$env:EMBEDDING_BASE_URL = "http://host.docker.internal:11434"

docker compose -f infra/docker-compose.yml up -d api worker
.\scripts\embedding-check.ps1
```

Before switching Compose to `local_bge`, make sure the model is available on the
host:

```powershell
ollama pull bge-m3
curl.exe -s http://localhost:11434/api/tags
```

## Local BGE Reranker

The API can call an external reranker through `RERANK_PROVIDER=external`. A local
BGE reranker service is available behind the optional Compose profile
`reranker`.

```powershell
$env:COMPOSE_PROFILES = "reranker"
$env:HF_ENDPOINT = "https://hf-mirror.com"
$env:EMBEDDING_PROVIDER = "local_bge"
$env:EMBEDDING_MODEL = "bge-m3"
$env:EMBEDDING_DIMENSION = "1024"
$env:EMBEDDING_BASE_URL = "http://host.docker.internal:11434"
$env:RERANK_PROVIDER = "external"
$env:RERANK_MODEL = "BAAI/bge-reranker-base"
$env:RERANK_BASE_URL = "http://reranker:8010/rerank"
$env:RERANK_TIMEOUT_SECONDS = "30"

docker compose -f infra/docker-compose.yml build reranker
docker compose -f infra/docker-compose.yml up -d reranker api
.\scripts\bge-rerank-test.ps1
```

The first run downloads the model into the `hf-models` Docker volume. If the
foreign Hugging Face endpoint is slow or unavailable, try
`HF_ENDPOINT=https://hf-mirror.com`. If the mirror returns metadata errors with
the current Hugging Face client, temporarily switch back to
`HF_ENDPOINT=https://huggingface.co` to warm the Docker volume, then rerun the
test.

Validated locally on 2026-05-16 with:

- Embedding: Ollama `bge-m3`, `EMBEDDING_PROVIDER=local_bge`
- Reranker: `BAAI/bge-reranker-base`
- Script: `.\scripts\bge-rerank-test.ps1`
- Expected search plan: `rerank_provider=external`, `rerank_degraded=false`
