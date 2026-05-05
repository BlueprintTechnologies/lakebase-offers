# Agent State & Feature Serving

For workloads that power ML inference, AI agents, and real-time personalization: feature stores, model serving state, agent context, recommendation tables. Typical effort: 2–4 weeks.

## What qualifies

- Feature store reads: `SELECT * FROM features WHERE entity_id = 'user_123'` at high QPS
- Agent context: reading/writing session state for AI agents between turns
- Recommendation tables: top-N items per user or item, refreshed on a schedule
- Model serving: low-latency lookup of precomputed scores or embeddings
- Write pattern: high-frequency batch writes (feature refresh pipelines) + high-frequency reads (serving)
- Latency requirement: < 50ms P95 for serving reads; batch writes can be higher

If the workload is purely analytical with no real-time serving requirement, use [Analytics to Delta](analytics-to-delta.md). If the serving latency requirement is < 20ms P99, add an external cache per the architecture below.

## Architecture

```
Feature Pipeline           AI Agent / Model Server
(Spark, dbt, Flink)               │
        │                         │ (high-QPS reads)
        ▼                         ▼
  Lakebase SQL Warehouse ←── Delta Tables
  (feature write path)       (feature store)
        │                         │
        └─────────────────────────┤
                            Lakebase Cache
                         (auto-managed, in-memory)
                                  │
                         Optional: Redis / Memcached
                         (< 20ms P99 requirement)
```

Delta tables act as the source-of-truth feature store. Lakebase's built-in cache handles the hot serving path. For sub-20ms requirements, add Redis in front.

## The migration steps

### Step 1: Create the feature table

```sql
-- Entity features table (point lookup by entity ID)
CREATE TABLE prod.ml.user_features (
  user_id         STRING NOT NULL,
  feature_version INT    NOT NULL,
  age_bucket      INT,
  purchase_count_30d INT,
  avg_order_value DOUBLE,
  last_active_ts  TIMESTAMP,
  top_categories  ARRAY<STRING>,
  computed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
USING DELTA
CLUSTER BY (user_id)
TBLPROPERTIES (
  'delta.bloomFilter.user_id.enabled' = 'true',
  'delta.bloomFilter.user_id.fpp'     = '0.01',
  'delta.enableChangeDataFeed'        = 'true'
);

-- Agent context / session state table
CREATE TABLE prod.ml.agent_sessions (
  session_id   STRING NOT NULL,
  agent_id     STRING NOT NULL,
  user_id      STRING,
  context_blob STRING,            -- JSON-serialized context
  turn_count   INT    DEFAULT 0,
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at   TIMESTAMP
)
USING DELTA
CLUSTER BY (session_id)
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
```

### Step 2: Migrate the feature pipeline

Replace source platform feature computation jobs with Databricks notebooks or Delta Live Tables:

```python
# Feature computation pipeline (runs on schedule: every 1–6 hours)
from pyspark.sql import functions as F

# Compute user features from raw events
user_features = spark.sql("""
  SELECT
    user_id,
    1 AS feature_version,
    DATEDIFF(CURRENT_DATE, MIN(created_at)) / 10 AS age_bucket,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL 30 DAYS) AS purchase_count_30d,
    AVG(amount) AS avg_order_value,
    MAX(event_ts) AS last_active_ts,
    COLLECT_LIST(DISTINCT category) AS top_categories,
    CURRENT_TIMESTAMP AS computed_at
  FROM prod.app.orders
  JOIN prod.app.events USING (user_id)
  GROUP BY user_id
""")

# MERGE to update existing feature rows
user_features.createOrReplaceTempView("new_features")
spark.sql("""
  MERGE INTO prod.ml.user_features AS target
  USING new_features AS source
  ON target.user_id = source.user_id
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *
""")
```

### Step 3: Validate feature values

Before switching serving traffic, validate that feature values match the source platform:

```python
# Compare feature distributions between source and Lakebase
source_stats = spark.read.format("jdbc") \
  .option("dbtable", "ml.user_features") \
  .load() \
  .agg(
    F.mean("purchase_count_30d").alias("mean_purchases"),
    F.stddev("purchase_count_30d").alias("stddev_purchases"),
    F.mean("avg_order_value").alias("mean_aov")
  ).collect()[0]

lakebase_stats = spark.sql("""
  SELECT
    AVG(purchase_count_30d) AS mean_purchases,
    STDDEV(purchase_count_30d) AS stddev_purchases,
    AVG(avg_order_value) AS mean_aov
  FROM prod.ml.user_features
""").collect()[0]

# Assert < 1% relative difference
for col in ["mean_purchases", "mean_aov"]:
    src = source_stats[col]
    lb  = lakebase_stats[col]
    diff_pct = abs(src - lb) / src * 100
    assert diff_pct < 1.0, f"{col}: {diff_pct:.2f}% difference (source={src}, lakebase={lb})"
print("Feature validation passed")
```

### Step 4: Load test the serving path

Feature serving is read-heavy and high-concurrency. Validate before routing production traffic:

