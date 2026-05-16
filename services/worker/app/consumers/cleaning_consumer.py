from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import pika
import psycopg
from psycopg.types.json import Jsonb
from qdrant_client.http import models

from app.chunkers.paragraph_chunker import TextChunk, chunk_by_paragraph
from app.cleaners.basic_cleaner import clean_text
from app.core.config import settings
from app.db.session import build_psycopg_url
from app.embeddings.embedding_client import build_embedding_client
from app.infra.object_store import download_document
from app.parsers.base import parse_document
from app.vectorstores.qdrant_client import build_qdrant_client, collection_name, upsert_vectors


@dataclass(frozen=True)
class CleaningJobMessage:
    job_id: str
    tenant_id: str
    knowledge_base_id: str
    permission_tags: list[str]
    document_id: str
    document_version_id: str
    object_key: str
    filename: str
    rebuild: bool = False
    operation: str = "INDEX_DOCUMENT"


def handle_cleaning_job(message: CleaningJobMessage) -> None:
    if _get_job_status(message.job_id) == "SUCCEEDED":
        print(f"skip succeeded job: {message.job_id}", flush=True)
        return

    _mark_job_started(message.job_id)
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = download_document(message.object_key, Path(tmp_dir), message.filename)
            parsed = parse_document(str(file_path))
            chunks = chunk_by_paragraph(clean_text(parsed.text))
            if not chunks:
                if message.rebuild:
                    stale_chunk_count = _delete_stale_chunks(message, keep_chunk_ids=[])
                else:
                    stale_chunk_count = 0
                _mark_job_finished(message, chunk_count=0, vector_count=0, stale_chunk_count=stale_chunk_count)
                return
            chunk_ids = _insert_chunks(message, chunks)
            vectors = build_embedding_client().embed_documents([chunk.content for chunk in chunks])
            upsert_vectors(
                vectors=vectors,
                chunk_ids=chunk_ids,
                payloads=[
                    {
                        "tenant_id": message.tenant_id,
                        "knowledge_base_id": message.knowledge_base_id,
                        "permission_tags": message.permission_tags,
                        "document_id": message.document_id,
                        "document_version_id": message.document_version_id,
                        "chunk_index": chunk.chunk_no,
                        **parsed.metadata,
                    }
                    for chunk in chunks
                ],
            )
            _insert_vector_records(message, chunk_ids)
            if message.rebuild:
                stale_chunk_count = _delete_stale_chunks(message, keep_chunk_ids=chunk_ids)
            else:
                stale_chunk_count = 0
        _mark_job_finished(
            message,
            chunk_count=len(chunk_ids),
            vector_count=len(chunk_ids),
            stale_chunk_count=stale_chunk_count,
        )
    except Exception as exc:
        _mark_job_failed(message, str(exc))
        raise


def consume_forever() -> None:
    credentials = pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_password)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.rabbitmq_host,
            port=settings.rabbitmq_port,
            credentials=credentials,
        )
    )
    channel = connection.channel()
    channel.queue_declare(queue=settings.rabbitmq_queue, durable=True)
    channel.basic_qos(prefetch_count=1)

    def on_message(
        channel: pika.adapters.blocking_connection.BlockingChannel,
        method: pika.spec.Basic.Deliver,
        properties: pika.BasicProperties,
        body: bytes,
    ) -> None:
        del properties
        payload = json.loads(body.decode("utf-8"))
        payload.setdefault("knowledge_base_id", "kb-default")
        payload.setdefault("permission_tags", ["public"])
        message = CleaningJobMessage(**payload)
        try:
            handle_cleaning_job(message)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            channel.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=_should_retry(message.job_id),
            )

    channel.basic_consume(queue=settings.rabbitmq_queue, on_message_callback=on_message)
    print(f"worker consuming queue: {settings.rabbitmq_queue}", flush=True)
    channel.start_consuming()


