from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.bash import BashSensor

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}


def _run_quality_checks():
    """Run data quality checks on silver/gold layers."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Quality checks would run here against S3 data")
    # In production, this would read from S3 and run src.quality.checks


with DAG(
    dag_id="stock_pipeline",
    default_args=default_args,
    description="Real-time stock data pipeline: API -> Kafka -> Spark -> S3",
    schedule_interval="*/6 * * * *",  # Every 6 minutes (API rate limit: 250/day)
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["stock", "kafka", "pipeline"],
) as dag:

    check_kafka_health = BashSensor(
        task_id="check_kafka_health",
        bash_command=(
            "python -c \""
            "from kafka import KafkaConsumer; "
            "import os; "
            "c = KafkaConsumer(bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')); "
            "c.topics(); "
            "c.close(); "
            "print('Kafka is healthy')\""
        ),
        timeout=60,
        poke_interval=10,
        mode="poke",
    )

    run_producer = BashOperator(
        task_id="run_producer",
        bash_command=(
            "cd /opt/airflow && "
            "PRODUCER_MAX_ITERATIONS=1 python -m src.producer"
        ),
    )

    run_quality_checks = PythonOperator(
        task_id="run_quality_checks",
        python_callable=_run_quality_checks,
    )

    check_kafka_health >> run_producer >> run_quality_checks
