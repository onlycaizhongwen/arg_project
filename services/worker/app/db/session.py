from app.core.config import settings


def build_psycopg_url() -> str:
    return (
        "postgresql://"
        f"{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )
