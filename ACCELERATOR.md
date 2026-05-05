# Lakebase Readiness Assessor: Technical Setup & Running Guide

This guide covers **how to run the `lakebase-assess` CLI** to evaluate workloads for Lakebase migration readiness.

## 📋 Prerequisites

### Your Environment
- **Python:** 3.10+
- **pip:** Latest version
- **Disk space:** 2–5 GB for SQLite cache (depends on data volume)

### Target Platform Access
You'll need **read-only credentials** for one of these platforms:

| Platform | Access Method | What's Needed |
|----------|---------------|---------------|
| **Snowflake** | OAuth or service account | Account name, role with `MONITOR` + `ACCOUNTADMIN` (read-only) |
| **BigQuery** | Service account JSON key | Project ID, service account with `bigquery.jobs.listAll`, `bigquery.datasets.get` |
| **Redshift** | IAM or database user | Cluster endpoint, database name, username (read-only), AWS role with `redshift-data:ExecuteStatement` |
| **Azure Synapse** | Azure AD / Managed Identity | Server name, database, SQL user (reader), Azure subscription |
| **Oracle** | DB user or SSH tunnel | Host, port, SID/service name, DB user (read-only) |
| **Teradata** | DB user | Server, database name, username (read-only) |
| **Vertica** | DB user | Host, port, database, username (read-only) |
| **Postgres/On-prem** | DB user or SSH tunnel | Host, port, database, username (read-only) |

**Golden Rule:** The assessor only runs **read-only queries**. No writes, no deletes, no schema changes. It will fail fast and safely if write permissions are detected.

---

## 🚀 Quick Start (5 minutes)

### 1. Install the Package

```bash
# Clone the repo
git clone https://github.com/BlueprintTechnologies/lakebase-offers.git
cd lakebase-offers

# Install lakebase-assess
pip install -e lakebase-assess/

# Verify installation
lakebase-assess --version
# Output: lakebase-assess, version 1.0.0
```

### 2. Create a Config File

```yaml
# my-assessment.yaml
platform: snowflake

snowflake:
  account: "xy12345"           # snowflake account ID (get from URL: https://xy12345.us-east-1.snowflakecomputing.com)
  user: "assessment_user"
  password: "${SNOWFLAKE_PASSWORD}"  # or use environment variable
  warehouse: "compute_wh"
  database: "analytics"
  schema: "public"
  role: "reader"

assessment:
  min_query_history_days: 30   # require at least 30 days of query history
  max_workloads: 200           # assess top 200 workloads by frequency
  anonymize: true              # strip company name / query text
  output_dir: "./results"
```

### 3. Set Credentials (Environment Variables)

```bash
export SNOWFLAKE_PASSWORD="your-password"
# or
export SNOWFLAKE_PRIVATE_KEY_PATH="/path/to/private_key.p8"
export SNOWFLAKE_PRIVATE_KEY_PASSPHRASE="your-passphrase"
```

### 4. Run the Assessment

```bash
lakebase-assess run --config my-assessment.yaml

# Output:
# ✅ Connected to Snowflake (xy12345)
# ⏳ Collecting query history (30 days)...
# ⏳ Analyzing 150 workloads...
# ⏳ Computing opportunity scores...
# ⏳ Generating reports...
# ✅ Assessment complete!
#
# Results:
#   - Executive Summary: ./results/executive_summary.html
#   - Detailed Report: ./results/assessment_report.pdf
#   - JSON Payload: ./results/assessment.json
#   - Blockers CSV: ./results/blockers.csv
```

### 5. View Results

Open `./results/executive_summary.html` in your browser to see:
- Opportunity scores (0–100 scale)
- Priority buckets (Priority 1 / Evaluate / Hold)
- Estimated annual savings
- Top 3 PoC candidates

---

## 🔧 Configuration Reference

### Full Config Structure

