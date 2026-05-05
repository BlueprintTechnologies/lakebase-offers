# Measuring Migration Success

A migration is only complete when you can prove it. This page defines the metrics and validation steps that confirm a workload is successfully migrated and the savings are real.

## The four success dimensions

| Dimension | Question | How to measure |
| --- | --- | --- |
| **Correctness** | Do Lakebase query results match the source platform? | Row count match, aggregation match, regression test suite |
| **Performance** | Does Lakebase meet or exceed the source platform SLA? | P95 latency, query execution time, concurrency |
| **Cost** | Are the actual savings tracking to the projection? | Lakebase DBU cost vs. source platform cost, same workload |
| **Reliability** | Is the workload stable in production? | Error rate, failure count, 72-hour monitoring window |

## Correctness validation

Run these queries against **both** the source platform and Lakebase, then diff the results:

### Row count match

```sql
-- Run on source platform
SELECT COUNT(*) AS row_count FROM schema.orders
WHERE created_at >= '2026-01-01' AND created_at < '2026-02-01';

-- Run on Lakebase (should match)
SELECT COUNT(*) AS row_count FROM catalog.schema.orders
WHERE created_at >= '2026-01-01' AND created_at < '2026-02-01';
```

A mismatch here is a blocking finding before cutover.

### Aggregation match (your most business-critical query)

```sql
-- Run on source, then Lakebase — compare results row by row
SELECT
  DATE(created_at) AS day,
  region,
  COUNT(*) AS orders,
  SUM(revenue) AS total_revenue,
  COUNT(DISTINCT customer_id) AS unique_customers
FROM orders
WHERE created_at >= '2026-01-01'
GROUP BY DATE(created_at), region
ORDER BY day, region;
```

Acceptable tolerance: row count 100%, numeric aggregations within 0.01% (floating point rounding).

### Spot check on recent data

```sql
-- Pick 5 specific high-value records and verify in both platforms
SELECT * FROM schema.orders WHERE order_id IN (
  'ord_001', 'ord_002', 'ord_003', 'ord_004', 'ord_005'
);
```

Every column should match. Differences in string casing or timestamp precision are acceptable if documented.

## Performance validation

### Latency benchmark

Run the 5 most-used queries (from the assessor output) on both platforms, 10 times each:

```bash
# Capture query runtime (example using Python + Databricks SDK)
import time
for i in range(10):
    start = time.time()
    cursor.execute("SELECT ...")
    elapsed = time.time() - start
    print(f"Run {i+1}: {elapsed:.3f}s")
```

Target: Lakebase P95 latency ≤ source platform P95 latency (or within SLA target).

### Concurrency test

If the workload serves concurrent users (dashboards, APIs), run a load test before cutover:

```python
# Simple concurrent query load test (adapt as needed)
from concurrent.futures import ThreadPoolExecutor
import time

def run_query():
    start = time.time()
    cursor.execute("SELECT ... (your target query)")
    return time.time() - start

with ThreadPoolExecutor(max_workers=50) as executor:
    latencies = list(executor.map(lambda _: run_query(), range(200)))

p95 = sorted(latencies)[int(len(latencies) * 0.95)]
print(f"P95 latency under 50 concurrent users: {p95:.3f}s")
```

Acceptable: P95 within 20% of SLA target under 2× expected peak concurrency.

## Cost validation

### Comparing actual costs

After 2 weeks of production traffic on Lakebase, compare actual costs:

**Lakebase cost (from Databricks billing):**

```sql
-- Query Databricks system billing table
SELECT
  DATE(usage_date) AS day,
  SUM(usage_quantity) AS total_dbus,
  SUM(usage_quantity * list_price) AS estimated_cost
FROM system.billing.usage
WHERE warehouse_id = 'your_warehouse_id'
  AND usage_date >= '2026-04-21'
GROUP BY DATE(usage_date)
ORDER BY day;
```

**Source platform cost (from your platform's billing console):**
Pull the equivalent 2-week cost for the same workload from your source platform billing console.

**Compare:**
```
Source platform (2 weeks): $X
Lakebase (2 weeks):         $Y
Savings (2 weeks):          $(X-Y)  →  annualized: $(X-Y) × 26
Savings %:                  (X-Y)/X × 100
```

If actual savings are more than 20% below projected, investigate:
- Is the Lakebase warehouse over-provisioned?
- Are there unexpected queries from other teams hitting the warehouse?
- Is the workload running more frequently than the historical baseline assumed?

### Right-sizing the warehouse

Most migrations start with a conservative warehouse size. After 2 weeks of production data, optimize:

```sql
-- View average and peak utilization
SELECT
  warehouse_id,
  AVG(avg_task_cpus) AS avg_cpu_util,
  MAX(peak_task_cpus) AS peak_cpu,
  AVG(queued_queries) AS avg_queue_depth
FROM system.compute.warehouse_events
WHERE timestamp >= NOW() - INTERVAL 14 DAYS
GROUP BY warehouse_id;
```

If average CPU utilization is below 30%, drop the warehouse size by one tier. If queue depth averages > 5, consider upgrading.

## Reliability monitoring

### 72-hour monitoring window

After cutover, monitor for 72 hours before decommissioning the source:

- [ ] Query error rate < 0.1%
- [ ] P95 latency within SLA every hour
- [ ] No data staleness issues (if incremental load is running)
- [ ] Downstream consumers (dashboards, pipelines, APIs) report no issues
- [ ] Business owner confirms results look correct

**Keep the source platform running in parallel during this window.** If a critical issue emerges, you can cut back with minimal downtime.

### Ongoing monitoring (post-cutover)

Set up these alerts in Databricks:

```sql
-- Alert: query error rate > 1% in last hour
SELECT
  DATE_TRUNC('hour', start_time) AS hour,
  COUNT(*) AS total_queries,
  SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed_queries,
  ROUND(100.0 * SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) / COUNT(*), 2) AS error_rate_pct
FROM system.query.history
WHERE warehouse_id = 'your_warehouse_id'
  AND start_time >= NOW() - INTERVAL 1 HOUR
GROUP BY DATE_TRUNC('hour', start_time);
```

Send alerts to a Slack channel or PagerDuty for the pod lead.

## Reporting success to the executive sponsor

After the 72-hour monitoring window, send a migration completion report:

```
✅ [Workload Name] — Migration Complete

Platform: Snowflake → Lakebase
Go-live date: 2026-05-07
Monitoring window: 2026-05-07 to 2026-05-10 (72 hours, no incidents)

Results:
  Query correctness:  100% match on regression test suite
  P95 latency:        2.1s (vs. 8.4s on Snowflake) — 4x improvement
  Error rate:         0.0% over 72 hours
  Monthly savings:    $18,400/month ($220,800/year)
  Savings vs. projection: 96% (slight savings from serverless efficiency)

Source platform workload: Decommissioned 2026-05-10

Next up: [Next workload name] sprint begins 2026-05-12
```

## Related

- The 72-hour window and sprint checklist: [Standing Up Your Migration Pod](migration-pod.md)
- Phase 2 planning: [Scaling to More Workloads](second-workload.md)
- Full program timeline: [30/60/90 Day Plan](30-60-90.md)
