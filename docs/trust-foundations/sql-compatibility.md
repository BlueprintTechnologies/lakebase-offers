# SQL Compatibility Check

The SQL compatibility check is the most important pre-migration step for engineers. It tells you exactly which queries need rewriting and how much effort each rewrite will take before the migration sprint begins.

## What this foundation closes

- Proprietary SQL functions with no direct Lakebase equivalent
- Unsupported syntax that will cause query failures on Lakebase
- Data type mismatches that produce incorrect results silently
- UDF and stored procedure dependencies that require rewrites

## Running the compatibility check

The `lakebase-assess` CLI includes a compatibility scanner you can run on demand:

```bash
lakebase-assess validate \
  --config my-assessment.yaml \
  --output-dir ./compat-output
```

This produces `compat-report.csv` with one row per flagged query, including:
- Severity (Critical / High / Medium / Low)
- Flag type (unsupported function, syntax, type mismatch, UDF dependency)
- Specific expression flagged
- Suggested Databricks SQL equivalent

## Function compatibility reference

### Snowflake → Databricks SQL

| Snowflake | Databricks SQL | Notes |
| --- | --- | --- |
| `FLATTEN(array_col)` | `EXPLODE(array_col)` or `LATERAL VIEW EXPLODE` | Direct equivalent |
| `PARSE_JSON(str)` | `FROM_JSON(str, schema)` | Must provide schema |
| `GET(obj, key)` | `obj:key` (colon notation) or `GET_JSON_OBJECT` | JSON path syntax differs |
| `ARRAY_SIZE(arr)` | `SIZE(arr)` | Direct equivalent |
| `OBJECT_CONSTRUCT(k,v,...)` | `NAMED_STRUCT(k,v,...)` or `MAP(k,v,...)` | Use MAP for dynamic keys |
| `ZEROIFNULL(col)` | `COALESCE(col, 0)` | Direct equivalent |
| `IFF(cond, t, f)` | `IF(cond, t, f)` | Direct equivalent |
| `QUALIFY ROW_NUMBER() OVER ... = 1` | Subquery with `WHERE rn = 1` | QUALIFY not supported; use subquery |
| `DATEADD(day, N, date)` | `DATE_ADD(date, N)` or `date + INTERVAL N DAYS` | Syntax differs |
| `DATEDIFF(day, d1, d2)` | `DATEDIFF(d2, d1)` | Argument order reversed |
| `LISTAGG(col, delim)` | `ARRAY_JOIN(COLLECT_LIST(col), delim)` | Two-function equivalent |
| `RATIO_TO_REPORT(col) OVER (...)` | `col / SUM(col) OVER (...)` | Manual calculation |

### BigQuery → Databricks SQL

| BigQuery | Databricks SQL | Notes |
| --- | --- | --- |
| `ARRAY_AGG(x IGNORE NULLS)` | `COLLECT_LIST(x)` (NULLs already excluded) | Direct equivalent |
| `COUNTIF(condition)` | `COUNT_IF(condition)` or `SUM(IF(condition,1,0))` | Both work |
| `DATE_DIFF(d1, d2, DAY)` | `DATEDIFF(d1, d2)` | Arg order differs; check sign |
| `GENERATE_DATE_ARRAY(start, end, INTERVAL N DAY)` | `SEQUENCE(start, end, INTERVAL N DAYS)` | Sequence function |
| `REGEXP_EXTRACT(str, re)` | `REGEXP_EXTRACT(str, re)` | Same |
| `STRING_AGG(col, delim)` | `ARRAY_JOIN(COLLECT_LIST(col), delim)` | Two-function equivalent |
| `FARM_FINGERPRINT(val)` | `HASH(val)` or `xxhash64(val)` | Different hash algorithm |
| `SAFE_DIVIDE(a, b)` | `a / NULLIF(b, 0)` | Direct equivalent |
| `STRUCT(fields...)` | `NAMED_STRUCT(fields...)` | Same semantics, different syntax |
| `UNNEST(array)` | `EXPLODE(array)` or `LATERAL VIEW EXPLODE` | Direct equivalent |

### Oracle / Teradata → Databricks SQL

