# lakebase-assess

**SQL-to-Databricks Lakebase Migration Assessment Engine**

A frictionless, locally-executable tool that enables clients to discover their own SQL-to-Databricks Lakebase migration opportunities. Connects read-only to 10+ SQL platforms, computes a proprietary Lakebase Opportunity Score, estimates cost deltas, and outputs prioritized migration reports.

## Features

- **10+ Platform Connectors**: Snowflake, Redshift, BigQuery, Synapse, PostgreSQL, Oracle, Vertica, Teradata, on-prem CSV/JSON import
- **Lakebase Opportunity Score**: Proprietary formula combining pain, business impact, and complexity
- **Cost Delta Estimation**: Current platform vs. projected Lakebase costs without billing invoices
- **Privacy-First**: 100% client-side, zero PII/billing data leakage, AES-256 encryption
- **Rich Outputs**: Executive PDF, interactive HTML dashboard, JSON/CSV reports, migration checklist
- **Optional BPCS Upload**: Anonymized trend tracking with `--upload`
- **Offline-Ready**: All outputs generated without external network calls

## Installation

### pip (local install)

```bash
cd lakebase-assess
pip install -e .
```

### Docker

```bash
cd lakebase-assess
docker build -t lakebase-assess .
docker run --rm -v $(pwd)/output:/app/output lakebase-assess run --output-dir /app/output
```

## Configuration

Create a YAML config file:

```yaml
# config.yaml
target_platforms:
  - snowflake
  - redshift
  - bigquery

query_history_days: 90
output_formats:
  - pdf
  - html
  - json
  - csv

env_overrides:
  SNOWFLAKE_ACCOUNT: "xxxxx"
  SNOWFLAKE_USER: "analytics"
  SNOWFLAKE_PASSWORD: "${SNOWFLAKE_PASSWORD}"
  SNOWFLAKE_ROLE: "ANALYST"
  SNOWFLAKE_WAREHOUSE: "COMPUTE_WH"
  SNOWFLAKE_DATABASE: "TARGET_DB"
  REDSHIFT_CLUSTER_ID: "my-cluster"
  REDSHIFT_USER: "reader"
  REDSHIFT_PASSWORD: "${REDSHIFT_PASSWORD}"
  REDSHIFT_DATABASE: "dev"
  REDSHIFT_REGION: "us-east-1"
  BQ_PROJECT_ID: "my-project"
  BQ_DATASET: "analytics"
```

## Usage

### Full Assessment

```bash
lakebase-assess run \
  --config config.yaml \
  --output-dir ./assessment-output \
  --anonymize \
  --encrypt
```

### Dry Run (validate config)

```bash
lakebase-assess run --dry-run --config config.yaml
```

### Validate Connectors Only

```bash
lakebase-assess validate --config config.yaml
```

### With CLI Options

```bash
lakebase-assess run \
  -p snowflake -p bigquery \
  -o ./output \
  --threshold 15 \
  --anonymize
```

### Generate Outputs Only (from existing JSON)

```bash
lakebase-assess run --config config.yaml --output-dir ./output
```

## CLI Reference

```
lakebase-assess [OPTIONS] COMMAND [ARGS]...

Commands:
  run        Run the full assessment pipeline
  validate   Validate config and connector connectivity
  upload     Prepare and send anonymized payload to BPCS

Options:
  --config PATH        Path to YAML config file
  -p, --platform TEXT  Platform(s) to assess (repeats allowed)
  -o, --output-dir PATH   Output directory for reports
  --anonymize          Strip all PII before scoring
  --encrypt            Encrypt local SQLite + JSON payload with AES-256
  --dry-run            Validate config without executing queries
  --threshold FLOAT    Minimum opportunity score for Priority (default: 10)
  --upload             Enable optional anonymized upload to BPCS trend tracking
  --version            Show version
  --help               Show this message
```

## Lakebase Opportunity Score Formula

```
Score = ((Pain × Business_Impact) / Complexity) × 10
Adjusted_Score = Score × (1 + (est_savings_pct / 100))
```

### Thresholds

| Score Range | Priority | Action |
|-------------|----------|--------|
| < 10 | Hold | Optimize in current platform first |
| 10–20 | Evaluate | Safe for PoC |
| ≥ 25 | Priority 1 | High confidence migration |

