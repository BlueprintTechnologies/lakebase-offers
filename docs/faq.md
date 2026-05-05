# FAQ

Frequently asked questions about the Lakebase Assessment and migration engagement.

## Assessment

**Q: How long does the assessment take?**

The tool runs in 1–4 hours depending on the number of tables, query history size, and network latency to the source platform. The full assessment engagement (setup → tool run → readout) is typically 1–3 weeks. The assessor output is a scorecard report; the readout meeting is where Blueprint presents findings and recommendations.

---

**Q: What credentials does the assessor need? Does it write anything to our database?**

The assessor is read-only. It requires:
- `SELECT` on all tables in scope
- Access to query history metadata (varies by platform — see [ACCELERATOR.md](../ACCELERATOR.md) for per-platform minimum grants)
- No `INSERT`, `UPDATE`, `DELETE`, or DDL permissions are needed or used

---

**Q: Does the assessor send our data to Blueprint or Databricks?**

No raw data leaves your environment. The assessor collects metadata (table names, column names, data types, row counts, query patterns) and schema samples. The optional BPCS aggregation upload is anonymized and requires explicit opt-in via `bpcs_upload: true` in your config. See the BPCS section in [ACCELERATOR.md](../ACCELERATOR.md).

---

**Q: Can I run the assessor against multiple source platforms?**

Yes. Each platform is a separate entry in your `config.yaml`. Run them sequentially or in parallel. The final scorecard aggregates workloads across all sources.

---

**Q: The assessor connected but discovered 0 tables. What's wrong?**

Check the `schemas:` filter in your config — if it's set, it must match existing schema names exactly. Remove the filter to discover all accessible schemas. Also verify the user has `SELECT` grants on at least one table. See [Troubleshooting](troubleshooting.md#assessment-runs-but-0-tables-are-discovered).

---

## Scoring

**Q: A workload I consider business-critical scored low. Why?**

The score measures migration ROI, not business importance. A critical workload with high complexity (many stored procedures, proprietary UDFs, binary formats) will score low because migration is expensive relative to the benefit. Low-scoring workloads are not abandoned — they're sequenced after Priority 1 workloads or flagged for a "Refactor First" approach.

---

**Q: One workload scored 30 but it's tiny. Another scored 12 but it's huge. Which do we migrate first?**

Migrate the 30 first. The score already accounts for business impact — a higher score on a smaller workload means the pain/impact ratio is better for that workload. The 12-score workload will have its turn in Wave 2.

---

**Q: Can we re-run the assessment after we fix some issues?**

Yes, and it's recommended. After resolving SQL compatibility flags or reducing complexity, re-run the assessor to confirm the score improvement and update the scorecard. The assessment is designed to be run periodically, not once.

---

## Migration

**Q: Do we have to take our application offline during migration?**

No. The standard approach is a parallel run: both the source platform and Lakebase run simultaneously, with CDC sync keeping them in sync. The cutover is a connection string change, not a downtime event. App backends typically achieve cutover in < 5 minutes. Analytics workloads have no cutover — dashboards are just re-pointed to the new warehouse.

---

**Q: What happens if the migrated workload doesn't meet our SLA?**

The source platform stays live until the 72-hour monitoring window passes with error rate < 0.1% and latency within SLA. If SLA isn't met, you don't cut over — you tune (OPTIMIZE, Z-order, scale warehouse) and re-test. The PoC de-risks this: if the PoC can't meet SLA, the Phase 2 engagement is redesigned before you've committed to migration.

---

**Q: How do Delta foreign keys work? Are they enforced?**

Delta foreign keys are informational only — they document the relationship for tools and humans, but Delta Lake does not enforce them on write. Your application must enforce referential integrity. This is a common "gotcha" for teams coming from Oracle or SQL Server where FK enforcement is the default. See [App Backends — Step 1](migration-playbooks/app-backends.md#step-1-schema-migration-with-constraints).

---

**Q: We use stored procedures extensively. Can Databricks SQL run them?**

Not directly — Databricks SQL doesn't execute procedural stored procedure blocks (PL/SQL, T-SQL procedural extensions, etc.). The migration path is to rewrite stored procedures as:
- Databricks Notebooks (for complex logic)
- Databricks Workflows (for orchestration)
- Python UDFs (for custom functions)

See [Heavy ETL — Refactor First](migration-playbooks/heavy-etl.md) for the full approach.

---

**Q: What SQL dialect does Lakebase use?**

Databricks SQL is ANSI SQL-compliant with extensions. Most standard DML (SELECT, INSERT, UPDATE, DELETE, MERGE, GROUP BY, window functions, CTEs) works without change. Platform-specific functions (DATEADD, IIFF, NVL, ROWNUM) need translation. See [SQL Compatibility Check](trust-foundations/sql-compatibility.md) for function-by-function mapping.

---

**Q: We're on BigQuery. Can we use Delta external tables to query BigQuery data without migrating?**

Delta Lake tables must store data in cloud object storage (S3, ADLS, GCS) — they don't federate queries to BigQuery natively. However, Databricks Lakeflow Connect can sync BigQuery tables to Delta incrementally, so you can query a Delta copy of your BigQuery data from Lakebase. For pure federation without copying, consider Databricks Lakehouse Federation (query-only, no write-back).

---

## Access and security

**Q: Can we restrict analysts to only see data for their region?**

Yes — use Unity Catalog row filters. A filter function can check `current_user()` or group membership and restrict visible rows accordingly. See [Access Control Review](trust-foundations/access-control.md#row-filters) and [Security & Compliance](security-and-compliance.md#row-level-security-row-filters).

---

**Q: We have GDPR right-to-delete requirements. How does Delta time travel interact with that?**

Deleted rows remain in Delta's historical versions until VACUUM runs. To immediately purge a deleted row from storage (required for GDPR in some interpretations), run `VACUUM table RETAIN 0 HOURS` after the DELETE. This disables time travel for that data. Coordinate with your legal/compliance team on whether the retention window (7 days by default) is acceptable before purge. See [Security & Compliance — GDPR](security-and-compliance.md#gdpr--ccpa-right-to-delete).

---

**Q: Does the assessor run as a Databricks job, or on our own machine?**

The assessor runs locally (or on any compute you control — a VM, container, or CI runner). It doesn't require a Databricks workspace to run the assessment itself. It does require network access to the source platform. The output (JSON/HTML/PDF) is generated locally and shared as a file.

---

## Cost

**Q: How much does Lakebase cost compared to our current platform?**

It depends on your workload pattern. The assessor's cost delta calculation uses the source platform's list price and your workload's DBU estimate. As a rough benchmark: analytics workloads typically cost 60–80% less on Databricks Serverless warehouses vs. Snowflake or BigQuery. App backends on Pro warehouses are typically 40–60% less than equivalent RDS or Aurora instances. See [DBUs and Billing](databricks-101/dbus-and-billing.md) for the math.

---

**Q: What does the Free Assessment include? What's in Free+?**

**Free Assessment (0 cost to customer):**
- Assessor tool run and configuration assistance
- Scored scorecard report (all workloads)
- Readout meeting with findings and recommendations
- 30/60/90 day migration plan

**Free+ PoC (0 cost to customer, up to $25K in Blueprint delivery hours):**
- One Priority 1 workload migrated end-to-end to Lakebase
- Performance benchmark report (P50/P95/P99 latency vs. source)
- Cost validation (projected vs. actual DBU consumption)
- Go/no-go recommendation for Phase 2

See [05-free-plus-offer-terms.md](../lakebase-assess/README.md) for full offer terms.

---

**Q: What does Phase 2 cost?**

Phase 2 is a custom statement of work. Typical range: $40K–$150K depending on number of workloads, complexity, and team augmentation needs. The PoC gives you a proven basis for scoping the Phase 2 estimate accurately.

---

## Technical

**Q: What Python version does the assessor require?**

Python 3.9 or higher. The `databricks-sql-connector`, `pyspark`, and platform-specific packages (snowflake-connector-python, google-cloud-bigquery, etc.) are installed via `pip install lakebase-assess[<platform>]`.

---

**Q: Can we run the assessor in a Docker container?**

Yes. A Dockerfile is included in the repo. Build with `docker build -t lakebase-assess .` and run with volume mounts for config and output:
```bash
docker run -v $(pwd)/config.yaml:/app/config.yaml \
           -v $(pwd)/output:/app/output \
           lakebase-assess run --config /app/config.yaml
```

---

**Q: We're on Databricks but not using Lakebase. Is this tool still relevant?**

Yes — the assessor can score existing Databricks workloads (using the `databricks` connector) for optimization opportunities: right-sizing warehouses, enabling Photon, converting to Serverless, applying OPTIMIZE/ZORDER, and identifying UDFs that could be rewritten for better performance. The workload classifications still apply.

---

**Q: Where is the source code? Can we contribute?**

The source code is in [`lakebase-assess/src/`](../lakebase-assess/). The project is licensed under Blueprint BSL 1.1 (source-available). Contributions from Blueprint customers and partners are welcome via pull request; open an issue first to discuss the change.
