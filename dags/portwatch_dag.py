
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    "owner": "indicateurs-eco",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    dag_id="portwatch_etl",
    default_args=default_args,
    description="ETL automatique hebdomadaire des données IMF PortWatch",
    start_date=datetime(2026, 8, 24),
    schedule="0 8 * * 1",
    catchup=True,
    tags=["portwatch", "imf", "etl"],
) as dag:

    load_portwatch = BashOperator(
        task_id="load_portwatch",
        bash_command="python3 -m src.load.load_portwatch",
    )