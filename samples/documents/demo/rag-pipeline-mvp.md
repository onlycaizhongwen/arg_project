# RAG Pipeline MVP Runbook

The MVP service accepts a document upload through FastAPI and stores the raw file in MinIO.
PostgreSQL records the document, document version, cleaning job, text chunks, and vector records.
RabbitMQ carries the cleaning job message so the Python Worker can process the document asynchronously.

The Worker parses the file, normalizes whitespace, creates paragraph chunks, and calls the configured Embedding provider.
For local validation the provider is local_bge, the model is bge-m3, and the vector dimension is 1024.
The resulting vectors are written to Qdrant with tenant_id, knowledge_base_id, document_id, and document_version_id payload fields.

The search API creates a query embedding, recalls candidates from Qdrant, applies recall_size and pre_rank_size limits, and returns top_k chunks.
In the MVP, rerank_enabled is false because Cross-Encoder reranking is reserved for the next stage.
