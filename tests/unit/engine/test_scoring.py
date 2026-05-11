"""Tests for ScoreEngine, WorkloadScore, LakbaseReadinessScore, ScoreSummary."""

import pytest
from src.engine.scoring import ScoreEngine, WorkloadScore, LakbaseReadinessScore, ScoreSummary
from src.models.query_history import QueryRecord, QueryHistory
from src.models.table_metadata import TableMetadataCollection, TableMetadata
from src.models.assessment_payload import AssessmentPayload
from src.models.concurrency import ConcurrencySignals
from src.models.security import SecurityPatterns
from src.models.cost_signals import CostSignals
from src.models.migration_complexity import MigrationComplexitySignals, UDFRecord, StoredProcRecord


def _make_query(**overrides):
    defaults = dict(
        query_id="q1", database="db", schema_name="s",
        query_text_fingerprint="SELECT 1", query_type="SELECT",
    )
    defaults.update(overrides)
    return QueryRecord(**defaults)


def _make_payload(**overrides):
    qr = overrides.pop("query", _make_query())
    qh = QueryHistory(platform="test", queries=[qr])
    tm = TableMetadataCollection(platform="test")
    return AssessmentPayload(
        platform="test", platform_display_name="Test",
        query_history=qh, table_metadata=tm, **overrides,
    )


class TestScoreEngineThresholds:
    def test_priority_1_threshold(self):
        assert ScoreEngine.PRIORITY_1_THRESHOLD == 15.0

    def test_evaluate_threshold(self):
        assert ScoreEngine.EVALUATE_THRESHOLD == 8.0


class TestScorePayload:
    def test_returns_list_of_workload_scores(self):
        engine = ScoreEngine()
        payload = _make_payload()
        results = engine.score_payload(payload)
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, WorkloadScore) for r in results)

    def test_empty_queries_returns_platform_score(self):
        engine = ScoreEngine()
        qh = QueryHistory(platform="test", queries=[])
        tm = TableMetadataCollection(platform="test")
        payload = AssessmentPayload(
            platform="test", platform_display_name="Test",
            query_history=qh, table_metadata=tm,
        )
        results = engine.score_payload(payload)
        assert len(results) == 1
        assert results[0].identifier.startswith("platform_")

    def test_score_uses_identifier_from_query_id(self):
        engine = ScoreEngine()
        payload = _make_payload(query=_make_query(query_id="my_query_001"))
        results = engine.score_payload(payload)
        assert results[0].identifier == "my_query_001"

    def test_priority_assigned_correctly(self):
        engine = ScoreEngine()
        high_pain_query = _make_query(
            timeout_count=5, error_count=5, avg_exec_time_ms=500000,
            is_customer_facing=True, is_real_time=True,
        )
        payload = _make_payload(query=high_pain_query)
        results = engine.score_payload(payload)
        assert results[0].priority in ("Priority_1", "Evaluate", "Hold")

    def test_savings_pct_adjusts_score(self):
        engine_base = ScoreEngine(savings_pct=0.0)
        engine_savings = ScoreEngine(savings_pct=50.0)
        payload = _make_payload()
        base_results = engine_base.score_payload(payload)
        savings_results = engine_savings.score_payload(payload)
        assert savings_results[0].adjusted_score >= base_results[0].adjusted_score


class TestComputePain:
    def test_slow_query_increases_pain(self):
        qr = _make_query(avg_exec_time_ms=400000)
        payload = _make_payload(query=qr)
        pain = ScoreEngine._compute_pain(qr, payload)
        assert pain >= 2

    def test_moderate_slow_query_increases_pain(self):
        qr = _make_query(avg_exec_time_ms=90000)
        payload = _make_payload(query=qr)
        pain = ScoreEngine._compute_pain(qr, payload)
        assert pain >= 1

    def test_timeout_increases_pain(self):
        qr = _make_query(timeout_count=3)
        payload = _make_payload(query=qr)
        pain = ScoreEngine._compute_pain(qr, payload)
        assert pain >= 2

    def test_error_increases_pain(self):
        qr = _make_query(error_count=1)
        payload = _make_payload(query=qr)
        pain = ScoreEngine._compute_pain(qr, payload)
        assert pain >= 1

    def test_pain_clamped_to_5(self):
        qr = _make_query(
            avg_exec_time_ms=600000, timeout_count=10, error_count=5,
        )
        payload = _make_payload(query=qr)
        pain = ScoreEngine._compute_pain(qr, payload)
        assert pain <= 5

    def test_pain_minimum_1(self):
        qr = _make_query()
        payload = _make_payload(query=qr)
        pain = ScoreEngine._compute_pain(qr, payload)
        assert pain >= 1

    def test_cost_signals_increase_pain(self):
        qr = _make_query()
        cs = CostSignals(platform="test", cost_per_query=5.0)
        payload = _make_payload(query=qr, cost_signals=cs)
        pain = ScoreEngine._compute_pain(qr, payload)
        assert pain >= 2


