param(
    [string]$ComposeFile = "infra/docker-compose.yml",
    [string]$Service = "api",
    [string]$Revision = "head"
)

$ErrorActionPreference = "Stop"

docker compose -f $ComposeFile exec $Service alembic -c /app/alembic.ini upgrade $Revision
