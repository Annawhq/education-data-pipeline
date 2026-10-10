import pendulum
from airflow.sdk import dag, task
from src.stg.load_quizapi_to_postgres import load_quizapi_questions


@dag(
    dag_id="load_quizapi_to_stg",
    start_date=pendulum.datetime(2026, 10, 10, tz="UTC"),
    schedule="@weekly",
    catchup=False,
    tags=["stg", "quizapi"],
)
def load_quizapi_to_stg():

    @task(retries=2)
    def load_questions():
        load_quizapi_questions(
            category="Python",
            total=100,
        )

    load_questions()


load_quizapi_to_stg()