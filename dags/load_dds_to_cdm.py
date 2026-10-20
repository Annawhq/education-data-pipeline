import pendulum
from airflow.sdk import dag, task
from src.cdm.load_dds_to_cdm import load_dds_to_cdm


@dag(
    dag_id="load_dds_to_cdm",
    start_date=pendulum.datetime(2026, 10, 10, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["cdm", "quizapi"],
)
def cdm_pipeline():
    @task(retries=2)
    def refresh():
        return load_dds_to_cdm()

    refresh()


cdm_pipeline()