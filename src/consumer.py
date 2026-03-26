import logging
import sys

from pyspark.sql import SparkSession

from src.config import config
from src.transformations import (
    bronze_transform,
    silver_transform,
    gold_transform,
    sp500_bronze_transform,
    sp500_silver_transform,
    sp500_gold_daily_summary,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def create_spark_session() -> SparkSession:
    builder = (
        SparkSession.builder
        .appName(config.spark_app_name)
        .config("spark.jars.packages", config.spark_packages)
    )

    if config.storage_mode == "s3":
        builder = (
            builder
            .config("spark.hadoop.fs.s3a.access.key", config.s3_region)
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        )

    return builder.getOrCreate()


# ---- API mode writers ----

def _write_bronze_api(batch_df, batch_id):
    bronze_df = bronze_transform(batch_df)
    bronze_df.write.mode("append").partitionBy("ingested_at").parquet(config.s3_bronze_path)
    logger.info("Bronze batch %d: wrote %d rows", batch_id, bronze_df.count())


def _write_silver_api(batch_df, batch_id):
    bronze_df = bronze_transform(batch_df)
    silver_df = silver_transform(bronze_df)
    silver_df.write.mode("append").partitionBy("ingested_at").parquet(config.s3_silver_path)
    logger.info("Silver batch %d: wrote %d rows", batch_id, silver_df.count())


def _write_gold_api(batch_df, batch_id):
    bronze_df = bronze_transform(batch_df)
    silver_df = silver_transform(bronze_df)
    gold_df = gold_transform(silver_df)
    gold_df.write.mode("append").parquet(config.s3_gold_path)
    logger.info("Gold batch %d: wrote %d rows", batch_id, gold_df.count())


# ---- CSV / S&P 500 mode writers ----

def _write_bronze_csv(batch_df, batch_id):
    bronze_df = sp500_bronze_transform(batch_df)
    bronze_df.write.mode("append").partitionBy("ingested_at").parquet(config.s3_bronze_path)
    logger.info("Bronze batch %d: wrote %d rows", batch_id, bronze_df.count())


def _write_silver_csv(batch_df, batch_id):
    bronze_df = sp500_bronze_transform(batch_df)
    silver_df = sp500_silver_transform(bronze_df)
    silver_df.write.mode("append").parquet(config.s3_silver_path)
    logger.info("Silver batch %d: wrote %d rows", batch_id, silver_df.count())


def _write_gold_csv(batch_df, batch_id):
    bronze_df = sp500_bronze_transform(batch_df)
    silver_df = sp500_silver_transform(bronze_df)
    gold_df = sp500_gold_daily_summary(silver_df)
    gold_df.write.mode("append").parquet(config.s3_gold_path)
    logger.info("Gold batch %d: wrote %d rows", batch_id, gold_df.count())


def run() -> None:
    spark = create_spark_session()
    mode = config.producer_mode
    logger.info(
        "Consumer started — broker=%s, topic=%s, storage=%s, mode=%s",
        config.kafka_bootstrap_servers,
        config.kafka_topic,
        config.storage_mode,
        mode,
    )

    kafka_df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", config.kafka_bootstrap_servers)
        .option("subscribe", config.kafka_topic)
        .option("startingOffsets", "latest")
        .load()
    )

    if mode == "csv":
        write_bronze = _write_bronze_csv
        write_silver = _write_silver_csv
        write_gold = _write_gold_csv
    else:
        write_bronze = _write_bronze_api
        write_silver = _write_silver_api
        write_gold = _write_gold_api

    def process_batch(batch_df, batch_id):
        if batch_df.isEmpty():
            return
        write_bronze(batch_df, batch_id)
        write_silver(batch_df, batch_id)
        write_gold(batch_df, batch_id)

    query = (
        kafka_df.writeStream
        .foreachBatch(process_batch)
        .outputMode("append")
        .option("checkpointLocation", config.checkpoint_path)
        .start()
    )

    logger.info("Streaming query started, awaiting termination...")
    query.awaitTermination()


if __name__ == "__main__":
    run()
