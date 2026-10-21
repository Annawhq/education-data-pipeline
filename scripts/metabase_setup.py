"""Идемпотентная настройка Metabase: первый админ + подключение к cdm."""
import os
import time

import requests

METABASE_URL = os.environ["METABASE_URL"]
ADMIN_EMAIL = os.environ["METABASE_ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["METABASE_ADMIN_PASSWORD"]
ADMIN_FIRST = os.getenv("METABASE_ADMIN_FIRST_NAME", "Admin")
ADMIN_LAST = os.getenv("METABASE_ADMIN_LAST_NAME", "User")

DB_NAME = os.environ["POSTGRES_DB"]
DB_HOST = os.getenv("METABASE_TARGET_HOST", "postgres")
DB_PORT = int(os.getenv("METABASE_TARGET_PORT", "5432"))
DB_USER = os.environ["METABASE_READER_USER"]
DB_PASSWORD = os.environ["METABASE_READER_PASSWORD"]
DB_DISPLAY_NAME = os.getenv("METABASE_DB_NAME", "QuizAPI CDM")
DB_SCHEMA = os.getenv("METABASE_DB_SCHEMA", "cdm")

TIMEOUT = 300


def wait_for_health():
    deadline = time.time() + TIMEOUT
    attempt = 0
    last_error = None
    while time.time() < deadline:
        attempt += 1
        try:
            r = requests.get(f"{METABASE_URL}/api/health", timeout=5)
            if r.ok and r.json().get("status") == "ok":
                print(f"Metabase healthy after {attempt} attempts")
                return
            last_error = f"HTTP {r.status_code}: {r.text[:200]}"
        except requests.RequestException as e:
            last_error = f"{type(e).__name__}: {e}"
        print(f"Attempt {attempt}: not ready ({last_error})")
        time.sleep(2)
    raise RuntimeError(
        f"Metabase не стал healthy за {TIMEOUT}s, last error: {last_error}"
    )


def get_setup_token():
    r = requests.get(f"{METABASE_URL}/api/session/properties", timeout=10)
    r.raise_for_status()
    token = r.json().get("setup-token")
    if token:
        print(f"Got setup-token from properties: {token[:8]}...")
    else:
        print("No setup-token — Metabase already initialised")
    return token


def setup_admin(token):
    payload = {
        "token": token,
        "user": {
            "first_name": ADMIN_FIRST,
            "last_name": ADMIN_LAST,
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        },
        "prefs": {"site_name": "QuizAPI"},
    }
    r = requests.post(f"{METABASE_URL}/api/setup", json=payload, timeout=15)
    if not r.ok:
        print(f"Setup failed: {r.status_code} - {r.text}")
    r.raise_for_status()
    return r.json().get("id")


def login():
    r = requests.post(
        f"{METABASE_URL}/api/session",
        json={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=10,
    )
    if not r.ok:
        print(f"Login failed: {r.status_code} - {r.text}")
    r.raise_for_status()
    return r.json().get("id")


def database_exists(session_id):
    r = requests.get(
        f"{METABASE_URL}/api/database",
        headers={"X-Metabase-Session": session_id},
        timeout=10,
    )
    r.raise_for_status()
    return any(db.get("name") == DB_DISPLAY_NAME for db in r.json().get("data", []))


def add_database(session_id):
    if database_exists(session_id):
        print(f"Database '{DB_DISPLAY_NAME}' already exists, skipping")
        return
    payload = {
        "name": DB_DISPLAY_NAME,
        "engine": "postgres",
        "details": {
            "host": DB_HOST,
            "port": DB_PORT,
            "db": DB_NAME,
            "user": DB_USER,
            "password": DB_PASSWORD,
            "ssl": False,
            "schema-filters-type": "inclusion",
            "schema-filters-patterns": DB_SCHEMA,
        },
        "is_full_sync": True,
        "is_sample": False,
    }
    r = requests.post(
        f"{METABASE_URL}/api/database",
        headers={"X-Metabase-Session": session_id},
        json=payload,
        timeout=30,
    )
    if not r.ok:
        print(f"add_database failed: {r.status_code} - {r.text}")
    r.raise_for_status()
    print(f"Database added, id={r.json().get('id')}")


def main():
    wait_for_health()
    token = get_setup_token()
    if token:
        print("Running initial setup (admin + db)")
        session = setup_admin(token)
    else:
        print("Already set up, logging in")
        session = login()
    add_database(session)
    print("Metabase setup complete")


if __name__ == "__main__":
    main()