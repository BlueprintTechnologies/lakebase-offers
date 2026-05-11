"""Tests for new models and their round-trip validation."""

import pytest
from pydantic import ValidationError

from src.models.access_patterns import AccessPatternSignals, CacheCandidate, QueryTemporalBucket
from src.models.cost_signals import CostSignals
from src.models.databricks_misuse import DatabricksMisuseFindings, MisuseFinding
from src.models.migration_complexity import (
    MigrationComplexitySignals,
    UDFRecord,
    StoredProcRecord,
    BinaryColumnRecord,
)
from src.models.availability_signals import AvailabilitySignals
from src.models.query_history import QueryRecord, QueryHistory
from src.models.table_metadata import TableMetadata
from src.models.assessment_payload import AssessmentPayload


class TestAccessPatternSignals:
    """Test AccessPatternSignals model round-trip."""

    def test_round_trip(self):
        """Test model validates itself."""
        signal = AccessPatternSignals(
            platform="mysql",
            read_write_ratio=0.8,
            point_lookup_pct=0.3,
            full_scan_pct=0.1,
            estimated_cacheable_pct=0.15,
            peak_hour_of_day=14,
            peak_day_of_week=1,
            has_burst_pattern=True,
        )
        round_tripped = AccessPatternSignals.model_validate(signal.model_dump())
        assert round_tripped.platform == "mysql"
        assert round_tripped.read_write_ratio == 0.8
        assert round_tripped.has_burst_pattern is True

    def test_cache_candidate_round_trip(self):
        """Test CacheCandidate model round-trip."""
        c = CacheCandidate(
            query_fingerprint="abc123",
            execution_count=100,
            avg_exec_time_ms=50.0,
            avg_rows_returned=10.0,
            data_freshness_hours=24.0,
            estimated_cache_hit_rate=0.8,
            recommended_ttl_seconds=3600,
            cache_type="redis",
        )
        round_tripped = CacheCandidate.model_validate(c.model_dump())
        assert round_tripped.cache_type == "redis"


class TestCostSignals:
    """Test CostSignals model round-trip."""

    def test_round_trip(self):
        """Test model validates itself."""
        signals = CostSignals(
            platform="snowflake",
            compute_units_per_month=100.0,
            compute_unit_name="credit",
            compute_cost_per_unit=28.0,
            estimated_compute_cost_monthly=2800.0,
            storage_gb_total=500.0,
            storage_cost_per_gb=0.023,
            estimated_storage_cost_monthly=11.5,
            bytes_scanned_per_month=1000.0 * 1024 * 1024,
            io_cost_per_mb=0.000005,
            estimated_io_cost_monthly=0.005,
            total_estimated_monthly_cost=2811.505,
            costs_from_billing_api=True,
        )
        round_tripped = CostSignals.model_validate(signals.model_dump())
        assert round_tripped.platform == "snowflake"
        assert round_tripped.total_estimated_monthly_cost == 2811.505

    def test_on_prem_defaults(self):
        """Test on-prem platform has correct defaults."""
        signals = CostSignals(platform="mysql")
        assert signals.has_license_cost is False
        assert signals.costs_from_billing_api is False


class TestMigrationComplexity:
    """Test MigrationComplexitySignals model."""

    def test_round_trip(self):
        """Test model validates itself."""
        mc = MigrationComplexitySignals(
            platform="snowflake",
            udf_count=5,
            udf_records=[UDFRecord(name="my_udf", language="SQL", is_portable=True)],
            stored_proc_count=3,
            stored_proc_records=[StoredProcRecord(name="my_proc", line_count=50, has_loops=True, has_external_calls=False, has_ddl=False, migration_path="sql_udf")],
            binary_column_count=2,
            binary_column_records=[BinaryColumnRecord(table="t1", column="data", data_type="BINARY", migration_path="base64_string")],
            has_unsupported_types=False,
        )
        round_tripped = MigrationComplexitySignals.model_validate(mc.model_dump())
        assert round_tripped.udf_count == 5
        assert round_tripped.stored_proc_count == 3

    def test_non_portable_udf(self):
        """Test UDFRecord non-portable flag."""
        udf = UDFRecord(name="python_udf", language="Python", is_portable=False)
        assert udf.is_portable is False


