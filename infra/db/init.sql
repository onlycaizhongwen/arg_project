CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS data_source (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ENABLED',
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    knowledge_base_id TEXT NOT NULL DEFAULT 'kb-default',
    data_source_id TEXT NOT NULL REFERENCES data_source(id),
    title TEXT NOT NULL,
    source_uri TEXT,
    content_type TEXT,
    status TEXT NOT NULL DEFAULT 'CREATED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL,
    object_key TEXT NOT NULL,
    checksum TEXT,
    status TEXT NOT NULL DEFAULT 'UPLOADED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, version_no)
);

CREATE TABLE IF NOT EXISTS cleaning_job (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_version_id UUID NOT NULL REFERENCES document_version(id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS text_chunk (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_version_id UUID NOT NULL REFERENCES document_version(id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL,
    knowledge_base_id TEXT NOT NULL DEFAULT 'kb-default',
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_version_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS vector_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID NOT NULL REFERENCES text_chunk(id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL,
    collection_name TEXT NOT NULL,
    vector_id TEXT NOT NULL,
    embedding_provider TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dimension INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (collection_name, vector_id)
);

CREATE INDEX IF NOT EXISTS idx_document_tenant_kb ON document (tenant_id, knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_document_tenant_source ON document (tenant_id, data_source_id);
CREATE INDEX IF NOT EXISTS idx_cleaning_job_status ON cleaning_job (status, created_at);
CREATE INDEX IF NOT EXISTS idx_text_chunk_tenant_kb ON text_chunk (tenant_id, knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_text_chunk_document_version ON text_chunk (document_version_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_text_chunk_content_fts ON text_chunk
USING GIN (to_tsvector('simple', content));
CREATE INDEX IF NOT EXISTS idx_vector_record_chunk ON vector_record (chunk_id);

INSERT INTO data_source (id, tenant_id, name, type, status)
VALUES ('default-file-source', 'default', 'default file source', 'FILE', 'ENABLED')
ON CONFLICT (id) DO UPDATE
SET
    tenant_id = EXCLUDED.tenant_id,
    name = EXCLUDED.name,
    type = EXCLUDED.type,
    status = EXCLUDED.status,
    updated_at = now();