```yaml
# ===== PLATFORM SELECTION =====
platform: "snowflake"  # or: bigquery, redshift, synapse, oracle, teradata, vertica, postgres

# ===== PLATFORM-SPECIFIC CREDENTIALS =====

snowflake:
  account: "xy12345"                          # Account ID
  user: "assessment_user"
  password: "${SNOWFLAKE_PASSWORD}"          # Can reference env var
  warehouse: "compute_wh"                    # Must have read access
  database: "analytics"                      # Optional: limits scope
  schema: "public"                           # Optional: limits scope
  role: "reader"                             # Optional: assumes this role
  authenticator: "https://my-sso.okta.com"   # Optional: for SAML/SSO

bigquery:
  project_id: "my-project"
  credentials_json: "/path/to/service-account.json"
  # or use GOOGLE_APPLICATION_CREDENTIALS env var
  dataset_filter: "analytics_*"  # Optional: only scan matching datasets

redshift:
  host: "my-cluster.us-east-1.redshift.amazonaws.com"
  port: 5439
  database: "dev"
  user: "analyst"
  password: "${REDSHIFT_PASSWORD}"
  # or use IAM auth:
  use_iam_auth: true
  iam_role_arn: "arn:aws:iam::123456789:role/RedshiftRole"

synapse:
  server: "my-server.database.windows.net"
  database: "datawarehouse"
  user: "analyst@my-org.onmicrosoft.com"
  password: "${AZURE_PASSWORD}"
  tenant_id: "${AZURE_TENANT_ID}"

oracle:
  host: "oracle-host.internal"
  port: 1521
  sid: "PROD"  # or service_name
  user: "assessment"
  password: "${ORACLE_PASSWORD}"
  # For on-prem, can use SSH tunnel:
  ssh_tunnel:
    host: "jumphost.internal"
    user: "ec2-user"
    private_key: "/path/to/key.pem"

# ===== ASSESSMENT SETTINGS =====

assessment:
  # Data collection
  min_query_history_days: 30          # Fail if < 30 days of history
  max_workloads: 200                  # Assess top N workloads by frequency
  
  # Output control
  anonymize: true                     # Strip company name, query text
  encrypt: false                      # AES-256 encrypt SQLite + JSON (optional)
  dry_run: false                      # Validate config only, don't run queries
  
  # Scoring
  opportunity_threshold: 10.0         # Min score to include in Priority list
  savings_percent_adjustment: 0.0     # Manual adjustment to cost savings (%)
  
  # Upload (optional)
  upload: false                       # Send anonymized results to BPCS
  upload_endpoint: "https://api.blueprinttech.dev/lakebase/submit"
  
  output_dir: "./assessment-output"

# ===== OPTIONAL: CUSTOM PRICING =====

# If you have negotiated rates, override defaults here:
pricing:
  platforms:
    snowflake:
      compute: 24.0  # $/credit (vs. default 28.0)
      storage: 0.02  # $/GB/mo
    lakebase:
      compute_dbu: 0.05  # $/DBU (vs. default 0.06, if you have committed capacity)
      storage: 0.04      # $/GB/mo
```

### Environment Variable Reference

Instead of hardcoding passwords, use env vars:

```bash
# Snowflake
export SNOWFLAKE_PASSWORD="secret"
export SNOWFLAKE_PRIVATE_KEY_PATH="./key.p8"

# BigQuery
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Redshift
export REDSHIFT_PASSWORD="secret"
export REDSHIFT_IAM_ROLE_ARN="arn:aws:iam::123456789:role/RedshiftRole"

# Oracle
export ORACLE_PASSWORD="secret"

# Azure
export AZURE_PASSWORD="secret"
export AZURE_TENANT_ID="tenant-guid"
```

Then in config:

```yaml
snowflake:
  password: "${SNOWFLAKE_PASSWORD}"
```

---

## 📊 Running the Assessment

### Basic Command

```bash
lakebase-assess run --config my-assessment.yaml
```

### With CLI Overrides

```bash
# Override settings without editing config file
lakebase-assess run \
  --config my-assessment.yaml \
  --platform snowflake \
  --output-dir /tmp/results \
  --anonymize \
  --threshold 10 \
  --max-workloads 100

# Dry-run (validate config, don't collect data)
lakebase-assess run \
  --config my-assessment.yaml \
  --dry-run

# Upload results to BPCS (after assessment)
lakebase-assess run \
  --config my-assessment.yaml \
  --upload \
  --anonymize
```

### Watching Progress

The assessor streams progress to stdout:

```
✅ Connected to Snowflake xy12345
⏳ Collecting query history (30 days)...
  📊 Found 150 queries from 8 users
  📊 Date range: 2026-04-05 to 2026-05-05
⏳ Analyzing table metadata...
  📊 Found 420 tables, 1200 columns
⏳ Computing opportunity scores...
  📊 Scoring 150 workloads...
  ⚠️  Low confidence: 32 workloads have < 7 days history
⏳ Classifying workloads...
  📊 Analytics: 42 workloads
  📊 Point lookups: 18 workloads
  📊 Heavy ETL: 12 workloads
  📊 Other: 78 workloads
⏳ Generating reports...
  📄 executive_summary.html (1.2 MB)
  📄 assessment_report.pdf (4.8 MB)
  📄 assessment.json (2.3 MB)
  📄 blockers.csv (150 KB)
✅ Assessment complete! (45 minutes elapsed)
```

---

## 📁 Output Files

After a successful run, you'll get:

| File | Format | For Whom | Contents |
|------|--------|----------|----------|
| `executive_summary.html` | HTML (interactive) | Executive sponsor | Top findings, scores, ROI, top 3 PoC candidates |
| `assessment_report.pdf` | PDF | Detailed review | Full workload scores, recommendations, effort estimates, blockers |
| `assessment.json` | JSON | Automation | Raw assessment data (can pipe to downstream tools) |
| `blockers.csv` | CSV | Triage | Per-workload blockers and remediation recommendations |
| `debug.log` | Text | Troubleshooting | Connection logs, query traces, errors |

### Example: Viewing the Executive Summary

