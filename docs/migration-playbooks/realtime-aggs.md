# Real-time Aggregations

For workloads that need continuously-updated aggregations: running totals, live leaderboards, fraud signals, real-time dashboards. Typical effort: 4–6 weeks.

## What qualifies

- Aggregations that must reflect data within seconds to minutes of it arriving
- Examples: fraud score running on last 5 minutes of transactions, live inventory count, real-time revenue dashboard
- Write pattern: high-throughput event streams (Kafka, Kinesis, Event Hubs)
- Read pattern: frequent reads of pre-aggregated results (dashboards, APIs)
- Acceptable latency to query: < 30 seconds end-to-end (event → visible in query)

If aggregations can be 1+ hours stale, use [Analytics to Delta](analytics-to-delta.md). If you need sub-second freshness with complex stateful operations, consider a dedicated stream processor (Flink) upstream of Lakebase.

## Architecture

```
Event Stream (Kafka / Kinesis)
        │
  Databricks Structured Streaming
  (micro-batch, 10–30s trigger)
        │
  Delta Tables (append-only raw events)
        │
  Materialized Aggregations
  (MERGE on each micro-batch)
        │
  Lakebase SQL Warehouse
  (read path: dashboards, APIs)
        │
  Lakebase Cache (result cache)
```

The key pattern: streaming jobs write raw events AND continuously refresh aggregation tables via MERGE. Dashboards query the aggregation tables, not the raw events, so reads are fast.

## The migration steps

### Step 1: Create the raw events table

```sql
-- Append-only raw events (immutable, partitioned by ingestion date)
CREATE TABLE prod.streaming.txn_events (
  event_id      STRING NOT NULL,
  user_id       STRING,
  merchant_id   STRING,
  amount        DECIMAL(12,2),
  currency      STRING,
  event_ts      TIMESTAMP NOT NULL,
  event_type    STRING,
  region        STRING,
  ingested_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
USING DELTA
PARTITION BY (DATE(event_ts))
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact'   = 'true'
);
```

### Step 2: Create the aggregation table

```sql
-- Pre-aggregated results (updated on each micro-batch)
CREATE TABLE prod.streaming.txn_agg_5min (
  window_start  TIMESTAMP NOT NULL,
  window_end    TIMESTAMP NOT NULL,
  user_id       STRING    NOT NULL,
  txn_count     BIGINT,
  total_amount  DECIMAL(14,2),
  distinct_merchants INT,
  max_single_txn     DECIMAL(12,2),
  updated_at    TIMESTAMP
)
USING DELTA
CLUSTER BY (user_id, window_start)
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
```

### Step 3: Write the streaming ingestion job

```python
# Ingest from Kafka into raw events table
from pyspark.sql import functions as F
from pyspark.sql.types import *

schema = StructType([
    StructField("event_id",    StringType()),
    StructField("user_id",     StringType()),
    StructField("merchant_id", StringType()),
    StructField("amount",      DecimalType(12,2)),
    StructField("currency",    StringType()),
    StructField("event_ts",    TimestampType()),
    StructField("event_type",  StringType()),
    StructField("region",      StringType()),
])

raw_stream = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "kafka:9092")
    .option("subscribe", "transactions")
    .option("startingOffsets", "latest")
    .load()
    .select(F.from_json(F.col("value").cast("string"), schema).alias("data"))
    .select("data.*")
    .withColumn("ingested_at", F.current_timestamp())
)

# Write raw events (append only)
raw_stream.writeStream \
    .format("delta") \
    .outputMode("append") \
    .option("checkpointLocation", "/checkpoints/txn_events") \
    .trigger(processingTime="15 seconds") \
    .toTable("prod.streaming.txn_events")
```

### Step 4: Write the aggregation refresh job

```python
# Compute and MERGE aggregations on each micro-batch
def merge_aggregations(batch_df, batch_id):
    # Compute 5-minute window aggregations for this batch
    agg_df = (
        batch_df
        .withColumn("window", F.window("event_ts", "5 minutes"))
        .groupBy("window.start", "window.end", "user_id")
        .agg(
            F.count("*").alias("txn_count"),
            F.sum("amount").alias("total_amount"),
            F.countDistinct("merchant_id").alias("distinct_merchants"),
            F.max("amount").alias("max_single_txn"),
        )
        .withColumnRenamed("start", "window_start")
        .withColumnRenamed("end", "window_end")
        .withColumn("updated_at", F.current_timestamp())
    )

    agg_df.createOrReplaceTempView("batch_agg")

    spark.sql("""
        MERGE INTO prod.streaming.txn_agg_5min AS target
        USING batch_agg AS source
        ON  target.user_id      = source.user_id
        AND target.window_start = source.window_start
        WHEN MATCHED THEN UPDATE SET
          txn_count           = source.txn_count,
          total_amount        = source.total_amount,
          distinct_merchants  = source.distinct_merchants,
          max_single_txn      = source.max_single_txn,
          updated_at          = source.updated_at
        WHEN NOT MATCHED THEN INSERT *
    """)

# Stream reads from raw events table; runs in parallel with ingestion job
events_stream = spark.readStream \
    .format("delta") \
    .option("readChangeFeed", "false") \
    .table("prod.streaming.txn_events")

events_stream.writeStream \
    .foreachBatch(merge_aggregations) \
    .option("checkpointLocation", "/checkpoints/txn_agg_5min") \
    .trigger(processingTime="30 seconds") \
    .start()
```