| Oracle / Teradata | Databricks SQL | Notes |
| --- | --- | --- |
| `NVL(col, val)` | `COALESCE(col, val)` | Direct equivalent |
| `DECODE(col, v1, r1, v2, r2, default)` | `CASE WHEN col=v1 THEN r1 WHEN col=v2 THEN r2 ELSE default END` | CASE expression |
| `ROWNUM` | `ROW_NUMBER() OVER (ORDER BY ...)` | Window function |
| `CONNECT BY` (hierarchical) | Recursive CTE (`WITH RECURSIVE`) | Supported in Databricks SQL |
| `MERGE` | `MERGE INTO` | Syntax is similar; verify ON clause |
| `TO_DATE(str, fmt)` | `TO_DATE(str, fmt)` | Same; verify format string tokens |
| `TO_CHAR(num, fmt)` | `FORMAT_NUMBER(num, fmt)` or `CAST(num AS STRING)` | Depends on use case |
| `SYSDATE` | `CURRENT_DATE` or `CURRENT_TIMESTAMP` | Standard SQL equivalent |
| `DUAL` (Oracle) | Not needed; `SELECT 1` works | Dummy table not required |
| `VARCHAR2` | `STRING` | Type mapping |
| `NUMBER(p,s)` | `DECIMAL(p,s)` | Direct equivalent |
| `DATE` (includes time in Oracle) | `TIMESTAMP` | Oracle DATE stores time; map to TIMESTAMP |

### Redshift → Databricks SQL

| Redshift | Databricks SQL | Notes |
| --- | --- | --- |
| `GETDATE()` | `CURRENT_TIMESTAMP` | Standard SQL equivalent |
| `DATEADD(unit, n, date)` | `DATEADD(unit, n, date)` | Same syntax |
| `DATEDIFF(unit, d1, d2)` | `DATEDIFF(d2, d1)` | Check arg order |
| `NVL(col, val)` | `COALESCE(col, val)` | Direct equivalent |
| `LISTAGG(col, delim) WITHIN GROUP (ORDER BY ...)` | `ARRAY_JOIN(COLLECT_LIST(col), delim)` | ORDER inside not yet supported; result order may differ |
| `APPROXIMATE COUNT DISTINCT` | `APPROX_COUNT_DISTINCT(col)` | Same semantics |
| `SUPER` (semi-structured) | `VARIANT` or `STRING` with JSON functions | Map to STRING + `FROM_JSON` |
| `COPY FROM S3` | `COPY INTO` or `read_files()` | Syntax differs; both work for bulk load |

## UDF and stored procedure migration

### Python UDFs

Python UDFs from Snowflake and BigQuery translate directly to Databricks Python UDFs:

```python
# Register a Python UDF in Databricks
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

@udf(StringType())
def normalize_phone(phone):
    import re
    return re.sub(r'\D', '', phone or '')

spark.udf.register("normalize_phone", normalize_phone)
```

### SQL scalar UDFs

```sql
-- Create a Databricks SQL UDF
CREATE OR REPLACE FUNCTION catalog.schema.fiscal_quarter(d DATE)
  RETURNS INT
  RETURN CASE
    WHEN MONTH(d) IN (1, 2, 3) THEN 1
    WHEN MONTH(d) IN (4, 5, 6) THEN 2
    WHEN MONTH(d) IN (7, 8, 9) THEN 3
    ELSE 4
  END;
```

### Oracle PL/SQL / T-SQL stored procedures

Stored procedures have no direct equivalent in Databricks SQL. The migration path:

1. **Decompose:** Break the stored procedure into discrete SQL statements
2. **Rewrite:** Each statement becomes a Databricks SQL query or a Python function
3. **Orchestrate:** Use a Databricks Workflow (DAG) to sequence the steps
4. **Test:** Validate input/output parity with the original procedure

Effort is High (1–4 weeks per complex procedure). This is the primary driver of Heavy ETL classification.

## What to do when you find a High-severity flag

1. Open [Databricks SQL Reference](https://docs.databricks.com/en/sql/language-manual/index.html) and find the equivalent
2. Rewrite the expression in the compatibility report
3. Run the rewritten query against a sample of data on Lakebase
4. Add a test case to your regression suite with expected output
5. Close the flag in the compatibility report

If no equivalent exists (rare), raise it with your account executive. Blueprint tracks unsupported functions across customers and feeds them to the Databricks product team.

## Related

- Complexity scoring (UDF depth is a key input): [Complexity](../scorecard-anatomy/03-complexity.md)
- Heavy ETL migration path: [Heavy ETL — Refactor First](../migration-playbooks/heavy-etl.md)
- Databricks SQL Language Reference: [docs.databricks.com/en/sql/language-manual](https://docs.databricks.com/en/sql/language-manual/index.html)
