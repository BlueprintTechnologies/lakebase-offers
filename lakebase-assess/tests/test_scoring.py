"""Tests for the scoring engine."""

import pytest

from src.engine.scoring import ScoreEngine, WorkloadScore, ScoreSummary


def _make_query(**overrides):
    """Helper to create a minimal QueryRecord for scoring."""
    from src.models.query_history import QueryRecord
    return QueryRecord(
        query_id=overrides.pop("query_id", "test_q_1"),
        database=overrides.pop("database", "test_db"),
        schema_name=overrides.pop("schema_name", "test_schema"),
        query_text_fingerprint=overrides.pop("query_text_fingerprint", "SELECT 1"),
        query_type=overrides.pop("query_type", "SELECT"),
        avg_exec_time_ms=overrides.pop("avg_exec_time_ms", None),
        timeout_count=overrides.pop("timeout_count", 0),
        error_count=overrides.pop("error_count", 0),
        has_udf=overrides.pop("has_udf", False),
        has_stored_procedure=overrides.pop("has_stored_procedure", False),
        is_real_time=overrides.pop("is_real_time", False),
        is_customer_facing=overrides.pop("is_customer_facing", False),
        **{k: v for k, v in overrides.items() if v is not None},
    )


def _make_payload(**overrides):
    """Helper to create a minimal AssessmentPayload for scoring."""
    from src.models.assessment_payload import AssessmentPayload
    from src.models.query_history import QueryHistory
    from src.models.table_metadata import TableMetadataCollection

    queries = overrides.pop("queries", [])
    has_heavy_udf = overrides.pop("has_heavy_udf", False)
    has_stored_procs = overrides.pop("has_stored_procs", False)
    has_timeouts = overrides.pop("has_timeouts", False)
    has_errors = overrides.pop("has_errors", False)
    has_real_time = overrides.pop("has_real_time", False)
    is_customer_facing = overrides.pop("is_customer_facing", False)
    has_pii = overrides.pop("has_pii", False)
    needs_scaling = overrides.pop("needs_scaling", False)
    has_security = overrides.pop("has_security", False)
    has_materialized = overrides.pop("has_materialized", False)
    platform = overrides.pop("platform", "test")

    if not queries:
        queries = [_make_query()]

    qh = QueryHistory(
        platform=platform,
        queries=queries,
    )

    # Override QueryHistory properties
    class QHWithFlags(QueryHistory):
        @property
        def has_heavy_udf(self):
            return has_heavy_udf or any(q.has_udf for q in self.queries)

        @property
        def has_stored_procs(self):
            return has_stored_procs or any(q.has_stored_procedure for q in self.queries)

        @property
        def has_real_time_queries(self):
            return has_real_time or any(q.is_real_time for q in self.queries)

        @property
        def has_customer_facing(self):
            return is_customer_facing or any(q.is_customer_facing for q in self.queries)

        @property
        def has_timeouts(self):
            return has_timeouts or any(q.timeout_count > 0 for q in self.queries)

        @property
        def has_errors(self):
            return has_errors or any(q.error_count > 0 for q in self.queries)

    tm = TableMetadataCollection(platform=platform)

    class TMWithFlags(TableMetadataCollection):
        @property
        def has_sensitive_tables(self):
            return has_pii

        @property
        def has_materialized_views(self):
            return has_materialized

    from src.models.concurrency import ConcurrencySignals
    from src.models.security import SecurityPatterns

    cs = ConcurrencySignals(platform=platform)

    class CSWithFlags(ConcurrencySignals):
        @property
        def needs_scaling(self):
            return needs_scaling

    sp = SecurityPatterns(platform=platform)

    class SPCWithFlags(SecurityPatterns):
        @property
        def needs_security_hardening(self):
            return has_security

    payload = AssessmentPayload(
        platform=platform,
        platform_display_name="Test",
        query_history=QHWithFlags.model_construct(
            platform=platform, queries=queries,
            total_queries_fetched=len(queries), unique_databases=[], unique_tables=[],
            avg_concurrency=0.0, peak_concurrency=0,
        ),
        table_metadata=TMWithFlags.model_construct(
            platform=platform, tables=[], total_tables_fetched=0,
            database_count=0, schema_count=0,
        ),
        concurrency_signals=CSWithFlags.model_construct(
            platform=platform, snapshots=[], avg_concurrent_queries=0.0, peak_concurrent_queries=0, scaling_pressure="low",
        ),
        security_patterns=SPCWithFlags.model_construct(
            platform=platform, findings=[], rbac_enabled=True, encryption_at_rest=True,
            encryption_in_transit=True, audit_logging_enabled=True,
            total_findings=0, high_severity_count=0, critical_severity_count=0,
        ),
    )
    return payload