```bash
# Open in browser
open ./assessment-output/executive_summary.html

# Or view JSON programmatically
jq '.platform_summary' ./assessment-output/assessment.json
# Output:
# {
#   "platform": "snowflake",
#   "total_workloads": 150,
#   "priority_1_count": 42,
#   "evaluate_count": 68,
#   "hold_count": 40,
#   "avg_score": 17.2,
#   "est_annual_savings_pct": 42,
#   "recommended_poc_workloads": [
#     {
#       "name": "customer_analytics",
#       "score": 95,
#       "priority": "Priority_1",
#       "est_monthly_savings": 18000
#     },
#     ...
#   ]
# }
```

---

## ⚠️ Troubleshooting

### "Connection Refused"

**Symptom:** `Error: [Errno 111] Connection refused`

**Causes & Fixes:**
1. **Wrong host/port:** Verify endpoint in config
2. **Firewall blocking:** Check if your IP has network access
3. **Credentials wrong:** Test manually: `mysql -h host -u user -p` (or `psql`, `sqlplus`, etc.)

```bash
# Test Snowflake connection
python -c "
from snowflake.connector import connect
conn = connect(account='xy12345', user='test', password='test')
print('✅ Connected!')
"
```

### "Permission Denied: Need MONITOR or ACCOUNTADMIN"

**Symptom:** `Error: User does not have permission to access system.query_history`

**Fix:** The assessor needs `MONITOR` privilege at minimum. Ask your Snowflake admin:

```sql
-- In Snowflake (run as ACCOUNTADMIN)
GRANT MONITOR ON ACCOUNT TO ROLE assessment_role;
GRANT USAGE ON DATABASE analytics TO ROLE assessment_role;
GRANT USAGE ON SCHEMA analytics.public TO ROLE assessment_role;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics.public TO ROLE assessment_role;
```

### "No Query History Found"

**Symptom:** `Warning: Found 0 queries in query history. Assessment cannot proceed.`

**Causes:**
1. **Query retention expired:** Snowflake retains query history for 365 days; if your account is new, history may be sparse
2. **Wrong date filter:** Check `min_query_history_days` in config
3. **No activity:** The platform has no queries in the past 30 days (legitimate, but assessment will be low-confidence)

**Fixes:**
- Lower `min_query_history_days` to 7 or 14 if you have limited history
- Run assessment against prod (not sandbox) to get real workload data

### "Timeout: Assessment Took Too Long"

**Symptom:** `TimeoutError: Query execution exceeded 60 seconds`

**Causes:**
1. **Large table metadata scan:** Huge schema (10K+ tables)
2. **Slow network/database:** Queries are I/O intensive

**Fixes:**
```yaml
# In config
assessment:
  timeout_seconds: 300  # Increase timeout
  max_workloads: 50     # Reduce scope
```

### "Out of Disk Space"

**Symptom:** `OSError: [Errno 28] No space left on device`

**Cause:** SQLite cache is large (1 query history entry per row scanned)

**Fix:**
```bash
# Clean up cache
rm -rf ~/.lakebase-assess/cache

# Or set custom cache location with more space
export LAKEBASE_CACHE_DIR=/mnt/large-disk/cache
```

---

## 🔒 Privacy & Security

### What Data Is Collected?

The assessor reads **metadata and query patterns only**:

- ✅ Table names, row counts, column data types
- ✅ Query frequency, runtime, execution plans
- ✅ User count, concurrency patterns
- ❌ **Never:** Query text, column values, PII, credentials

### What Leaves Your System?

**By default: Nothing.** All data stays local in an encrypted SQLite database.

**Optional upload** (requires explicit `--upload` flag):

If you opt-in, **anonymized metrics only** are sent to BPCS:

```json
{
  "platform": "snowflake",
  "industry": "Financial Services",
  "company_size": "Enterprise",
  "avg_score": 18.7,
  "priority_1_count": 42,
  "est_annual_savings_pct": 42
}
```

**Never sent:**
- Company name
- Query text
- Table names
- IP addresses
- Custom pricing

See [BPCS Aggregation Pipeline](../docs/aggregation-pipeline.md) for details.

---

## 📖 Next Steps

1. **Read your assessment results:** Open `executive_summary.html`
2. **Understand the scores:** See [docs/scorecard-anatomy/](./docs/scorecard-anatomy/) for what each dimension means
3. **Plan your migration:** Use the recommended PoC scope and timeline
4. **Contact Blueprint:** Interested in a PoC? Email [sales@bpcs.com](mailto:sales@bpcs.com)

---

## 🆘 Support

### Issues & Bugs

Found a bug? Open an issue on [GitHub](https://github.com/BlueprintTechnologies/lakebase-offers/issues).

### Questions?

- **General:** See [docs/faq.md](./docs/faq.md)
- **Technical:** Email [support@bpcs.com](mailto:support@bpcs.com)
- **Commercial:** Email [sales@bpcs.com](mailto:sales@bpcs.com)

