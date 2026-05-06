"""Integration tests for connectors — mocked DB, realistic sample data.

For each new connector, tests:
1. Mocks the DB connection (no real credentials needed in CI)
2. Supplies realistic sample rows for each SELECT query
3. Asserts the returned model passes model.model_validate(model.model_dump())
4. Asserts key computed fields are non-None and in expected ranges
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.models.table_metadata import TableMetadata, TableMetadataCollection
from src.models.query_history import QueryHistory, QueryRecord
from src.models.security import SecurityPatterns
from src.models.cost_signals import CostSignals
from src.models.migration_complexity import MigrationComplexitySignals
from src.models.access_patterns import AccessPatternSignals
from src.engine.billing import BillingCalculator


# -- helpers -- #

class _MockCursor:
    """Thin mock that returns pre-seeded rows via fetchall."""

    def __init__(self, rows: list, columns: list | None = None):
        self._rows = rows
        self._columns = columns or [f"c{i}" for i in range(len(rows[0]))] if rows else []

    def execute(self, sql: str, params=None):
        pass

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    @property
    def description(self):
        return [(c,) for c in (self._columns if isinstance(self._columns, list) and self._columns and isinstance(self._columns[0], str) else self._columns)] if self._rows else []


class _MockConn:
    def cursor(self):
        return self._cursor

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class _MockSnowflakeConn(_MockConn):
    def __init__(self, table_rows, query_rows, columns, cost_rows):
        self._table_cursor = _MockCursor(table_rows)
        self._query_cursor = _MockCursor(query_rows, columns)
        self._cost_cursor = _MockCursor(cost_rows)
        self._misc_cursor = _MockCursor([])

    def cursor(self):
        # Return different cursors depending on what's needed
        if not hasattr(self, '_call_count'):
            self._call_count = 0
        self._call_count += 1
        if self._call_count == 1:
            return self._table_cursor
        if self._call_count == 2:
            return self._query_cursor
        if self._call_count == 3:
            return self._cost_cursor
        return self._misc_cursor


# -- Snowflake stale stats (item 7d) -- #

class TestSnowflakeStaleStats:
    """Test is_stale_stats detection via mocked Snowflake table metadata."""

    def test_table_with_recent_analyze_is_not_stale(self):
        """Tables with last_altered within 30 days should have is_stale_stats=False."""
        from datetime import datetime as dt

        recent_date = (dt.now(timezone.utc) - timedelta(days=2)).isoformat()
        recent_rows = [
            ("ANALYTICS", "PUBLIC", "orders", "TABLE", 50000000, 21474836480, recent_date, "N"),
        ]
        from unittest.mock import patch
        from src.connectors.snowflake import SnowflakeConnector

        mock_conn = _MockSnowflakeConn(recent_rows, [], [], [])

        with patch.object(SnowflakeConnector, "_snowflake_connect", return_value=mock_conn):
            conn = SnowflakeConnector(snowflake_account="a", snowflake_user="u", snowflake_password="p")
            conn._connected = True
            tm = conn.fetch_table_metadata()

            validated = TableMetadataCollection.model_validate(tm.model_dump())
            assert validated.total_tables_fetched == 1

            table = validated.tables[0]
            assert table.table_name == "orders"
            assert table.is_stale_stats is False, "Recent table should not be stale"
            assert table.last_analyzed is not None

    def test_table_with_old_analyze_is_stale(self):
        """Tables with last_altered > 30 days ago should have is_stale_stats=True."""
        from datetime import datetime as dt

        old_date = (dt.now(timezone.utc) - timedelta(days=45)).isoformat()
        old_rows = [
            ("ANALYTICS", "PUBLIC", "legacy_table", "TABLE", 1000000, 52428800, old_date, "N"),
        ]
        from unittest.mock import patch
        from src.connectors.snowflake import SnowflakeConnector

        mock_conn = _MockSnowflakeConn(old_rows, [], [], [])

        with patch.object(SnowflakeConnector, "_snowflake_connect", return_value=mock_conn):
            conn = SnowflakeConnector(snowflake_account="a", snowflake_user="u", snowflake_password="p")
            conn._connected = True
            tm = conn.fetch_table_metadata()

            validated = TableMetadataCollection.model_validate(tm.model_dump())
            table = validated.tables[0]
            assert table.table_name == "legacy_table"
            assert table.is_stale_stats is True, "Old table should be stale"

    def test_table_with_no_analyze_date_is_not_stale(self):
        """Tables with NULL last_altered should have is_stale_stats=False (never analyzed)."""
        none_rows = [
            ("ANALYTICS", "PUBLIC", "new_table", "TABLE", 100, 4096, None, "N"),
        ]
        from unittest.mock import patch
        from src.connectors.snowflake import SnowflakeConnector

        mock_conn = _MockSnowflakeConn(none_rows, [], [], [])

        with patch.object(SnowflakeConnector, "_snowflake_connect", return_value=mock_conn):
            conn = SnowflakeConnector(snowflake_account="a", snowflake_user="u", snowflake_password="p")
            conn._connected = True
            tm = conn.fetch_table_metadata()

            validated = TableMetadataCollection.model_validate(tm.model_dump())
            table = validated.tables[0]
            assert table.table_name == "new_table"
            assert table.is_stale_stats is False
            assert table.last_analyzed is None


# -- Shared stale stats logic (item 7d) -- #

class TestStaleStatsLogic:
    """Test _is_stats_stale helper used by all connectors."""

    def test_recent_analyze_not_stale(self):
        """last_analyzed 2 days ago → not stale."""
        from src.connectors.base import AbstractBaseConnector
        recent = datetime.now(timezone.utc) - timedelta(days=2)
        assert AbstractBaseConnector._is_stats_stale(recent) is False

    def test_old_analyze_is_stale(self):
        """last_analyzed 45 days ago → stale."""
        from src.connectors.base import AbstractBaseConnector
        old = datetime.now(timezone.utc) - timedelta(days=45)
        assert AbstractBaseConnector._is_stats_stale(old) is True

    def test_null_analyze_not_stale(self):
        """Never analyzed → not stale (cannot determine)."""
        from src.connectors.base import AbstractBaseConnector
        assert AbstractBaseConnector._is_stats_stale(None) is False

    def test_boundary_30_days(self):
        """Exactly 30 days → not stale (must be > 30)."""
        from src.connectors.base import AbstractBaseConnector
        exactly = datetime.now(timezone.utc) - timedelta(days=30)
        assert AbstractBaseConnector._is_stats_stale(exactly) is False
        just_over = datetime.now(timezone.utc) - timedelta(days=31)
        assert AbstractBaseConnector._is_stats_stale(just_over) is True

    @pytest.mark.skipif(
        True,
        reason="google-cloud-bigquery not installed",
    )
    def test_bigquery_connector_stale_detection(self):
        """BigQuery connector uses stale detection logic for modified timestamps."""
        from src.connectors.bigquery import BigQueryConnector
        old = datetime.now(timezone.utc) - timedelta(days=60)
        recent = datetime.now(timezone.utc) - timedelta(days=5)
        assert BigQueryConnector._is_stats_stale(old) is True
        assert BigQueryConnector._is_stats_stale(recent) is False


# -- Connector model round-trips (item 9) -- #

class TestConnectorModelRoundTrips:
    """Assert returned models pass model_validate(model_dump()) and key fields."""

    def test_query_history_round_trip(self):
        """QueryHistory with realistic data validates correctly."""
        qh = QueryHistory(
            platform="snowflake",
            queries=[
                QueryRecord(
                    query_id="q1",
                    database="db1",
                    schema_name="schema1",
                    query_text_fingerprint="abc123",
                    query_type="SELECT",
                    avg_exec_time_ms=150.5,
                    total_executions=1000,
                    avg_rows_returned=50.0,
                    avg_bytes_scanned=5242880.0,
                    last_executed=datetime.now(),
                    first_executed=datetime.now() - timedelta(days=30),
                ),
            ],
            total_queries_fetched=100,
            avg_concurrency=5.0,
            peak_concurrency=20,
        )
        validated = QueryHistory.model_validate(qh.model_dump())
        assert validated.platform == "snowflake"
        assert validated.total_queries_fetched == 100
        assert validated.avg_concurrency == 5.0
        assert validated.peak_concurrency == 20
        assert validated.queries[0].avg_exec_time_ms == 150.5

    def test_security_patterns_round_trip(self):
        """SecurityPatterns with findings validates correctly."""
        sp = SecurityPatterns(
            platform="snowflake",
            findings=[],
            rbac_enabled=True,
            rbac_depth=3,
            encryption_at_rest=True,
            encryption_in_transit=True,
            audit_logging_enabled=True,
            row_level_security=True,
            sso_integration=True,
            mfa_required=True,
            compliance_certifications=["SOC2", "HIPAA"],
            total_findings=0,
            high_severity_count=0,
            critical_severity_count=0,
            active_users_last_30d=15,
            active_service_accounts_last_30d=3,
        )
        sp.findings = []  # clear the bad findings
        validated = SecurityPatterns.model_validate(sp.model_dump())
        assert validated.rbac_enabled is True
        assert validated.active_users_last_30d == 15
        assert validated.active_service_accounts_last_30d == 3

    def test_cost_signals_round_trip(self):
        """CostSignals with known values validates correctly."""
        cs = CostSignals(
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
        validated = CostSignals.model_validate(cs.model_dump())
        assert validated.total_estimated_monthly_cost == 2811.505
        assert validated.costs_from_billing_api is True

    def test_migration_complexity_round_trip(self):
        """MigrationComplexitySignals validates correctly."""
        mc = MigrationComplexitySignals(
            platform="snowflake",
            udf_count=3,
            stored_proc_count=2,
            trigger_count=1,
            cross_db_join_count=4,
            binary_column_count=0,
            estimated_migration_weeks=6.0,
            has_unsupported_types=False,
        )
        validated = MigrationComplexitySignals.model_validate(mc.model_dump())
        assert validated.udf_count == 3
        assert validated.cross_db_join_count == 4
        assert validated.estimated_migration_weeks == 6.0

    def test_access_patterns_round_trip(self):
        """AccessPatternSignals validates correctly."""
        ap = AccessPatternSignals(
            platform="snowflake",
            read_write_ratio=0.8,
            point_lookup_pct=0.3,
            full_scan_pct=0.1,
            estimated_cacheable_pct=0.15,
            peak_hour_of_day=14,
            off_peak_query_pct=0.4,
            has_burst_pattern=True,
        )
        validated = AccessPatternSignals.model_validate(ap.model_dump())
        assert validated.read_write_ratio == 0.8
        assert validated.point_lookup_pct == 0.3
        assert validated.has_burst_pattern is True


# -- Billing with CostSignals (item 9) -- #

class TestBillingWithCostSignals:
    """Test billing calculator produces real values (not proxy) when CostSignals is provided."""

    def test_cost_delta_uses_actual_cost_not_proxy(self):
        """When CostSignals is provided, current_estimated_monthly_cost should match the signal."""
        from src.models.cost_signals import CostSignals
        from src.engine.billing import BillingCalculator

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
        calc = BillingCalculator()
        delta = calc.calculate_cost_delta("snowflake", "Snowflake", cost_signals=signals)

        # Key assertion: cost source must be actual, not proxy
        assert delta["cost_data_source"] == "actual_signals"
        # The current cost must exactly match the signal total
        assert delta["current_estimated_monthly_cost"] == pytest.approx(2811.51, abs=0.01)
        # Lakebase cost should be non-zero
        assert delta["projected_lakebase_cost"] > 0
        # Savings percentage should be computed
        assert "savings_pct" in delta

    def test_cost_delta_falls_back_to_proxy_without_signals(self):
        """Without CostSignals, billing should use proxy estimates."""
        from dataclasses import dataclass

        @dataclass
        class MockScore:
            identifier: str; raw_score: float; adjusted_score: float; priority: str

        calc = BillingCalculator()
        scores = [MockScore("q1", 50.0, 50.0, "Hold") for _ in range(5)]
        delta = calc.calculate_cost_delta("snowflake", "Snowflake", cost_signals=None, scores=scores)

        assert delta["cost_data_source"] == "proxy_estimates"
