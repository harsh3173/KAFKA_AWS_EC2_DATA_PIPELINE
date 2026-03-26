import json

import pytest
from pyspark.sql import SparkSession

from src.transformations import bronze_transform, silver_transform, gold_transform, gold_top_movers


@pytest.fixture(scope="session")
def spark():
    session = (
        SparkSession.builder
        .master("local[1]")
        .appName("test")
        .getOrCreate()
    )
    yield session
    session.stop()


@pytest.fixture
def raw_kafka_df(spark):
    """Simulate a Kafka DataFrame with value and timestamp columns."""
    records = [
        {"symbol": "NVDA", "name": "NVIDIA", "change": 1.78, "price": 119.37, "changesPercentage": 1.51},
        {"symbol": "AAPL", "name": "Apple", "change": -0.79, "price": 229.00, "changesPercentage": -0.34},
        {"symbol": "BAD", "name": "Bad Stock", "change": 0.0, "price": -5.0, "changesPercentage": 0.0},
    ]
    json_str = json.dumps(records)
    return spark.createDataFrame(
        [(json_str, "2024-01-01 00:00:00")],
        ["value", "timestamp"],
    )


def test_bronze_transform(raw_kafka_df):
    result = bronze_transform(raw_kafka_df)
    assert "raw_json" in result.columns
    assert "kafka_timestamp" in result.columns
    assert "ingested_at" in result.columns
    assert result.count() == 1


def test_silver_transform(raw_kafka_df):
    bronze = bronze_transform(raw_kafka_df)
    silver = silver_transform(bronze)

    # BAD stock should be filtered out (price <= 0)
    assert silver.count() == 2
    symbols = [row.symbol for row in silver.select("symbol").collect()]
    assert "BAD" not in symbols
    assert "NVDA" in symbols
    assert "AAPL" in symbols


def test_silver_transform_deduplicates(spark):
    records = [
        {"symbol": "NVDA", "name": "NVIDIA", "change": 1.0, "price": 100.0, "changesPercentage": 1.0},
        {"symbol": "NVDA", "name": "NVIDIA", "change": 2.0, "price": 101.0, "changesPercentage": 2.0},
    ]
    json_str = json.dumps(records)
    raw_df = spark.createDataFrame(
        [(json_str, "2024-01-01 00:00:00")],
        ["value", "timestamp"],
    )
    bronze = bronze_transform(raw_df)
    silver = silver_transform(bronze)

    assert silver.count() == 1


def test_gold_transform(raw_kafka_df):
    bronze = bronze_transform(raw_kafka_df)
    silver = silver_transform(bronze)
    gold = gold_transform(silver)

    assert gold.count() == 1
    row = gold.collect()[0]
    assert row.total_stocks == 2
    assert row.avg_price > 0
    assert "computed_at" in gold.columns


def test_gold_top_movers(raw_kafka_df):
    bronze = bronze_transform(raw_kafka_df)
    silver = silver_transform(bronze)
    movers = gold_top_movers(silver, n=1)

    assert movers.count() == 1
    # NVDA has higher abs change percentage (1.51 vs 0.34)
    assert movers.collect()[0].symbol == "NVDA"
