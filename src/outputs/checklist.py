"""Checklist markdown generator for migration implementation."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ChecklistGenerator:
    """Generate a migration implementation checklist in markdown."""

    def generate(
        self,
        scores: dict[str, list[Any]],
        buckets: dict[str, list[dict[str, Any]]],
        output_path: str,
    ) -> str:
        """Generate checklist markdown from assessment results."""
        lines: list[str] = []
        lines.append("# Lakebase Migration Implementation Checklist")
        lines.append("")
        lines.append("> Auto-generated from assessment results.")
        lines.append("")

        # Section 1: Priority 1 items
        priority_items: list[dict[str, Any]] = []
        for platform, platform_scores in scores.items():
            for s in platform_scores:
                priority = getattr(s, "priority", "Hold") if hasattr(s, "priority") else s.get("priority", "Hold")
                if priority == "Priority_1":
                    priority_items.append({
                        "platform": platform,
                        "identifier": getattr(s, "identifier", "") if hasattr(s, "identifier") else s.get("identifier", ""),
                        "score": getattr(s, "adjusted_score", 0) if hasattr(s, "adjusted_score") else s.get("adjusted_score", 0),
                    })

        if priority_items:
            lines.append("## Priority 1: High-Confidence Migration Targets")
            lines.append("")
            for item in priority_items:
                lines.append(f"- [ ] **{item['identifier']}** ({item['platform']}) — Score: {item['score']:.1f}")
            lines.append("")

        # Section 2: Migration buckets
        lines.append("## Migration Buckets")
        lines.append("")
        for bucket_name, items in buckets.items():
            if not items:
                continue
            lines.append(f"### {bucket_name}")
            lines.append("")
            for item in items:
                ident = item.get("identifier", "unknown")
                sc = item.get("adjusted_score", item.get("score", 0))
                lines.append(f"- [ ] `{ident}` (score: {sc:.1f})")
            lines.append("")

        # Section 3: Pre-migration steps
        lines.append("## Pre-Migration Checklist")
        lines.append("")
        lines.append("- [ ] Review data governance policies")
        lines.append("- [ ] Verify network connectivity to Databricks workspace")
        lines.append("- [ ] Set up Databricks Terraform provider or CLI")
        lines.append("- [ ] Configure Databricks SQL warehouse")
        lines.append("- [ ] Set up Delta Lake storage containers")
        lines.append("- [ ] Validate schema compatibility")
        lines.append("- [ ] Test query parity on a sample workload")
        lines.append("- [ ] Run benchmark comparison (current vs. Lakebase)")
        lines.append("- [ ] Document migration rollback plan")
        lines.append("")

        # Section 4: Post-migration validation
        lines.append("## Post-Migration Validation")
        lines.append("")
        lines.append("- [ ] Verify query results match source platform")
        lines.append("- [ ] Measure query latency improvement")
        lines.append("- [ ] Validate cost savings match estimates")
        lines.append("- [ ] Update monitoring and alerting")
        lines.append("- [ ] Train team on Databricks SQL tooling")
        lines.append("- [ ] Decommission legacy infrastructure")
        lines.append("")

        # Section 5: Platform-specific notes
        lines.append("## Platform-Specific Notes")
        lines.append("")
        for platform, delta_items in scores.items():
            has_udf = any(
                getattr(s, "classification", "") == "Heavy ETL/UDF" if hasattr(s, "classification")
                else s.get("classification", "") == "Heavy ETL/UDF"
                for s in delta_items
            )
            if has_udf:
                lines.append(f"### {platform}")
                lines.append("")
                lines.append("- [ ] **UDF Refactoring Required**: Migrate stored procedures to Databricks UDFs or Spark SQL")
                lines.append("- [ ] Review and rewrite complex joins for Delta optimization")
                lines.append("- [ ] Test with Delta Lake format (Z-ordering, OPTIMIZE, VACUUM)")
                lines.append("")

        content = "\n".join(lines)
        p = Path(output_path)
        with open(p, "w") as f:
            f.write(content)
        return str(p)
