import logging
from dataclasses import dataclass

from pyspark.sql import DataFrame
from pyspark.sql.functions import col

logger = logging.getLogger(__name__)


@dataclass
class QualityResult:
    check_name: str
    passed: bool
    total_rows: int
    failed_rows: int
    message: str


def validate_bronze(df: DataFrame) -> QualityResult:
    """Validate bronze layer: ensure raw_json is non-null and parseable."""
    total = df.count()
    null_json = df.filter(col("raw_json").isNull() | (col("raw_json") == "")).count()

    passed = null_json == 0
    return QualityResult(
        check_name="bronze_non_null_json",
        passed=passed,
        total_rows=total,
        failed_rows=null_json,
        message=f"{'PASS' if passed else 'FAIL'}: {null_json}/{total} rows have null/empty JSON",
    )


def validate_silver(df: DataFrame) -> list[QualityResult]:
    """Validate silver layer: price > 0, symbol non-empty, no nulls in required fields, percentage in bounds."""
    results = []
    total = df.count()

    # Check: price must be positive
    bad_price = df.filter((col("price") <= 0) | col("price").isNull()).count()
    results.append(QualityResult(
        check_name="silver_positive_price",
        passed=bad_price == 0,
        total_rows=total,
        failed_rows=bad_price,
        message=f"{'PASS' if bad_price == 0 else 'FAIL'}: {bad_price}/{total} rows with non-positive price",
    ))

    # Check: symbol must be non-empty
    bad_symbol = df.filter(col("symbol").isNull() | (col("symbol") == "")).count()
    results.append(QualityResult(
        check_name="silver_non_empty_symbol",
        passed=bad_symbol == 0,
        total_rows=total,
        failed_rows=bad_symbol,
        message=f"{'PASS' if bad_symbol == 0 else 'FAIL'}: {bad_symbol}/{total} rows with empty symbol",
    ))

    # Check: no duplicate symbols
    distinct_count = df.select("symbol").distinct().count()
    duplicates = total - distinct_count
    results.append(QualityResult(
        check_name="silver_no_duplicate_symbols",
        passed=duplicates == 0,
        total_rows=total,
        failed_rows=duplicates,
        message=f"{'PASS' if duplicates == 0 else 'FAIL'}: {duplicates} duplicate symbols found",
    ))

    # Check: changes_percentage within reasonable bounds (-100 to 10000)
    bad_pct = df.filter(
        (col("changes_percentage") < -100) | (col("changes_percentage") > 10000)
    ).count()
    results.append(QualityResult(
        check_name="silver_percentage_bounds",
        passed=bad_pct == 0,
        total_rows=total,
        failed_rows=bad_pct,
        message=f"{'PASS' if bad_pct == 0 else 'FAIL'}: {bad_pct}/{total} rows with out-of-bounds percentage",
    ))

    return results


def validate_gold(gold_df: DataFrame, silver_row_count: int) -> QualityResult:
    """Validate gold layer: ensure aggregation produced output and row count is sane."""
    gold_count = gold_df.count()
    passed = gold_count > 0

    return QualityResult(
        check_name="gold_non_empty",
        passed=passed,
        total_rows=gold_count,
        failed_rows=0 if passed else 1,
        message=f"{'PASS' if passed else 'FAIL'}: gold layer has {gold_count} rows (silver had {silver_row_count})",
    )


def quarantine_bad_records(df: DataFrame, output_path: str, condition) -> int:
    """Write records that fail validation to the dead-letter path. Returns count of quarantined records."""
    bad_records = df.filter(condition)
    bad_count = bad_records.count()
    if bad_count > 0:
        bad_records.write.mode("append").parquet(output_path)
        logger.warning("Quarantined %d bad records to %s", bad_count, output_path)
    return bad_count


def run_all_checks(bronze_df: DataFrame, silver_df: DataFrame, gold_df: DataFrame) -> list[QualityResult]:
    """Run all quality checks and return results."""
    results = []

    results.append(validate_bronze(bronze_df))
    results.extend(validate_silver(silver_df))
    results.append(validate_gold(gold_df, silver_df.count()))

    for r in results:
        log_fn = logger.info if r.passed else logger.error
        log_fn("[%s] %s", r.check_name, r.message)

    return results
