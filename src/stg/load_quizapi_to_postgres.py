import uuid
from datetime import datetime, timezone
from psycopg.types.json import Jsonb
from src.db import get_connection
from src.stg.quizapi_client import get_questions


def load_quizapi_questions(
        category: str = "Python",
        total: int = 100,):
    """
    Получает вопросы из QuizAPI
    и сохраняет их в STG PostgreSQL.
    """

    started_at = datetime.now(timezone.utc)

    print(
        f"Запрашиваем {total} вопросов "
        f"категории {category}..."
    )

    questions = get_questions(
        category=category,
        total=total,
    )

    print(
        f"QuizAPI вернул вопросов: "
        f"{len(questions)}"
    )

    batch_id = uuid.uuid4()

    request_params = {
        "category": category,
        "total": total,
    }

    with get_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO stg.load_batches (
                    batch_id,
                    source_system,
                    entity_type,
                    request_params,
                    started_at,
                    status,
                    records_loaded
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    batch_id,
                    "quizapi",
                    "questions",
                    Jsonb(request_params),
                    started_at,
                    "RUNNING",
                    0,
                ),
            )

            records_loaded = 0

            for question in questions:
                cursor.execute(
                    """
                    INSERT INTO stg.quizapi_questions_raw (
                        source_system,
                        external_id,
                        payload,
                        batch_id
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    ON CONFLICT (
                        batch_id,
                        external_id
                    )
                    DO NOTHING
                    """,
                    (
                        "quizapi",
                        question["id"],
                        Jsonb(question),
                        batch_id,
                    ),
                )

                records_loaded += cursor.rowcount

            finished_at = datetime.now(timezone.utc)

            cursor.execute(
                """
                UPDATE stg.load_batches
                SET
                    finished_at = %s,
                    status = %s,
                    records_loaded = %s
                WHERE batch_id = %s
                """,
                (
                    finished_at,
                    "SUCCESS",
                    records_loaded,
                    batch_id,
                ),
            )

    print()
    print("Загрузка завершена.")
    print(f"Batch ID: {batch_id}")
    print(f"Записано вопросов: {records_loaded}")


if __name__ == "__main__":
    load_quizapi_questions(
        category="Python",
        total=100,
    )
