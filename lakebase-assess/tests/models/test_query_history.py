"""Tests for QueryRecord and QueryHistory models."""

import pytest
from datetime import datetime
from src.models.query_history import QueryRecord, QueryHistory


class TestQueryRecord:
    def test_basic_creation(self):
        qr = QueryRecord(
            query_id="q1", database="db", schema_name="s",
            query_text_fingerprint="SELECT 1", query_type="SELECT",
        )
        assert qr.query_id == "q1"
        assert qr.query_type == "SELECT"

    def test_pii_stripped_from_fingerprint(self):
        qr = QueryRecord(
            query_id="q1", database="db", schema_name="s",
            query_text_fingerprint="WHERE email = user@example.com",
            query_type="SELECT",
        )
        assert "user@example.com" not in qr.query_text_fingerprint
        assert "[REDACTED]" in qr.query_text_fingerprint

    def test_ssn_stripped(self):
        qr = QueryRecord(
            query_id="q1", database="db", schema_name="s",
            query_text_fingerprint="WHERE ssn = 123-45-6789",
            query_type="SELECT",
        )
        assert "123-45-6789" not in qr.query_text_fingerprint

    def test_fingerprint_truncated_at_500(self):
        long_text = "SELECT " + "x" * 600
        qr = QueryRecord(
            query_id="q1", database="db", schema_name="s",
            query_text_fingerprint=long_text, query_type="SELECT",
        )
        assert len(qr.query_text_fingerprint) <= 500

    def test_defaults(self):
        qr = QueryRecord(
            query_id="q1", database="db", schema_name="s",
            query_text_fingerprint="SELECT 1", query_type="SELECT",
        )
        assert qr.total_executions == 1
        assert qr.has_udf is False
        assert qr.has_stored_procedure is False
        assert qr.is_real_time is False
        assert qr.is_customer_facing is False
        assert qr.timeout_count == 0
        assert qr.error_count == 0
        assert qr.cache_hit is False
        assert qr.is_point_lookup is False
        assert qr.is_full_scan is False
        assert qr.is_write is False
        assert qr.table_names == []
        assert qr.hour_of_day_histogram == []

    def test_optional_fields_none(self):
        qr = QueryRecord(
            query_id="q1", database="db", schema_name="s",
            query_text_fingerprint="SELECT 1", query_type="SELECT",
        )
        assert qr.avg_exec_time_ms is None
        assert qr.avg_rows_returned is None
        assert qr.avg_bytes_scanned is None
        assert qr.last_executed is None
        assert qr.first_executed is None

    def test_datetime_fields(self):
        now = datetime.now()
        qr = QueryRecord(
            query_id="q1", database="db", schema_name="s",
            query_text_fingerprint="SELECT 1", query_type="SELECT",
            first_executed=now, last_executed=now,
        )
        assert qr.first_executed == now
        assert qr.last_executed == now

    def test_ip_address_stripped(self):
        qr = QueryRecord(
            query_id="q1", database="db", schema_name="s",
            query_text_fingerprint="WHERE ip = '192.168.1.1'",
            query_type="SELECT",
        )
        assert "192.168.1.1" not in qr.query_text_fingerprint

    def test_password_stripped(self):
        qr = QueryRecord(
            query_id="q1", database="db", schema_name="s",
            query_text_fingerprint="WHERE password=secret123",
            query_type="SELECT",
        )
        assert "secret123" not in qr.query_text_fingerprint


class TestQueryHistory:
    def _make_qr(self, **overrides):
        defaults = dict(
            query_id="q1", database="db", schema_name="s",
            query_text_fingerprint="SELECT 1", query_type="SELECT",
        )
        defaults.update(overrides)
        return QueryRecord(**defaults)

    def test_basic_creation(self):
        qh = QueryHistory(platform="snowflake", queries=[])
        assert qh.platform == "snowflake"
        assert qh.queries == []

    def test_has_heavy_udf_true(self):
        qr = self._make_qr(has_udf=True)
        qh = QueryHistory(platform="test", queries=[qr])
        assert qh.has_heavy_udf is True

    def test_has_heavy_udf_false(self):
        qr = self._make_qr(has_udf=False)
        qh = QueryHistory(platform="test", queries=[qr])
        assert qh.has_heavy_udf is False

    def test_has_stored_procs_true(self):
        qr = self._make_qr(has_stored_procedure=True)
        qh = QueryHistory(platform="test", queries=[qr])
        assert qh.has_stored_procs is True

    def test_has_real_time_queries_true(self):
        qr = self._make_qr(is_real_time=True)
        qh = QueryHistory(platform="test", queries=[qr])
        assert qh.has_real_time_queries is True

    def test_has_customer_facing_true(self):
        qr = self._make_qr(is_customer_facing=True)
        qh = QueryHistory(platform="test", queries=[qr])
        assert qh.has_customer_facing is True

    def test_has_timeouts_true(self):
        qr = self._make_qr(timeout_count=2)
        qh = QueryHistory(platform="test", queries=[qr])
        assert qh.has_timeouts is True

    def test_has_errors_true(self):
        qr = self._make_qr(error_count=1)
        qh = QueryHistory(platform="test", queries=[qr])
        assert qh.has_errors is True

    def test_all_properties_false_when_empty(self):
        qh = QueryHistory(platform="test", queries=[])
        assert qh.has_heavy_udf is False
        assert qh.has_stored_procs is False
        assert qh.has_real_time_queries is False
        assert qh.has_customer_facing is False
        assert qh.has_timeouts is False
        assert qh.has_errors is False

    def test_total_queries_fetched(self):
        queries = [self._make_qr(query_id=f"q{i}") for i in range(5)]
        qh = QueryHistory(platform="test", queries=queries, total_queries_fetched=5)
        assert qh.total_queries_fetched == 5

    def test_unique_databases(self):
        qh = QueryHistory(platform="test", queries=[], unique_databases=["db1", "db2"])
        assert len(qh.unique_databases) == 2
