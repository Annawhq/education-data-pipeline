CREATE SCHEMA IF NOT EXISTS cdm;

-- Денормализованный факт: одна строка = текущая версия вопроса из DDS.
CREATE TABLE IF NOT EXISTS cdm.fact_questions (
    question_version_id  BIGINT PRIMARY KEY,
    external_id          TEXT NOT NULL,
    question_text        TEXT NOT NULL,
    category             TEXT,
    difficulty           TEXT,
    question_type        TEXT,
    quiz_title           TEXT,

    answer_count         INTEGER NOT NULL DEFAULT 0,
    correct_answer_count INTEGER NOT NULL DEFAULT 0,
    has_correct_answer   BOOLEAN NOT NULL DEFAULT FALSE,

    tag_count            INTEGER NOT NULL DEFAULT 0,
    tags                 TEXT[]  NOT NULL DEFAULT '{}',

    valid_from           TIMESTAMPTZ NOT NULL,
    cdm_updated_at       TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT fact_questions_correct_answer_consistency
        CHECK (has_correct_answer = (correct_answer_count > 0)),
    CONSTRAINT fact_questions_correct_le_total
        CHECK (correct_answer_count <= answer_count)
);

CREATE INDEX IF NOT EXISTS idx_fact_questions_category
    ON cdm.fact_questions (category);
CREATE INDEX IF NOT EXISTS idx_fact_questions_difficulty
    ON cdm.fact_questions (difficulty);
CREATE INDEX IF NOT EXISTS idx_fact_questions_tags_gin
    ON cdm.fact_questions USING GIN (tags);

-- Агрегат по категориям: пересобирается целиком.
CREATE TABLE IF NOT EXISTS cdm.agg_questions_by_category (
    category             TEXT PRIMARY KEY,
    question_count       BIGINT NOT NULL,
    with_correct_answer  BIGINT NOT NULL,
    correct_answer_ratio NUMERIC(6, 4) NOT NULL,
    avg_answer_count     NUMERIC(8, 2) NOT NULL,
    refreshed_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Агрегат по тегам: один вопрос с N тегами даёт N строк.
CREATE TABLE IF NOT EXISTS cdm.agg_questions_by_tag (
    tag                  TEXT PRIMARY KEY,
    question_count       BIGINT NOT NULL,
    with_correct_answer  BIGINT NOT NULL,
    correct_answer_ratio NUMERIC(6, 4) NOT NULL,
    refreshed_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);