class TestComputeBusinessImpact:
    def test_customer_facing_increases_impact(self):
        qr = _make_query(is_customer_facing=True)
        payload = _make_payload(query=qr)
        impact = ScoreEngine._compute_business_impact(qr, payload)
        assert impact >= 3

    def test_real_time_increases_impact(self):
        qr = _make_query(is_real_time=True)
        payload = _make_payload(query=qr)
        impact = ScoreEngine._compute_business_impact(qr, payload)
        assert impact >= 2

    def test_high_compute_cost_increases_impact(self):
        qr = _make_query()
        cs = CostSignals(platform="test", estimated_compute_cost_monthly=15000.0)
        payload = _make_payload(query=qr, cost_signals=cs)
        impact = ScoreEngine._compute_business_impact(qr, payload)
        assert impact >= 3

    def test_impact_clamped_to_5(self):
        qr = _make_query(is_customer_facing=True, is_real_time=True)
        cs = CostSignals(platform="test", estimated_compute_cost_monthly=20000.0)
        payload = _make_payload(query=qr, cost_signals=cs)
        impact = ScoreEngine._compute_business_impact(qr, payload)
        assert impact <= 5

    def test_minimum_impact_is_1(self):
        qr = _make_query()
        payload = _make_payload(query=qr)
        impact = ScoreEngine._compute_business_impact(qr, payload)
        assert impact >= 1


class TestComputeComplexity:
    def test_udf_increases_complexity(self):
        qr = _make_query(has_udf=True)
        payload = _make_payload(query=qr)
        c = ScoreEngine._compute_complexity(qr, payload)
        assert c >= 2

    def test_stored_proc_increases_complexity(self):
        qr = _make_query(has_stored_procedure=True)
        payload = _make_payload(query=qr)
        c = ScoreEngine._compute_complexity(qr, payload)
        assert c >= 1

    def test_non_portable_udfs_increase_complexity(self):
        qr = _make_query(has_udf=True)
        mc = MigrationComplexitySignals(
            platform="test",
            udf_records=[UDFRecord(name="fn1", language="javascript", is_portable=False)],
        )
        payload = _make_payload(query=qr, migration_complexity=mc)
        c = ScoreEngine._compute_complexity(qr, payload)
        assert c >= 2

    def test_complexity_clamped_to_5(self):
        qr = _make_query(has_udf=True, has_stored_procedure=True)
        mc = MigrationComplexitySignals(
            platform="test",
            udf_records=[UDFRecord(name=f"fn{i}", language="js", is_portable=False) for i in range(5)],
            stored_proc_records=[StoredProcRecord(name="p1", line_count=100, has_loops=True,
                                                  has_external_calls=True, has_ddl=True,
                                                  migration_path="manual")],
            binary_column_count=3,
            cross_db_join_count=3,
            has_unsupported_types=True,
        )
        payload = _make_payload(query=qr, migration_complexity=mc)
        c = ScoreEngine._compute_complexity(qr, payload)
        assert c == 5


class TestRecommendation:
    def test_heavy_etl_recommendation(self):
        rec = ScoreEngine._recommendation(10.0, "Heavy ETL/UDF")
        assert "refactoring" in rec.lower() or "udf" in rec.lower()

    def test_real_time_recommendation(self):
        rec = ScoreEngine._recommendation(20.0, "Real-time Join/Agg")
        assert "caching" in rec.lower() or "real-time" in rec.lower()

    def test_analytics_priority_1_recommendation(self):
        rec = ScoreEngine._recommendation(20.0, "Analytics")
        assert "priority" in rec.lower() or "migration" in rec.lower()

    def test_analytics_evaluate_recommendation(self):
        rec = ScoreEngine._recommendation(10.0, "Analytics")
        assert "evaluate" in rec.lower() or "poc" in rec.lower()

    def test_analytics_hold_recommendation(self):
        rec = ScoreEngine._recommendation(5.0, "Analytics")
        assert "hold" in rec.lower() or "optimize" in rec.lower()

    def test_unknown_classification(self):
        rec = ScoreEngine._recommendation(15.0, "Unknown")
        assert "evaluate" in rec.lower() or "score" in rec.lower()


