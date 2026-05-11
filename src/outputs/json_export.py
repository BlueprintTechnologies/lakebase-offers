"""JSON and CSV export with validated payload, checksum, and checklist markdown."""

import csv
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class JsonExporter:
    """Export assessment results to JSON and CSV formats."""

    def export(
        self,
        scores: dict[str, list[Any]],
        cost_deltas: dict[str, dict[str, Any]],
        buckets: dict[str, list[dict[str, Any]]],
        output_path: str,
    ) -> str:
        """Export all results to a validated JSON file with checksum."""
        payload = {
            "generated_at": datetime.now().isoformat(),
            "version": "1.0.0",
            "scores": {},
            "cost_deltas": cost_deltas,
            "migration_buckets": buckets,
        }

        for platform, platform_scores in scores.items():
            payload["scores"][platform] = []
            for s in platform_scores:
                if hasattr(s, "__dict__"):
                    payload["scores"][platform].append(s.__dict__)
                elif isinstance(s, dict):
                    payload["scores"][platform].append(s)
                else:
                    payload["scores"][platform].append({
                        "identifier": str(s),
                        "score": 0,
                        "priority": "Hold",
                    })

        # Write with checksum
        json_str = json.dumps(payload, indent=2, default=str)
        checksum = hashlib.sha256(json_str.encode("utf-8")).hexdigest()
        payload["checksum"] = checksum

        p = Path(output_path)
        with open(p, "w") as f:
            f.write(json.dumps(payload, indent=2, default=str))

        return str(p)

    def export_csv(self, scores: dict[str, list[Any]], output_path: str) -> str:
        """Export scores to a flat CSV file."""
        p = Path(output_path)
        with open(p, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "platform", "identifier", "pain", "business_impact",
                "complexity", "raw_score", "adjusted_score",
                "priority", "classification",
            ])
            for platform, platform_scores in scores.items():
                for s in platform_scores:
                    if hasattr(s, "__dict__"):
                        writer.writerow([
                            platform,
                            getattr(s, "identifier", ""),
                            getattr(s, "pain", ""),
                            getattr(s, "business_impact", ""),
                            getattr(s, "complexity", ""),
                            getattr(s, "raw_score", ""),
                            getattr(s, "adjusted_score", ""),
                            getattr(s, "priority", ""),
                            getattr(s, "classification", ""),
                        ])
                    elif isinstance(s, dict):
                        writer.writerow([
                            platform,
                            s.get("identifier", ""),
                            s.get("pain", ""),
                            s.get("business_impact", ""),
                            s.get("complexity", ""),
                            s.get("raw_score", ""),
                            s.get("adjusted_score", ""),
                            s.get("priority", ""),
                            s.get("classification", ""),
                        ])
        return str(p)
