"""Tests for SnowflakeConnector."""

import pytest
from unittest.mock import patch, MagicMock
from src.connectors.snowflake import SnowflakeConnector


class TestSnowflakeValidateCredentials:
    def test_raises_without_account(self):
        conn = SnowflakeConnector()
        with pytest.raises(ValueError, match="SNOWFLAKE_ACCOUNT"):
            conn.validate_credentials()

    def test_raises_without_user(self):
        conn = SnowflakeConnector(snowflake_account="myaccount")
        with pytest.raises(ValueError, match="SNOWFLAKE_USER"):
            conn.validate_credentials()

    def test_raises_without_password(self):
        conn = SnowflakeConnector(snowflake_account="myaccount", snowflake_user="user")
        mock_sf = MagicMock()
        with patch.dict("sys.modules", {"snowflake": mock_sf, "snowflake.connector": mock_sf}):
            with pytest.raises(ValueError, match="SNOWFLAKE_PASSWORD"):
                conn.validate_credentials()

    def test_succeeds_on_valid_connection(self):
        conn = SnowflakeConnector(
            snowflake_account="myaccount", snowflake_user="user", snowflake_password="pw"
        )
        mock_sf = MagicMock()
        mock_conn = MagicMock()
        mock_sf.connector.connect.return_value = mock_conn
        mock_sf.connector.errors = MagicMock()
        mock_sf.connector.errors.Error = Exception

        with patch.dict("sys.modules", {"snowflake": mock_sf, "snowflake.connector": mock_sf.connector}):
            result = conn.validate_credentials()
        assert result is True


class TestSnowflakeFetchQueryHistory:
    def _make_conn(self, rows, columns):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        mock_cursor.description = [(col,) for col in columns]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn

    def test_returns_query_history(self):
        conn = SnowflakeConnector(
            snowflake_account="acc", snowflake_user="user", snowflake_password="pw"
        )
        cols = ["QUERY_ID", "QUERY_TEXT", "DATABASE_NAME", "SCHEMA_NAME",
                "QUERY_TYPE", "TOTAL_ELAPSED_TIME", "ROWS_PRODUCED",
                "BYTES_SCANNED", "CONCURRENT_CONCURRENCY", "QUERY_FAILURES",
                "QUERY_STATUS", "START_TIME", "END_TIME",
                "IS_CLIENT_QUERY_AGENT_REPORTING", "HAS_OUT_PUT_PARAMS", "SESSION_ID"]
        rows = [
            ("q1", "SELECT * FROM orders", "mydb", "public", "SELECT",
             5000, 100, 10240, 1, 0, "SUCCESS", None, None, False, False, "s1"),
        ]
        mock_conn = self._make_conn(rows, cols)
        with patch.object(conn, "_snowflake_connect", return_value=mock_conn):
            conn._connected = True
            qh = conn.fetch_query_history()
        assert qh.platform == "snowflake"
        assert len(qh.queries) == 1

    def test_empty_returns_empty(self):
        conn = SnowflakeConnector(
            snowflake_account="acc", snowflake_user="user", snowflake_password="pw"
        )
        cols = ["QUERY_ID", "QUERY_TEXT", "DATABASE_NAME", "SCHEMA_NAME",
                "QUERY_TYPE", "TOTAL_ELAPSED_TIME", "ROWS_PRODUCED",
                "BYTES_SCANNED", "CONCURRENT_CONCURRENCY", "QUERY_FAILURES",
                "QUERY_STATUS", "START_TIME", "END_TIME",
                "IS_CLIENT_QUERY_AGENT_REPORTING", "HAS_OUT_PUT_PARAMS", "SESSION_ID"]
        mock_conn = self._make_conn([], cols)
        with patch.object(conn, "_snowflake_connect", return_value=mock_conn):
            conn._connected = True
            qh = conn.fetch_query_history()
        assert qh.total_queries_fetched == 0


class TestSnowflakeFetchTableMetadata:
    def test_returns_table_metadata(self):
        conn = SnowflakeConnector(
            snowflake_account="acc", snowflake_user="user", snowflake_password="pw"
        )
        cols = ["database_name", "schema_name", "table_name", "table_type",
                "row_count", "bytes", "last_altered", "is_materialized"]
        rows = [("mydb", "public", "orders", "TABLE", 1000000, 536870912, None, "N")]
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        mock_cursor.description = [(col,) for col in cols]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch.object(conn, "_snowflake_connect", return_value=mock_conn):
            tm = conn.fetch_table_metadata()
        assert tm.platform == "snowflake"
        assert tm.total_tables_fetched == 1


class TestSnowflakeFetchAccessPatterns:
    def test_returns_access_patterns(self):
        conn = SnowflakeConnector(
            snowflake_account="acc", snowflake_user="user", snowflake_password="pw"
        )
        cols = ["QUERY_TEXT", "QUERY_TYPE", "TOTAL_ELAPSED_TIME", "ROWS_PRODUCED",
                "BYTES_SCANNED", "START_TIME", "IS_CLIENT_QUERY_AGENT_REPORTING", "RESULT_CACHED"]
        rows = [
            ("SELECT * FROM t WHERE id=1", "SELECT", 1000, 1, 8192, None, False, False),
            ("SELECT * FROM t WHERE id=2", "SELECT", 2000, 1, 8192, None, False, False),
        ]
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        mock_cursor.description = [(col,) for col in cols]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch.object(conn, "_snowflake_connect", return_value=mock_conn):
            ap = conn.fetch_access_patterns()
        assert ap.platform == "snowflake"
        assert ap.read_write_ratio == 1.0


class TestSnowflakeFetchMigrationComplexity:
    def test_returns_migration_complexity(self):
        conn = SnowflakeConnector(
            snowflake_account="acc", snowflake_user="user", snowflake_password="pw"
        )
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [
            [],  # UDFs
            [],  # stored procs
            [],  # triggers
            [],  # binary columns
        ]
        mock_cursor.description = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch.object(conn, "_snowflake_connect", return_value=mock_conn):
            mc = conn.fetch_migration_complexity()
        assert mc.platform == "snowflake"
        assert mc.udf_count == 0
        assert mc.stored_proc_count == 0
