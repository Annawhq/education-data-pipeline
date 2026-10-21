import json

from airflow.sdk import dag, task

from src.db import get_connection

CHECKS: list[tuple[str, str]] = [
    ("dds_one_current_version_per_question", """
        SELECT COUNT(*) FROM (
            SELECT 1 FROM dds.questions
            WHERE is_current
            GROUP BY source_system, external_id
            HAVING COUNT(*) > 1
        ) t
    """),
    ("dds_current_flag_matches_valid_to", """
        SELECT COUNT(*) FROM dds.questions
        WHERE (is_current AND valid_to IS NOT NULL)
           OR (NOT is_current AND valid_to IS NULL)
    """),
    ("dds_no_overlapping_version_intervals", """
        SELECT COUNT(*) FROM dds.questions a
        JOIN dds.questions b
          ON a.source_system = b.source_system
         AND a.external_id = b.external_id
         AND a.question_version_id < b.question_version_id
        WHERE a.valid_from < COALESCE(b.valid_to, 'infinity'::timestamptz)
          AND b.valid_from < COALESCE(a.valid_to, 'infinity'::timestamptz)
    """),
    ("dds_every_question_has_exactly_one_current", """
        SELECT COUNT(*) FROM (
            SELECT 1 FROM dds.questions
            GROUP BY source_system, external_id
            HAVING COUNT(*) FILTER (WHERE is_current) <> 1
        ) t
    """),
    ("dds_current_questions_have_answers", """
        SELECT COUNT(*) FROM dds.questions q
        WHERE q.is_current
          AND NOT EXISTS (
              SELECT 1 FROM dds.answers a
              WHERE a.question_version_id = q.question_version_id)
    """),
    ("dds_tags_normalized", """
        SELECT COUNT(*) FROM dds.tags
        WHERE tag_name <> btrim(tag_name) OR tag_name = ''
    """),
    ("cdm_fact_set_matches_dds_current", """
        SELECT (SELECT COUNT(*) FROM (
                    SELECT question_version_id FROM dds.questions WHERE is_current
                    EXCEPT
                    SELECT question_version_id FROM cdm.fact_questions) x)
             + (SELECT COUNT(*) FROM (
                    SELECT question_version_id FROM cdm.fact_questions
                    EXCEPT
                    SELECT question_version_id FROM dds.questions WHERE is_current) y)
    """),
    ("cdm_answer_counts_match_dds", """
        SELECT COUNT(*) FROM cdm.fact_questions f
        WHERE f.answer_count <> (
                   SELECT COUNT(*) FROM dds.answers a
                   WHERE a.question_version_id = f.question_version_id)
           OR f.correct_answer_count <> (
                   SELECT COUNT(*) FROM dds.answers a
                   WHERE a.question_version_id = f.question_version_id
                     AND a.is_correct)
    """),
    ("cdm_tag_count_matches_links", """
        SELECT COUNT(*) FROM cdm.fact_questions f
        WHERE f.tag_count <> (
                   SELECT COUNT(*) FROM dds.question_tags qt
                   WHERE qt.question_version_id = f.question_version_id)
           OR f.tag_count <> cardinality(f.tags)
    """),
    ("cdm_agg_category_self_consistent", """
        SELECT COUNT(*) FROM cdm.agg_questions_by_category
        WHERE question_count <= 0
           OR with_correct_answer > question_count
           OR correct_answer_ratio <>
              ROUND(with_correct_answer::numeric / question_count, 4)
    """),
    ("cdm_agg_category_matches_fact", """
        SELECT COUNT(*) FROM (
            SELECT category,
                   COUNT(*) AS question_count,
                   COUNT(*) FILTER (WHERE has_correct_answer) AS with_correct_answer
            FROM cdm.fact_questions
            GROUP BY category
        ) r
        FULL JOIN cdm.agg_questions_by_category a USING (category)
        WHERE r.question_count IS DISTINCT FROM a.question_count
           OR r.with_correct_answer IS DISTINCT FROM a.with_correct_answer
    """),
    ("cdm_agg_tag_matches_fact", """
        SELECT COUNT(*) FROM (
            SELECT t.tag,
                   COUNT(*) AS question_count,
                   COUNT(*) FILTER (WHERE f.has_correct_answer) AS with_correct_answer
            FROM cdm.fact_questions f
            CROSS JOIN LATERAL unnest(f.tags) AS t(tag)
            GROUP BY t.tag
        ) r
        FULL JOIN cdm.agg_questions_by_tag a USING (tag)
        WHERE r.question_count IS DISTINCT FROM a.question_count
           OR r.with_correct_answer IS DISTINCT FROM a.with_correct_answer
    """),
]


@task
def run_quality_checks() -> dict:
    results = []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for name, sql in CHECKS:
                cur.execute(sql)
                violated = int(cur.fetchone()[0])
                results.append((name, "fail" if violated else "pass", violated, sql))
            cur.executemany(
                """INSERT INTO dq.check_results
                       (check_name, status, rows_violated, details)
                   VALUES (%s, %s, %s, %s::jsonb)""",
                [(n, s, v, json.dumps({"sql": q}, ensure_ascii=False))
                 for n, s, v, q in results],
            )
        conn.commit()
    finally:
        conn.close()

    failed = [(n, v) for n, s, v, _ in results if s == "fail"]
    if failed:
        raise ValueError(f"DQ checks failed: {failed}")
    return {"checks": len(results), "failed": 0}


@dag(schedule=None, catchup=False, max_active_runs=1,
     dag_id="check_data_quality",
     description="Проверки качества DDS/CDM перед экспортом")
def check_data_quality_dag():
    run_quality_checks()


check_data_quality_dag()