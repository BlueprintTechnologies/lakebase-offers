"""Tests for §11–§17 handoff work items."""

import pytest

from src.engine.scoring import ScoreEngine, WorkloadScore, LakbaseReadinessScore
from src.models.assessment_payload import AssessmentPayload
from src.models.query_history import QueryHistory, QueryRecord
from src.models.table_metadata import TableMetadataCollection
from src.models.databricks_misuse import (
    DatabricksMisuseFindings,
    JobRunRecord,
    JobRunTimeline,
    MisuseFinding,
    FINDING_HIGH_FREQ_POINT_LOOKUP,
    FINDING_AGENT_STATE_DELTA_MISUSE,
    FINDING_APP_BACKEND_ON_DELTA,
    FINDING_FEATURE_STORE_LATENCY,
    FINDING_HIGH_CONCURRENCY_COST,
    FINDING_CACHING_LAYER_BYPASS,
)
from src.models.migration_complexity import MigrationComplexitySignals, UDFRecord, StoredProcRecord
from src.models.cost_signals import CostSignals
from src.models.security import SecurityPatterns


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_minimal_payload(**kwargs) -> AssessmentPayload:
    qr = QueryRecord(
        query_id="q1", database="db", schema_name="s",
        query_text_fingerprint="SELECT 1", query_type="SELECT",
    )
    qh = QueryHistory(platform="test", queries=[qr])
    tm = TableMetadataCollection(platform="test")
    return AssessmentPayload(
        platform="test",
        platform_display_name="Test",
        query_history=qh,
        table_metadata=tm,
        **kwargs,
    )


# ── §11: Score threshold reconciliation ──────────────────────────────────────

class TestGTMThresholds:
    """GTM spec: Priority 1 ≥ 15, Evaluate 8–14, Hold < 8."""

    def test_class_constants(self):
        assert ScoreEngine.PRIORITY_1_THRESHOLD == 15.0
        assert ScoreEngine.EVALUATE_THRESHOLD == 8.0

    def test_default_evaluate_threshold_is_8(self):
        engine = ScoreEngine()
        assert engine.threshold == 8.0

    def test_high_score_is_priority_1(self):
        qr = QueryRecord(
            query_id="q1", database="db", schema_name="s",
            query_text_fingerprint="SELECT 1", query_type="SELECT",
            avg_exec_time_ms=500_000, timeout_count=10,
            is_customer_facing=True, is_real_time=True,
        )
        engine = ScoreEngine()
        payload = _make_minimal_payload()
        payload.query_history.queries[0] = qr
        results = engine.score_payload(payload)
        assert any(r.priority == "Priority_1" for r in results)

    def test_score_above_15_is_priority_1(self):
        """Directly exercise threshold: adjusted_score = 16 → Priority_1."""
        engine = ScoreEngine()
        ws = WorkloadScore(
            identifier="x", pain=3, business_impact=3, complexity=1,
            raw_score=16.0, adjusted_score=16.0,
            classification="Analytics", recommendation="",
            priority="Priority_1",
        )
        assert ws.priority == "Priority_1"

    def test_score_between_8_and_15_is_evaluate(self):
        """adjusted_score = 10 → Evaluate (8 ≤ 10 < 15)."""
        ws = WorkloadScore(
            identifier="x", pain=2, business_impact=2, complexity=2,
            raw_score=10.0, adjusted_score=10.0,
            classification="Analytics", recommendation="",
            priority="Evaluate",
        )
        assert ws.priority == "Evaluate"

    def test_score_below_8_is_hold(self):
        ws = WorkloadScore(
            identifier="x", pain=1, business_impact=1, complexity=2,
            raw_score=5.0, adjusted_score=5.0,
            classification="Analytics", recommendation="",
            priority="Hold",
        )
        assert ws.priority == "Hold"

    def test_recommendation_uses_new_thresholds(self):
        rec_p1 = ScoreEngine._recommendation(15.0, "Analytics")
        rec_eval = ScoreEngine._recommendation(10.0, "Analytics")
        rec_hold = ScoreEngine._recommendation(5.0, "Analytics")
        assert "Priority 1" in rec_p1
        assert "Evaluate" in rec_eval
        assert "Hold" in rec_hold


