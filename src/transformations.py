from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    avg,
    col,
    count,
    current_timestamp,
    explode,
    from_json,
    lag,
    round as spark_round,
    sum as spark_sum,
    to_date,
    max as spark_max,
    min as spark_min,
    abs as spark_abs,
)
from pyspark.sql.window import Window

from src.schemas import STOCK_ARRAY_DDL, SP500_STOCK_ARRAY_DDL


# ============================================================
# API-based transforms (FinancialModelingPrep live data)
# ============================================================

def bronze_transform(raw_df: DataFrame) -> DataFrame:
    """Extract raw JSON string from Kafka message and add ingestion timestamp."""
    return (
        raw_df
        .selectExpr("CAST(value AS STRING) as raw_json", "timestamp as kafka_timestamp")
        .withColumn("ingested_at", current_timestamp())
    )


def silver_transform(bronze_df: DataFrame) -> DataFrame:
    """Parse JSON array, explode into individual records, deduplicate by symbol."""
    parsed = (
        bronze_df
        .select(
            explode(from_json("raw_json", STOCK_ARRAY_DDL)).alias("data"),
            "kafka_timestamp",
            "ingested_at",
        )
        .select(
            col("data.symbol").alias("symbol"),
            col("data.name").alias("name"),
            col("data.change").alias("change"),
            col("data.price").alias("price"),
            col("data.changesPercentage").alias("changes_percentage"),
            "kafka_timestamp",
            "ingested_at",
        )
    )

    cleaned = parsed.filter(
        col("symbol").isNotNull()
        & (col("symbol") != "")
        & (col("price") > 0)
    )

    deduped = cleaned.dropDuplicates(["symbol"])
    return deduped


def gold_transform(silver_df: DataFrame) -> DataFrame:
    """Aggregate stock data into summary metrics per micro-batch."""
    return (
        silver_df
        .agg(
            count("symbol").alias("total_stocks"),
            avg("price").alias("avg_price"),
            avg("changes_percentage").alias("avg_change_pct"),
            spark_max("changes_percentage").alias("max_gainer_pct"),
            spark_min("changes_percentage").alias("max_loser_pct"),
            spark_max("price").alias("highest_price"),
            spark_min("price").alias("lowest_price"),
        )
        .withColumn("computed_at", current_timestamp())
    )


def gold_top_movers(silver_df: DataFrame, n: int = 10) -> DataFrame:
    """Extract top N gainers and losers by percentage change."""
    with_abs = silver_df.withColumn("abs_change_pct", spark_abs(col("changes_percentage")))
    return with_abs.orderBy(col("abs_change_pct").desc()).limit(n).drop("abs_change_pct")


# ============================================================
# Kaggle S&P 500 transforms (batch / CSV-based)
# ============================================================

def sp500_bronze_transform(raw_df: DataFrame) -> DataFrame:
    """Extract raw JSON from Kafka message for S&P 500 OHLCV data."""
    return (
        raw_df
        .selectExpr("CAST(value AS STRING) as raw_json", "timestamp as kafka_timestamp")
        .withColumn("ingested_at", current_timestamp())
    )


def sp500_silver_transform(bronze_df: DataFrame) -> DataFrame:
    """Parse S&P 500 OHLCV JSON, clean and add derived columns."""
    parsed = (
        bronze_df
        .select(
            explode(from_json("raw_json", SP500_STOCK_ARRAY_DDL)).alias("data"),
            "kafka_timestamp",
            "ingested_at",
        )
        .select(
            to_date(col("data.date")).alias("date"),
            col("data.symbol").alias("symbol"),
            col("data.adj_close").alias("adj_close"),
            col("data.close").alias("close"),
            col("data.high").alias("high"),
            col("data.low").alias("low"),
            col("data.open").alias("open"),
            col("data.volume").alias("volume"),
            "kafka_timestamp",
            "ingested_at",
        )
    )

    # Filter out rows with missing price data
    cleaned = parsed.filter(
        col("symbol").isNotNull()
        & (col("symbol") != "")
        & col("close").isNotNull()
        & (col("close") > 0)
    )

    # Add daily return: (close - open) / open * 100
    with_return = cleaned.withColumn(
        "daily_return_pct",
        spark_round((col("close") - col("open")) / col("open") * 100, 4),
    )

    return with_return


def sp500_gold_daily_summary(silver_df: DataFrame) -> DataFrame:
    """Aggregate daily market summary across all stocks."""
    return (
        silver_df
        .groupBy("date")
        .agg(
            count("symbol").alias("stocks_traded"),
            spark_round(avg("close"), 2).alias("avg_close"),
            spark_round(avg("daily_return_pct"), 4).alias("avg_daily_return_pct"),
            spark_max("daily_return_pct").alias("best_return_pct"),
            spark_min("daily_return_pct").alias("worst_return_pct"),
            spark_sum("volume").alias("total_volume"),
            spark_max("close").alias("highest_close"),
            spark_min("close").alias("lowest_close"),
        )
        .orderBy("date")
    )


def sp500_gold_sector_performance(silver_df: DataFrame, companies_df: DataFrame) -> DataFrame:
    """Aggregate performance by sector (join stock data with company metadata)."""
    joined = silver_df.join(companies_df.select("symbol", "sector", "industry"), on="symbol", how="left")

    return (
        joined
        .groupBy("date", "sector")
        .agg(
            count("symbol").alias("num_stocks"),
            spark_round(avg("close"), 2).alias("avg_close"),
            spark_round(avg("daily_return_pct"), 4).alias("avg_return_pct"),
            spark_sum("volume").alias("total_volume"),
        )
        .orderBy("date", "sector")
    )


def sp500_gold_top_movers(silver_df: DataFrame, date_val: str, n: int = 10) -> DataFrame:
    """Get top N movers for a specific date."""
    day_df = silver_df.filter(col("date") == date_val)
    with_abs = day_df.withColumn("abs_return", spark_abs(col("daily_return_pct")))
    return with_abs.orderBy(col("abs_return").desc()).limit(n).drop("abs_return")
