# Troubleshooting

Common problems encountered during the Lakebase assessment and migration, with diagnostic steps and fixes.

## Assessment tool issues

### `ConnectionError: Connection refused` when running the assessor

**Cause:** The source platform is not reachable from where the assessor is running.

**Diagnosis:**
```bash
# Test TCP connectivity to the source
nc -zv <source-host> <port>
# PostgreSQL: port 5432 | MySQL: 3306 | Oracle: 1521 | SQL Server: 1433
# Snowflake: 443 | BigQuery: 443 | Redshift: 5439
```

**Fix:**
1. If running assessor locally: check VPN — the source DB may be in a private VPC
2. If running on an EC2/VM: check security group rules — add assessor IP to the DB's inbound allowlist
3. If source is Snowflake/BigQuery/Redshift: check IP allowlist in the cloud platform console
4. For Snowflake: ensure the account identifier format is correct (`orgname-accountname`, not just `accountname`)

---

### `PermissionError: User lacks SELECT privilege`

**Cause:** The credentials supplied to the assessor have insufficient permissions.

**Minimum required grants:**
```sql
-- PostgreSQL
GRANT CONNECT ON DATABASE mydb TO assessor_user;
GRANT USAGE ON SCHEMA public TO assessor_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO assessor_user;

-- Snowflake
GRANT USAGE ON DATABASE mydb TO ROLE assessor_role;
GRANT USAGE ON SCHEMA mydb.public TO ROLE assessor_role;
GRANT SELECT ON ALL TABLES IN SCHEMA mydb.public TO ROLE assessor_role;
GRANT MONITOR USAGE ON ACCOUNT TO ROLE assessor_role;  -- for query history

-- BigQuery
GRANT roles/bigquery.dataViewer ON DATASET myproject.mydataset TO serviceAccount:assessor@project.iam.gserviceaccount.com;
GRANT roles/bigquery.jobUser ON PROJECT myproject TO serviceAccount:assessor@project.iam.gserviceaccount.com;
```

---

### Assessment runs but 0 tables are discovered

**Cause:** Schema filter in `config.yaml` doesn't match any tables, or the user has no grants on any tables.

**Diagnosis:**
```bash
# Run with verbose logging
lakebase-assess run --config config.yaml --verbose 2>&1 | grep "schema\|table\|found"
```

**Fix:**
1. Check `schemas:` in config.yaml — remove filters to discover all schemas
2. Verify the user can see tables: `SELECT table_name FROM information_schema.tables LIMIT 5`
3. For Snowflake: check the role is set correctly (`ALTER SESSION SET ROLE = assessor_role`)

---

### `DiskFullError` or `MemoryError` during profiling

**Cause:** Table row profiling downloads sample data locally. Large tables with wide schemas can exhaust disk or RAM.

**Fix:**
```yaml
# In config.yaml — reduce sample size or disable profiling for large tables
profiling:
  sample_rows: 1000      # default: 10000
  max_table_size_gb: 50  # skip profiling tables larger than this
  skip_tables:
    - large_schema.huge_log_table
    - raw.clickstream_events
```

---

## SQL Warehouse connection issues

### `Error: Could not open client transport with JDBC Url`

**Cause:** Wrong HTTP path or server hostname in the connection string.

**Fix:**
1. In your Databricks workspace: SQL Warehouses → click your warehouse → Connection Details
2. Copy the exact server hostname and HTTP path
3. HTTP path format: `/sql/1.0/warehouses/abc123def456` (contains your warehouse ID)

```python
# Correct format
conn = sql.connect(
    server_hostname="adb-1234567890.12.azuredatabricks.net",  # no https://
    http_path="/sql/1.0/warehouses/abc123def456",            # exact path
    access_token="dapi1234..."
)
```

---

### `Error: Invalid access token`

**Cause:** Token has expired, was revoked, or was entered with extra whitespace.

**Fix:**
1. Workspace UI → Settings → Developer → Access Tokens → generate a new token
2. Copy token carefully — no leading/trailing spaces
3. For CI/CD: store in Databricks Secrets, not in environment variables or code

---

### Warehouse takes 30+ seconds to respond to first query

**Cause:** Serverless or Pro warehouse is in auto-stop state and needs to start.

**Fix:**
1. For BI dashboards: pre-warm the warehouse with a `SELECT 1` query before users arrive
2. For app backends: use Pro tier with auto-stop disabled or set to 60+ minutes
3. Configure warehouse to start on schedule:
   ```bash
   databricks warehouses start <warehouse-id>
   ```
4. Consider keeping a minimum of 1 cluster always warm (Pro warehouses only)

---

### `Error: Too many simultaneous queries` / connection pool exhaustion

**Cause:** More connections than the warehouse can handle, or application not using a pool.

