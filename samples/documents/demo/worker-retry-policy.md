# Worker Retry And Idempotency Policy

Each cleaning job moves from PENDING to RUNNING when the Worker starts processing it.
If processing fails, the Worker increments retry_count and marks the job as RETRYING while retry_count is below WORKER_MAX_RETRIES.
RabbitMQ requeues the message when the job status is RETRYING.

After the maximum retry count is reached, the job status becomes FAILED and the error_message is stored for troubleshooting.
If a job has already reached SUCCEEDED, duplicate messages are skipped.
Text chunk identifiers are deterministic from document_version_id and chunk_index, so repeated processing uses upsert instead of creating duplicate chunks.

This idempotency rule protects the MVP from repeated delivery, worker restart, and manual retry during local demonstrations.
