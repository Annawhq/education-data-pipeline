CREATE SCHEMA IF NOT EXISTS dds;

-- Каждая строка — отдельная версия вопроса (SCD2).
CREATE TABLE IF NOT EXISTS dds.questions (
    question_version_id BIGSERIAL PRIMARY KEY,
    source_system TEXT NOT NULL,
    external_id TEXT NOT NULL,
    question_text TEXT NOT NULL,
    category TEXT,
    difficulty TEXT,
    question_type TEXT,
    explanation TEXT,
    quiz_external_id TEXT,
    quiz_title TEXT,

    -- SHA-256 нормализованного содержимого, включая ответы и теги.
    content_hash TEXT NOT NULL
        CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    batch_id UUID NOT NULL REFERENCES stg.load_batches(batch_id),

    -- Интервал действия версии: [valid_from, valid_to).
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT questions_valid_interval
        CHECK (valid_to IS NULL OR valid_to > valid_from),
    CONSTRAINT questions_current_consistency
        CHECK (is_current = (valid_to IS NULL)),
    UNIQUE (source_system, external_id, valid_from)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_one_current
    ON dds.questions (source_system, external_id)
    WHERE is_current;

CREATE INDEX IF NOT EXISTS idx_questions_batch_id
    ON dds.questions (batch_id);

CREATE TABLE IF NOT EXISTS dds.answers (
    answer_id BIGSERIAL PRIMARY KEY,
    question_version_id BIGINT NOT NULL
        REFERENCES dds.questions(question_version_id),
    external_id TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    answer_position INTEGER NOT NULL CHECK (answer_position > 0),
    UNIQUE (question_version_id, external_id),
    UNIQUE (question_version_id, answer_position)
);

CREATE TABLE IF NOT EXISTS dds.tags (
    tag_id BIGSERIAL PRIMARY KEY,
    tag_name TEXT NOT NULL UNIQUE,
    CONSTRAINT tags_nonempty_name
        CHECK (tag_name = btrim(tag_name) AND tag_name <> '')
);

CREATE TABLE IF NOT EXISTS dds.question_tags (
    question_version_id BIGINT NOT NULL
        REFERENCES dds.questions(question_version_id),
    tag_id BIGINT NOT NULL REFERENCES dds.tags(tag_id),
    PRIMARY KEY (question_version_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_question_tags_tag_id
    ON dds.question_tags (tag_id);
