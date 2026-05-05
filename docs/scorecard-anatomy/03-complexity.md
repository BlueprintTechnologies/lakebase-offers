# Complexity — How Hard Is the Move?

**Outcome question:** *How much work does it take to migrate this workload to Lakebase?*

Complexity is the denominator of the opportunity score. It tempers how attractive a migration looks. A very painful, very important workload can still score low if it requires months of refactoring to move safely.

## What the assessor measures

| Signal | How it is collected | What high means |
| --- | --- | --- |
| **SQL dialect compatibility** | Query text sampling + function inventory | Many proprietary functions that need rewriting |
| **UDF / stored procedure depth** | Count and complexity of user-defined functions | High rewrite effort before migration is possible |
| **Join complexity** | Max tables per query, join depth, self-joins | Complex query patterns that may need tuning |
| **Data type alignment** | Source types vs. Delta type system | Type mapping required (VARIANT→STRUCT, custom types) |
| **Schema complexity** | Table count, foreign key depth, denormalization | Schema redesign risk |
| **Write pattern** | Read/write ratio, UPDATE/DELETE frequency | High-write OLTP patterns may need caching design |
| **Third-party tool dependency** | BI tools, ETL frameworks, custom connectors | Connection string updates and tool re-testing |
| **Compliance constraints** | PII, PHI, HIPAA, PCI flags in metadata | Pre-migration governance work required |

Complexity is normalized to a 1–10 scale:

| Score | What it looks like |
| --- | --- |
| **1–3** | Simple SELECT queries. Standard SQL. No UDFs. Small schema. Direct compatibility. |
| **4–6** | Multi-table joins. Some proprietary syntax. Moderate UDFs. Minor tuning needed. |
| **7–9** | Heavy stored procedures. Oracle PL/SQL or T-SQL specifics. Large schema with custom types. |
| **10** | Custom binary serialization. Embedded ML. Non-SQL compute logic. Fundamental redesign required. |

## Why Complexity is the denominator

In the formula `(Pain × Business_Impact) / Complexity`, high complexity penalizes the score proportionally. A workload that scores 80 on pain and impact but has complexity 8 will score 100 — still strong. The same workload with complexity 10 scores 80. That difference is meaningful: it moves a workload from Priority 1 to Evaluate.

This is intentional. The score reflects migration confidence, not just desirability. A workload you desperately want to migrate but cannot safely execute in < 12 weeks belongs in Evaluate until you have resolved the complexity.

## Common complexity drivers and their resolutions

### Proprietary SQL functions

Every platform has functions that do not exist in standard SQL. The assessor flags these:

| Source Function | Lakebase Equivalent | Effort |
| --- | --- | --- |
| Snowflake `FLATTEN()` | `EXPLODE()` or `LATERAL VIEW EXPLODE` | Low |
| Snowflake `PARSE_JSON()` | `FROM_JSON()` | Low |
| BigQuery `ARRAY_AGG()` | `COLLECT_LIST()` | Low |
| Oracle `NVL()` | `COALESCE()` | Low |
| Oracle `CONNECT BY` (hierarchical) | Recursive CTE or `graphframes` | Medium |
| SQL Server `CROSS APPLY` | `LATERAL JOIN` | Low–Medium |
| Teradata `QUALIFY` window filter | Subquery with `WHERE ROW_NUMBER()` | Medium |
| Oracle PL/SQL block | Python UDF or Databricks notebook | High |
| T-SQL stored procedure | Databricks workflow + SQL | High |

The [SQL Compatibility Check](../trust-foundations/sql-compatibility.md) playbook walks through the full inventory and rewrite patterns.

### UDFs and stored procedures

UDFs written in Python or standard SQL translate with low effort. UDFs written in PL/SQL, T-SQL, or Java require full rewrites and are the most common source of High complexity scores.

**Approach:** Inventory all UDFs called by Priority 1 workloads. If a UDF can be replaced by a Databricks built-in function, it is Low effort. If it requires a Python rewrite, it is Medium. If it requires custom JVM code or embedded ML, it is High.

### Schema complexity

Deeply normalized schemas (6+ join depth) or schemas with hundreds of foreign key relationships translate to Lakebase with low friction — Delta Lake handles relational schemas well. The effort is in testing join correctness after migration, not in schema redesign.

Schemas with custom serialization (BLOB, XML, binary), proprietary partitioning schemes, or materialized views with business logic embedded in them require redesign before migration.

### Write-heavy OLTP patterns

Lakebase SQL handles writes, but OLTP patterns optimized for high-volume single-row updates (UPDATE WHERE pk=X at 10K/sec) need a caching layer or connection pooling design. The assessor flags workloads where write frequency exceeds the analytics-optimized threshold. See [App Backends](../migration-playbooks/app-backends.md) and [Point Lookups + Cache](../migration-playbooks/point-lookups.md).

## Reducing complexity before the PoC

If a workload's complexity is blocking its migration, two paths reduce it:

1. **Scope reduction.** Migrate a subset of the workload first — the read-only queries, the non-UDF reporting layer, the lowest-traffic schemas. Validate those, then tackle the complex remainder.
2. **Pre-migration refactoring.** Rewrite UDFs, resolve proprietary functions, and simplify schema before the Lakebase migration sprint. This adds time upfront but significantly de-risks the migration and often improves the workload on the current platform in the interim.

Blueprint can scope a pre-migration refactoring sprint as part of the Free+ engagement.

## Related

- Scoring formula: [Anatomy of Your Scorecard](index.md)
- SQL function rewrite guide: [SQL Compatibility Check](../trust-foundations/sql-compatibility.md)
- High-complexity playbook: [Heavy ETL — Refactor First](../migration-playbooks/heavy-etl.md)
- For engineers executing the migration: [For Engineers](../reading-your-readout/engineer.md)
