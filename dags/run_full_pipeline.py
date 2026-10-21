from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sdk import dag


def _trigger(task_id: str, dag_id: str) -> TriggerDagRunOperator:
    return TriggerDagRunOperator(
        task_id=task_id,
        trigger_dag_id=dag_id,
        wait_for_completion=True,
        reset_dag_run=True,
        poke_interval=15,
    )


@dag(schedule=None, catchup=False, max_active_runs=1,
     dag_id="run_full_pipeline",
     description="STG -> DDS -> CDM -> DQ -> Export одной кнопкой")
def run_full_pipeline():
    stg = _trigger("run_stg", "load_quizapi_to_stg")
    dds = _trigger("run_dds", "load_stg_to_dds")
    cdm = _trigger("run_cdm", "load_dds_to_cdm")
    dq = _trigger("run_dq", "check_data_quality")
    exp = _trigger("run_export", "export_dataset")
    stg >> dds >> cdm >> dq >> exp


run_full_pipeline()