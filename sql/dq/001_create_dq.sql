CREATE SCHEMA IF NOT EXISTS dq;

-- Журнал результатов проверок качества данных.
CREATE TABLE IF NOT EXISTS dq.check_results (
    check_id      BIGSERIAL PRIMARY KEY,
    check_name    TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('pass', 'fail')),
    rows_violated BIGINT NOT NULL,
    details       JSONB NOT NULL DEFAULT '{}',
    checked_at    TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_check_results_name_time
    ON dq.check_results (check_name, checked_at DESC);