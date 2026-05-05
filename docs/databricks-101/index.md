# Databricks 101

New to Databricks? Start here. This section explains the five concepts you need to understand your Lakebase assessment and migration.

## The five concepts

| Concept | One sentence | Start here |
| --- | --- | --- |
| **[Lakebase SQL](lakebase-sql.md)** | The SQL engine on Databricks that replaces your legacy data warehouse | [Lakebase SQL](lakebase-sql.md) |
| **[Unity Catalog](unity-catalog.md)** | The single governance layer for all your data: tables, files, models | [Unity Catalog](unity-catalog.md) |
| **[Delta Lake](delta-lake.md)** | The open table format that stores your data in Databricks | [Delta Lake](delta-lake.md) |
| **[DBUs and Billing](dbus-and-billing.md)** | How Databricks charges for compute, and how to read your cost estimate | [DBUs and Billing](dbus-and-billing.md) |
| **[Governed Tags](governed-tags.md)** | How Databricks tracks domain ownership, PII, and classification | [Governed Tags](governed-tags.md) |

## How these concepts connect

```
                        Unity Catalog
                   (governance & access control)
                            │
              ┌─────────────┼─────────────┐
              │             │             │
         Delta Lake    Delta Lake    Delta Lake
          (tables)     (tables)      (files)
              │             │             │
         Lakebase SQL  Lakebase SQL  Notebooks
          (analytics)  (app backend)  (ML/Python)
              │
          SQL Warehouse
           (compute)
              │
       DBUs → Billing
```

Your data lives in Delta Lake tables, governed by Unity Catalog, queried by Lakebase SQL on a SQL Warehouse, billed in DBUs.

## The vocabulary shift

If you are coming from a specific platform, here is the translation:

| Your platform | Databricks equivalent |
| --- | --- |
| Snowflake Virtual Warehouse | SQL Warehouse |
| Snowflake Database / Schema | Unity Catalog Schema |
| BigQuery Project / Dataset | Unity Catalog Catalog / Schema |
| Redshift Cluster | SQL Warehouse |
| Oracle Database | Unity Catalog Catalog |
| SQL Server Database | Unity Catalog Catalog |
| Any table you own | Delta Lake table in Unity Catalog |

If you want the full vocabulary, the [Glossary](../glossary.md) has every term used in these docs.
