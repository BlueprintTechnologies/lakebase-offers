# Point Lookups + Cache

For workloads that need sub-second response time on single-row or small-set queries: customer master data, product catalog, pricing tables, configuration lookups. Typical effort: 2–4 weeks.

## What qualifies

- Single-row lookups: `SELECT * FROM customers WHERE customer_id = 'X'`
- Small-set lookups: `SELECT * FROM products WHERE category = 'electronics'` (< 10K rows)
- High concurrency: 100–5000 requests/second from application backends or APIs
- Latency requirement: < 100ms P95 (often < 50ms)
- Write pattern: mostly reads; updates are infrequent (hourly batches or rare real-time updates)

If the workload has complex aggregations over millions of rows, use [Analytics to Delta](analytics-to-delta.md). If writes are frequent and transactional, use [App Backends](app-backends.md).

## Architecture

```
Application → SQL Warehouse (Lakebase)
                    │
               Lakebase Cache
              (in-memory, auto-managed)
                    │
              Delta Table
           (source of truth, hot data)
```

Lakebase SQL Warehouses include a built-in result cache and disk cache. For point lookup patterns, cache hit rates of 70–90% are common, which dramatically reduces actual DBU consumption and latency.

## The migration steps

### Step 1: Create the Delta table

```sql
CREATE TABLE prod.ops.customers (
  customer_id   STRING NOT NULL,
  email         STRING,
  name          STRING,
  region        STRING,
  tier          STRING,
  updated_at    TIMESTAMP
)
USING DELTA
-- Liquid clustering: better than static partitions for point lookups
CLUSTER BY (customer_id);

-- Enable bloom filter on the lookup key
ALTER TABLE prod.ops.customers
  SET TBLPROPERTIES (
    'delta.bloomFilter.customer_id.enabled' = 'true',
    'delta.bloomFilter.customer_id.fpp'     = '0.01'
  );
```

### Step 2: Load data (initial + incremental)

```python
# Initial load
df = spark.read.format("jdbc").option("dbtable", "schema.customers").load()
df.write.format("delta").mode("overwrite").saveAsTable("prod.ops.customers")

# Incremental MERGE (runs on schedule: hourly or near-real-time)
spark.sql("""
  MERGE INTO prod.ops.customers AS target
  USING (
    SELECT * FROM source_platform.customers
    WHERE updated_at > (SELECT MAX(updated_at) FROM prod.ops.customers)
  ) AS source
  ON target.customer_id = source.customer_id
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")
```

### Step 3: Validate the lookup query

```sql
-- This should return in < 50ms on a warmed-up warehouse
SELECT * FROM prod.ops.customers WHERE customer_id = 'cust_12345';

-- Also test the most-common filter patterns
SELECT * FROM prod.ops.customers WHERE region = 'us-west' AND tier = 'gold';
```

### Step 4: Load test concurrency

Before cutover, load test with your expected peak concurrency:

```python
from concurrent.futures import ThreadPoolExecutor
import time

def lookup(customer_id):
    start = time.time()
    cursor.execute(f"SELECT * FROM prod.ops.customers WHERE customer_id = '{customer_id}'")
    cursor.fetchone()
    return time.time() - start

customer_ids = ["cust_001", "cust_002", ...]  # sample of real IDs

with ThreadPoolExecutor(max_workers=200) as executor:
    latencies = list(executor.map(lookup, customer_ids * 10))

p50 = sorted(latencies)[len(latencies)//2]
p95 = sorted(latencies)[int(len(latencies)*0.95)]
p99 = sorted(latencies)[int(len(latencies)*0.99)]
print(f"P50: {p50*1000:.0f}ms  P95: {p95*1000:.0f}ms  P99: {p99*1000:.0f}ms")
```

Target: P95 < 100ms at 2× expected peak concurrency. If P95 > 100ms, try:
1. Increase warehouse size
2. Check bloom filter is enabled on the lookup key
3. Verify CLUSTER BY is on the lookup column (not partition by)

### Step 5: Verify cache behavior

After warm-up (run the same queries 3× to populate cache):

```sql
-- Check cache hit rate for the warehouse
SELECT
  DATE(start_time) AS day,
  SUM(CASE WHEN from_result_cache THEN 1 ELSE 0 END) AS cached_queries,
  COUNT(*) AS total_queries,
  ROUND(100.0 * SUM(CASE WHEN from_result_cache THEN 1 ELSE 0 END) / COUNT(*), 1) AS cache_hit_pct
FROM system.query.history
WHERE warehouse_id = '<your-warehouse-id>'
  AND start_time >= NOW() - INTERVAL 24 HOURS
GROUP BY DATE(start_time);
```

Cache hit rate ≥ 60% means the workload is well-suited for the Lakebase caching model. Below 30% usually means the query parameters are too diverse — consider an external cache (Redis) for the hottest keys.

### Step 6: Update application connection strings

Point application backends at the Lakebase JDBC endpoint. For Python:

```python
from databricks import sql

conn = sql.connect(
  server_hostname="<workspace>.databricks.com",
  http_path="/sql/1.0/warehouses/<warehouse-id>",
  access_token="<token>"
)
cursor = conn.cursor()
cursor.execute("SELECT * FROM prod.ops.customers WHERE customer_id = ?", ["cust_12345"])
```

### Step 7: Monitor and tune

After go-live, monitor daily for the first 2 weeks:

```sql
-- P95 latency trend by day
SELECT
  DATE(start_time) AS day,
  PERCENTILE_APPROX(total_time_ms, 0.95) AS p95_ms,
  PERCENTILE_APPROX(total_time_ms, 0.99) AS p99_ms,
  COUNT(*) AS query_count
FROM system.query.history
WHERE warehouse_id = '<your-warehouse-id>'
GROUP BY DATE(start_time)
ORDER BY day;
```

## When to add an external cache

If Lakebase caching alone does not meet SLA (typical for > 2000 req/sec or < 20ms P99 requirements), add Redis or Memcached in front of Lakebase:

```
Application → Redis (cache)  →  Lakebase (source of truth)
                  │
            Cache miss: fetch from Lakebase, populate Redis (TTL=60s)
            Cache hit: return from Redis immediately (< 5ms)
```

This pattern reduces Lakebase query volume by 80–95% and brings P99 below 5ms for cached keys.

## Related

- If writes are heavy or transactional: [App Backends](app-backends.md)
- If the lookup serves ML model inference: [Agent State & Feature Serving](agent-state.md)
- Monitoring latency post-migration: [Measuring Migration Success](../after-the-engagement/measuring-success.md)