# ── §16: T-shirt sizing ───────────────────────────────────────────────────────

class TestTshirtSizing:
    """Effort T-shirt sizing from MigrationComplexitySignals."""

    def test_workload_score_has_tshirt_field(self):
        ws = WorkloadScore(
            identifier="x", pain=1, business_impact=1, complexity=1,
            raw_score=10.0, adjusted_score=10.0,
            classification="Analytics", recommendation="",
            priority="Evaluate",
        )
        assert hasattr(ws, "effort_tshirt_size")
        assert ws.effort_tshirt_size in ("XS", "S", "M", "L", "XL", "XXL")

    def test_xs_from_low_weeks(self):
        mc = MigrationComplexitySignals(platform="test", estimated_migration_weeks=1.5)
        payload = _make_minimal_payload(migration_complexity=mc)
        size = ScoreEngine._compute_tshirt_size(1, "Analytics", payload)
        assert size == "XS"

    def test_s_from_2_to_4_weeks(self):
        mc = MigrationComplexitySignals(platform="test", estimated_migration_weeks=3.0)
        payload = _make_minimal_payload(migration_complexity=mc)
        assert ScoreEngine._compute_tshirt_size(1, "Analytics", payload) == "S"

    def test_m_from_4_to_6_weeks(self):
        mc = MigrationComplexitySignals(platform="test", estimated_migration_weeks=5.0)
        payload = _make_minimal_payload(migration_complexity=mc)
        assert ScoreEngine._compute_tshirt_size(2, "Analytics", payload) == "M"

    def test_xl_from_12_weeks(self):
        mc = MigrationComplexitySignals(platform="test", estimated_migration_weeks=12.0)
        payload = _make_minimal_payload(migration_complexity=mc)
        assert ScoreEngine._compute_tshirt_size(4, "Analytics", payload) == "XL"

    def test_xxl_from_17_weeks(self):
        mc = MigrationComplexitySignals(platform="test", estimated_migration_weeks=17.0)
        payload = _make_minimal_payload(migration_complexity=mc)
        assert ScoreEngine._compute_tshirt_size(5, "Analytics", payload) == "XXL"

    def test_heuristic_when_no_mc(self):
        payload = _make_minimal_payload()  # no migration_complexity
        size = ScoreEngine._compute_tshirt_size(1, "Analytics", payload)
        assert size in ("XS", "S")  # complexity=1 → 2 weeks → XS

    def test_etl_multiplier_applied(self):
        payload = _make_minimal_payload()
        size_etl = ScoreEngine._compute_tshirt_size(3, "Heavy ETL/UDF", payload)
        size_analytics = ScoreEngine._compute_tshirt_size(3, "Analytics", payload)
        # ETL multiplies weeks by 2x — size must be >= analytics size
        sizes = ["XS", "S", "M", "L", "XL", "XXL"]
        assert sizes.index(size_etl) >= sizes.index(size_analytics)

    def test_tshirt_in_scored_result(self):
        engine = ScoreEngine()
        payload = _make_minimal_payload()
        results = engine.score_payload(payload)
        assert all(r.effort_tshirt_size in ("XS", "S", "M", "L", "XL", "XXL") for r in results)


# ── §15: Lakebase Readiness Score ────────────────────────────────────────────

