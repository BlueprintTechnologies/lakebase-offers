"""Tests for VerticaConnector."""

import pytest
from unittest.mock import patch, MagicMock
from src.connectors.vertica import VerticaConnector


class TestVerticaValidateCredentials:
    def test_raises_without_host(self):
        conn = VerticaConnector()
        with pytest.raises(ValueError, match="VERTICA_HOST"):
            conn.validate_credentials()

    def test_raises_without_user(self):
        conn = VerticaConnector(vertica_host="myhost")
        with pytest.raises(ValueError, match="VERTICA_USER"):
            conn.validate_credentials()

    def test_raises_on_import_error(self):
        conn = VerticaConnector(vertica_host="myhost", vertica_user="admin")
        with patch.dict("sys.modules", {"vertica_python": None}):
            with pytest.raises(ImportError):
                conn.validate_credentials()


class TestVerticaClassifyQuery:
    @pytest.mark.parametrize("query,expected", [
        ("SELECT * FROM t", "SELECT"),
        ("INSERT INTO t VALUES (1)", "INSERT"),
        ("UPDATE t SET x=1", "UPDATE"),
        ("DELETE FROM t", "DELETE"),
        ("CREATE TABLE t (id INT)", "DDL"),
        ("DROP TABLE t", "DDL"),
        ("ALTER TABLE t ADD col INT", "DDL"),
        ("", "OTHER"),
    ])
    def test_classify(self, query, expected):
        assert VerticaConnector._classify_query(query) == expected


class TestVerticaFetchSecurityPatterns:
    def test_returns_security_patterns(self):
        conn = VerticaConnector(vertica_host="h", vertica_user="u")
        sp = conn.fetch_security_patterns()
        assert sp.platform == "vertica"
        assert sp.rbac_enabled is True
        assert sp.total_findings == 1


class TestVerticaFetchConcurrencySignals:
    def test_low_active_connections(self):
        mock_vp = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_vp.connect.return_value = mock_conn
        mock_vp.errors = MagicMock()

        conn = VerticaConnector(vertica_host="h", vertica_user="u")
        with patch.dict("sys.modules", {"vertica_python": mock_vp}):
            cs = conn.fetch_concurrency_signals()
        assert cs.platform == "vertica"
        assert cs.scaling_pressure == "low"

    def test_high_active_connections(self):
        mock_vp = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (60,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_vp.connect.return_value = mock_conn
        mock_vp.errors = MagicMock()

        conn = VerticaConnector(vertica_host="h", vertica_user="u")
        with patch.dict("sys.modules", {"vertica_python": mock_vp}):
            cs = conn.fetch_concurrency_signals()
        assert cs.scaling_pressure == "high"