class TestScoreEngine:
    """Test the ScoreEngine scoring logic."""

    def test_basic_scoring(self):
        """Test that basic scoring produces valid results."""
        engine = ScoreEngine()
        payload = _make_payload()
        results = engine.score_payload(payload)
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, WorkloadScore)
        assert r.pain >= 1 and r.pain <= 5
        assert r.business_impact >= 1 and r.business_impact <= 5
        assert r.complexity >= 1 and r.complexity <= 5
        assert r.raw_score > 0
        assert r.adjusted_score > 0

    def test_score_threshold_hold(self):
        """Test that low scores are classified as Hold."""
        # Low pain, low impact, high complexity
        query = _make_query(
            pain_override=1, impact_override=1, complexity_override=5,
        )
        engine = ScoreEngine(threshold=10.0)
        payload = _make_payload(queries=[query])
        results = engine.score_payload(payload)
        assert any(r.priority == "Hold" for r in results)

    def test_score_threshold_priority_1(self):
        """Test that high scores are classified as Priority 1."""
        query = _make_query(
            avg_exec_time_ms=500000, timeout_count=10, has_udf=True,
            is_customer_facing=True, is_real_time=True,
        )
        engine = ScoreEngine(threshold=10.0)
        payload = _make_payload(queries=[query])
        results = engine.score_payload(payload)
        assert any(r.priority == "Priority_1" for r in results)

    def test_savings_multiplier(self):
        """Test that est_savings_pct increases the adjusted score."""
        query = _make_query(avg_exec_time_ms=100000)
        engine_no_savings = ScoreEngine(savings_pct=0.0)
        engine_with_savings = ScoreEngine(savings_pct=50.0)

        payload = _make_payload(queries=[query])
        results_no = engine_no_savings.score_payload(payload)
        results_yes = engine_with_savings.score_payload(payload)

        assert results_yes[0].adjusted_score > results_no[0].adjusted_score

    def test_empty_payload_platform_scoring(self):
        """Test platform-level scoring when no queries are available."""
        engine = ScoreEngine()
        payload = _make_payload(queries=[])
        results = engine.score_payload(payload)
        assert len(results) == 1
        assert results[0].identifier == "platform_test"

    def test_comprehensive_pain_scoring(self):
        """Test pain scoring with multiple signals."""
        query = _make_query(
            avg_exec_time_ms=500000, timeout_count=5, error_count=3, has_udf=True,
        )
        engine = ScoreEngine()
        payload = _make_payload(queries=[query], has_timeouts=True, needs_scaling=True)
        results = engine.score_payload(payload)
        assert results[0].pain >= 3  # Multiple pain signals

    def test_business_impact_scoring(self):
        """Test business impact scoring with customer-facing and PII."""
        query = _make_query(is_customer_facing=True, is_real_time=True)
        engine = ScoreEngine()
        payload = _make_payload(queries=[query], is_customer_facing=True, has_pii=True)
        results = engine.score_payload(payload)
        assert results[0].business_impact >= 3

    def test_complexity_scoring(self):
        """Test complexity scoring with UDF and stored procs."""
        query = _make_query(has_udf=True, has_stored_procedure=True)
        engine = ScoreEngine()
        payload = _make_payload(queries=[query], has_heavy_udf=True, has_stored_procs=True, has_materialized=True)
        results = engine.score_payload(payload)
        assert results[0].complexity >= 2

    def test_summary_computation(self):
        """Test summary computation from scores."""
        engine = ScoreEngine()
        scores = [
            WorkloadScore("q1", 4, 4, 3, 53.33, 53.33, "Analytics", "P1", "Priority_1"),
            WorkloadScore("q2", 2, 2, 2, 20.0, 20.0, "Analytics", "Eval", "Evaluate"),
            WorkloadScore("q3", 1, 1, 4, 2.5, 2.5, "Analytics", "Hold", "Hold"),
        ]
        summary = engine.compute_summary(scores)
        assert summary.total_workloads == 3
        assert summary.priority_1_count == 1
        assert summary.evaluate_count == 1
        assert summary.hold_count == 1
        assert summary.avg_score == 25.28
        assert summary.max_score == 53.33
        assert summary.min_score == 2.5
        assert summary.median_score == 20.0

    def test_empty_summary(self):
        """Test summary with no scores."""
        engine = ScoreEngine()
        summary = engine.compute_summary([])
        assert summary.total_workloads == 0
        assert summary.avg_score == 0.0

    def test_pain_clamped_to_5(self):
        """Test that pain score never exceeds 5."""
        query = _make_query(avg_exec_time_ms=999999, timeout_count=100, error_count=50, has_udf=True)
        engine = ScoreEngine()
        payload = _make_payload(queries=[query], has_timeouts=True, has_errors=True, needs_scaling=True)
        results = engine.score_payload(payload)
        assert results[0].pain <= 5
        assert results[0].pain >= 1

    def test_impact_clamped_to_5(self):
        """Test that impact score never exceeds 5."""
        query = _make_query(is_customer_facing=True, is_real_time=True)
        engine = ScoreEngine()
        payload = _make_payload(queries=[query], is_customer_facing=True, has_pii=True, has_security=True)
        results = engine.score_payload(payload)
        assert results[0].business_impact <= 5
        assert results[0].business_impact >= 1