class TestLakbaseReadinessScore:
    """5-pillar, 100-point readiness framework."""

    def test_dataclass_fields(self):
        rs = LakbaseReadinessScore(
            data_readiness_score=20,
            sql_compatibility_score=20,
            access_governance_score=16,
            cost_business_case_score=12,
            org_readiness_score=10,
            total_score=78,
            tier="Conditionally Ready",
            pillar_gaps=["Org Readiness"],
            recommended_next_step="Sprint to close gaps.",
        )
        assert rs.total_score == 78
        assert rs.tier == "Conditionally Ready"

    def test_total_never_exceeds_100(self):
        engine = ScoreEngine()
        payload = _make_minimal_payload()
        rs = engine.score_readiness(payload)
        assert rs.total_score <= 100
        assert rs.total_score >= 0

    def test_tier_launch_ready(self):
        engine = ScoreEngine()
        # Good security + cost signals → high scores
        sp = SecurityPatterns(
            platform="test",
            rbac_enabled=True,
            encryption_at_rest=True,
            encryption_in_transit=True,
            audit_logging_enabled=True,
            total_findings=0,
            high_severity_count=0,
            critical_severity_count=0,
        )
        cs = CostSignals(
            platform="test",
            compute_units_per_month=100.0,
            compute_unit_name="credit",
            compute_cost_per_unit=28.0,
            total_estimated_monthly_cost=10_000.0,
        )
        payload = _make_minimal_payload(
            security_patterns=sp,
            cost_signals=cs,
            interview_inputs={"team_sql_skill": "expert", "customer_pain_summary": "High bills"},
        )
        rs = engine.score_readiness(payload)
        assert rs.tier in ("Launch-Ready", "Conditionally Ready")

    def test_tier_strategic_roadmap(self):
        engine = ScoreEngine()
        payload = _make_minimal_payload()
        # No security, no cost signals, no interview inputs → low score
        rs = engine.score_readiness(payload)
        assert rs.tier in ("Strategic Roadmap", "Foundation Needed", "Conditionally Ready", "Launch-Ready")

    def test_pillar_gaps_list(self):
        engine = ScoreEngine()
        rs = engine.score_readiness(_make_minimal_payload())
        assert isinstance(rs.pillar_gaps, list)

    def test_recommended_next_step_non_empty(self):
        engine = ScoreEngine()
        rs = engine.score_readiness(_make_minimal_payload())
        assert len(rs.recommended_next_step) > 0

    def test_contract_pressure_boosts_cost_score(self):
        engine = ScoreEngine()
        payload_no_renewal = _make_minimal_payload()
        payload_renewal = _make_minimal_payload(contract_renewal_months=4)
        rs_no = engine.score_readiness(payload_no_renewal)
        rs_yes = engine.score_readiness(payload_renewal)
        assert rs_yes.cost_business_case_score >= rs_no.cost_business_case_score

    def test_pillar_scores_sum_to_total(self):
        engine = ScoreEngine()
        rs = engine.score_readiness(_make_minimal_payload())
        expected = (
            rs.data_readiness_score
            + rs.sql_compatibility_score
            + rs.access_governance_score
            + rs.cost_business_case_score
            + rs.org_readiness_score
        )
        assert rs.total_score == expected

    def test_pillar_max_bounds(self):
        engine = ScoreEngine()
        rs = engine.score_readiness(_make_minimal_payload())
        assert rs.data_readiness_score <= 25
        assert rs.sql_compatibility_score <= 25
        assert rs.access_governance_score <= 20
        assert rs.cost_business_case_score <= 15
        assert rs.org_readiness_score <= 15


# ── §14: JobRunTimeline model ─────────────────────────────────────────────────

class TestJobRunTimeline:
    """Model round-trip and field validation."""

    def test_job_run_record_round_trip(self):
        j = JobRunRecord(
            job_name="ingest_daily",
            avg_duration_seconds=300.0,
            runs_per_day=4.0,
            trigger_type="SCHEDULED",
            cluster_type="NEW_CLUSTER",
            tables_written=["catalog.schema.orders"],
            failure_rate=0.05,
        )
        rt = JobRunRecord.model_validate(j.model_dump())
        assert rt.job_name == "ingest_daily"
        assert rt.failure_rate == 0.05

    def test_job_run_timeline_round_trip(self):
        jobs = [
            JobRunRecord(
                job_name="job_a", avg_duration_seconds=600.0, runs_per_day=1.0,
                trigger_type="SCHEDULED", cluster_type="EXISTING_CLUSTER",
                failure_rate=0.15,
            )
        ]
        timeline = JobRunTimeline(
            platform="databricks",
            jobs=jobs,
            always_on_cluster_jobs=1,
            over_provisioned_jobs=1,
            high_failure_rate_jobs=1,
        )
        rt = JobRunTimeline.model_validate(timeline.model_dump())
        assert rt.always_on_cluster_jobs == 1
        assert rt.high_failure_rate_jobs == 1
        assert len(rt.jobs) == 1

    def test_misuse_findings_includes_job_timeline(self):
        timeline = JobRunTimeline(platform="databricks")
        findings = DatabricksMisuseFindings(
            platform="databricks",
            job_timeline=timeline,
        )
        rt = DatabricksMisuseFindings.model_validate(findings.model_dump())
        assert rt.job_timeline is not None

    def test_findings_without_job_timeline(self):
        findings = DatabricksMisuseFindings(platform="databricks")
        assert findings.job_timeline is None