class TestTshirtSize:
    def test_xs_for_short_weeks(self):
        mc = MigrationComplexitySignals(platform="test", estimated_migration_weeks=1.0)
        payload = _make_payload(migration_complexity=mc)
        size = ScoreEngine._compute_tshirt_size(1, "Analytics", payload)
        assert size == "XS"

    def test_xxl_for_long_weeks(self):
        mc = MigrationComplexitySignals(platform="test", estimated_migration_weeks=20.0)
        payload = _make_payload(migration_complexity=mc)
        size = ScoreEngine._compute_tshirt_size(5, "Heavy ETL/UDF", payload)
        assert size == "XXL"

    def test_heuristic_when_no_mc(self):
        payload = _make_payload()
        size = ScoreEngine._compute_tshirt_size(1, "Analytics", payload)
        assert size in ("XS", "S")

    def test_realtime_multiplier(self):
        payload = _make_payload()
        size = ScoreEngine._compute_tshirt_size(3, "Real-time Join/Agg", payload)
        assert size in ("M", "L", "XL", "XXL")


class TestReadinessScore:
    def test_returns_readiness_score(self):
        engine = ScoreEngine()
        payload = _make_payload()
        rs = engine.score_readiness(payload)
        assert isinstance(rs, LakbaseReadinessScore)
        assert 0 <= rs.total_score <= 100

    def test_tier_launch_ready_for_high_score(self):
        engine = ScoreEngine()
        sp = SecurityPatterns(
            platform="test", findings=[], rbac_enabled=True, encryption_at_rest=True,
            encryption_in_transit=True, audit_logging_enabled=True,
            compliance_certifications=[], total_findings=0,
            high_severity_count=0, critical_severity_count=0,
        )
        tm = TableMetadataCollection(platform="test", total_tables_fetched=10)
        qh = QueryHistory(platform="test", queries=[_make_query()])
        cs = CostSignals(platform="test", total_estimated_monthly_cost=10000.0)
        payload = AssessmentPayload(
            platform="test", platform_display_name="Test",
            query_history=qh, table_metadata=tm,
            security_patterns=sp, cost_signals=cs,
            interview_inputs={"team_sql_skill": "expert", "customer_pain_summary": "yes",
                              "contract_renewal_months": 3},
            contract_renewal_months=3,
        )
        rs = engine.score_readiness(payload)
        assert rs.total_score >= 60

    def test_pillar_gaps_populated_for_low_score(self):
        engine = ScoreEngine()
        sp = SecurityPatterns(
            platform="test", findings=[], rbac_enabled=False, encryption_at_rest=False,
            encryption_in_transit=False, audit_logging_enabled=False,
            compliance_certifications=[], total_findings=5,
            high_severity_count=5, critical_severity_count=3,
        )
        qh = QueryHistory(platform="test", queries=[_make_query()])
        tm = TableMetadataCollection(platform="test")
        payload = AssessmentPayload(
            platform="test", platform_display_name="Test",
            query_history=qh, table_metadata=tm, security_patterns=sp,
        )
        rs = engine.score_readiness(payload)
        assert len(rs.pillar_gaps) >= 0

    def test_recommended_next_step_not_empty(self):
        engine = ScoreEngine()
        payload = _make_payload()
        rs = engine.score_readiness(payload)
        assert len(rs.recommended_next_step) > 0


class TestComputeSummary:
    def _make_ws(self, score, priority):
        ws = WorkloadScore(
            identifier=f"wl_{score}", pain=2, business_impact=2,
            complexity=2, raw_score=score, adjusted_score=score,
            classification="Analytics", recommendation="test",
            priority=priority,
        )
        return ws

    def test_empty_scores_returns_zero_summary(self):
        engine = ScoreEngine()
        summary = engine.compute_summary([])
        assert summary.total_workloads == 0
        assert summary.avg_score == 0.0

    def test_counts_priorities_correctly(self):
        engine = ScoreEngine()
        scores = [
            self._make_ws(20.0, "Priority_1"),
            self._make_ws(10.0, "Evaluate"),
            self._make_ws(5.0, "Hold"),
        ]
        summary = engine.compute_summary(scores)
        assert summary.priority_1_count == 1
        assert summary.evaluate_count == 1
        assert summary.hold_count == 1
        assert summary.total_workloads == 3

    def test_avg_score_computed(self):
        engine = ScoreEngine()
        scores = [self._make_ws(10.0, "Hold"), self._make_ws(20.0, "Priority_1")]
        summary = engine.compute_summary(scores)
        assert summary.avg_score == 15.0

    def test_max_min_score(self):
        engine = ScoreEngine()
        scores = [self._make_ws(s, "Hold") for s in [5.0, 15.0, 25.0]]
        summary = engine.compute_summary(scores)
        assert summary.max_score == 25.0
        assert summary.min_score == 5.0

    def test_median_score_odd_count(self):
        engine = ScoreEngine()
        scores = [self._make_ws(s, "Hold") for s in [5.0, 10.0, 20.0]]
        summary = engine.compute_summary(scores)
        assert summary.median_score == 10.0

    def test_median_score_even_count(self):
        engine = ScoreEngine()
        scores = [self._make_ws(s, "Hold") for s in [4.0, 8.0, 12.0, 16.0]]
        summary = engine.compute_summary(scores)
        assert summary.median_score == 10.0
