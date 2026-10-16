-- Журнал предотвращает повторное проигрывание старых версий при перезапуске.
CREATE TABLE IF NOT EXISTS dds.processed_raw (
    raw_id BIGINT PRIMARY KEY REFERENCES stg.quizapi_questions_raw(id),
    processed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
