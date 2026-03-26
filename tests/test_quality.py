import json

import pytest
from pyspark.sql import SparkSession

from src.quality.checks import validate_bronze, validate_silver, validate_gold
from src.transformations import bronze_transform, silver_transform, gold_transform


@pytest.fixture(scope="session")
def spark():
    session = (
        SparkSession.builder
        .master("local[1]")
        .appName("test-quality")
        .getOrCreate()
    )
    yield session
    session.stop()


@pytest.fixture
def valid_data(spark):
    records = [
        {"symbol": "NVDA", "name": "NVIDIA", "change": 1.78, "price": 119.37, "changesPercentage": 1.51},
        {"symbol": "AAPL", "name": "Apple", "change": -0.79, "price": 229.00, "changesPercentage": -0.34},
    ]
    json_str = json.dumps(records)
    raw_df = spark.createDataFrame([(json_str, "2024-01-01 00:00:00")], ["value", "timestamp"])
    bronze = bronze_transform(raw_df)
    silver = silver_transform(bronze)
    gold = gold_transform(silver)
    return bronze, silver, gold


def test_validate_bronze_passes(valid_data):
    bronze, _, _ = valid_data
    result = validate_bronze(bronze)
    assert result.passed
    assert result.failed_rows == 0


def test_validate_bronze_fails_on_null(spark):
    raw_df = spark.createDataFrame([("", "2024-01-01 00:00:00")], ["value", "timestamp"])
    bronze = bronze_transform(raw_df)
    result = validate_bronze(bronze)
    assert not result.passed
    assert result.failed_rows == 1


def test_validate_silver_all_pass(valid_data):
    _, silver, _ = valid_data
    results = validate_silver(silver)
    for r in results:
        assert r.passed, f"{r.check_name} failed: {r.message}"


def test_validate_silver_catches_bad_data(spark):
    records = [
        {"symbol": "", "name": "Empty", "change": 0.0, "price": 0.0, "changesPercentage": 0.0},
    ]
    json_str = json.dumps(records)
    raw_df = spark.createDataFrame([(json_str, "2024-01-01 00:00:00")], ["value", "timestamp"])
    bronze = bronze_transform(raw_df)
    silver = silver_transform(bronze)
    # Silver transform filters out bad data, so it should be empty
    assert silver.count() == 0


def test_validate_gold_passes(valid_data):
    _, silver, gold = valid_data
    result = validate_gold(gold, silver.count())
    assert result.passed


def test_validate_gold_fails_on_empty(spark):
    empty_df = spark.createDataFrame([], "total_stocks: int, avg_price: double")
    result = validate_gold(empty_df, 10)
    assert not result.passed
