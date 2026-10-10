# Education Data Pipeline

Пайплайн сбора и обработки образовательных вопросов.

## Архитектура

QuizAPI → Airflow → STG → DDS → CDM → Metabase

## Реализовано

На первом этапе был реализован слой STG:

- получение вопросов из QuizAPI;
- пагинация;
- загрузка исходных JSON-объектов в PostgreSQL;
- журналирование загрузок по batch_id;
- запуск загрузки через Apache Airflow;
- запуск инфраструктуры через Docker Compose.

## Запуск

1. Создать `.env` в корневой папке.
2. Добавить необходимые поля.
3. Запустить:

```bash
docker compose build
docker compose up -d
```

Airflow доступен на:
http://localhost:8080

DAG:
load_quizapi_to_stg
