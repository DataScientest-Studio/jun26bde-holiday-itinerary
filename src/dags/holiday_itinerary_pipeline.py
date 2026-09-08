from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

with DAG(
    dag_id="holiday_itinerary_pipeline",
    description="Batch pipeline for a holiday itinerary project",
    start_date=datetime(2026, 8, 30),
    schedule="@daily",
    catchup=False,
    tags=["holiday-itinerary"]
) as dag:

    extract = BashOperator(
        task_id="extract_data",
        bash_command="cd /opt/airflow/project && python -m src.etl.extract",
    )

    transform = BashOperator(
        task_id="transform_data",
        bash_command="cd /opt/airflow/project && python -m src.etl.transform",
    )

    cluster = BashOperator(
        task_id="cluster_data",
        bash_command="cd /opt/airflow/project && python -m src.models.cluster",
    )

    load_postgres = BashOperator(
        task_id="load_postgres",
        bash_command="cd /opt/airflow/project && python -m src.database.load_sql",
    )

    load_neo4j = BashOperator(
        task_id="load_neo4j",
        bash_command="cd /opt/airflow/project && python -m src.database.load_neo4j"
    )

    extract >> transform >> cluster
    cluster >> [load_postgres, load_neo4j]