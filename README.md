# Education Data Pipeline

Пайплайн сбора и обработки образовательных вопросов.

## Архитектура

```
QuizAPI → Airflow → STG → DDS → CDM → Metabase
```

- **STG** — сырые JSON-объекты вопросов из QuizAPI, журнал загрузок по батчам.
- **DDS** — нормализованные вопросы, ответы, теги с историей изменений (SCD2).
- **CDM** — денормализованный факт и агрегатные витрины для BI.
- **Metabase** — визуализация витрин `cdm.*`.

## Реализовано

### STG

- получение вопросов из QuizAPI с пагинацией;
- загрузка исходных JSON-объектов в PostgreSQL;
- журналирование загрузок по `batch_id`;
- запуск загрузки через Apache Airflow;
- запуск инфраструктуры через Docker Compose.

### DDS

- разбор JSON из успешных загрузок STG;
- запись вопросов, ответов и тегов в отдельные связанные таблицы;
- дедупликация: неизменившиеся вопросы не создают новые версии;
- SCD2: сохранение истории изменений вопросов, ответов и тегов;
- журналирование обработанных записей для повторного запуска без дублей;
- запуск через Apache Airflow.

### CDM и Metabase

- денормализованный факт `cdm.fact_questions` по текущим версиям вопросов DDS;
- агрегаты `cdm.agg_questions_by_category` и `cdm.agg_questions_by_tag`;
- DAG `load_dds_to_cdm` в Airflow;
- автоматическое подключение Metabase к схеме `cdm` через init-контейнер
  `metabase-setup` (идемпотентно).

## Требования

