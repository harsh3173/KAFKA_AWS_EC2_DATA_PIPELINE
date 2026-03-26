import logging
import sys

from pyspark.sql import SparkSession

from src.config import config
from src.transformations import bronze_transform, silver_transform, gold_transform

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def create_spark_session() -> SparkSession:
    return (
        SparkSession.builder
        .appName(config.spark_app_name)
        .config("spark.jars.packages", config.spark_packages)
        .config("spark.hadoop.fs.s3a.access.key", config.s3_region)
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )


def _write_bronze(batch_df, batch_id):
    """Write raw data to bronze layer."""
    bronze_df = bronze_transform(batch_df)
    (
        bronze_df.write
        .mode("append")
        .partitionBy("ingested_at")
        .parquet(config.s3_bronze_path)
    )
    logger.info("Bronze batch %d: wrote %d rows", batch_id, bronze_df.count())


def _write_silver(batch_df, batch_id):
    """Write cleaned data to silver layer."""
    bronze_df = bronze_transform(batch_df)
    silver_df = silver_transform(bronze_df)
    (
        silver_df.write
        .mode("append")
        .partitionBy("ingested_at")
        .parquet(config.s3_silver_path)
    )
    logger.info("Silver batch %d: wrote %d rows", batch_id, silver_df.count())


def _write_gold(batch_df, batch_id):
    """Write aggregated data to gold layer."""
    bronze_df = bronze_transform(batch_df)
    silver_df = silver_transform(bronze_df)
    gold_df = gold_transform(silver_df)
    (
        gold_df.write
        .mode("append")
        .parquet(config.s3_gold_path)
    )
    logger.info("Gold batch %d: wrote %d rows", batch_id, gold_df.count())


def run() -> None:
    spark = create_spark_session()
    logger.info(
        "Consumer started — broker=%s, topic=%s",
        config.kafka_bootstrap_servers,
        config.kafka_topic,
    )

    # Read from Kafka
    kafka_df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", config.kafka_bootstrap_servers)
        .option("subscribe", config.kafka_topic)
        .option("startingOffsets", "latest")
        .load()
    )

    # Write to all three layers using foreachBatch
    def process_batch(batch_df, batch_id):
        if batch_df.isEmpty():
            return
        _write_bronze(batch_df, batch_id)
        _write_silver(batch_df, batch_id)
        _write_gold(batch_df, batch_id)

    query = (
        kafka_df.writeStream
        .foreachBatch(process_batch)
        .outputMode("append")
        .option("checkpointLocation", f"s3a://{config.s3_bucket}/checkpoints/stock_pipeline")
        .start()
    )

    logger.info("Streaming query started, awaiting termination...")
    query.awaitTermination()


if __name__ == "__main__":
    run()
