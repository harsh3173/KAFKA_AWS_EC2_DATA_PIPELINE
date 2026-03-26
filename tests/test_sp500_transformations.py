import json

import pytest
from pyspark.sql import SparkSession

from src.transformations import (
    sp500_bronze_transform,
    sp500_silver_transform,
    sp500_gold_daily_summary,
    sp500_gold_sector_performance,
    sp500_gold_top_movers,
)


@pytest.fixture(scope="session")
def spark():
    session = (
        SparkSession.builder
        .master("local[1]")
        .appName("test-sp500")
        .getOrCreate()
    )
    yield session
    session.stop()


@pytest.fixture
def raw_sp500_df(spark):
    """Simulate Kafka DataFrame with S&P 500 OHLCV data."""
    records = [
        {"date": "2024-01-02", "symbol": "AAPL", "adj_close": 185.0, "close": 185.0,
         "high": 186.0, "low": 183.0, "open": 184.0, "volume": 50000000},
        {"date": "2024-01-02", "symbol": "MSFT", "adj_close": 375.0, "close": 375.0,
         "high": 378.0, "low": 372.0, "open": 373.0, "volume": 30000000},
        {"date": "2024-01-02", "symbol": "BAD", "adj_close": None, "close": None,
         "high": None, "low": None, "open": None, "volume": 0},
        {"date": "2024-01-03", "symbol": "AAPL", "adj_close": 186.0, "close": 186.0,
         "high": 187.0, "low": 184.0, "open": 185.0, "volume": 45000000},
    ]
    json_str = json.dumps(records)
    return spark.createDataFrame(
        [(json_str, "2024-01-02 09:30:00")],
        ["value", "timestamp"],
    )


@pytest.fixture
def companies_df(spark):
    """Simulated company metadata."""
    return spark.createDataFrame(
        [
            ("AAPL", "Technology", "Consumer Electronics"),
            ("MSFT", "Technology", "Software"),
        ],
        ["symbol", "sector", "industry"],
    )


def test_sp500_bronze_transform(raw_sp500_df):
    result = sp500_bronze_transform(raw_sp500_df)
    assert "raw_json" in result.columns
    assert "kafka_timestamp" in result.columns
    assert "ingested_at" in result.columns
    assert result.count() == 1


def test_sp500_silver_transform_filters_nulls(raw_sp500_df):
    bronze = sp500_bronze_transform(raw_sp500_df)
    silver = sp500_silver_transform(bronze)

    # BAD record should be filtered (null close)
    assert silver.count() == 3
    symbols = [row.symbol for row in silver.select("symbol").collect()]
    assert "BAD" not in symbols


def test_sp500_silver_adds_daily_return(raw_sp500_df):
    bronze = sp500_bronze_transform(raw_sp500_df)
    silver = sp500_silver_transform(bronze)

    assert "daily_return_pct" in silver.columns
    # AAPL 2024-01-02: (185 - 184) / 184 * 100 = 0.5435
    aapl_row = silver.filter("symbol = 'AAPL' AND date = '2024-01-02'").collect()[0]
    assert abs(aapl_row.daily_return_pct - 0.5435) < 0.01


def test_sp500_gold_daily_summary(raw_sp500_df):
    bronze = sp500_bronze_transform(raw_sp500_df)
    silver = sp500_silver_transform(bronze)
    gold = sp500_gold_daily_summary(silver)

    # Two dates: 2024-01-02 and 2024-01-03
    assert gold.count() == 2
    assert "stocks_traded" in gold.columns
    assert "avg_close" in gold.columns
    assert "total_volume" in gold.columns

    jan2 = gold.filter("date = '2024-01-02'").collect()[0]
    assert jan2.stocks_traded == 2  # AAPL + MSFT


def test_sp500_gold_sector_performance(raw_sp500_df, companies_df):
    bronze = sp500_bronze_transform(raw_sp500_df)
    silver = sp500_silver_transform(bronze)
    sector = sp500_gold_sector_performance(silver, companies_df)

    assert sector.count() > 0
    assert "sector" in sector.columns
    assert "avg_return_pct" in sector.columns


def test_sp500_gold_top_movers(raw_sp500_df):
    bronze = sp500_bronze_transform(raw_sp500_df)
    silver = sp500_silver_transform(bronze)
    movers = sp500_gold_top_movers(silver, "2024-01-02", n=1)

    assert movers.count() == 1
