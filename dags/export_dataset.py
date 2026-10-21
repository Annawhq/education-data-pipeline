import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from airflow.sdk import dag, task

from src.db import get_connection

EXPORT_DIR = Path(os.getenv("EXPORT_DIR", "/opt/airflow/data/export"))

EXPORT_SQL = """
    SELECT
        q.question_version_id,
        q.external_id,
        q.question_text,
        q.category,
        q.difficulty,
        q.question_type,
        q.explanation,
        COALESCE(tg.tags, '{}')    AS tags,
        COALESCE(ans.answers, '[]') AS answers
    FROM dds.questions q
    LEFT JOIN LATERAL (
        SELECT array_agg(t.tag_name ORDER BY t.tag_name) AS tags
        FROM dds.question_tags qt
        JOIN dds.tags t ON t.tag_id = qt.tag_id
        WHERE qt.question_version_id = q.question_version_id
    ) tg ON TRUE
    LEFT JOIN LATERAL (
        SELECT json_agg(
                   json_build_object('position', a.answer_position,
                                     'text', a.answer_text,
                                     'is_correct', a.is_correct)
                   ORDER BY a.answer_position) AS answers
        FROM dds.answers a
        WHERE a.question_version_id = q.question_version_id
    ) ans ON TRUE
    WHERE q.is_current
    ORDER BY q.external_id
"""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _lora_record(row: dict) -> dict:
    options = "\n".join(
        f"{chr(64 + a['position'])}) {a['text']}" for a in row["answers"])
    correct = [a for a in row["answers"] if a["is_correct"]]
    answer = correct[0]["text"] if correct else "нет правильного ответа"
    output = f"Правильный ответ: {answer}."
    if row["explanation"]:
        output += f" Объяснение: {row['explanation']}"
    return {
        "instruction": f"Вопрос: {row['question_text']}\n{options}",
        "output": output,
        "category": row["category"],
        "tags": row["tags"],
    }


@task
def export_dataset() -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(EXPORT_SQL)
            columns = [d.name for d in cur.description]
            rows = [dict(zip(columns, r)) for r in cur.fetchall()]
    finally:
        conn.close()

    df = pd.DataFrame(rows)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    parquet = EXPORT_DIR / "questions.parquet"
    jsonl = EXPORT_DIR / "questions.jsonl"
    lora = EXPORT_DIR / "lora_sft.jsonl"
    meta = EXPORT_DIR / "metadata.json"

    df.to_parquet(parquet, index=False)
    df.to_json(jsonl, orient="records", lines=True, force_ascii=False)
    with lora.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(_lora_record(row), ensure_ascii=False) + "\n")

    files = {}
    for p in (parquet, jsonl, lora):
        files[p.name] = {"bytes": p.stat().st_size, "sha256": _sha256(p)}
    metadata = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(rows),
        "source": "dds.questions (is_current) + dds.answers + dds.tags",
        "files": files,
    }
    meta.write_text(json.dumps(metadata, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return {"row_count": len(rows), "files": sorted(files)}


@dag(schedule=None, catchup=False, max_active_runs=1,
     dag_id="export_dataset",
     description="Экспорт датасета (Parquet/JSONL/LoRA) в ./data/export")
def export_dataset_dag():
    export_dataset()


export_dataset_dag()