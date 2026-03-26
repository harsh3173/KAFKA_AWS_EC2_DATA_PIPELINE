import argparse
import logging
import sys
from json import dumps
from time import sleep

import pandas as pd
import requests
from kafka import KafkaProducer

from src.config import config
from src.metrics import inc, start_metrics_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def create_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=[config.kafka_bootstrap_servers],
        value_serializer=lambda x: dumps(x).encode("utf-8"),
    )


# ---- API mode (live FinancialModelingPrep data) ----

def fetch_stock_data() -> list[dict]:
    response = requests.get(config.api_url, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError(f"Expected list from API, got {type(data)}")
    logger.info("Fetched %d stock records from API", len(data))
    return data


def publish_to_kafka(producer: KafkaProducer, data: list[dict]) -> None:
    producer.send(config.kafka_topic, value=data)
    producer.flush()
    inc("pipeline_records_produced_total", len(data))
    inc("pipeline_batches_sent_total")
    logger.info("Published %d records to topic '%s'", len(data), config.kafka_topic)


def run_api_mode(continuous: bool = True) -> None:
    start_metrics_server()
    producer = create_producer()
    logger.info(
        "API Producer started — broker=%s, topic=%s, interval=%ds",
        config.kafka_bootstrap_servers,
        config.kafka_topic,
        config.producer_interval_seconds,
    )

    iteration = 0
    max_iter = config.producer_max_iterations

    try:
        while True:
            try:
                data = fetch_stock_data()
                publish_to_kafka(producer, data)
            except requests.RequestException as e:
                inc("pipeline_errors_total")
                logger.error("API request failed: %s", e)
            except Exception as e:
                inc("pipeline_errors_total")
                logger.error("Unexpected error: %s", e)

            iteration += 1
            if not continuous or (max_iter > 0 and iteration >= max_iter):
                break

            logger.info("Sleeping %ds until next fetch...", config.producer_interval_seconds)
            sleep(config.producer_interval_seconds)
    finally:
        producer.close()
        logger.info("Producer shut down")


# ---- CSV mode (Kaggle S&P 500 data) ----

def load_csv(file_path: str) -> pd.DataFrame:
    df = pd.read_csv(file_path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def run_csv_mode(
    stocks_path: str = "data/sp500_stocks.csv",
    batch_size: int = 500,
    delay: float = 0.5,
) -> None:
    """Stream CSV data through Kafka, simulating real-time ingestion.

    Sends rows grouped by date as batches to the Kafka topic.
    """
    start_metrics_server()
    producer = create_producer()
    topic = config.kafka_topic

    logger.info("CSV Producer started — file=%s, topic=%s", stocks_path, topic)

    df = load_csv(stocks_path)
    # Drop rows where close price is missing
    df = df.dropna(subset=["close"])

    # Rename columns to match schema
    df = df.rename(columns={"adj_close": "adj_close"})

    dates = sorted(df["date"].unique())
    logger.info("Loaded %d rows across %d trading days", len(df), len(dates))

    try:
        for i, date in enumerate(dates):
            day_data = df[df["date"] == date]
            records = day_data.to_dict(orient="records")

            # Send in batches
            for start in range(0, len(records), batch_size):
                batch = records[start : start + batch_size]
                producer.send(topic, value=batch)
                inc("pipeline_batches_sent_total")

            producer.flush()
            inc("pipeline_records_produced_total", len(records))
            logger.info(
                "[%d/%d] Published %d records for %s",
                i + 1,
                len(dates),
                len(records),
                date,
            )

            if delay > 0:
                sleep(delay)
    finally:
        producer.close()
        logger.info("CSV Producer shut down — sent %d dates", len(dates))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stock pipeline Kafka producer")
    parser.add_argument(
        "--mode",
        choices=["api", "csv"],
        default="api",
        help="Ingestion mode: 'api' for live data, 'csv' for Kaggle S&P 500 data",
    )
    parser.add_argument("--stocks-path", default="data/sp500_stocks.csv", help="Path to sp500_stocks.csv")
    parser.add_argument("--batch-size", type=int, default=500, help="Records per Kafka message in CSV mode")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between date batches in CSV mode")
    parser.add_argument("--once", action="store_true", help="Run once then exit (API mode)")

    args = parser.parse_args()

    if args.mode == "csv":
        run_csv_mode(
            stocks_path=args.stocks_path,
            batch_size=args.batch_size,
            delay=args.delay,
        )
    else:
        run_api_mode(continuous=not args.once)
