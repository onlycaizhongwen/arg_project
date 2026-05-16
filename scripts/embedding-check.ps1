param(
    [string]$ComposeFile = "infra/docker-compose.yml",
    [string]$ApiService = "api",
    [string]$WorkerService = "worker"
)

$ErrorActionPreference = "Stop"

Write-Host "[embedding] checking API query embedding"
docker compose -f $ComposeFile exec $ApiService python -c @"
from app.core.config import settings
from app.embeddings.embedding_client import build_embedding_client

settings.validate()
client = build_embedding_client()
vector = client.embed_query('semantic search smoke query')
print({
    'service': 'api',
    'provider': settings.embedding_provider,
    'model': settings.embedding_model,
    'dimension': len(vector),
    'expected_dimension': settings.embedding_dimension,
})
assert len(vector) == settings.embedding_dimension
"@

Write-Host "[embedding] checking Worker document embedding"
docker compose -f $ComposeFile exec $WorkerService python -c @"
from app.core.config import settings
from app.embeddings.embedding_client import build_embedding_client

settings.validate()
client = build_embedding_client()
vectors = client.embed_documents(['semantic search smoke document'])
print({
    'service': 'worker',
    'provider': settings.embedding_provider,
    'model': settings.embedding_model,
    'dimension': len(vectors[0]),
    'expected_dimension': settings.embedding_dimension,
})
assert len(vectors) == 1
assert len(vectors[0]) == settings.embedding_dimension
"@