**Fix:**
1. Implement connection pooling (see [App Backends playbook — Step 5](migration-playbooks/app-backends.md#step-5-configure-connection-pooling))
2. Increase warehouse cluster count: SQL Warehouses → Edit → Max Clusters
3. Check warehouse size — X-Large handles ~200 concurrent queries; scale up if needed

---

## Data migration issues

### Row count mismatch after initial load

**Cause:** Writes to source platform during the load window; or load picked up a partial snapshot.

**Diagnosis:**
```sql
-- Check if source count has changed since you loaded
-- Source:
SELECT COUNT(*), MAX(updated_at) FROM schema.orders;

-- Lakebase:
SELECT COUNT(*), MAX(updated_at) FROM prod.sales.orders;
```

**Fix:**
1. Re-run the load with a watermark based on the timestamp where counts diverge
2. For live tables, use a snapshot export at a specific SCN/LSN:
   ```python
   # PostgreSQL: export at a specific point in time
   df = spark.read.format("jdbc") \
     .option("dbtable", "(SELECT * FROM orders WHERE updated_at <= '2026-05-01 00:00:00') t") \
     .load()
   ```
3. After the load, run CDC sync to catch up from the snapshot timestamp

---

### Numeric aggregation mismatch (small but non-zero difference)

**Cause:** Floating-point precision differences between platforms. Snowflake uses 38-digit precision; Databricks DOUBLE is 64-bit IEEE 754.

**Fix:**
1. Use `DECIMAL(p,s)` instead of `DOUBLE`/`FLOAT` for financial amounts:
   ```sql
   ALTER TABLE prod.sales.orders
     ALTER COLUMN amount TYPE DECIMAL(14,2);
   ```
2. If < 0.01% difference is acceptable, the workload passes validation — document the tolerance

---

### `AnalysisException: Table not found` after loading data

**Cause:** Table was created in a different catalog or schema than expected, or default catalog is not set.

**Fix:**
```sql
-- Check where the table actually is
SHOW TABLES IN prod.sales;

-- Set default catalog/schema for your session
USE CATALOG prod;
USE SCHEMA sales;

-- Or use fully qualified names always
SELECT * FROM prod.sales.orders;
```

---

### MERGE is slow on large tables

**Cause:** Large target table without OPTIMIZE; or MERGE predicate doesn't use the clustering column.

**Fix:**
```sql
-- Run OPTIMIZE first
OPTIMIZE prod.app.orders;

-- Enable low-shuffle merge for large merges
SET spark.databricks.delta.merge.enableLowShuffle = true;

-- Ensure MERGE ON clause uses the clustering column
MERGE INTO prod.app.orders AS t
USING source AS s
ON t.order_id = s.order_id  -- must match CLUSTER BY column
...
```

---

## Performance issues

### Queries slower than source platform

**Diagnosis:**
```sql
-- Check if the query is using file pruning
EXPLAIN SELECT * FROM prod.sales.orders WHERE region = 'us-west';
-- Look for: PartitionFilters, DataFilters in the plan

-- Check query execution details
SELECT *
FROM system.query.history
WHERE statement_text LIKE '%orders%'
ORDER BY start_time DESC
LIMIT 10;
```

**Common fixes:**
1. Run `OPTIMIZE prod.sales.orders ZORDER BY (region, customer_id)` — co-locate data for your filter pattern
2. Verify bloom filter is enabled on high-cardinality lookup columns
3. Run `ANALYZE TABLE ... COMPUTE STATISTICS FOR ALL COLUMNS` — updates optimizer statistics
4. Scale warehouse up one tier; re-measure P95
5. Check if query is hitting the result cache: `from_result_cache = true` in query history

---

### VACUUM removes too much history

**Cause:** VACUUM was run with a short retention period, deleting time travel history needed for debugging.

**Fix:**
```sql
-- Check current retention setting
SHOW TBLPROPERTIES prod.sales.orders;

-- Set minimum 7-day retention (Databricks default)
ALTER TABLE prod.sales.orders
  SET TBLPROPERTIES ('delta.deletedFileRetentionDuration' = 'interval 7 days');

-- Run VACUUM with explicit retention
VACUUM prod.sales.orders RETAIN 168 HOURS;  -- 7 days
```

---

## Access and permission issues

### `SecurityException: User does not have SELECT privilege on table`

**Fix:**
```sql
-- Check what grants exist on the table
SHOW GRANTS ON TABLE prod.sales.orders;

-- Grant access to the user or group
GRANT SELECT ON TABLE prod.sales.orders TO `analyst-team`;
GRANT SELECT ON TABLE prod.sales.orders TO `user@example.com`;
```

---

### Column masking not applying

**Cause:** Mask function references a group the user is not in, or mask was applied to the wrong column.

**Diagnosis:**
```sql
-- Check if mask is applied
DESCRIBE EXTENDED prod.app.users;
-- Look for "Mask Function" in the output

-- Test the mask function directly
SELECT prod.security.mask_email('test@example.com');
```

---

## Getting more help

1. Check the [FAQ](faq.md) for common questions
2. Review your workload's [migration playbook](migration-playbooks/index.md)
3. Databricks documentation: [docs.databricks.com](https://docs.databricks.com)
4. Open a support ticket with your Blueprint engagement lead, including:
   - The error message (full stack trace)
   - Which assessor version: `lakebase-assess --version`
   - Which source platform and connector
   - What you've already tried