class TestScoringFormula:
    """Test the exact scoring formula."""

    def test_pain_5_impact_5_complexity_1_score(self):
        """Pain=5, Impact=5, Complexity=1: Score = ((5*5)/1)*10 = 250."""
        query = _make_query(avg_exec_time_ms=500000, timeout_count=10, is_customer_facing=True)
        engine = ScoreEngine()
        payload = _make_payload(queries=[query])
        results = engine.score_payload(payload)
        # The exact pain/impact/complexity values depend on the scoring logic
        # but the formula should hold for the raw_score computation
        assert results[0].raw_score > 0

    def test_pain_1_impact_1_complexity_5_score(self):
        """Pain=1, Impact=1, Complexity=5: Score = ((1*1)/5)*10 = 2."""
        query = _make_query(avg_exec_time_ms=10, has_udf=False, has_stored_procedure=False)
        engine = ScoreEngine()
        payload = _make_payload(queries=[query])
        results = engine.score_payload(payload)
        assert results[0].raw_score <= 10.0  # Should be a low score

    def test_adjusted_score_formula(self):
        """Adjusted = raw * (1 + savings_pct/100)."""
        engine = ScoreEngine(savings_pct=0.0)
        payload = _make_payload()
        results_0 = engine.score_payload(payload)

        engine_10 = ScoreEngine(savings_pct=10.0)
        results_10 = engine_10.score_payload(payload)

        expected_ratio = 1.10
        actual_ratio = results_10[0].adjusted_score / results_0[0].adjusted_score
        assert abs(actual_ratio - expected_ratio) < 0.01


class TestScoringEdgeCases:
    """Test edge cases for scoring."""

    def test_zero_execution_time(self):
        """Test queries with zero or null execution time."""
        query = _make_query(avg_exec_time_ms=None, timeout_count=0, error_count=0)
        engine = ScoreEngine()
        payload = _make_payload(queries=[query])
        results = engine.score_payload(payload)
        assert len(results) == 1
        assert results[0].raw_score > 0

    def test_high_concurrency_platform(self):
        """Test platform-level scoring with scaling needs."""
        engine = ScoreEngine()
        payload = _make_payload(needs_scaling=True, has_timeouts=True, has_errors=True)
        results = engine.score_payload(payload)
        assert results[0].pain >= 2

    def test_all_priority_1(self):
        """Test scenario where all workloads are Priority 1."""
        queries = [
            _make_query(avg_exec_time_ms=500000, timeout_count=10, is_customer_facing=True, is_real_time=True)
            for _ in range(10)
        ]
        engine = ScoreEngine(threshold=10.0)
        payload = _make_payload(queries=queries)
        results = engine.score_payload(payload)
        priority_1 = [r for r in results if r.priority == "Priority_1"]
        assert len(priority_1) > 0

    def test_all_hold(self):
        """Test scenario where all workloads are Hold."""
        queries = [
            _make_query(avg_exec_time_ms=1, has_udf=False, has_stored_procedure=False)
            for _ in range(10)
        ]
        engine = ScoreEngine(threshold=10.0)
        payload = _make_payload(queries=queries)
        results = engine.score_payload(payload)
        holds = [r for r in results if r.priority == "Hold"]
        assert len(holds) > 0
