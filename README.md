# Real-Time Stock Data Pipeline

End-to-end data engineering pipeline that ingests stock market data (live API + Kaggle S&P 500 dataset) using Apache Kafka and Apache Spark Structured Streaming, lands it in an S3 data lake with a medallion architecture (bronze/silver/gold), and visualizes insights through a Streamlit dashboard. Orchestrated by Airflow, monitored with Prometheus & Grafana, and provisioned with Terraform.

## Architecture

```
Data Sources
├── FinancialModelingPrep API (live)
└── Kaggle S&P 500 CSV (historical)
        |
   Kafka Producer (scheduled by Airflow, every 6 min)
        |
   Apache Kafka (Docker Compose locally / EC2 via Terraform)
        |
   Spark Structured Streaming
        |
   S3 Data Lake
   ├── Bronze (raw JSON, partitioned by ingestion date)
   ├── Silver (cleaned & deduplicated Parquet)
   └── Gold (aggregated metrics: sector performance, top movers)
        |
   ┌────────────────────────────────┐
   │  Streamlit Dashboard           │
   │  ├── Price Trends              │
   │  ├── Sector Analysis           │
   │  ├── Top Daily Movers          │
   │  └── Index Correlation         │
   └────────────────────────────────┘
        |
   AWS Glue Catalog + Athena (SQL query layer)
        |
   Prometheus + Grafana (monitoring)
```

## Tech Stack

| Component        | Technology                          |
|------------------|-------------------------------------|
| Ingestion        | Python, `kafka-python`, `requests`  |
| Streaming        | Apache Kafka (Confluent Platform)   |
| Processing       | Apache Spark Structured Streaming   |
| Storage          | AWS S3 (Parquet)                    |
| Orchestration    | Apache Airflow                      |
| Visualization    | Streamlit, Plotly                   |
| Monitoring       | Prometheus, Grafana                 |
| Infrastructure   | Terraform, Docker Compose           |
| Data Quality     | Custom validation framework         |
| CI/CD            | GitHub Actions (ruff, pytest, tf)   |
| Query Layer      | AWS Athena + Glue Catalog           |

## Dataset

Kaggle S&P 500 dataset (`data/`):
- **sp500_stocks.csv** — ~618K rows of daily OHLCV prices for S&P 500 stocks (2010-2024)
- **sp500_companies.csv** — 503 companies with sector, industry, market cap, revenue growth
- **sp500_index.csv** — S&P 500 index daily values (2014-2024)

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- AWS account (for S3/Terraform deployment)

### Local Development

1. **Clone and configure:**
   ```bash
   git clone <repo-url>
   cd KAFKA_AWS_EC2_DATA_PIPELINE
   cp .env.example .env
   # Edit .env — for CSV mode, API_KEY is optional
   ```

2. **Start the full stack:**
   ```bash
   docker-compose up -d
   ```
   This starts Zookeeper, Kafka, Spark consumer, producer, Airflow, and the dashboard.

3. **Or use CSV mode to stream Kaggle data through Kafka:**
   ```bash
   PRODUCER_MODE=csv docker-compose up -d
   ```

4. **Try the demo stack (lightweight, no AWS dependencies):**
   ```bash
   docker-compose -f docker-compose.demo.yml up -d
   ```

5. **Access services:**
   - Dashboard: http://localhost:8501
   - Airflow UI: http://localhost:8080 (admin/admin)
   - Spark UI: http://localhost:4040
   - Grafana: http://localhost:3000
   - Prometheus: http://localhost:9090
   - Kafka broker: localhost:9092

6. **Run dashboard standalone (no Docker):**
   ```bash
   pip install -r requirements.txt
   streamlit run src/dashboard.py
   ```

7. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

8. **Lint:**
   ```bash
   ruff check src/ tests/ dags/
   ```

### AWS Deployment

1. **Provision infrastructure:**
   ```bash
   cd terraform
   terraform init
   terraform plan -var="key_pair_name=your-key"
   terraform apply -var="key_pair_name=your-key"
   ```

2. **Deploy to EC2:**
   ```bash
   ./scripts/deploy.sh
   ```

3. **Tear down:**
   ```bash
   ./scripts/teardown.sh
   ```

## S3 Data Lake Layout

