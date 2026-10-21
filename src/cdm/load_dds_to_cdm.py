"""Наполнение CDM-витрин из DDS."""

import logging

from src.db import get_connection

log = logging.getLogger(__name__)


FACT_QUESTIONS_SQL = """
INSERT INTO cdm.fact_questions (
    question_version_id, external_id, question_text,
    category, difficulty, question_type, quiz_title,
    answer_count, correct_answer_count, has_correct_answer,
    tag_count, tags, valid_from, cdm_updated_at
)
SELECT
    q.question_version_id,
    q.external_id,
    q.question_text,
    q.category,
    q.difficulty,
    q.question_type,
    q.quiz_title,
    COALESCE(a.answer_count, 0)             AS answer_count,
    COALESCE(a.correct_answer_count, 0)     AS correct_answer_count,
    COALESCE(a.correct_answer_count, 0) > 0 AS has_correct_answer,
    COALESCE(t.tag_count, 0)                AS tag_count,
    COALESCE(t.tags, '{}')                  AS tags,
    q.valid_from,
    clock_timestamp()                       AS cdm_updated_at
FROM dds.questions q
LEFT JOIN LATERAL (
    SELECT
        COUNT(*)                           AS answer_count,
        COUNT(*) FILTER (WHERE is_correct) AS correct_answer_count
    FROM dds.answers ans
    WHERE ans.question_version_id = q.question_version_id
) a ON TRUE
LEFT JOIN LATERAL (
    SELECT
        COUNT(*)                            AS tag_count,
        COALESCE(array_agg(tg.tag_name ORDER BY tg.tag_name), '{}') AS tags
    FROM dds.question_tags qt
    JOIN dds.tags tg ON tg.tag_id = qt.tag_id
    WHERE qt.question_version_id = q.question_version_id
) t ON TRUE
WHERE q.is_current
ON CONFLICT (question_version_id) DO UPDATE SET
    question_text        = EXCLUDED.question_text,
    category             = EXCLUDED.category,
    difficulty           = EXCLUDED.difficulty,
    question_type        = EXCLUDED.question_type,
    quiz_title           = EXCLUDED.quiz_title,
    answer_count         = EXCLUDED.answer_count,
    correct_answer_count = EXCLUDED.correct_answer_count,
    has_correct_answer   = EXCLUDED.has_correct_answer,
    tag_count            = EXCLUDED.tag_count,
    tags                 = EXCLUDED.tags,
    valid_from           = EXCLUDED.valid_from,
    cdm_updated_at       = clock_timestamp();
"""


AGG_CATEGORY_SQL = """
TRUNCATE cdm.agg_questions_by_category;

INSERT INTO cdm.agg_questions_by_category (
    category, question_count, with_correct_answer,
    correct_answer_ratio, avg_answer_count
)
SELECT
    COALESCE(category, 'unknown')                              AS category,
    COUNT(*)                                                   AS question_count,
    COUNT(*) FILTER (WHERE has_correct_answer)                 AS with_correct_answer,
    ROUND(
        COUNT(*) FILTER (WHERE has_correct_answer)::numeric
        / NULLIF(COUNT(*), 0),
        4
    )                                                           AS correct_answer_ratio,
    ROUND(AVG(answer_count)::numeric, 2)                       AS avg_answer_count
FROM cdm.fact_questions
GROUP BY COALESCE(category, 'unknown');
"""


AGG_TAG_SQL = """
TRUNCATE cdm.agg_questions_by_tag;

INSERT INTO cdm.agg_questions_by_tag (
    tag, question_count, with_correct_answer, correct_answer_ratio
)
SELECT
    tag,
    COUNT(*)                                                   AS question_count,
    COUNT(*) FILTER (WHERE f.has_correct_answer)               AS with_correct_answer,
    ROUND(
        COUNT(*) FILTER (WHERE f.has_correct_answer)::numeric
        / NULLIF(COUNT(*), 0),
        4
    )                                                           AS correct_answer_ratio
FROM cdm.fact_questions f
CROSS JOIN LATERAL unnest(f.tags) AS tag
GROUP BY tag;
"""


def refresh_fact_questions(cursor):
    cursor.execute(FACT_QUESTIONS_SQL)
    log.info("cdm.fact_questions refreshed")


def refresh_aggregates(cursor):
    cursor.execute(AGG_CATEGORY_SQL)
    log.info("cdm.agg_questions_by_category refreshed")
    cursor.execute(AGG_TAG_SQL)
    log.info("cdm.agg_questions_by_tag refreshed")


def load_dds_to_cdm():
    """Пересчитывает CDM-витрины из DDS в одной транзакции."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            # Второй ключ = 2, чтобы не пересекаться с DDS (там ключ = 1).
            cursor.execute("SELECT pg_advisory_xact_lock(847231, 2)")
            refresh_fact_questions(cursor)
            refresh_aggregates(cursor)
            cursor.execute("SELECT COUNT(*) FROM cdm.fact_questions")
            total = cursor.fetchone()[0]
    log.info("CDM refreshed: %s current question versions", total)
    return {"fact_questions": total}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    load_dds_to_cdm()