### Step 5: Validate end-to-end freshness

Measure time from event creation to query visibility:

```python
import time
from databricks import sql

# Insert a canary event with a known timestamp
canary_ts = time.time()
cursor.execute("""
  INSERT INTO prod.streaming.txn_events VALUES (
    'canary_001', 'user_test', 'merch_test',
    1.00, 'USD', CURRENT_TIMESTAMP, 'canary', 'us-west', CURRENT_TIMESTAMP
  )
""")

# Poll until canary appears in aggregations
max_wait = 60  # seconds
poll_interval = 5
start = time.time()
while time.time() - start < max_wait:
    cursor.execute("""
      SELECT MAX(updated_at) FROM prod.streaming.txn_agg_5min
      WHERE user_id = 'user_test'
    """)
    last_updated = cursor.fetchone()[0]
    if last_updated and last_updated.timestamp() > canary_ts:
        latency = time.time() - canary_ts
        print(f"End-to-end latency: {latency:.1f}s")
        break
    time.sleep(poll_interval)
else:
    print("WARN: canary not visible within 60s — check streaming job logs")
```

Target: canary visible within 30 seconds. If not, check trigger interval and warehouse auto-start time.

### Step 6: Validate aggregation correctness

Run both the source aggregation system and Lakebase in parallel for 24 hours and compare:

```sql
-- Compare hourly totals between source and Lakebase
-- (run equivalent query on source platform)
SELECT
  DATE_TRUNC('hour', window_start) AS hour,
  SUM(txn_count)   AS total_txns,
  SUM(total_amount) AS total_amount
FROM prod.streaming.txn_agg_5min
WHERE window_start >= NOW() - INTERVAL 24 HOURS
GROUP BY 1
ORDER BY 1;
```

Acceptable tolerance: < 0.1% difference in totals. Differences > 1% indicate a windowing or watermark mismatch.

### Step 7: Tune the streaming pipeline

**If end-to-end latency is too high:**

1. Reduce trigger interval (15s → 5s), but watch DBU cost
2. Check if the MERGE is running long due to too many open windows — add a watermark:
   ```python
   events_stream.withWatermark("event_ts", "5 minutes")
   ```
3. Scale the streaming cluster (more workers = faster MERGE)

**If DBU cost is high:**
- Use a small dedicated cluster for the streaming job (2–4 workers)
- Use Serverless Streaming (preview) if available in your workspace

**If the aggregation table grows unbounded:**
```sql
-- Archive old windows (keep only last 90 days hot)
DELETE FROM prod.streaming.txn_agg_5min
WHERE window_end < NOW() - INTERVAL 90 DAYS;

VACUUM prod.streaming.txn_agg_5min RETAIN 168 HOURS;
```

### Step 8: Connect dashboards to the aggregation table

Point BI tools at the aggregation table (not the raw events). Update connection strings:

```sql
-- Example: real-time fraud risk dashboard query (runs every 30s via BI tool auto-refresh)
SELECT
  user_id,
  SUM(txn_count)    AS txns_last_5min,
  SUM(total_amount) AS amount_last_5min,
  MAX(max_single_txn) AS max_txn,
  MAX(updated_at)   AS last_refreshed
FROM prod.streaming.txn_agg_5min
WHERE window_end >= NOW() - INTERVAL 5 MINUTES
GROUP BY user_id
HAVING SUM(txn_count) > 10   -- potential fraud signal
ORDER BY SUM(total_amount) DESC
LIMIT 100;
```

## Monitoring after go-live

```sql
-- Streaming job lag: how far behind is the aggregation from raw events?
SELECT
  MAX(ingested_at) AS latest_raw_event,
  MAX(updated_at)  AS latest_agg_update,
  DATEDIFF(SECOND, MAX(updated_at), MAX(ingested_at)) AS lag_seconds
FROM prod.streaming.txn_events e
JOIN prod.streaming.txn_agg_5min a
  ON e.user_id = a.user_id;

-- Row rate: events per minute (should be stable)
SELECT
  DATE_TRUNC('minute', ingested_at) AS minute,
  COUNT(*) AS events_per_minute
FROM prod.streaming.txn_events
WHERE ingested_at >= NOW() - INTERVAL 1 HOUR
GROUP BY 1
ORDER BY 1;
```

## Related

- For batch aggregations that don't need real-time freshness: [Analytics to Delta](analytics-to-delta.md)
- For agent state that uses streaming context: [Agent State & Feature Serving](agent-state.md)
- Delta streaming internals: [Delta Lake](../databricks-101/delta-lake.md)
- Monitoring latency post-migration: [Measuring Migration Success](../after-the-engagement/measuring-success.md)
