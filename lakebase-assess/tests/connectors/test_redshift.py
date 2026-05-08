"""Tests for RedshiftConnector."""

import pytest
from unittest.mock import patch, MagicMock
from src.connectors.redshift import RedshiftConnector


class TestRedshiftValidateCredentials:
    def test_raises_without_cluster_id(self):
        conn = RedshiftConnector()
        with pytest.raises(ValueError, match="REDSHIFT_CLUSTER_ID"):
            conn.validate_credentials()

    def test_raises_without_user(self):
        conn = RedshiftConnector(redshift_cluster_id="mycluster")
        with pytest.raises(ValueError, match="REDSHIFT_USER"):
            conn.validate_credentials()

    def test_raises_without_password(self):
        conn = RedshiftConnector(redshift_cluster_id="mycluster", redshift_user="admin")
        mock_import = MagicMock()
        with patch.dict("sys.modules", {"psycopg2": mock_import}):
            with pytest.raises(ValueError, match="REDSHIFT_PASSWORD"):
                conn.validate_credentials()

    def test_raises_on_connection_failure(self):
        import psycopg2
        conn = RedshiftConnector(
            redshift_cluster_id="mycluster", redshift_user="admin", redshift_password="pw"
        )
        with patch("psycopg2.connect", side_effect=psycopg2.OperationalError("fail")):
            with pytest.raises(ConnectionError):
                conn.validate_credentials()

    def test_succeeds_on_valid_connection(self):
        conn = RedshiftConnector(
            redshift_cluster_id="mycluster", redshift_user="admin", redshift_password="pw"
        )
        mock_conn = MagicMock()
        with patch("psycopg2.connect", return_value=mock_conn):
            result = conn.validate_credentials()
        assert result is True


class TestRedshiftFetchQueryHistory:
    def test_returns_query_history(self):
        conn = RedshiftConnector(
            redshift_cluster_id="mycluster", redshift_user="admin", redshift_password="pw"
        )
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("q1", "SELECT", "mydb", "public", "user1", None, None,
             50000, 5000, 100, "SELECT * FROM orders", 0, 0, None, None),
        ]
        mock_cursor.description = [
            ("queryid",), ("query",), ("database",), ("schema",), ("userid",),
            ("starttime",), ("endtime",), ("total_time",), ("max_query_time",),
            ("rows",), ("query_text",), ("aborted",), ("segment",), ("phase",), ("node",),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch("psycopg2.connect", return_value=mock_conn):
            qh = conn.fetch_query_history()
        assert qh.platform == "redshift"
        assert len(qh.queries) == 1

    def test_empty_rows(self):
        conn = RedshiftConnector(
            redshift_cluster_id="mycluster", redshift_user="admin", redshift_password="pw"
        )
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = [
            ("queryid",), ("query",), ("database",), ("schema",), ("userid",),
            ("starttime",), ("endtime",), ("total_time",), ("max_query_time",),
            ("rows",), ("query_text",), ("aborted",), ("segment",), ("phase",), ("node",),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch("psycopg2.connect", return_value=mock_conn):
            qh = conn.fetch_query_history()
        assert qh.total_queries_fetched == 0


class TestRedshiftFetchSecurityPatterns:
    def test_returns_security_patterns(self):
        conn = RedshiftConnector(
            redshift_cluster_id="mycluster", redshift_user="admin", redshift_password="pw"
        )
        sp = conn.fetch_security_patterns()
        assert sp.platform == "redshift"
        assert sp.rbac_enabled is True
        assert sp.encryption_at_rest is True
        assert "SOC2" in sp.compliance_certifications

    def test_two_findings(self):
        conn = RedshiftConnector(
            redshift_cluster_id="mycluster", redshift_user="admin", redshift_password="pw"
        )
        sp = conn.fetch_security_patterns()
        assert sp.total_findings == 2
