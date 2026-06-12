CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS production_cases (
    id TEXT PRIMARY KEY,
    owner_user_id TEXT,
    owner_alias TEXT,
    status TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    bundle JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS case_versions (
    case_id TEXT NOT NULL REFERENCES production_cases(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    bundle JSONB NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (case_id, version)
);

CREATE TABLE IF NOT EXISTS case_documents (
    case_id TEXT NOT NULL REFERENCES production_cases(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    document_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    entity_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(body, ''))
    ) STORED,
    PRIMARY KEY (case_id, version, document_id)
);
CREATE INDEX IF NOT EXISTS case_documents_search ON case_documents USING GIN(search_vector);

CREATE TABLE IF NOT EXISTS retrieval_chunks (
    chunk_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    document_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding VECTOR(768),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS retrieval_chunks_vector
    ON retrieval_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS case_assets (
    case_id TEXT NOT NULL,
    path TEXT NOT NULL,
    public_url TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (case_id, path)
);