class TestDatabricksMisuse:
    """Test DatabricksMisuseFindings model."""

    def test_round_trip(self):
        """Test model validates itself."""
        findings = DatabricksMisuseFindings(
            findings=[
                MisuseFinding(
                    finding_type="Cache candidate",
                    severity="high",
                    affected_object="fp123",
                    description="Repeated query",
                    evidence="ran 100 times in 24h",
                    recommendation="Use Redis cache",
                    estimated_monthly_savings_dbu=5.0,
                ),
            ],
            cache_candidate_queries=1,
            total_estimated_wasted_dbu_monthly=5.0,
        )
        round_tripped = DatabricksMisuseFindings.model_validate(findings.model_dump())
        assert round_tripped.cache_candidate_queries == 1
        assert round_tripped.findings[0].finding_type == "Cache candidate"


class TestAvailabilitySignals:
    """Test AvailabilitySignals model."""

    def test_round_trip(self):
        """Test model validates itself."""
        signals = AvailabilitySignals(
            platform="snowflake",
            incidents_last_90d=2,
            avg_incident_duration_minutes=15.0,
            sla_target_pct=99.9,
            sla_actual_pct=99.85,
            rto_minutes=60,
            rpo_minutes=15,
        )
        round_tripped = AvailabilitySignals.model_validate(signals.model_dump())
        assert round_tripped.incidents_last_90d == 2
        assert round_tripped.rto_minutes == 60


class TestQueryHistoryEnhanced:
    """Test enhanced QueryRecord with new fields."""

    def test_new_fields_round_trip(self):
        """Test new QueryRecord fields round-trip."""
        record = QueryRecord(
            query_id="q1",
            database="test_db",
            schema_name="test_schema",
            query_text_fingerprint="abc123",
            query_type="SELECT",
            is_point_lookup=True,
            is_full_scan=False,
            is_write=False,
            cache_hit=True,
            user_type="app_service_account",
            hour_of_day_histogram=[0, 0, 0, 0, 0, 0, 0, 5, 10, 15, 20, 15, 10, 15, 20, 15, 10, 5, 0, 0, 0, 0, 0, 0],
        )
        round_tripped = QueryRecord.model_validate(record.model_dump())
        assert round_tripped.is_point_lookup is True
        assert round_tripped.cache_hit is True
        assert round_tripped.user_type == "app_service_account"
        assert len(round_tripped.hour_of_day_histogram) == 24

    def test_table_metadata_growth_fields(self):
        """Test TableMetadata growth rate fields."""
        from src.models.table_metadata import TableMetadata

        t = TableMetadata(
            database="db",
            schema_name="schema",
            table_name="my_table",
            table_type="TABLE",
            row_count=1000000,
            row_count_30d_ago=750000,
            monthly_growth_rate_pct=33.3,
            is_fast_growing=True,
        )
        assert t.monthly_growth_rate_pct == 33.3
        assert t.is_fast_growing is True


class TestAssessmentPayload:
    """Test AssessmentPayload with new fields."""

    def test_payload_with_new_signals(self):
        """Test payload accepts all new signal types."""
        from src.models.cost_signals import CostSignals

        payload = AssessmentPayload(
            platform="snowflake",
            cost_signals=CostSignals(platform="snowflake"),
            access_patterns=AccessPatternSignals(platform="snowflake"),
            migration_complexity=MigrationComplexitySignals(platform="snowflake"),
            contract_renewal_months=6,
            has_pending_license_increase=False,
            workload_context={"has_multi_region": True},
        )
        round_tripped = AssessmentPayload.model_validate(payload.model_dump())
        assert round_tripped.cost_signals is not None
        assert round_tripped.contract_renewal_months == 6
        assert round_tripped.workload_context["has_multi_region"] is True


class TestQueryRecordPIIProtection:
    """Test QueryRecord PII protection."""

    def test_pii_masked_in_fingerprint(self):
        """Test PII patterns are stripped from fingerprints."""
        record = QueryRecord(
            query_id="q1",
            database="db",
            schema_name="schema",
            query_text_fingerprint="SELECT * FROM users WHERE ssn = '123-45-6789' AND email = 'test@example.com'",
            query_type="SELECT",
        )
        assert "123-45-6789" not in record.query_text_fingerprint
        assert "test@example.com" not in record.query_text_fingerprint
        assert "[REDACTED]" in record.query_text_fingerprint