"""Workload classifier that maps scored workloads to Lakebase migration buckets."""

from typing import Any

# Lakebase fit classification buckets
BUCKET_ANALYTICS = "Analytics → Keep in Delta"
BUCKET_POINT_LOOKUPS = "Point Lookups → Migrate to Lakebase"
BUCKET_AGENT_STATE = "Agent State → Migrate to Lakebase"
BUCKET_APP_BACKENDS = "App Backends → Migrate to Lakebase"
BUCKET_FEATURE_SERVING = "Feature Serving → Migrate to Lakebase"
BUCKET_HEAVY_ETL = "Heavy ETL/UDF → Flag for refactoring first"
BUCKET_REALTIME = "Real-time Join/Agg → Lakebase + caching layer"


class WorkloadClassifier:
    """Classify workloads into Lakebase migration buckets."""

    def classify_all(self, scores: list[Any]) -> dict[str, list[dict[str, Any]]]:
        """Classify all workloads into buckets.

        Args:
            scores: List of WorkloadScore or dict with score data.

        Returns:
            Dict mapping bucket name to list of workload dicts.
        """
        buckets: dict[str, list[dict[str, Any]]] = {
            BUCKET_ANALYTICS: [],
            BUCKET_POINT_LOOKUPS: [],
            BUCKET_AGENT_STATE: [],
            BUCKET_APP_BACKENDS: [],
            BUCKET_FEATURE_SERVING: [],
            BUCKET_HEAVY_ETL: [],
            BUCKET_REALTIME: [],
        }

        for score in scores:
            # Handle both WorkloadScore dataclass and dict
            if hasattr(score, "classification"):
                classification = score.classification
                identifier = score.identifier
                adjusted = score.adjusted_score
                pain = score.pain
                biz = score.business_impact
                comp = score.complexity
            elif isinstance(score, dict):
                classification = score.get("classification", "Analytics")
                identifier = score.get("identifier", "unknown")
                adjusted = score.get("adjusted_score", 0)
                pain = score.get("pain", 1)
                biz = score.get("business_impact", 1)
                comp = score.get("complexity", 1)
            else:
                continue

            bucket = self._classify_one(identifier, classification, adjusted, pain, biz, comp)
            buckets[bucket].append({
                "identifier": identifier,
                "adjusted_score": adjusted,
                "pain": pain,
                "business_impact": biz,
                "complexity": comp,
                "original_classification": classification,
            })

        return buckets

    def classify_single(self, score: Any) -> str:
        """Classify a single workload into a bucket."""
        if hasattr(score, "classification"):
            return self._classify_one(
                score.identifier, score.classification,
                score.adjusted_score, score.pain,
                score.business_impact, score.complexity,
            )
        return BUCKET_ANALYTICS

    def _classify_one(
        self,
        identifier: str,
        classification: str,
        score: float,
        pain: int,
        business_impact: int,
        complexity: int,
    ) -> str:
        """Determine the Lakebase migration bucket for a workload."""

        # High complexity with UDF/stored procs → needs refactoring
        if complexity >= 4 and pain >= 3:
            return BUCKET_HEAVY_ETL

        # High business impact + real-time → Lakebase with caching
        if business_impact >= 4 and score >= 15:
            return BUCKET_REALTIME

        # Point lookups: low complexity, moderate pain
        if complexity <= 2 and pain >= 2:
            return BUCKET_POINT_LOOKUPS

        # Agent state: specific identifier patterns
        if "agent" in identifier.lower() or "state" in identifier.lower():
            return BUCKET_AGENT_STATE

        # App backends: identifier patterns
        if "app" in identifier.lower() or "backend" in identifier.lower() or "api" in identifier.lower():
            return BUCKET_APP_BACKENDS

        # Feature serving: identifier patterns
        if "feature" in identifier.lower() or "serve" in identifier.lower():
            return BUCKET_FEATURE_SERVING

        # Default: Analytics that stays in Delta (or migrate if score is high)
        if score >= 25:
            return BUCKET_APP_BACKENDS
        return BUCKET_ANALYTICS