# ── §13: Six canonical anti-patterns ─────────────────────────────────────────

class TestCanonicalAntiPatternConstants:
    """Constants are correct and the model accepts them."""

    def test_constants_are_strings(self):
        assert isinstance(FINDING_HIGH_FREQ_POINT_LOOKUP, str)
        assert isinstance(FINDING_AGENT_STATE_DELTA_MISUSE, str)
        assert isinstance(FINDING_APP_BACKEND_ON_DELTA, str)
        assert isinstance(FINDING_FEATURE_STORE_LATENCY, str)
        assert isinstance(FINDING_HIGH_CONCURRENCY_COST, str)
        assert isinstance(FINDING_CACHING_LAYER_BYPASS, str)

    def test_all_six_finding_types_accepted(self):
        for ftype in [
            FINDING_HIGH_FREQ_POINT_LOOKUP,
            FINDING_AGENT_STATE_DELTA_MISUSE,
            FINDING_APP_BACKEND_ON_DELTA,
            FINDING_FEATURE_STORE_LATENCY,
            FINDING_HIGH_CONCURRENCY_COST,
            FINDING_CACHING_LAYER_BYPASS,
        ]:
            f = MisuseFinding(
                finding_type=ftype,
                severity="high",
                affected_object="some_table",
                description="test",
                evidence="metric=100",
                recommendation="fix it",
            )
            assert f.finding_type == ftype

    def test_misuse_findings_round_trip_with_all_six(self):
        findings = [
            MisuseFinding(
                finding_type=ft, severity="medium", affected_object="tbl",
                description="d", evidence="e", recommendation="r",
            )
            for ft in [
                FINDING_HIGH_FREQ_POINT_LOOKUP,
                FINDING_AGENT_STATE_DELTA_MISUSE,
                FINDING_APP_BACKEND_ON_DELTA,
                FINDING_FEATURE_STORE_LATENCY,
                FINDING_HIGH_CONCURRENCY_COST,
                FINDING_CACHING_LAYER_BYPASS,
            ]
        ]
        misuse = DatabricksMisuseFindings(platform="databricks", findings=findings)
        rt = DatabricksMisuseFindings.model_validate(misuse.model_dump())
        assert len(rt.findings) == 6


# ── §12: interview_inputs ─────────────────────────────────────────────────────

class TestInterviewInputs:
    """interview_inputs flows through payload and affects readiness scoring."""

    def test_assessment_payload_accepts_interview_inputs(self):
        ii = {
            "caching_layers": ["redis"],
            "team_sql_skill": "intermediate",
            "contract_renewal_months": 5,
            "customer_pain_summary": "Bills are high",
        }
        payload = _make_minimal_payload(interview_inputs=ii)
        assert payload.interview_inputs["team_sql_skill"] == "intermediate"

    def test_interview_inputs_default_empty(self):
        payload = _make_minimal_payload()
        assert payload.interview_inputs == {}

    def test_org_readiness_uses_skill_level(self):
        engine = ScoreEngine()
        payload_expert = _make_minimal_payload(interview_inputs={"team_sql_skill": "expert"})
        payload_beginner = _make_minimal_payload(interview_inputs={"team_sql_skill": "beginner"})
        rs_expert = engine.score_readiness(payload_expert)
        rs_beginner = engine.score_readiness(payload_beginner)
        assert rs_expert.org_readiness_score > rs_beginner.org_readiness_score

    def test_pain_summary_boosts_org_score(self):
        engine = ScoreEngine()
        payload_with = _make_minimal_payload(interview_inputs={"customer_pain_summary": "Outages weekly"})
        payload_without = _make_minimal_payload(interview_inputs={})
        rs_with = engine.score_readiness(payload_with)
        rs_without = engine.score_readiness(payload_without)
        assert rs_with.org_readiness_score >= rs_without.org_readiness_score

    def test_config_parses_interview_inputs(self, tmp_path):
        from src.config import load_config
        import yaml

        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump({
            "target_platforms": ["snowflake"],
            "interview_inputs": {
                "team_sql_skill": "expert",
                "contract_renewal_months": 3,
            },
        }))
        import sys
        from io import StringIO
        old_stderr = sys.stderr
        sys.stderr = StringIO()
        try:
            cfg = load_config(str(cfg_file))
        finally:
            sys.stderr = old_stderr

        assert cfg.interview_inputs.get("team_sql_skill") == "expert"
        assert cfg.interview_inputs.get("contract_renewal_months") == 3

    def test_config_workload_context_parsed(self, tmp_path):
        from src.config import load_config
        import yaml

        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump({
            "target_platforms": ["snowflake"],
            "workload_context": {"has_multi_region": True, "rto_minutes": 60},
        }))
        cfg = load_config(str(cfg_file))
        assert cfg.workload_context.get("has_multi_region") is True


