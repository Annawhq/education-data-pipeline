-- Read-only роль для Metabase.
-- Логин и пароль читаются из переменных окружения контейнера init-db:
--   METABASE_READER_USER, METABASE_READER_PASSWORD.
-- Если переменная пустая или не задана — psql падает (ON_ERROR_STOP=1),
-- init-db завершается с ошибкой, downstream-сервисы не стартуют.

\getenv metabase_reader_user     METABASE_READER_USER
\getenv metabase_reader_password METABASE_READER_PASSWORD

SELECT
    (:'metabase_reader_user'     <> '')::text AS user_ok,
    (:'metabase_reader_password' <> '')::text AS pass_ok
\gset

\if :user_ok
\else
    \echo 'ERROR: METABASE_READER_USER is not set or empty'
    \quit 1
\endif

\if :pass_ok
\else
    \echo 'ERROR: METABASE_READER_PASSWORD is not set or empty'
    \quit 1
\endif

-- Создаём роль, если её ещё нет.
SELECT format('CREATE ROLE %I LOGIN', :'metabase_reader_user')
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = :'metabase_reader_user'
)
\gexec

-- Выставляем (или обновляем) пароль. Идемпотентно при повторных запусках.
SELECT format(
    'ALTER ROLE %I PASSWORD %L',
    :'metabase_reader_user',
    :'metabase_reader_password'
)
\gexec

-- Доступ к схеме cdm (read-only).
GRANT USAGE ON SCHEMA cdm TO :"metabase_reader_user";
GRANT SELECT ON ALL TABLES IN SCHEMA cdm TO :"metabase_reader_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA cdm
    GRANT SELECT ON TABLES TO :"metabase_reader_user";

-- CONNECT на текущую БД (PGDATABASE уже проброшен в init-db).
\getenv db_name PGDATABASE
SELECT format(
    'GRANT CONNECT ON DATABASE %I TO %I',
    :'db_name',
    :'metabase_reader_user'
)
\gexec