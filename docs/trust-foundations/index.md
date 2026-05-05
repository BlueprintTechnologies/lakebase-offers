# Trust Foundations

Trust Foundations are the five preparation steps that reduce migration risk and ensure your Lakebase deployment is reliable, secure, and governable from day one.

These playbooks are not migration steps — they are **pre-migration** steps. Each one closes a class of blockers or complexity drivers that would otherwise slow the migration sprint or introduce post-migration incidents.

## The five foundations

| Foundation | What it closes | Effort |
| --- | --- | --- |
| [Data Inventory & Schema Docs](data-inventory.md) | Missing metadata, undocumented schemas, unknown data owners | Medium (2–5 days) |
| [Access Control Review](access-control.md) | ACL mismatches, over-privileged accounts, ungoverned service accounts | Medium (1–3 days) |
| [Data Quality Baseline](data-quality.md) | Null handling differences, type coercion, duplicate key behavior | Medium (2–4 days) |
| [Compliance & Governance](compliance.md) | PII masking, HIPAA/SOX gating, audit trail requirements | Variable (1–4 weeks) |
| [SQL Compatibility Check](sql-compatibility.md) | Proprietary functions, unsupported syntax, UDF dependencies | Low–High (hours to weeks) |

## When to run these

Run Trust Foundations in parallel with, or just before, your migration sprint — not weeks before. The foundations are most valuable when they are directly feeding a known migration scope.

**Recommended sequence:**

```
1. Run the assessment (lakebase-assess)
2. Identify PoC workloads (Priority 1, low or no blockers)
3. For each PoC workload, complete the relevant Trust Foundations:
   - SQL Compatibility Check (always)
   - Access Control Review (always)
   - Compliance & Governance (if PII or regulatory flags exist)
   - Data Inventory (if documentation is sparse)
   - Data Quality Baseline (if the workload is data-critical)
4. Begin migration sprint
```

You do not need to complete all five foundations for every workload. Apply the ones that address the blockers shown on the engineer page.

## Who does this work

| Foundation | Primary owner | Supporting role |
| --- | --- | --- |
| Data Inventory & Schema Docs | Data engineer or analyst | Data owner |
| Access Control Review | Platform admin or data engineer | Security team |
| Data Quality Baseline | Data engineer | QA or analytics |
| Compliance & Governance | Data governance team | Legal / compliance |
| SQL Compatibility Check | Data engineer | DBA |

## What to do when you are stuck

If a Trust Foundation is blocked (e.g., you cannot get a compliance decision in time for the PoC), two options:

1. **Scope the PoC around the blocker.** Choose a different workload that does not trigger the blocking foundation.
2. **Run the PoC in a dev environment.** Demonstrate migration on synthetic data while compliance review completes, then cut over production after approval.

Blueprint can advise on either path during the Free+ engagement.