def _insert_chunks(message: CleaningJobMessage, chunks: list[TextChunk]) -> list[str]:
    chunk_ids = [
        str(uuid5(NAMESPACE_URL, f"{message.document_version_id}:{chunk.chunk_no}"))
        for chunk in chunks
    ]
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            for chunk_id, chunk in zip(chunk_ids, chunks, strict=True):
                cursor.execute(
                    """
                    INSERT INTO text_chunk (
                        id, document_version_id, tenant_id, knowledge_base_id, permission_tags, chunk_index, content, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (document_version_id, chunk_index)
                    DO UPDATE SET
                        knowledge_base_id = EXCLUDED.knowledge_base_id,
                        permission_tags = EXCLUDED.permission_tags,
                        content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        chunk_id,
                        message.document_version_id,
                        message.tenant_id,
                        message.knowledge_base_id,
                        message.permission_tags,
                        chunk.chunk_no,
                        chunk.content,
                        Jsonb(chunk.metadata),
                    ),
                )
    return chunk_ids


def _insert_vector_records(message: CleaningJobMessage, chunk_ids: list[str]) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            for chunk_id in chunk_ids:
                cursor.execute(
                    """
                    INSERT INTO vector_record (
                        chunk_id,
                        tenant_id,
                        collection_name,
                        vector_id,
                        embedding_provider,
                        embedding_model,
                        embedding_dimension
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (collection_name, vector_id)
                    DO UPDATE SET
                        chunk_id = EXCLUDED.chunk_id,
                        tenant_id = EXCLUDED.tenant_id,
                        embedding_provider = EXCLUDED.embedding_provider,
                        embedding_model = EXCLUDED.embedding_model,
                        embedding_dimension = EXCLUDED.embedding_dimension
                    """,
                    (
                        chunk_id,
                        message.tenant_id,
                        settings.qdrant_collection,
                        chunk_id,
                        settings.embedding_provider,
                        settings.embedding_model,
                        settings.embedding_dimension,
                    ),
                )


def _delete_stale_chunks(message: CleaningJobMessage, keep_chunk_ids: list[str]) -> int:
    stale_chunk_ids = _load_stale_chunk_ids(message, keep_chunk_ids)
    if not stale_chunk_ids:
        return 0
    client = build_qdrant_client()
    client.delete(
        collection_name=collection_name(),
        points_selector=models.PointIdsList(points=stale_chunk_ids),
        wait=True,
    )
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM vector_record WHERE chunk_id = ANY(%s::uuid[])", (stale_chunk_ids,))
            cursor.execute("DELETE FROM text_chunk WHERE id = ANY(%s::uuid[])", (stale_chunk_ids,))
    return len(stale_chunk_ids)


def _load_stale_chunk_ids(message: CleaningJobMessage, keep_chunk_ids: list[str]) -> list[str]:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            if keep_chunk_ids:
                cursor.execute(
                    """
                    SELECT id
                    FROM text_chunk
                    WHERE document_version_id = %s
                      AND tenant_id = %s
                      AND NOT (id = ANY(%s::uuid[]))
                    """,
                    (message.document_version_id, message.tenant_id, keep_chunk_ids),
                )
            else:
                cursor.execute(
                    """
                    SELECT id
                    FROM text_chunk
                    WHERE document_version_id = %s
                      AND tenant_id = %s
                    """,
                    (message.document_version_id, message.tenant_id),
                )
            rows = cursor.fetchall()
    return [str(row[0]) for row in rows]


def _get_job_status(job_id: str) -> str | None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT status FROM cleaning_job WHERE id = %s", (job_id,))
            row = cursor.fetchone()
    return row[0] if row else None


def _mark_job_started(job_id: str) -> None:
    _execute(
        """
        UPDATE cleaning_job
        SET status = 'RUNNING', started_at = now(), updated_at = now()
        WHERE id = %s
        """,
        (job_id,),
    )


def _mark_job_finished(
    message: CleaningJobMessage,
    *,
    chunk_count: int,
    vector_count: int,
    stale_chunk_count: int,
) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE cleaning_job
                SET status = 'SUCCEEDED', finished_at = now(), updated_at = now()
                WHERE id = %s
                """,
                (message.job_id,),
            )
            cursor.execute(
                """
                UPDATE document_version
                SET status = 'SUPERSEDED'
                WHERE document_id = %s
                  AND id <> %s
                  AND status = 'INDEXED'
                """,
                (message.document_id, message.document_version_id),
            )
            cursor.execute(
                """
                UPDATE document_version
                SET status = 'INDEXED'
                WHERE id = %s
                """,
                (message.document_version_id,),
            )
            cursor.execute(
                """
                UPDATE document
                SET
                    status = 'INDEXED',
                    operation_status = CASE
                        WHEN operation_lock_id = %s THEN NULL
                        ELSE operation_status
                    END,
                    operation_lock_id = CASE
                        WHEN operation_lock_id = %s THEN NULL
                        ELSE operation_lock_id
                    END,
                    operation_started_at = CASE
                        WHEN operation_lock_id = %s THEN NULL
                        ELSE operation_started_at
                    END,
                    updated_at = now()
                WHERE id = %s
                  AND status <> 'DELETED'
                """,
                (message.job_id, message.job_id, message.job_id, message.document_id),
            )
            cursor.execute(
                """
                INSERT INTO document_audit_event (
                    id,
                    tenant_id,
                    document_id,
                    document_version_id,
                    job_id,
                    operation,
                    actor_id,
                    request_source,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'worker', 'worker', %s)
                """,
                (
                    str(uuid4()),
                    message.tenant_id,
                    message.document_id,
                    message.document_version_id,
                    message.job_id,
                    _success_audit_operation(message),
                    Jsonb(
                        {
                            "job_operation": message.operation,
                            "chunk_count": chunk_count,
                            "vector_count": vector_count,
                            "stale_chunk_count": stale_chunk_count,
                            "embedding_provider": settings.embedding_provider,
                            "embedding_model": settings.embedding_model,
                            "embedding_dimension": settings.embedding_dimension,
                        }
                    ),
                ),
            )


def _mark_job_failed(message: CleaningJobMessage, error_message: str) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE cleaning_job
                SET
                    retry_count = retry_count + 1,
                    status = CASE
                        WHEN retry_count + 1 < %s THEN 'RETRYING'
                        ELSE 'FAILED'
                    END,
                    error_message = %s,
                    finished_at = CASE
                        WHEN retry_count + 1 < %s THEN NULL
                        ELSE now()
                    END,
                    updated_at = now()
                WHERE id = %s
                RETURNING status
                """,
                (
                    settings.worker_max_retries,
                    error_message[:2000],
                    settings.worker_max_retries,
                    message.job_id,
                ),
            )
            row = cursor.fetchone()
            if row and row[0] == "FAILED":
                cursor.execute(
                    """
                    UPDATE document
                    SET
                        operation_status = NULL,
                        operation_lock_id = NULL,
                        operation_started_at = NULL,
                        updated_at = now()
                    WHERE id = %s
                      AND tenant_id = %s
                      AND operation_lock_id = %s
                    """,
                    (message.document_id, message.tenant_id, message.job_id),
                )
                cursor.execute(
                    """
                    INSERT INTO document_audit_event (
                        id,
                        tenant_id,
                        document_id,
                        document_version_id,
                        job_id,
                        operation,
                        actor_id,
                        request_source,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'worker', 'worker', %s)
                    """,
                    (
                        str(uuid4()),
                        message.tenant_id,
                        message.document_id,
                        message.document_version_id,
                        message.job_id,
                        _failure_audit_operation(message),
                        Jsonb(
                            {
                                "job_operation": message.operation,
                                "error_message": error_message[:2000],
                                "worker_max_retries": settings.worker_max_retries,
                            }
                        ),
                    ),
                )


def _success_audit_operation(message: CleaningJobMessage) -> str:
    if message.operation == "REBUILD_INDEX":
        return "DOCUMENT_INDEX_REBUILD_SUCCEEDED"
    if message.operation == "RETRY_JOB":
        return "JOB_RETRY_SUCCEEDED"
    return "DOCUMENT_VERSION_INDEXED"


def _failure_audit_operation(message: CleaningJobMessage) -> str:
    if message.operation == "REBUILD_INDEX":
        return "DOCUMENT_INDEX_REBUILD_FAILED"
    if message.operation == "RETRY_JOB":
        return "JOB_RETRY_FAILED"
    return "DOCUMENT_VERSION_INDEX_FAILED"


def _should_retry(job_id: str) -> bool:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT status FROM cleaning_job WHERE id = %s", (job_id,))
            row = cursor.fetchone()
    return bool(row and row[0] == "RETRYING")


def _execute(sql: str, params: tuple[object, ...]) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
