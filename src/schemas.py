from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
)

# --- API Schema (FinancialModelingPrep active stocks) ---

STOCK_SCHEMA = StructType([
    StructField("symbol", StringType(), True),
    StructField("name", StringType(), True),
    StructField("change", DoubleType(), True),
    StructField("price", DoubleType(), True),
    StructField("changesPercentage", DoubleType(), True),
])

STOCK_ARRAY_SCHEMA = ArrayType(STOCK_SCHEMA)

STOCK_ARRAY_DDL = "array<struct<symbol:string,name:string,change:double,price:double,changesPercentage:double>>"

REQUIRED_FIELDS = ["symbol", "name", "change", "price", "changesPercentage"]

# --- Kaggle S&P 500 Schemas ---

# sp500_stocks.csv: Date, Symbol, Adj Close, Close, High, Low, Open, Volume
SP500_STOCK_SCHEMA = StructType([
    StructField("date", StringType(), True),
    StructField("symbol", StringType(), True),
    StructField("adj_close", DoubleType(), True),
    StructField("close", DoubleType(), True),
    StructField("high", DoubleType(), True),
    StructField("low", DoubleType(), True),
    StructField("open", DoubleType(), True),
    StructField("volume", LongType(), True),
])

SP500_STOCK_ARRAY_DDL = (
    "array<struct<date:string,symbol:string,adj_close:double,close:double,"
    "high:double,low:double,open:double,volume:bigint>>"
)

# sp500_companies.csv: company metadata
SP500_COMPANY_SCHEMA = StructType([
    StructField("exchange", StringType(), True),
    StructField("symbol", StringType(), True),
    StructField("shortname", StringType(), True),
    StructField("longname", StringType(), True),
    StructField("sector", StringType(), True),
    StructField("industry", StringType(), True),
    StructField("currentprice", DoubleType(), True),
    StructField("marketcap", LongType(), True),
    StructField("ebitda", DoubleType(), True),
    StructField("revenuegrowth", DoubleType(), True),
    StructField("city", StringType(), True),
    StructField("state", StringType(), True),
    StructField("country", StringType(), True),
    StructField("fulltimeemployees", LongType(), True),
    StructField("longbusinesssummary", StringType(), True),
    StructField("weight", DoubleType(), True),
])

# sp500_index.csv: Date, S&P500
SP500_INDEX_SCHEMA = StructType([
    StructField("date", StringType(), True),
    StructField("sp500", DoubleType(), True),
])
