CREATE SCHEMA IF NOT EXISTS stg;


CREATE TABLE IF NOT EXISTS stg.load_batches (
    batch_id UUID PRIMARY KEY,

    source_system TEXT NOT NULL,
    entity_type TEXT NOT NULL,

    request_params JSONB NOT NULL,

    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,

    status TEXT NOT NULL,

    records_loaded INTEGER NOT NULL DEFAULT 0
);


CREATE TABLE IF NOT EXISTS stg.quizapi_questions_raw (
    id BIGSERIAL PRIMARY KEY,

    source_system TEXT NOT NULL,

    external_id TEXT NOT NULL,

    payload JSONB NOT NULL,

    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    batch_id UUID NOT NULL
        REFERENCES stg.load_batches(batch_id),

    UNIQUE (batch_id, external_id)
);


CREATE INDEX IF NOT EXISTS idx_quizapi_questions_external_id
    ON stg.quizapi_questions_raw (external_id);


CREATE INDEX IF NOT EXISTS idx_quizapi_questions_batch_id
    ON stg.quizapi_questions_raw (batch_id);