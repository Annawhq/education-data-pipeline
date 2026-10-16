"""Общее подключение к PostgreSQL для слоёв пайплайна."""

import os

import psycopg
from dotenv import load_dotenv


load_dotenv()


def get_connection():
    """
    Создает подключение к PostgreSQL.
    """
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )
