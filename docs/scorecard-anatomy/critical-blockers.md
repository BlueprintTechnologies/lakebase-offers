# Critical Blockers

Critical blockers are issues that **prevent a workload from migrating regardless of its Opportunity Score**. A workload can score 90 and still be blocked. Blockers must be resolved before the migration sprint begins.

The assessor flags blockers separately from scoring so they surface cleanly on the engineer page and in the blocker summary — a high-scoring workload with a critical blocker is still a Priority 1 migration, just with a prerequisite step.

## The blocker hierarchy

| Severity | What it means | Typical resolution time |
| --- | --- | --- |
| **Critical** | Migration cannot proceed at all until this is resolved | 1–4 weeks |
| **High** | Migration is possible but risky without resolution; strong recommendation to resolve first | 1–2 weeks |
| **Medium** | Manageable during the migration sprint with careful testing | Days |
| **Low** | Informational. Will not block migration. | Hours |

## Critical blocker catalog

### Compliance gating

**What it is:** A regulatory or policy requirement mandates additional review before data can be migrated to a new platform. Common in financial services (SOX, FINRA), healthcare (HIPAA), and public sector (FedRAMP, StateRAMP).

**How it is detected:** Metadata flags from the assessor's security scan, or customer input during the tech champion interview.

**Resolution:** Work with your compliance team to document the Databricks/Unity Catalog controls that satisfy the regulatory requirement. Databricks holds SOC 2, ISO 27001, HIPAA, PCI-DSS, and FedRAMP certifications. See [Security and Compliance](../security-and-compliance.md) for the full control mapping.

**Typical timeline:** 2–4 weeks for a standard compliance review. Faster if your Databricks workspace is already approved for the data classification in question.

---

### PII without masking

**What it is:** A table contains personally identifiable information (PII) and does not have column-level masking configured. Migrating unmasked PII to a new platform requires prior approval in most organizations.

**How it is detected:** The assessor's privacy scan flags column names and data patterns consistent with PII (email, SSN, phone, date of birth, etc.).

**Resolution:** Apply Unity Catalog column masks to the affected columns before migration. The mask can return a redacted or tokenized value for non-privileged users. See [Compliance & Governance](../trust-foundations/compliance.md).

**Typical timeline:** 1–2 days per table with Unity Catalog access.

---

### Unsupported data type

**What it is:** The source platform uses a data type that has no direct Delta Lake equivalent and requires explicit conversion logic.

**How it is detected:** The SQL compatibility scan in the assessor.

**Common cases:**

| Source type | Resolution |
| --- | --- |
| Oracle `XMLTYPE` | Convert to `STRING` and parse with Databricks XML functions |
| Oracle `BLOB` / `RAW` | Convert to `BINARY` in Delta; validate downstream consumers |
| Snowflake `GEOGRAPHY` | Convert to `STRUCT<lat DOUBLE, lon DOUBLE>` or use Databricks spatial functions |
| SQL Server `UNIQUEIDENTIFIER` | Cast to `STRING` |
| Teradata `BYTEINT` | Cast to `TINYINT` |
| Custom serialized formats | Binary format conversion required; High effort |

**Typical timeline:** Low–Medium effort per column. Batch the conversions for all affected tables before the migration sprint.

---

### Custom binary serialization

**What it is:** The workload relies on binary-serialized data stored in the source platform (Avro, Protobuf, custom formats in BLOB columns). Delta Lake stores data in Parquet; binary blobs must be deserialized and re-stored.

**How it is detected:** Column type scan + content sampling.

**Resolution:** Write a one-time conversion job (Spark) to deserialize the binary column and write the structured output to Delta. This is typically a Medium-effort task but is listed as Critical because it must complete before any downstream migration can proceed.

---

### Missing source access

**What it is:** The assessor could not connect to one or more source platforms, so those workloads were not assessed. Any migration plan is incomplete if workloads are missing.

**How it is detected:** Connection failure in the assessor run log.

**Resolution:** Re-provision credentials and re-run the assessment for the missing platform. Your account executive can guide credential scoping.

---

### Deprecated or sunset workload

**What it is:** During the tech champion interview, a workload was identified as planned for retirement. Migrating a workload that will be shut down in 6 months has negative ROI.

**How it is detected:** Customer input during tech champion interview.

**Resolution:** Remove from migration scope. If retirement date is uncertain, keep in the Evaluate bucket and revisit after the retirement decision is made.

## What to do when you have critical blockers

1. **Identify the owner.** Compliance and PII blockers go to the data governance team. SQL type blockers go to data engineering. Missing access goes to the platform/DBA team.
2. **Scope the resolution.** Most critical blockers take 1–4 weeks to resolve. Include blocker resolution in your PoC timeline.
3. **Do not skip blockers.** Migrating a workload with an unresolved critical blocker typically results in compliance findings, data loss, or downstream failures. The extra week upfront is cheaper than the incident response.
4. **Re-run the assessment** after resolving blockers to confirm the flag is cleared.

## Related

- For engineers closing blockers: [For Engineers](../reading-your-readout/engineer.md)
- Trust Foundations for compliance and PII: [Compliance & Governance](../trust-foundations/compliance.md)
- SQL type compatibility: [SQL Compatibility Check](../trust-foundations/sql-compatibility.md)
- Security overview: [Security and Compliance](../security-and-compliance.md)
