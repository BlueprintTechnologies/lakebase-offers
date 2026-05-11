"""Tests for AssessmentPayload."""

import pytest
from src.models.assessment_payload import AssessmentPayload
from src.models.query_history import QueryHistory, QueryRecord
from src.models.table_metadata import TableMetadata, TableMetadataCollection
from src.models.concurrency import ConcurrencySignals
from src.models.security import SecurityPatterns, SecurityFinding
from src.models.cost_signals import CostSignals


def _make_payload(**kwargs) -> AssessmentPayload:
    return AssessmentPayload(platform="snowflake", **kwargs)


class TestAssessmentPayloadDefaults:
    def test_default_platform(self):
        p = _make_payload()
        assert p.platform == "snowflake"

    def test_default_query_history_empty(self):
        p = _make_payload()
        assert p.query_history.platform == ""

    def test_default_table_metadata_empty(self):
        p = _make_payload()
        assert p.table_metadata.platform == ""

    def test_optional_fields_none(self):
        p = _make_payload()
        assert p.concurrency_signals is None
        assert p.security_patterns is None
        assert p.cost_signals is None
        assert p.access_patterns is None
        assert p.migration_complexity is None

    def test_contract_renewal_months_default(self):
        p = _make_payload()
        assert p.contract_renewal_months is None

    def test_has_pending_license_increase_default(self):
        p = _make_payload()
        assert p.has_pending_license_increase is False


class TestAssessmentPayloadProperties:
    def _qh_with_udf(self):
        return QueryHistory(
            platform="snowflake",
            queries=[
                QueryRecord(
                    query_id="q1", database="db", schema_name="s",
                    query_text_fingerprint="fp", query_type="SELECT",
                    has_udf=True,
                )
            ],
        )

    def test_has_heavy_udf(self):
        p = AssessmentPayload(platform="snowflake", query_history=self._qh_with_udf())
        assert p.has_heavy_udf is True

    def test_has_stored_procs(self):
        qh = QueryHistory(
            platform="snowflake",
            queries=[
                QueryRecord(
                    query_id="q1", database="db", schema_name="s",
                    query_text_fingerprint="fp", query_type="SELECT",
                    has_stored_procedure=True,
                )
            ],
        )
        p = AssessmentPayload(platform="snowflake", query_history=qh)
        assert p.has_stored_procs is True

    def test_has_pii_sensitive_data(self):
        tm = TableMetadataCollection(
            platform="snowflake",
            tables=[
                TableMetadata(
                    database="db", schema_name="s", table_name="pii_users",
                    table_type="TABLE", is_sensitive=True,
                )
            ],
        )
        p = AssessmentPayload(platform="snowflake", table_metadata=tm)
        assert p.has_pii_sensitive_data is True

    def test_total_tables(self):
        tm = TableMetadataCollection(
            platform="snowflake",
            tables=[
                TableMetadata(database="db", schema_name="s", table_name="t1", table_type="TABLE"),
                TableMetadata(database="db", schema_name="s", table_name="t2", table_type="TABLE"),
            ],
        )
        p = AssessmentPayload(platform="snowflake", table_metadata=tm)
        assert p.total_tables == 2

    def test_total_queries(self):
        qh = QueryHistory(
            platform="snowflake",
            queries=[
                QueryRecord(query_id="q1", database="db", schema_name="s",
                            query_text_fingerprint="fp", query_type="SELECT"),
                QueryRecord(query_id="q2", database="db", schema_name="s",
                            query_text_fingerprint="fp2", query_type="SELECT"),
            ],
        )
        p = AssessmentPayload(platform="snowflake", query_history=qh)
        assert p.total_queries == 2

    def test_needs_scaling_with_high_pressure(self):
        cs = ConcurrencySignals(platform="snowflake", scaling_pressure="high")
        p = AssessmentPayload(platform="snowflake", concurrency_signals=cs)
        assert p.needs_scaling is True

    def test_needs_scaling_with_low_pressure(self):
        cs = ConcurrencySignals(platform="snowflake", scaling_pressure="low")
        p = AssessmentPayload(platform="snowflake", concurrency_signals=cs)
        assert p.needs_scaling is False

    def test_needs_scaling_without_signals(self):
        p = _make_payload()
        assert p.needs_scaling is False

    def test_has_security_issues_with_critical(self):
        sp = SecurityPatterns(
            platform="snowflake",
            findings=[
                SecurityFinding(
                    category="RBAC", severity="critical",
                    description="Critical finding",
                )
            ],
            critical_severity_count=1,
        )
        p = AssessmentPayload(platform="snowflake", security_patterns=sp)
        assert p.has_security_issues is True

    def test_has_security_issues_without_signals(self):
        p = _make_payload()
        assert p.has_security_issues is False

    def test_has_timeouts(self):
        qh = QueryHistory(
            platform="snowflake",
            queries=[
                QueryRecord(
                    query_id="q1", database="db", schema_name="s",
                    query_text_fingerprint="fp", query_type="SELECT",
                    timeout_count=1,
                )
            ],
        )
        p = AssessmentPayload(platform="snowflake", query_history=qh)
        assert p.has_timeouts is True

    def test_has_errors(self):
        qh = QueryHistory(
            platform="snowflake",
            queries=[
                QueryRecord(
                    query_id="q1", database="db", schema_name="s",
                    query_text_fingerprint="fp", query_type="SELECT",
                    error_count=2,
                )
            ],
        )
        p = AssessmentPayload(platform="snowflake", query_history=qh)
        assert p.has_errors is True
