from app.core.config import settings
from app.consumers.cleaning_consumer import consume_forever
from app.embeddings.embedding_client import build_embedding_client


def main() -> None:
    settings.validate()
    embedding_client = build_embedding_client()
    print(
        "worker ready",
        {
            "env": settings.app_env,
            "queue": settings.rabbitmq_queue,
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
            "embedding_dimension": embedding_client.dimension,
        },
    )
    consume_forever()


if __name__ == "__main__":
    main()
