import os
from dataclasses import dataclass


@dataclass
class Config:
    # Kafka
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    kafka_topic: str = os.getenv("KAFKA_TOPIC", "test_kafka_aws")

    # API
    api_base_url: str = os.getenv("API_BASE_URL", "https://financialmodelingprep.com/api/v3/stock_market/actives")
    api_key: str = os.getenv("API_KEY", "")

    # AWS / S3
    s3_bucket: str = os.getenv("S3_BUCKET", "stock-pipeline-data")
    s3_region: str = os.getenv("S3_REGION", "us-east-1")
    s3_bronze_prefix: str = "bronze/stocks"
    s3_silver_prefix: str = "silver/stocks"
    s3_gold_prefix: str = "gold/stocks"
    s3_dead_letter_prefix: str = "dead_letter/stocks"

    # Storage mode: "s3" or "local"
    storage_mode: str = os.getenv("STORAGE_MODE", "s3")
    local_data_dir: str = os.getenv("LOCAL_DATA_DIR", "/app/output")

    # Spark
    spark_app_name: str = os.getenv("SPARK_APP_NAME", "StockPipeline")
    spark_packages: str = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.apache.hadoop:hadoop-aws:3.3.4"

    # Producer
    producer_mode: str = os.getenv("PRODUCER_MODE", "csv")  # "api" or "csv"
    producer_interval_seconds: int = int(os.getenv("PRODUCER_INTERVAL_SECONDS", "360"))
    producer_max_iterations: int = int(os.getenv("PRODUCER_MAX_ITERATIONS", "0"))  # 0 = infinite

    @property
    def api_url(self) -> str:
        return f"{self.api_base_url}?apikey={self.api_key}"

    @property
    def s3_bronze_path(self) -> str:
        if self.storage_mode == "local":
            return f"{self.local_data_dir}/{self.s3_bronze_prefix}"
        return f"s3a://{self.s3_bucket}/{self.s3_bronze_prefix}"

    @property
    def s3_silver_path(self) -> str:
        if self.storage_mode == "local":
            return f"{self.local_data_dir}/{self.s3_silver_prefix}"
        return f"s3a://{self.s3_bucket}/{self.s3_silver_prefix}"

    @property
    def s3_gold_path(self) -> str:
        if self.storage_mode == "local":
            return f"{self.local_data_dir}/{self.s3_gold_prefix}"
        return f"s3a://{self.s3_bucket}/{self.s3_gold_prefix}"

    @property
    def s3_dead_letter_path(self) -> str:
        if self.storage_mode == "local":
            return f"{self.local_data_dir}/{self.s3_dead_letter_prefix}"
        return f"s3a://{self.s3_bucket}/{self.s3_dead_letter_prefix}"

    @property
    def checkpoint_path(self) -> str:
        if self.storage_mode == "local":
            return f"{self.local_data_dir}/checkpoints/stock_pipeline"
        return f"s3a://{self.s3_bucket}/checkpoints/stock_pipeline"


config = Config()
