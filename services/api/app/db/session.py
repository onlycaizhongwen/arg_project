from collections.abc import Iterator

import psycopg

from app.core.config import settings


def build_database_url() -> str:
    return (
        "postgresql+psycopg://"
        f"{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


def build_psycopg_url() -> str:
    return (
        "postgresql://"
        f"{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


def get_connection() -> Iterator[psycopg.Connection]:
    connection = psycopg.connect(build_psycopg_url())
    try:
        yield connection
    finally:
        connection.close()
