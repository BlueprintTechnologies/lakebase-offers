"""Lakebase Opportunity Score engine with exact formula and threshold logic."""

import logging
from dataclasses import dataclass
from typing import Any, Optional

from src.models.assessment_payload import AssessmentPayload

logger = logging.getLogger(__name__)


@dataclass
class WorkloadScore:
    """Score result for a single workload/identifier."""

    identifier: str
    pain: int
    business_impact: int
    complexity: int
    raw_score: float
    adjusted_score: float
    classification: str
    recommendation: str
    priority: str  # "Priority_1" | "Evaluate" | "Hold"


@dataclass
class ScoreSummary:
    """Aggregated scoring summary for a platform."""

    platform: str
    total_workloads: int
    priority_1_count: int
    evaluate_count: int
    hold_count: int
    avg_score: float
    max_score: float
    min_score: float
    median_score: float


class ScoreEngine:
    """Compute the Lakebase Opportunity Score for workloads.

    Formula:
        Score = ((Pain × Business_Impact) / Complexity) × 10
        Adjusted_Score = Score × (1 + (est_savings_pct / 100))

    Thresholds:
        < 10:  Hold. Optimize first.
        10-20: Evaluate. Safe for PoC.
        >= 25: Priority 1. High confidence migration.
    """

    def __init__(
        self,
        threshold: float = 10.0,
        savings_pct: float = 0.0,
    ) -> None:
        self.threshold = threshold
        self._savings_pct = savings_pct

    def score_payload(self, payload: AssessmentPayload) -> list[WorkloadScore]:
        """Score all workloads in a payload and return a list of results."""
        results: list[WorkloadScore] = []

        for query in payload.query_history.queries:
            score = self._compute_workload_score(query, payload)
            results.append(score)

        # If no queries, score the platform as a whole
        if not results:
            score = self._score_platform(payload)
            results.append(score)

        return results

    def _compute_workload_score(self, query, payload: AssessmentPayload) -> WorkloadScore:
        """Compute the Lakebase Opportunity Score for a single workload."""
        pain = self._compute_pain(query, payload)
        business_impact = self._compute_business_impact(query, payload)
        complexity = self._compute_complexity(query, payload)

        # Core formula
        denom = max(complexity, 1)  # avoid division by zero
        raw_score = ((pain * business_impact) / denom) * 10

        # Adjusted score with savings multiplier
        adjusted_score = raw_score * (1 + self._savings_pct / 100)

        # Classification
        classification = self._classify_workload(query, payload)

        # Recommendation
        recommendation = self._recommendation(adjusted_score, classification)

        # Priority
        if adjusted_score >= 25:
            priority = "Priority_1"
        elif adjusted_score >= self.threshold:
            priority = "Evaluate"
        else:
            priority = "Hold"

        identifier = query.query_id or f"workload_{hash(query.query_text_fingerprint) % 10**6}"

        return WorkloadScore(
            identifier=identifier,
            pain=pain,
            business_impact=business_impact,
            complexity=complexity,
            raw_score=round(raw_score, 2),
            adjusted_score=round(adjusted_score, 2),
            classification=classification,
            recommendation=recommendation,
            priority=priority,
        )

    def _score_platform(self, payload: AssessmentPayload) -> WorkloadScore:
        """Score the platform as a whole when no individual query data is available."""
        # Aggregate signals
        has_timeouts = payload.has_timeouts
        has_errors = payload.has_errors
        has_udf = payload.has_heavy_udf
        has_sp = payload.has_stored_procs
        is_customer_facing = payload.is_customer_facing
        needs_scaling = payload.needs_scaling
        has_pii = payload.has_pii_sensitive_data
        has_security_issues = payload.has_security_issues

        # Pain: cost and stability signals
        pain = 1
        if has_timeouts or has_errors:
            pain += 1
        if has_udf or has_sp:
            pain += 1
        if needs_scaling:
            pain += 1
        pain = min(pain, 5)

        # Business impact: data criticality signals
        biz = 1
        if is_customer_facing:
            biz += 1
        if has_pii:
            biz += 1
        if has_security_issues:
            biz += 1
        biz = min(biz, 5)

        # Complexity: technical signals
        comp = 1
        if has_udf and has_sp:
            comp += 1
        if has_timeouts:
            comp += 1
        comp = min(comp, 5)

        denom = max(comp, 1)
        raw_score = ((pain * biz) / denom) * 10
        adjusted_score = raw_score * (1 + self._savings_pct / 100)

        classification = "Analytics"
        recommendation = self._recommendation(adjusted_score, classification)

        if adjusted_score >= 25:
            priority = "Priority_1"
        elif adjusted_score >= self.threshold:
            priority = "Evaluate"
        else:
            priority = "Hold"

        return WorkloadScore(
            identifier=f"platform_{payload.platform}",
            pain=pain,
            business_impact=biz,
            complexity=comp,
            raw_score=round(raw_score, 2),
            adjusted_score=round(adjusted_score, 2),
            classification=classification,
            recommendation=recommendation,
            priority=priority,
        )

    # -- sub-scorers (1-5 scale) -- #

    @staticmethod
    def _compute_pain(query, payload: AssessmentPayload) -> int:
        """Compute pain score (1-5) based on cost/stability signals."""
        pain = 1

        # Query performance signals
        if query.avg_exec_time_ms and query.avg_exec_time_ms > 300000:
            pain += 1  # Very slow queries
        elif query.avg_exec_time_ms and query.avg_exec_time_ms > 60000:
            pain += 0.5

        if query.timeout_count > 0:
            pain += 1
        if query.error_count > 0:
            pain += 0.5

        # Payload-level signals
        if payload.has_timeouts:
            pain += 1
        if payload.has_errors:
            pain += 0.5
        if payload.needs_scaling:
            pain += 1

        # New: cost per query above platform median
        if payload.cost_signals and payload.cost_signals.cost_per_query > 0:
            pain += 1

        # New: burst pattern
        if payload.access_patterns and payload.access_patterns.has_burst_pattern:
            pain += 1

        # New: concurrency p99
        if payload.concurrency_signals and payload.concurrency_signals.p99_queue_time_ms and payload.concurrency_signals.p99_queue_time_ms > 5000:
            pain += 2

        # Round and clamp
        return max(1, min(5, int(round(pain))))

    @staticmethod
    def _compute_business_impact(query, payload: AssessmentPayload) -> int:
        """Compute business impact score (1-5)."""
        impact = 1

        if query.is_customer_facing or payload.is_customer_facing:
            impact += 2
        if query.is_real_time or payload.has_real_time:
            impact += 1
        if payload.has_pii_sensitive_data:
            impact += 1
        if payload.has_security_issues:
            impact += 0.5

        # New: app-serving workload (high point lookup percentage)
        if payload.access_patterns and payload.access_patterns.point_lookup_pct > 0.5:
            impact += 1

        # New: high compute cost
        if payload.cost_signals and payload.cost_signals.estimated_compute_cost_monthly > 10000:
            impact += 2

        return max(1, min(5, int(round(impact))))

    @staticmethod
    def _compute_complexity(query, payload: AssessmentPayload) -> int:
        """Compute complexity score (1-5)."""
        complexity = 1

        if query.has_udf:
            complexity += 1
        if query.has_stored_procedure:
            complexity += 0.5
        if payload.has_heavy_udf and payload.has_stored_procs:
            complexity += 1
        if payload.table_metadata.has_materialized_views:
            complexity += 0.5

        # New: count-based migration complexity signals
        mc = payload.migration_complexity
        if mc:
            non_portable_udfs = sum(1 for u in mc.udf_records if not u.is_portable)
            complexity += min(non_portable_udfs, 3)
            loop_procs = sum(1 for p in mc.stored_proc_records if p.has_loops)
            complexity += min(loop_procs, 2)
            complexity += min(mc.binary_column_count, 2)
            complexity += min(mc.cross_db_join_count, 2)
            complexity += 3 if mc.has_unsupported_types else 0

        return max(1, min(5, int(round(complexity))))

    def _classify_workload(self, query, payload: AssessmentPayload) -> str:
        """Classify workload into a Lakebase fit bucket."""
        udf_heavy = query.has_udf and payload.has_heavy_udf
        sp_heavy = query.has_stored_procedure and payload.has_stored_procs
        real_time = query.is_real_time or payload.has_real_time
        customer_facing = query.is_customer_facing or payload.is_customer_facing

        if udf_heavy:
            return "Heavy ETL/UDF"
        if real_time and customer_facing:
            return "Real-time Join/Agg"
        if customer_facing:
            return "Analytics"
        if sp_heavy:
            return "Heavy ETL/UDF"
        return "Analytics"

    @staticmethod
    def _recommendation(score: float, classification: str) -> str:
        """Generate a human-readable recommendation."""
        if classification == "Heavy ETL/UDF":
            return f"Score: {score:.1f}. Flag for refactoring first. UDF-heavy workloads need ETL rewrites before migration."
        if classification == "Real-time Join/Agg":
            return f"Score: {score:.1f}. Lakebase + caching layer recommended for real-time query patterns."
        if classification == "Analytics":
            if score >= 25:
                return f"Score: {score:.1f}. Priority 1 migration target. High confidence for Lakebase."
            elif score >= 10:
                return f"Score: {score:.1f}. Evaluate for PoC. Low-risk migration candidate."
            else:
                return f"Score: {score:.1f}. Hold. Optimize in current platform first."
        if classification == "Point Lookups":
            return f"Score: {score:.1f}. Excellent Lakebase fit for point lookup workloads."
        if classification == "Agent State":
            return f"Score: {score:.1f}. Migrate to Lakebase for low-latency state management."
        if classification == "App Backends":
            return f"Score: {score:.1f}. Migrate to Lakebase for scalable app backend."
        if classification == "Feature Serving":
            return f"Score: {score:.1f}. Migrate to Lakebase for feature serving."
        return f"Score: {score:.1f}. Evaluate based on migration bucket analysis."

    def compute_summary(self, scores: list[WorkloadScore]) -> ScoreSummary:
        """Compute an aggregated summary from a list of scores."""
        if not scores:
            return ScoreSummary(
                platform="unknown",
                total_workloads=0,
                priority_1_count=0,
                evaluate_count=0,
                hold_count=0,
                avg_score=0.0,
                max_score=0.0,
                min_score=0.0,
                median_score=0.0,
            )

        vals = [s.adjusted_score for s in scores]
        sorted_vals = sorted(vals)
        n = len(sorted_vals)
        median = sorted_vals[n // 2] if n % 2 == 1 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2

        return ScoreSummary(
            platform=scores[0].identifier.split("_")[0] if "_" in scores[0].identifier else "platform",
            total_workloads=n,
            priority_1_count=sum(1 for s in scores if s.priority == "Priority_1"),
            evaluate_count=sum(1 for s in scores if s.priority == "Evaluate"),
            hold_count=sum(1 for s in scores if s.priority == "Hold"),
            avg_score=round(sum(vals) / n, 2),
            max_score=max(vals),
            min_score=min(vals),
            median_score=round(median, 2),
        )
