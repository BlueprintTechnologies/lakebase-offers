"""Tests for PostgresConnector."""

import pytest
from unittest.mock import patch, MagicMock
from src.connectors.postgres import PostgresConnector


class TestPostgresValidateCredentials:
    def test_raises_without_host(self):
        conn = PostgresConnector()
        with pytest.raises(ValueError, match="PG_HOST"):
            conn.validate_credentials()

    def test_raises_without_user(self):
        conn = PostgresConnector(pg_host="localhost")
        with pytest.raises(ValueError, match="PG_USER"):
            conn.validate_credentials()

    def test_raises_on_import_error(self):
        conn = PostgresConnector(pg_host="localhost", pg_user="user")
        with patch.dict("sys.modules", {"psycopg2": None}):
            with pytest.raises(ImportError):
                conn.validate_credentials()

    def test_raises_on_connection_failure(self):
        import psycopg2
        conn = PostgresConnector(pg_host="localhost", pg_user="user")
        with patch("psycopg2.connect", side_effect=psycopg2.OperationalError("fail")):
            with pytest.raises(ConnectionError):
                conn.validate_credentials()

    def test_succeeds_on_valid_connection(self):
        conn = PostgresConnector(pg_host="localhost", pg_user="user")
        mock_conn = MagicMock()
        with patch("psycopg2.connect", return_value=mock_conn):
            result = conn.validate_credentials()
        assert result is True


class TestPostgresClassifyQuery:
    @pytest.mark.parametrize("query,expected", [
        ("SELECT id FROM t", "SELECT"),
        ("INSERT INTO t VALUES (1)", "INSERT"),
        ("UPDATE t SET x=1", "UPDATE"),
        ("DELETE FROM t", "DELETE"),
        ("CREATE TABLE t (id INT)", "DDL"),
        ("DROP TABLE t", "DDL"),
        ("ALTER TABLE t ADD col INT", "DDL"),
        ("TRUNCATE TABLE t", "DDL"),
        ("CALL my_proc()", "OTHER"),
        ("", "OTHER"),
    ])
    def test_classify(self, query, expected):
        assert PostgresConnector._classify_postgres_query(query) == expected


class TestPostgresFetchQueryHistory:
    def test_fetch_returns_query_history(self):
        conn = PostgresConnector(pg_host="localhost", pg_user="user")
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("q1", "SELECT * FROM orders", "testdb", "testuser", 50,
             5000.0, 100.0, 500, 1000, 200, 0, 0),
        ]
        mock_cursor.description = [
            ("queryid",), ("query",), ("datname",), ("usename",), ("calls",),
            ("total_exec_time",), ("mean_exec_time",), ("rows",),
            ("shared_blks_hit",), ("shared_blks_read",), ("temp_blks_written",), ("wal_bytes",),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch("psycopg2.connect", return_value=mock_conn):
            qh = conn.fetch_query_history()
        assert qh.platform == "postgres"
        assert len(qh.queries) == 1
        assert qh.total_queries_fetched == 1

    def test_fetch_empty_returns_empty_history(self):
        conn = PostgresConnector(pg_host="localhost", pg_user="user")
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = [
            ("queryid",), ("query",), ("datname",), ("usename",), ("calls",),
            ("total_exec_time",), ("mean_exec_time",), ("rows",),
            ("shared_blks_hit",), ("shared_blks_read",), ("temp_blks_written",), ("wal_bytes",),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch("psycopg2.connect", return_value=mock_conn):
            qh = conn.fetch_query_history()
        assert qh.total_queries_fetched == 0


class TestPostgresFetchTableMetadata:
    def test_fetch_table_metadata(self):
        conn = PostgresConnector(pg_host="localhost", pg_user="user", pg_database="mydb")
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("public", "orders", "owner", 536870912, 1000000, None, False),
        ]
        mock_cursor.description = [
            ("schemaname",), ("tablename",), ("tableowner",),
            ("table_size_bytes",), ("row_count",), ("last_analyze",), ("is_partition_table",),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch("psycopg2.connect", return_value=mock_conn):
            tm = conn.fetch_table_metadata()
        assert tm.platform == "postgres"
        assert tm.total_tables_fetched == 1


class TestPostgresFetchConcurrencySignals:
    def test_low_pressure(self):
        conn = PostgresConnector(pg_host="localhost", pg_user="user")
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch("psycopg2.connect", return_value=mock_conn):
            cs = conn.fetch_concurrency_signals()
        assert cs.platform == "postgres"
        assert cs.avg_concurrent_queries == 5.0
        assert cs.scaling_pressure == "low"

    def test_high_pressure(self):
        conn = PostgresConnector(pg_host="localhost", pg_user="user")
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (15,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch("psycopg2.connect", return_value=mock_conn):
            cs = conn.fetch_concurrency_signals()
        assert cs.scaling_pressure == "medium"


class TestPostgresFetchCostSignals:
    def test_returns_cost_signals(self):
        conn = PostgresConnector(pg_host="localhost", pg_user="user")
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("10 GB",)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch("psycopg2.connect", return_value=mock_conn):
            cost = conn.fetch_cost_signals()
        assert cost.platform == "postgres"
        assert cost.costs_from_billing_api is False
        assert cost.storage_gb_total == pytest.approx(10.0)

    def test_rds_host_uses_cloud_estimate(self):
        conn = PostgresConnector(pg_host="mydb.rds.amazonaws.com", pg_user="user")
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("5 GB",)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch("psycopg2.connect", return_value=mock_conn):
            cost = conn.fetch_cost_signals()
        assert cost.estimated_compute_cost_monthly > 100.0


class TestPostgresFetchSecurityPatterns:
    def test_returns_security_patterns(self):
        conn = PostgresConnector(pg_host="localhost", pg_user="user")
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        with patch("psycopg2.connect", return_value=mock_conn):
            sp = conn.fetch_security_patterns()
        assert sp.platform == "postgres"
        assert sp.rbac_enabled is True
        assert sp.encryption_in_transit is True