```python
from concurrent.futures import ThreadPoolExecutor
import time

def serve_features(user_id):
    start = time.time()
    cursor.execute(
        "SELECT * FROM prod.ml.user_features WHERE user_id = ? AND feature_version = 1",
        [user_id]
    )
    cursor.fetchone()
    return time.time() - start

user_ids = ["user_001", "user_002", ...]  # representative sample

with ThreadPoolExecutor(max_workers=500) as executor:
    latencies = list(executor.map(serve_features, user_ids * 5))

p50 = sorted(latencies)[len(latencies)//2]
p95 = sorted(latencies)[int(len(latencies)*0.95)]
p99 = sorted(latencies)[int(len(latencies)*0.99)]
print(f"P50: {p50*1000:.0f}ms  P95: {p95*1000:.0f}ms  P99: {p99*1000:.0f}ms")
```

Target: P95 < 50ms. If not met, check bloom filter, CLUSTER BY column alignment, and warehouse size.

### Step 5: Wire up agent context reads/writes

For AI agent workloads that need to persist context between turns:

```python
from databricks import sql

conn = sql.connect(
    server_hostname="<workspace>.databricks.com",
    http_path="/sql/1.0/warehouses/<warehouse-id>",
    access_token="<token>"
)

def get_agent_context(session_id: str) -> dict:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT context_blob, turn_count FROM prod.ml.agent_sessions WHERE session_id = ?",
        [session_id]
    )
    row = cursor.fetchone()
    if row:
        import json
        return {"context": json.loads(row[0]), "turn": row[1]}
    return {"context": {}, "turn": 0}

def update_agent_context(session_id: str, context: dict, turn: int):
    import json
    cursor = conn.cursor()
    cursor.execute("""
        MERGE INTO prod.ml.agent_sessions AS t
        USING (SELECT ? AS session_id) AS s ON t.session_id = s.session_id
        WHEN MATCHED THEN UPDATE SET
          context_blob = ?,
          turn_count   = ?,
          updated_at   = CURRENT_TIMESTAMP
        WHEN NOT MATCHED THEN INSERT (session_id, context_blob, turn_count)
          VALUES (?, ?, ?)
    """, [session_id, json.dumps(context), turn, session_id, json.dumps(context), turn])
```

### Step 6: Add external cache for sub-20ms requirements

If model serving or agent state requires < 20ms P99:

```python
import redis
import json
from databricks import sql

redis_client = redis.Redis(host="redis-host", port=6379)
CACHE_TTL = 300  # 5-minute TTL for feature cache

def get_features_cached(user_id: str) -> dict:
    # Try cache first
    cached = redis_client.get(f"features:{user_id}")
    if cached:
        return json.loads(cached)

    # Cache miss: fetch from Lakebase
    cursor = lakebase_conn.cursor()
    cursor.execute(
        "SELECT * FROM prod.ml.user_features WHERE user_id = ?",
        [user_id]
    )
    row = cursor.fetchone()
    if row:
        features = dict(zip([d[0] for d in cursor.description], row))
        redis_client.setex(f"features:{user_id}", CACHE_TTL, json.dumps(features, default=str))
        return features
    return {}
```

Cache invalidation: use Delta Change Data Feed to detect updated feature rows and proactively evict stale keys.

### Step 7: Monitor feature freshness and serving latency

```sql
-- Feature freshness: how many users have stale features (> 6 hours old)?
SELECT
  COUNT(*) AS total_users,
  COUNT(*) FILTER (WHERE computed_at < NOW() - INTERVAL 6 HOURS) AS stale_users,
  ROUND(100.0 * COUNT(*) FILTER (WHERE computed_at < NOW() - INTERVAL 6 HOURS) / COUNT(*), 1) AS stale_pct
FROM prod.ml.user_features;

-- Serving latency trend (from system query history)
SELECT
  DATE(start_time) AS day,
  PERCENTILE_APPROX(total_time_ms, 0.50) AS p50_ms,
  PERCENTILE_APPROX(total_time_ms, 0.95) AS p95_ms,
  COUNT(*) AS query_count
FROM system.query.history
WHERE warehouse_id = '<your-warehouse-id>'
  AND statement_text LIKE '%user_features%'
GROUP BY DATE(start_time)
ORDER BY day;
```

## Feature store integration

If the organization uses MLflow for model tracking, register the Delta feature table as an MLflow feature table:

```python
from databricks.feature_store import FeatureStoreClient

fs = FeatureStoreClient()

fs.register_table(
    delta_table="prod.ml.user_features",
    primary_keys=["user_id"],
    description="Per-user behavioral features, refreshed every 6 hours"
)

# Training: auto-join features to training data
training_df = fs.create_training_set(
    df=labels_df,
    feature_lookups=[FeatureLookup(table_name="prod.ml.user_features", lookup_key="user_id")],
    label="target"
).load_dataframe(spark)
```

## Related

- If the workload is pure analytics with no real-time serving: [Analytics to Delta](analytics-to-delta.md)
- If the serving read pattern is identical to a customer master lookup: [Point Lookups + Cache](point-lookups.md)
- ACID transactions for context writes: [Delta Lake](../databricks-101/delta-lake.md)
- Monitoring latency post-migration: [Measuring Migration Success](../after-the-engagement/measuring-success.md)