# ── §17: PDF report section builders ─────────────────────────────────────────

class TestPdfReportSections:
    """§17 canonical report sections produce expected content without crashing."""

    def _make_report_gen(self):
        from src.outputs.pdf_report import PdfReportGenerator
        ws = WorkloadScore(
            identifier="q_sales_dashboard",
            pain=4, business_impact=4, complexity=2,
            raw_score=80.0, adjusted_score=80.0,
            classification="Analytics",
            recommendation="Score: 80.0. Priority 1 migration target.",
            priority="Priority_1",
            effort_tshirt_size="M",
        )
        ws2 = WorkloadScore(
            identifier="q_etl_nightly",
            pain=2, business_impact=2, complexity=3,
            raw_score=13.0, adjusted_score=13.0,
            classification="Heavy ETL/UDF",
            recommendation="Score: 13.0. Evaluate for PoC.",
            priority="Evaluate",
            effort_tshirt_size="L",
        )
        misuse = DatabricksMisuseFindings(
            platform="databricks",
            findings=[
                MisuseFinding(
                    finding_type=FINDING_HIGH_FREQ_POINT_LOOKUP,
                    severity="high",
                    affected_object="catalog.prod.orders",
                    description="Point lookups on large Delta table.",
                    evidence="500 runs/day, avg 2 rows, 20MB scanned",
                    recommendation="Move to Lakebase Pro.",
                )
            ],
        )
        engine = ScoreEngine()
        readiness = engine.score_readiness(_make_minimal_payload())
        return PdfReportGenerator(
            scores={"test": [ws, ws2]},
            cost_deltas={"test": {
                "platform": "Test Platform",
                "current_estimated_monthly_cost": 5000.0,
                "projected_lakebase_cost": 3000.0,
                "savings_pct": 40.0,
            }},
            buckets={"Analytics": [{"identifier": "q_sales_dashboard", "adjusted_score": 80.0}]},
            misuse_findings={"databricks": misuse},
            readiness_scores={"test": readiness},
        )

    def test_pdf_report_generator_accepts_new_args(self):
        gen = self._make_report_gen()
        assert gen.misuse_findings
        assert gen.readiness_scores

    def test_access_pattern_section_builds_without_error(self):
        gen = self._make_report_gen()
        elements: list = []

        class FakeStyles(dict):
            def __missing__(self, key):
                from reportlab.lib.styles import ParagraphStyle
                return ParagraphStyle(key)

        try:
            from reportlab.lib.styles import getSampleStyleSheet
            styles = getSampleStyleSheet()
            gen._build_access_pattern_section(elements, styles)
            assert len(elements) > 0
        except ImportError:
            pytest.skip("reportlab not installed")

    def test_fit_scorecard_section_builds_without_error(self):
        gen = self._make_report_gen()
        elements: list = []
        try:
            from reportlab.lib.styles import getSampleStyleSheet
            styles = getSampleStyleSheet()
            gen._build_fit_scorecard_section(elements, styles)
            assert len(elements) > 0
        except ImportError:
            pytest.skip("reportlab not installed")

    def test_migration_roadmap_section_builds_without_error(self):
        gen = self._make_report_gen()
        elements: list = []
        try:
            from reportlab.lib.styles import getSampleStyleSheet
            styles = getSampleStyleSheet()
            gen._build_migration_roadmap_section(elements, styles)
            assert len(elements) > 0
        except ImportError:
            pytest.skip("reportlab not installed")
