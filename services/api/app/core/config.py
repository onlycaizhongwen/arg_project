from functools import lru_cache
from os import getenv


class Settings:
    app_name: str = getenv("APP_NAME", "rag-cleaning-api")
    app_version: str = getenv("APP_VERSION", "0.1.0")
    app_env: str = getenv("APP_ENV", "local")

    postgres_host: str = getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = getenv("POSTGRES_DB", "rag_cleaning")
    postgres_user: str = getenv("POSTGRES_USER", "rag")
    postgres_password: str = getenv("POSTGRES_PASSWORD", "rag")

    rabbitmq_host: str = getenv("RABBITMQ_HOST", "localhost")
    rabbitmq_port: int = int(getenv("RABBITMQ_PORT", "5672"))
    rabbitmq_user: str = getenv("RABBITMQ_USER", "rag")
    rabbitmq_password: str = getenv("RABBITMQ_PASSWORD", "rag")
    rabbitmq_queue: str = getenv("RABBITMQ_QUEUE", "cleaning.jobs")

    minio_endpoint: str = getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_access_key: str = getenv("MINIO_ACCESS_KEY", "rag")
    minio_secret_key: str = getenv("MINIO_SECRET_KEY", "rag_password")
    minio_bucket: str = getenv("MINIO_BUCKET", "rag-documents")
    minio_secure: bool = getenv("MINIO_SECURE", "false").lower() == "true"

    qdrant_host: str = getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(getenv("QDRANT_PORT", "6333"))
    qdrant_collection: str = getenv("QDRANT_COLLECTION", "rag_chunks")

    embedding_provider: str = getenv("EMBEDDING_PROVIDER", "mock")
    embedding_model: str = getenv("EMBEDDING_MODEL", "mock-embedding")
    embedding_dimension: int = int(getenv("EMBEDDING_DIMENSION", "1024"))
    embedding_output_type: str = getenv("EMBEDDING_OUTPUT_TYPE", "dense")
    dashscope_api_key: str = getenv("DASHSCOPE_API_KEY", "")
    embedding_base_url: str = getenv("EMBEDDING_BASE_URL", "")
    rerank_provider: str = getenv("RERANK_PROVIDER", "disabled")
    rerank_model: str = getenv("RERANK_MODEL", "mock-reranker")
    rerank_base_url: str = getenv("RERANK_BASE_URL", "")
    rerank_timeout_seconds: float = float(getenv("RERANK_TIMEOUT_SECONDS", "5"))

    def validate(self) -> None:
        required = {
            "POSTGRES_HOST": self.postgres_host,
            "POSTGRES_DB": self.postgres_db,
            "POSTGRES_USER": self.postgres_user,
            "POSTGRES_PASSWORD": self.postgres_password,
            "RABBITMQ_HOST": self.rabbitmq_host,
            "RABBITMQ_USER": self.rabbitmq_user,
            "RABBITMQ_PASSWORD": self.rabbitmq_password,
            "MINIO_ENDPOINT": self.minio_endpoint,
            "MINIO_ACCESS_KEY": self.minio_access_key,
            "MINIO_SECRET_KEY": self.minio_secret_key,
            "QDRANT_HOST": self.qdrant_host,
            "QDRANT_COLLECTION": self.qdrant_collection,
            "EMBEDDING_PROVIDER": self.embedding_provider,
            "EMBEDDING_MODEL": self.embedding_model,
            "EMBEDDING_OUTPUT_TYPE": self.embedding_output_type,
            "RERANK_PROVIDER": self.rerank_provider,
            "RERANK_MODEL": self.rerank_model,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise RuntimeError(f"Missing required settings: {', '.join(missing)}")
        if self.embedding_provider == "dashscope" and not self.dashscope_api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is required when EMBEDDING_PROVIDER=dashscope")
        if self.embedding_provider == "local_bge" and not self.embedding_base_url:
            raise RuntimeError("EMBEDDING_BASE_URL is required when EMBEDDING_PROVIDER=local_bge")
        if self.embedding_dimension <= 0:
            raise RuntimeError("EMBEDDING_DIMENSION must be greater than 0")
        if self.embedding_output_type != "dense":
            raise RuntimeError("Only EMBEDDING_OUTPUT_TYPE=dense is supported in the MVP")
        if self.rerank_provider not in {"disabled", "mock", "external"}:
            raise RuntimeError("RERANK_PROVIDER must be one of disabled, mock, external")
        if self.rerank_provider == "external" and not self.rerank_base_url:
            raise RuntimeError("RERANK_BASE_URL is required when RERANK_PROVIDER=external")
        if self.rerank_timeout_seconds <= 0:
            raise RuntimeError("RERANK_TIMEOUT_SECONDS must be greater than 0")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
