import pendulum
from airflow.sdk import dag, task
from src.dds.load_stg_to_dds import load_stg_to_dds


@dag(
    dag_id="load_stg_to_dds",
    start_date=pendulum.datetime(2026, 10, 10, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["dds", "quizapi"],
)
def dds_pipeline():
    @task(retries=2)
    def load_questions():
        return load_stg_to_dds()

    load_questions()


dds_pipeline()