### Scale Definitions

| Dimension | 1 | 3 | 5 |
|-----------|---|---|---|
| Pain | Low cost/stable | Moderate scaling pain/timeout | $50k/mo, nightly fails, heavy UDF/SP debt |
| Business Impact | Internal reporting | Customer-facing/BI | Revenue-critical/regulatory/real-time |
| Complexity | Flat/simple SQL | Normalized/moderate ETL | Heavy SPs/custom caching/strict ACID/legacy drivers |

### Workload Classification Buckets

- **Analytics → Keep in Delta**: Standard analytics workloads stay in Delta Lake
- **Point Lookups → Migrate to Lakebase**: Low-complexity queries ideal for Lakebase
- **Agent State → Migrate to Lakebase**: State management patterns
- **App Backends → Migrate to Lakebase**: Application backend data patterns
- **Feature Serving → Migrate to Lakebase**: Feature store patterns
- **Heavy ETL/UDF → Flag for refactoring first**: UDF-heavy workloads need rewrites
- **Real-time Join/Agg → Lakebase + caching layer**: Real-time patterns with caching

## Output Files

| File | Description |
|------|-------------|
| `executive.pdf` | Executive brief with scorecard, cost table, migration buckets |
| `dashboard.html` | Interactive Plotly dashboard with score distributions and heatmaps |
| `report.json` | Complete validated payload with checksum |
| `report.csv` | Flat CSV of all scored workloads |
| `checklist.md` | Migration implementation checklist |
| `payload.enc` | AES-256 encrypted payload (with `--encrypt`) |

## Privacy & Security

- **No external network calls** unless `--upload` is explicitly provided
- **All data stored locally** in SQLite + AES-256 encrypted JSON
- **PII masking** strips SSNs, emails, IPs, credentials from query fingerprints
- **Hashed identifiers** used for all anonymized data
- **BPCS upload payload** only includes: `platform`, `avg_score`, `priority_1_count`, `est_savings_pct`

## Testing

```bash
cd lakebase-assess
pip install -e ".[dev]"
pytest tests/ -v
```

## Architecture

```
lakebase-assess/
├── src/
│   ├── cli.py              # CLI entrypoint (click)
│   ├── config.py           # YAML config loader, env vars, validation
│   ├── connectors/
│   │   ├── base.py         # AbstractBaseConnector
│   │   ├── snowflake.py    # Snowflake connector
│   │   ├── redshift.py     # Redshift connector
│   │   ├── bigquery.py     # BigQuery connector
│   │   ├── synapse.py      # Azure Synapse connector
│   │   ├── postgres.py     # PostgreSQL connector
│   │   ├── oracle.py       # Oracle connector
│   │   ├── vertica.py      # Vertica connector
│   │   ├── teradata.py     # Teradata connector
│   │   └── onprem_dump.py  # CSV/JSON import fallback
│   ├── models/
│   │   ├── query_history.py
│   │   ├── table_metadata.py
│   │   ├── concurrency.py
│   │   ├── security.py
│   │   └── assessment_payload.py
│   ├── engine/
│   │   ├── scoring.py      # Lakebase Opportunity Score engine
│   │   ├── billing.py      # Default billing calculator & cost delta
│   │   └── classifier.py   # Workload bucket mapper
│   ├── outputs/
│   │   ├── pdf_report.py   # Executive PDF generator
│   │   ├── dashboard.py    # Plotly HTML dashboard
│   │   ├── json_export.py  # JSON/CSV export
│   │   └── checklist.py    # Migration checklist
│   └── security/
│       ├── encryption.py   # AES-256 local storage
│       └── privacy.py      # PII mask, query filter, schema validator
├── pricing_maps/
│   ├── platform_rates.yaml # Compute/storage/IO/scaling multipliers
│   └── dbu_mapping.yaml    # DBU tier mappings
├── templates/
│   ├── executive_report.md.j2
│   └── checklist.md.j2
├── tests/
│   ├── test_connectors.py
│   ├── test_scoring.py
│   ├── test_billing.py
│   └── test_privacy.py
├── pyproject.toml
├── Dockerfile
└── README.md
```

## License

MIT
