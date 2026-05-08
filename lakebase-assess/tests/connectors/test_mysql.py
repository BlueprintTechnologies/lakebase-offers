"""Tests for MySQLConnector."""

import pytest
from unittest.mock import patch, MagicMock
from src.connectors.mysql import MySQLConnector


class TestMySQLValidateCredentials:
    def test_raises_without_host(self):
        conn = MySQLConnector()
        with pytest.raises(ValueError, match="MYSQL_HOST"):
            conn.validate_credentials()

    def test_raises_without_user(self):
        conn = MySQLConnector(mysql_host="localhost")
        with pytest.raises(ValueError, match="MYSQL_USER"):
            conn.validate_credentials()


class TestMySQLClassifyQuery:
    @pytest.mark.parametrize("query,expected", [
        ("SELECT id FROM t", "SELECT"),
        ("select * from t", "SELECT"),
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
        assert MySQLConnector._classify_query(query) == expected


class TestMySQLIsPointLookup:
    def test_where_id_equals_param(self):
        assert MySQLConnector._is_point_lookup("SELECT * FROM t WHERE id = ?") is True

    def test_where_pk_id_equals_param(self):
        assert MySQLConnector._is_point_lookup("SELECT * FROM t WHERE user_id = ?") is True

    def test_where_id_equals_param_no_space(self):
        assert MySQLConnector._is_point_lookup("SELECT * FROM t WHERE id=?") is True

    def test_full_scan_not_point_lookup(self):
        assert MySQLConnector._is_point_lookup("SELECT * FROM t") is False

    def test_range_query_not_point_lookup(self):
        assert MySQLConnector._is_point_lookup("SELECT * FROM t WHERE created_at > '2024-01-01'") is False


class TestMySQLDetectUserType:
    def test_service_account(self):
        result = MySQLConnector._detect_user_type("-- from service_account app")
        assert result == "app_service_account"

    def test_etl_user(self):
        result = MySQLConnector._detect_user_type("-- ETL batch job")
        assert result == "etl_job"

    def test_admin_user(self):
        result = MySQLConnector._detect_user_type("-- admin query")
        assert result == "admin"

    def test_unknown_user(self):
        result = MySQLConnector._detect_user_type("SELECT id FROM users")
        assert result == ""


class TestMySQLConnectFetchQueryHistory:
    def _make_mock_conn(self, digest_rows, digest_columns):
        mock_cursor = MagicMock()
        # availability check uses execute (no fetchall), main query is the first fetchall
        mock_cursor.fetchall.side_effect = [
            digest_rows,   # main query fetchall
        ]
        mock_cursor.description = [(col,) for col in digest_columns]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn

    def test_fetch_with_digest_table(self):
        conn = MySQLConnector(mysql_host="localhost", mysql_user="user")
        cols = ["DIGEST_TEXT", "SCHEMA_NAME", "COUNT_STAR", "total_exec_ms",
                "min_exec_ms", "max_exec_ms", "SUM_ROWS_EXAMINED", "SUM_ROWS_SENT",
                "SUM_NO_GOOD_INDEX_USED", "SUM_NO_INDEX_USED", "FIRST_SEEN", "LAST_SEEN"]
        rows = [
            ("SELECT * FROM orders", "production", 100, 50000.0, 100.0, 2000.0,
             500, 50, 0, 0, "2026-04-01 10:00:00", "2026-05-01 10:00:00"),
        ]
        mock_conn = self._make_mock_conn(rows, cols)
        with patch.object(conn, "_mysql_connect", return_value=mock_conn):
            qh = conn.fetch_query_history()
        assert qh.platform == "mysql"
        assert len(qh.queries) == 1
        assert qh.queries[0].total_executions == 100

    def test_fetch_returns_empty_on_no_rows(self):
        conn = MySQLConnector(mysql_host="localhost", mysql_user="user")
        cols = ["DIGEST_TEXT", "SCHEMA_NAME", "COUNT_STAR", "total_exec_ms",
                "min_exec_ms", "max_exec_ms", "SUM_ROWS_EXAMINED", "SUM_ROWS_SENT",
                "SUM_NO_GOOD_INDEX_USED", "SUM_NO_INDEX_USED", "FIRST_SEEN", "LAST_SEEN"]
        mock_conn = self._make_mock_conn([], cols)
        with patch.object(conn, "_mysql_connect", return_value=mock_conn):
            qh = conn.fetch_query_history()
        assert qh.total_queries_fetched == 0


class TestMySQLFetchTableMetadata:
    def test_fetch_table_metadata(self):
        conn = MySQLConnector(mysql_host="localhost", mysql_user="user")
        table_cols = ["TABLE_SCHEMA", "TABLE_NAME", "TABLE_TYPE", "TABLE_ROWS",
                      "DATA_LENGTH", "INDEX_LENGTH", "CREATE_TIME", "UPDATE_TIME", "ENGINE"]
        table_rows = [
            ("production", "orders", "BASE TABLE", 1000000, 536870912, 0, None, "2026-04-01", "InnoDB"),
        ]
        col_cols = ["TABLE_SCHEMA", "TABLE_NAME", "COLUMN_NAME", "DATA_TYPE",
                    "IS_NULLABLE", "COLUMN_KEY", "COLUMN_TYPE"]
        col_rows = []

        mock_cursor = MagicMock()
        call_count = {"n": 0}

        def fetchall():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return table_rows
            return col_rows

        mock_cursor.fetchall = fetchall
        mock_cursor.description = [(col,) for col in table_cols]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(conn, "_mysql_connect", return_value=mock_conn):
            tm = conn.fetch_table_metadata()

        assert tm.platform == "mysql"
        assert tm.total_tables_fetched == 1


class TestMySQLFetchConcurrencySignals:
    def test_low_active_connections(self):
        conn = MySQLConnector(mysql_host="localhost", mysql_user="user")
        mock_cursor = MagicMock()
        call_count = {"n": 0}

        def fetchall():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return [("Threads_connected", "5"), ("Threads_running", "2")]
            return []

        def fetchone():
            return ("Questions", "10000")

        mock_cursor.fetchall = fetchall
        mock_cursor.fetchone = fetchone
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock the PROCESSLIST query
        mock_cursor.fetchone = MagicMock(side_effect=[("Questions", "10000"), (5,)])

        with patch.object(conn, "_mysql_connect", return_value=mock_conn):
            cs = conn.fetch_concurrency_signals()

        assert cs.platform == "mysql"
        assert cs.scaling_pressure in ("low", "medium", "high")


class TestMySQLFetchCostSignals:
    def test_returns_cost_signals(self):
        conn = MySQLConnector(mysql_host="localhost", mysql_user="user")
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            (50.0,),   # storage_gb query
            (1000000,), # total_queries
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(conn, "_mysql_connect", return_value=mock_conn):
            cost = conn.fetch_cost_signals()

        assert cost.platform == "mysql"
        assert cost.storage_gb_total == 50.0
        assert cost.costs_from_billing_api is False

    def test_enterprise_license_detected(self):
        conn = MySQLConnector(mysql_host="localhost", mysql_user="user",
                              mysql_edition="Enterprise")
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [(10.0,), (0,)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(conn, "_mysql_connect", return_value=mock_conn):
            cost = conn.fetch_cost_signals()

        assert cost.has_license_cost is True
        assert cost.license_type == "enterprise"


class TestMySQLFetchSecurityPatterns:
    def test_returns_security_patterns(self):
        conn = MySQLConnector(mysql_host="localhost", mysql_user="user")
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [
            [("GRANT SELECT ON *.* TO 'user'@'%'",)],  # USER_PRIVILEGES
            [("GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost'",)],  # GRANTS
        ]
        mock_cursor.fetchone.side_effect = [
            ("require_secure_transport", "ON"),   # SSL
            ("innodb_encrypt_tables", "ON"),       # encryption
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(conn, "_mysql_connect", return_value=mock_conn):
            with patch.object(conn, "_is_mariadb", return_value=False):
                sp = conn.fetch_security_patterns()

        assert sp.platform == "mysql"
        assert sp.rbac_enabled is True
