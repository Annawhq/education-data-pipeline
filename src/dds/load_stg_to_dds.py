"""Разбор успешных загрузок STG с сохранением истории SCD2."""

import hashlib
import json
from datetime import timedelta

from src.db import get_connection


FIELDS = ("text", "category", "difficulty", "type", "explanation", "quizId", "quizTitle")


def normalize(payload):
    if not isinstance(payload, dict):
        raise ValueError("Вопрос должен быть JSON-объектом")
    content = {key: payload.get(key) for key in FIELDS}
    if not isinstance(content["text"], str) or not content["text"].strip():
        raise ValueError("Отсутствует текст вопроса")
    for key, value in content.items():
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Поле {key} должно быть строкой или null")
    answers = payload.get("answers")
    tags = payload.get("tags")
    if not isinstance(answers, list) or not isinstance(tags, list):
        raise ValueError("answers и tags должны быть массивами")
    content["answers"] = []
    seen = set()
    for answer in answers:
        if not isinstance(answer, dict):
            raise ValueError("Ответ должен быть объектом")
        answer_id = answer.get("id")
        if not isinstance(answer_id, str) or not answer_id or answer_id in seen:
            raise ValueError("Отсутствующий или повторный ID ответа")
        if not isinstance(answer.get("text"), str) or type(answer.get("isCorrect")) is not bool:
            raise ValueError("Некорректный текст или isCorrect ответа")
        seen.add(answer_id)
        content["answers"].append({key: answer[key] for key in ("id", "text", "isCorrect")})
    if any(not isinstance(tag, str) or not tag.strip() for tag in tags):
        raise ValueError("Теги должны быть непустыми строками")
    # Порядок тегов незначим; порядок ответов сохраняем и сравниваем.
    content["tags"] = sorted({tag.strip() for tag in tags})
    digest = hashlib.sha256(
        json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return content, digest


def get_current_version(cursor, source, external_id):
    cursor.execute("""
        SELECT question_version_id, content_hash, valid_from
        FROM dds.questions
        WHERE source_system = %s AND external_id = %s AND is_current
    """, (source, external_id))
    return cursor.fetchone()


def check_observation_order(cursor, source, external_id, loaded_at, raw_id):
    """Сравнивает тот же составной ключ, по которому читаются записи STG."""
    cursor.execute("""
        SELECT r.loaded_at, r.id
        FROM dds.processed_raw p
        JOIN stg.quizapi_questions_raw r ON r.id = p.raw_id
        WHERE r.source_system = %s AND r.external_id = %s
        ORDER BY r.loaded_at DESC, r.id DESC
        LIMIT 1
    """, (source, external_id))
    last_seen = cursor.fetchone()
    if last_seen is not None and (loaded_at, raw_id) < last_seen:
        raise ValueError("Поздняя запись STG: требуется пересчёт истории")


def save_answers_and_tags(cursor, version_id, content):
    cursor.executemany("""
        INSERT INTO dds.answers (
            question_version_id, external_id, answer_text, is_correct, answer_position
        ) VALUES (%s, %s, %s, %s, %s)
    """, [
        (version_id, answer["id"], answer["text"], answer["isCorrect"], position)
        for position, answer in enumerate(content["answers"], start=1)
    ])
    cursor.executemany(
        "INSERT INTO dds.tags (tag_name) VALUES (%s) ON CONFLICT DO NOTHING",
        [(tag,) for tag in content["tags"]],
    )
    cursor.execute("""
        INSERT INTO dds.question_tags (question_version_id, tag_id)
        SELECT %s, tag_id FROM dds.tags WHERE tag_name = ANY(%s)
    """, (version_id, content["tags"]))


def create_version(cursor, source, external_id, batch_id, loaded_at, content, digest, current):
    valid_from = loaded_at
    if current:
        # Разные наблюдения могут иметь одинаковое время загрузки.
        valid_from = max(valid_from, current[2] + timedelta(microseconds=1))
        cursor.execute("""
            UPDATE dds.questions SET valid_to = %s, is_current = false
            WHERE question_version_id = %s
        """, (valid_from, current[0]))
    cursor.execute("""
        INSERT INTO dds.questions (
            source_system, external_id, question_text, category, difficulty,
            question_type, explanation, quiz_external_id, quiz_title,
            content_hash, batch_id, valid_from
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING question_version_id
    """, (
        source, external_id, *(content[key] for key in FIELDS),
        digest, batch_id, valid_from,
    ))
    version_id = cursor.fetchone()[0]
    save_answers_and_tags(cursor, version_id, content)


def process_question(cursor, row):
    raw_id, source, external_id, payload, batch_id, loaded_at = row
    try:
        content, digest = normalize(payload)
        if str(payload.get("id")) != external_id:
            raise ValueError("payload.id не совпадает с external_id")
        check_observation_order(cursor, source, external_id, loaded_at, raw_id)
        current = get_current_version(cursor, source, external_id)
        if current and current[1] == digest:
            outcome = "unchanged"
        else:
            create_version(
                cursor, source, external_id, batch_id, loaded_at, content, digest, current,
            )
            outcome = "changed" if current else "created"
        cursor.execute("INSERT INTO dds.processed_raw (raw_id) VALUES (%s)", (raw_id,))
        return outcome
    except ValueError as error:
        raise ValueError(f"STG id={raw_id}: {error}") from error


def process_pending(connection):
    """Работает в транзакции вызывающего кода; при ошибке изменения откатываются."""
    stats = {"processed": 0, "created": 0, "changed": 0, "unchanged": 0}
    with connection.cursor() as cursor:
        # Сериализует запуски загрузчика, включая ручные запуски вне Airflow.
        cursor.execute("SELECT pg_advisory_xact_lock(847231, 1)")
        # Серверный курсор читает фиксированную выборку порциями, без fetchall().
        with connection.cursor(name="dds_pending") as pending:
            pending.itersize = 500
            pending.execute("""
                SELECT r.id, r.source_system, r.external_id, r.payload, r.batch_id, r.loaded_at
                FROM stg.quizapi_questions_raw r
                JOIN stg.load_batches b USING (batch_id)
                WHERE b.status = 'SUCCESS'
                  AND NOT EXISTS (
                      SELECT 1 FROM dds.processed_raw p WHERE p.raw_id = r.id
                  )
                ORDER BY r.loaded_at, r.id
            """)
            for row in pending:
                outcome = process_question(cursor, row)
                stats[outcome] += 1
                stats["processed"] += 1
    return stats


def load_stg_to_dds():
    with get_connection() as connection:
        stats = process_pending(connection)
    print(f"STG → DDS: {stats}")
    return stats


if __name__ == "__main__":
    load_stg_to_dds()