```
s3://<bucket>/
├── bronze/stocks/       # Raw JSON from Kafka
├── silver/stocks/       # Cleaned Parquet, partitioned by date
├── gold/stocks/         # Aggregated metrics
├── dead_letter/         # Quarantined bad records
└── checkpoints/         # Spark streaming checkpoints
```

## Dashboard

The Streamlit dashboard (`src/dashboard.py`) provides four interactive views:

| Tab | Description |
|-----|-------------|
| **Price Trends** | Multi-stock closing price and volume over time |
| **Sector Analysis** | Market cap distribution, avg returns by sector, volume trends |
| **Top Movers** | Daily gainers/losers with bar charts and sortable table |
| **Index Correlation** | Any stock vs S&P 500 index (normalized), Pearson correlation, OLS scatter |

Sidebar filters: sector selection, date range.

## Monitoring

Prometheus scrapes pipeline metrics exposed by `src/metrics.py`, and Grafana provides pre-built dashboards:

- **Kafka Pipeline Dashboard** — broker health, consumer lag, message throughput
- Datasource and dashboard provisioning is automated via `monitoring/` configs

## Data Quality

Validation runs between each medallion layer:
- **Bronze**: Non-null JSON payload
- **Silver**: Positive price, non-empty symbol, no duplicates, percentage within bounds
- **Gold**: Non-empty aggregation output, row count sanity

Failed records are quarantined to `s3://<bucket>/dead_letter/`.

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR to `main`:
1. **Lint** — `ruff check` on all Python code
2. **Test** — `pytest` on the full test suite
3. **Terraform Validate** — Ensures infrastructure config is valid

## Project Structure

```
├── src/
│   ├── config.py              # Environment-based configuration
│   ├── schemas.py             # Spark schema definitions (API + Kaggle)
│   ├── producer.py            # Kafka producer (API or CSV mode)
│   ├── consumer.py            # Spark streaming consumer (Kafka -> S3)
│   ├── transformations.py     # Bronze -> Silver -> Gold transforms
│   ├── metrics.py             # Prometheus metrics exposition
│   ├── dashboard.py           # Streamlit dashboard
│   └── quality/
│       └── checks.py          # Data quality validation
├── dags/
│   └── stock_pipeline_dag.py  # Airflow DAG
├── terraform/
│   ├── main.tf                # Provider config & backend
│   ├── ec2.tf                 # EC2 instance for Kafka
│   ├── s3.tf                  # S3 bucket with lifecycle rules
│   ├── iam.tf                 # IAM roles & policies
│   ├── variables.tf           # Input variables
│   └── outputs.tf             # Output values
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml     # Prometheus scrape config
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources/datasource.yml
│       │   └── dashboards/dashboards.yml
│       └── dashboards/
│           └── kafka_pipeline.json
├── scripts/
│   ├── deploy.sh              # EC2 deployment script
│   ├── teardown.sh            # Infrastructure teardown
│   └── shutdown_kafka.sh      # Kafka graceful shutdown
├── tests/
│   ├── test_producer.py
│   ├── test_transformations.py
│   └── test_quality.py
├── notebooks/                 # Original exploration notebooks
├── data/                      # Kaggle S&P 500 dataset
├── .github/workflows/ci.yml  # CI pipeline
├── docker-compose.yml         # Full-stack local development
├── docker-compose.demo.yml    # Lightweight demo stack
├── Dockerfile.producer        # Producer container
├── Dockerfile.spark           # Spark + Python dependencies
├── Dockerfile.dashboard       # Streamlit dashboard container
├── requirements.txt           # Python dependencies
└── .env.example               # Environment variable template
```

## Configuration

All config lives in `src/config.py` and is loaded from environment variables. See `.env.example` for the full list.

Key variables:
| Variable | Description |
|----------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address (`localhost:9092`) |
| `KAFKA_TOPIC` | Topic name for stock data |
| `API_KEY` | FinancialModelingPrep API key (optional for CSV mode) |
| `S3_BUCKET` | Target S3 bucket name |
| `PRODUCER_MODE` | `api` or `csv` (Docker Compose) |

Inside Docker Compose, Kafka internal listener is `kafka:29092`; external is `localhost:9092`.

## Schemas

Defined in `src/schemas.py`:
- **API schema**: symbol, name, change, price, changesPercentage
- **Kaggle OHLCV**: date, symbol, adj_close, close, high, low, open, volume
- **Company metadata**: exchange, symbol, sector, industry, marketcap
- **Index**: date, sp500
