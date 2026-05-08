"""Tests for DatabricksMisuseFindings and related models."""

import pytest
from src.models.databricks_misuse import (
    MisuseFinding,
    JobRunRecord,
    JobRunTimeline,
    DatabricksMisuseFindings,
    FINDING_HIGH_FREQ_POINT_LOOKUP,
    FINDING_AGENT_STATE_DELTA_MISUSE,
    FINDING_APP_BACKEND_ON_DELTA,
    FINDING_FEATURE_STORE_LATENCY,
    FINDING_HIGH_CONCURRENCY_COST,
    FINDING_CACHING_LAYER_BYPASS,
)


class TestFindingConstants:
    def test_all_constants_defined(self):
        assert FINDING_HIGH_FREQ_POINT_LOOKUP == "HIGH_FREQ_POINT_LOOKUP"
        assert FINDING_AGENT_STATE_DELTA_MISUSE == "AGENT_STATE_DELTA_MISUSE"
        assert FINDING_APP_BACKEND_ON_DELTA == "APP_BACKEND_ON_DELTA"
        assert FINDING_FEATURE_STORE_LATENCY == "FEATURE_STORE_LATENCY"
        assert FINDING_HIGH_CONCURRENCY_COST == "HIGH_CONCURRENCY_COST"
        assert FINDING_CACHING_LAYER_BYPASS == "CACHING_LAYER_BYPASS"


class TestMisuseFinding:
    def test_basic_construction(self):
        f = MisuseFinding(
            finding_type=FINDING_HIGH_FREQ_POINT_LOOKUP,
            severity="high",
            affected_object="orders_table",
            description="High frequency point lookups",
            evidence="1000 lookups/min",
            recommendation="Migrate to Lakebase",
        )
        assert f.finding_type == FINDING_HIGH_FREQ_POINT_LOOKUP
        assert f.severity == "high"
        assert f.estimated_monthly_savings_dbu == 0.0

    def test_with_savings(self):
        f = MisuseFinding(
            finding_type=FINDING_HIGH_CONCURRENCY_COST,
            severity="medium",
            affected_object="wh1",
            description="Over-provisioned",
            evidence="avg util < 20%",
            recommendation="Downsize warehouse",
            estimated_monthly_savings_dbu=500.0,
        )
        assert f.estimated_monthly_savings_dbu == 500.0


class TestJobRunRecord:
    def test_basic_construction(self):
        jr = JobRunRecord(
            job_name="ETL Pipeline",
            avg_duration_seconds=3600.0,
            runs_per_day=4.0,
            trigger_type="CRON",
            cluster_type="NEW_CLUSTER",
        )
        assert jr.job_name == "ETL Pipeline"
        assert jr.failure_rate == 0.0
        assert jr.tables_written == []

    def test_with_failure_rate(self):
        jr = JobRunRecord(
            job_name="Flaky Job",
            avg_duration_seconds=120.0,
            runs_per_day=24.0,
            trigger_type="SCHEDULED",
            cluster_type="EXISTING_CLUSTER",
            failure_rate=0.25,
        )
        assert jr.failure_rate == 0.25


class TestJobRunTimeline:
    def test_defaults(self):
        jt = JobRunTimeline()
        assert jt.platform == "databricks"
        assert jt.jobs == []
        assert jt.always_on_cluster_jobs == 0
        assert jt.over_provisioned_jobs == 0
        assert jt.high_failure_rate_jobs == 0

    def test_with_jobs(self):
        jr = JobRunRecord(
            job_name="Test", avg_duration_seconds=60.0,
            runs_per_day=1.0, trigger_type="MANUAL", cluster_type="SERVERLESS",
        )
        jt = JobRunTimeline(jobs=[jr], always_on_cluster_jobs=2)
        assert len(jt.jobs) == 1
        assert jt.always_on_cluster_jobs == 2


class TestDatabricksMisuseFindings:
    def test_defaults(self):
        dmf = DatabricksMisuseFindings()
        assert dmf.platform == "databricks"
        assert dmf.findings == []
        assert dmf.cache_candidate_queries == 0
        assert dmf.total_estimated_wasted_dbu_monthly == 0.0

    def test_with_findings(self):
        f = MisuseFinding(
            finding_type=FINDING_HIGH_FREQ_POINT_LOOKUP,
            severity="high",
            affected_object="table1",
            description="desc",
            evidence="ev",
            recommendation="rec",
            estimated_monthly_savings_dbu=100.0,
        )
        dmf = DatabricksMisuseFindings(
            findings=[f],
            total_estimated_wasted_dbu_monthly=100.0,
        )
        assert len(dmf.findings) == 1
        assert dmf.total_estimated_wasted_dbu_monthly == 100.0