- Docker Desktop (или Docker Engine + Docker Compose v2);
- ключ QuizAPI (https://quizapi.io).

## Запуск

1. Создать `.env` в корневой папке (пример — ниже, в разделе «.env»).
2. Запустить инфраструктуру:

   ```bash
   docker compose build
   docker compose up -d
   ```

Сервисы и интерфейсы:

| Сервис | Адрес | Назначение |
|---|---|---|
| Airflow | http://localhost:8080 | Оркестрация DAG’ов |
| Metabase | http://localhost:3000 | BI и дашборды |
| PostgreSQL (основная) | `localhost:15432` | STG / DDS / CDM |

DAG’и в Airflow:

- `load_quizapi_to_stg` — по расписанию `@weekly`;
- `load_stg_to_dds` — вручную;
- `load_dds_to_cdm` — вручную (запускать после `load_stg_to_dds`).

### Порядок запуска пайплайна

1. Дождаться успешного запуска `load_quizapi_to_stg`
   (по расписанию или вручную).
2. Запустить `load_stg_to_dds` — разбор STG в DDS.
3. Запустить `load_dds_to_cdm` — пересчёт витрин CDM.
4. Открыть Metabase (http://localhost:3000) и работать с `cdm.*`.

## .env

Пример полного `.env` для всего стека. Скопировать в корень проекта под
именем `.env` и заменить значения-плейсхолдеры на свои.

```env
# --- PostgreSQL (основная БД с STG / DDS / CDM) ---
POSTGRES_DB=education
POSTGRES_USER=education
POSTGRES_PASSWORD=change_me_strong_password

# --- QuizAPI ---
QUIZAPI_KEY=ваш_ключ_quizapi

# --- Metabase (собственная БД приложения) ---
METABASE_DB_PASSWORD=change_me_metabase_db_password
METABASE_ENCRYPTION_KEY=change_me_at_least_32_characters_long_secret_key

# --- Metabase (первый администратор) ---
METABASE_ADMIN_EMAIL=admin@example.com
METABASE_ADMIN_PASSWORD=Str0ng!Passw0rd2026

# --- Metabase (read-only роль для подключения к cdm) ---
METABASE_READER_USER=metabase_reader
METABASE_READER_PASSWORD=change_me_metabase_reader_password
```

### Пояснения по переменным

| Переменная | Обязательна | Требования |
|---|---|---|
| `POSTGRES_DB` | да | Имя БД в основной PostgreSQL |
| `POSTGRES_USER` | да | Пользователь-владелец БД |
| `POSTGRES_PASSWORD` | да | **Непустой** — иначе официальный образ `postgres` не инициализируется |
| `QUIZAPI_KEY` | да | Ключ QuizAPI; без него DAG `load_quizapi_to_stg` падает |
| `METABASE_DB_PASSWORD` | да | Пароль БД приложения Metabase (отдельный инстанс PostgreSQL) |
| `METABASE_ENCRYPTION_KEY` | да | Любая длинная случайная строка; используется для шифрования кредов подключений в Metabase |
| `METABASE_ADMIN_EMAIL` | да | Логин первого админа Metabase |
| `METABASE_ADMIN_PASSWORD` | да | **Не короче 15 символов**, с заглавными/строчными/цифрами/спецсимволами. Metabase отклоняет распространённые пароли (`password`, `qwerty123`) с ошибкой `password is too common` |
| `METABASE_READER_USER` | да | Имя read-only роли для подключения Metabase к `cdm` |
| `METABASE_READER_PASSWORD` | да | Пароль этой роли. Используется и в `sql/cdm/002_metabase_reader.sql`, и в `scripts/metabase_setup.py` — одно значение, одно место правки |

## Detail Data Store

Слой DDS:

- разбор JSON из успешных загрузок STG;
- запись вопросов, ответов и тегов в отдельные связанные таблицы;
- дедупликация: неизменившиеся вопросы не создают новые версии;
- SCD2: сохранение истории изменений вопросов, ответов и тегов;
- журналирование обработанных записей для повторного запуска без дублей;
- запуск через Apache Airflow.

### Запуск DDS

1. Запустить проект командой `docker compose up -d`. Сервис `init-db`
   автоматически создаст таблицы STG, DDS и журнал обработки. Airflow
   запустится после его успешного завершения. Существующие данные сохраняются.
2. Дождаться успешной загрузки `load_quizapi_to_stg`.
3. Вручную запустить DAG `load_stg_to_dds` в Airflow.
4. После успешного DDS запустить `load_dds_to_cdm` (см. раздел «CDM и Metabase»).

## CDM и Metabase

Слой CDM:

- денормализованный факт `cdm.fact_questions` по текущим версиям вопросов DDS;
- агрегаты `cdm.agg_questions_by_category` и `cdm.agg_questions_by_tag`;
- DAG `load_dds_to_cdm` в Airflow;
- Metabase на http://localhost:3000, подключённый только к схеме `cdm`.

### Схема CDM

| Таблица | Назначение |
|---|---|
| `cdm.fact_questions` | Одна строка = текущая версия вопроса. Содержит `answer_count`, `correct_answer_count`, `has_correct_answer`, `tag_count`, `tags[]` |
| `cdm.agg_questions_by_category` | Агрегат: количество вопросов, доля с правильным ответом, среднее число ответов — в разрезе категорий |
| `cdm.agg_questions_by_tag` | То же в разрезе тегов (один вопрос с N тегами даёт N строк) |

### Запуск CDM

1. Убедиться, что DDS-пайплайн отработал (`load_stg_to_dds` успешен,
   в `dds.questions` есть строки с `is_current = TRUE`).
2. В Airflow вручную запустить DAG `load_dds_to_cdm`.
3. Проверить, что витрины наполнились:

   ```sql
   SELECT COUNT(*) FROM cdm.fact_questions;
   SELECT * FROM cdm.agg_questions_by_category;
   SELECT * FROM cdm.agg_questions_by_tag ORDER BY question_count DESC LIMIT 10;
   ```

### Metabase

Metabase поднимается автоматически вместе с проектом. Init-контейнер
`metabase-setup` создаёт первого администратора (если его ещё нет) и
подключает БД со схемой `cdm` (только её — `stg` и `dds` Metabase не видит).

- URL: http://localhost:3000
- Логин/пароль: `METABASE_ADMIN_EMAIL` / `METABASE_ADMIN_PASSWORD` из `.env`

Скрипт идемпотентен:

- на чистом томе `metabase_postgres_data` — создаёт админа и подключение к `cdm`;
- при повторных `docker compose up` — логинится под существующим админом и
  пропускает уже созданное подключение.

Если после сброса тома `metabase_postgres_data` пароль в `.env` отличается от
того, что был установлен в Metabase ранее, `metabase-setup` завершится с
`401` — это ожидаемо. Нужно либо выровнять пароль в `.env`, либо сбросить
том ещё раз.

### Что строить в Metabase

Базовые карточки без SQL (Question Builder):

- **Количество вопросов по категориям**: `cdm.fact_questions`,
  Summarize → Count, Group by → `category`, bar chart.
- **Доля вопросов с правильным ответом по категориям**: `cdm.fact_questions`,
  Summarize → Average of `has_correct_answer`, Group by → `category`.
- **Распределение по сложности**: `cdm.fact_questions`, Count,
  Group by → `difficulty`, donut.

Быстрые карточки по готовым агрегатам:

- `cdm.agg_questions_by_category` — таблица + bar chart;
- `cdm.agg_questions_by_tag` — топ-N тегов по `question_count`.


## Сброс инфраструктуры

Полный сброс (удаляет все данные, включая витрины и настройки Metabase):

```bash
docker compose down -v
docker compose up -d
```

После этого `init-db` пересоздаст схемы STG/DDS/CDM, а `metabase-setup` —
админа и подключение к `cdm`.