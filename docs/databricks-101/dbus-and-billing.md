# DBUs and Billing

Understanding how Databricks bills for compute is essential for validating your assessment's cost savings projections and tracking actual savings in production.

## What is a DBU?

A **Databricks Unit (DBU)** is Databricks' unit of compute consumption. One DBU is roughly equivalent to one hour of a standard virtual machine core running a Databricks workload. Every compute resource in Databricks — SQL Warehouses, all-purpose clusters, jobs clusters — consumes DBUs.

DBU consumption depends on the instance type (CPU, memory), the product tier (Serverless, Pro, Classic), and the workload type (SQL, ML, streaming).

## How SQL Warehouse billing works

SQL Warehouses are what you use for Lakebase SQL queries. Billing is:

```
Cost = DBUs consumed × DBU price
DBUs consumed = warehouse size × hours active
```

**Warehouse sizes and DBU rates (approximate, US East, Serverless):**

| Warehouse size | DBU/hour | Approximate $/hour |
| --- | --- | --- |
| 2X-Small | 1 | $0.06–$0.10 |
| X-Small | 2 | $0.12–$0.20 |
| Small | 4 | $0.24–$0.40 |
| Medium | 8 | $0.48–$0.80 |
| Large | 16 | $0.96–$1.60 |
| X-Large | 32 | $1.92–$3.20 |
| 2X-Large | 64 | $3.84–$6.40 |
| 3X-Large | 128 | $7.68–$12.80 |

> **Actual rates vary** by cloud provider (AWS, Azure, GCP), region, product tier, and your negotiated Databricks agreement. Your assessment report uses default rates unless you provided your actual pricing.

## The serverless advantage

Serverless SQL Warehouses scale to zero when idle. With traditional data warehouses, you pay for the warehouse even when no queries are running.

**Example:**
- A Snowflake M warehouse running 24/7 = $4/credit × 24 hours × 30 days = $2,880/month (even if it only runs queries 6 hours/day)
- A Lakebase Serverless warehouse consuming 100 DBUs/day × $0.06 = $6/day × 30 days = $180/month

This 16× difference is the single largest driver of assessment savings projections for Snowflake-to-Lakebase migrations. The math changes if your warehouse is genuinely 24/7 busy (rare for analytics), but most warehouses have significant idle time.

## Reading your assessment cost estimate

Your assessment report shows:

```
Platform: Snowflake
Current monthly cost: $12,400
  - Compute (warehouses): $9,200
  - Storage: $1,800
  - Networking: $1,400

Lakebase projected monthly cost: $2,100
  - Compute (DBUs): $1,600  (100 DBUs/day × 30 × $0.06 × workload_scaling)
  - Storage: $480           (12 TB × $0.04/GB/mo)
  - Networking: $20         (same data, fewer reads from external services)

Estimated monthly savings: $10,300 (83%)
Confidence: High (6 months of history)
```

The compute projection is the most sensitive number. It is based on:
- Your **query volume** (queries/day from history)
- Your **average query runtime** (from history)
- A **DBU/query conversion factor** based on warehouse size and query complexity
- Your **workload type** (analytics queries use DBUs differently from high-concurrency point lookups)

## What affects actual vs. projected cost

**Things that make actuals lower than projected:**
- Lakebase query optimizer is more efficient than the historical baseline assumed
- Delta caching reduces repeated scans
- Serverless auto-scales down faster than assumed during off-peak hours

**Things that make actuals higher than projected:**
- Other teams start using the same warehouse (cost is shared, but total rises)
- Warehouse is over-provisioned for the actual workload
- Exploratory/ad-hoc queries run on the same warehouse as production
- Query rewrites were less efficient than the original

Monitor actuals using `system.billing.usage` and right-size monthly. Most teams save an additional 10–20% in the first 90 days through right-sizing alone.

## Tracking costs in production

```sql
-- Daily DBU and cost by warehouse
SELECT
  usage_date,
  warehouse_name,
  SUM(usage_quantity) AS total_dbus,
  SUM(usage_quantity * list_price) AS estimated_cost
FROM system.billing.usage
WHERE sku_name LIKE '%SERVERLESS_SQL%'
  AND usage_date >= CURRENT_DATE - INTERVAL 30 DAYS
GROUP BY usage_date, warehouse_name
ORDER BY usage_date DESC, estimated_cost DESC;

-- Total monthly cost comparison
SELECT
  DATE_FORMAT(usage_date, 'yyyy-MM') AS month,
  SUM(usage_quantity * list_price) AS monthly_cost
FROM system.billing.usage
WHERE usage_date >= '2026-01-01'
GROUP BY DATE_FORMAT(usage_date, 'yyyy-MM')
ORDER BY month;
```

## Committed use discounts

Databricks offers significant discounts for committed DBU consumption (pre-purchased DBU packages):

| Commitment | Typical discount |
| --- | --- |
| No commitment (pay-as-you-go) | List price |
| 1-year commit | 20–35% off list |
| 3-year commit | 35–50% off list |

If your assessment projections use list price and you plan to commit capacity, re-run the projection with your actual discount rate applied to DBU costs. This typically increases projected savings by an additional 10–25%.

## Related

- Compute layer: [Lakebase SQL](lakebase-sql.md)
- Storage: [Delta Lake](delta-lake.md)
- Monitoring costs after migration: [Measuring Migration Success](../after-the-engagement/measuring-success.md)
- Databricks pricing: [databricks.com/pricing](https://www.databricks.com/product/pricing)
