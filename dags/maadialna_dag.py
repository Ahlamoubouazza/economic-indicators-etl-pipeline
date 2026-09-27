from airflow import DAG
from airflow.operators.python import PythonOperator

from datetime import datetime

from src.transform.transform_maadialna import transform_maadialna
from src.transform.transform_national_maadialna import transform_national_maadialna
from src.load.load_maadialna import load_historical
from src.load.load_postgresql_maadialna import load_maadialna


def extract_transform_barrages():

    df = transform_maadialna()

    df.to_csv(
        "data/barrages.csv",
        index=False,
        encoding="utf-8-sig"
    )


def extract_transform_national():

    df = transform_national_maadialna()

    df.to_csv(
        "data/national_barrages.csv",
        index=False,
        encoding="utf-8-sig"
    )


def update_history():

    load_historical(
        "data/barrages.csv",
        "data/historique_barrages.csv"
    )

    load_historical(
        "data/national_barrages.csv",
        "data/history_national_barrages.csv"
    )


def load_database():

    load_maadialna(
        barrages_path="data/historique_barrages.csv",
        national_path="data/history_national_barrages.csv"
    )


with DAG(
    dag_id="maadialna_pipeline",
    start_date=datetime(2026,8,1),
    schedule="0 8 * * 1",
    catchup=False
) as dag:


    t1 = PythonOperator(
        task_id="extract_transform_barrages",
        python_callable=extract_transform_barrages
    )


    t2 = PythonOperator(
        task_id="extract_transform_national",
        python_callable=extract_transform_national
    )


    t3 = PythonOperator(
        task_id="update_history",
        python_callable=update_history
    )


    t4 = PythonOperator(
        task_id="load_postgresql",
        python_callable=load_database
    )


    t1 >> t2 >> t3 >> t4