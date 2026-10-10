import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

BASE_URL = "https://quizapi.io/api/v1"
API_KEY = os.getenv("QUIZAPI_KEY")
MAX_PAGE_SIZE = 50


def get_questions_page(
        category: str = "Python",
        limit: int = 50,
        offset: int = 0,
        difficulty: str | None = None,
        question_type: str | None = None,) -> dict:
    """
    Получает одну страницу вопросов QuizAPI.
    """

    if not API_KEY:
        raise RuntimeError(
            "Не найден QUIZAPI_KEY. "
            "Проверь файл .env."
        )

    if not 1 <= limit <= MAX_PAGE_SIZE:
        raise ValueError(
            f"QuizAPI позволяет получать от 1 до {MAX_PAGE_SIZE} "
            "вопросов за один запрос."
        )

    url = f"{BASE_URL}/questions"

    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    params = {
        "category": category,
        "limit": limit,
        "offset": offset,
    }

    if difficulty:
        params["difficulty"] = difficulty

    if question_type:
        params["type"] = question_type

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def get_questions(
        category: str = "Python",
        total: int = 100,
        difficulty: str | None = None,
        question_type: str | None = None,) -> list[dict]:
    """
    Получает нужное количество вопросов,
    автоматически выполняя несколько запросов.
    """

    questions = []
    offset = 0

    while len(questions) < total:
        page_size = min(
            MAX_PAGE_SIZE,
            total - len(questions),
        )

        response = get_questions_page(
            category=category,
            limit=page_size,
            offset=offset,
            difficulty=difficulty,
            question_type=question_type,
        )

        page_questions = response.get("data", [])

        if not page_questions:
            break

        questions.extend(page_questions)

        offset += len(page_questions)

        if len(page_questions) < page_size:
            break

    return questions


if __name__ == "__main__":
    questions = get_questions(
        category="Python",
        total=100,
    )

    print(f"Получено вопросов: {len(questions)}")

    if questions:
        print()
        print("Первый вопрос:")
        print(questions[0]["text"])
