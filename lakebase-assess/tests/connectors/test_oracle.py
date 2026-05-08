"""Tests for OracleConnector."""

import pytest
from unittest.mock import patch, MagicMock
from src.connectors.oracle import OracleConnector


class TestOracleValidateCredentials:
    def test_raises_without_host(self):
        conn = OracleConnector()
        with pytest.raises(ValueError, match="ORACLE_HOST"):
            conn.validate_credentials()

    def test_raises_without_user(self):
        conn = OracleConnector(oracle_host="myhost")
        with pytest.raises(ValueError, match="ORACLE_USER"):
            conn.validate_credentials()

    def test_raises_on_import_error(self):
        conn = OracleConnector(oracle_host="myhost", oracle_user="admin")
        with patch.dict("sys.modules", {"cx_Oracle": None}):
            with pytest.raises(ImportError):
                conn.validate_credentials()


class TestOracleClassifyQuery:
    @pytest.mark.parametrize("query,expected", [
        ("SELECT id FROM dual", "SELECT"),
        ("INSERT INTO t VALUES (1)", "INSERT"),
        ("UPDATE t SET x=1", "UPDATE"),
        ("DELETE FROM t", "DELETE"),
        ("CREATE TABLE t (id INT)", "DDL"),
        ("DROP TABLE t", "DDL"),
        ("ALTER TABLE t ADD col INT", "DDL"),
        ("EXEC my_proc()", "OTHER"),
        ("", "OTHER"),
    ])
    def test_classify(self, query, expected):
        assert OracleConnector._classify_oracle_query(query) == expected


class TestOracleFetchSecurityPatterns:
    def test_returns_security_patterns(self):
        conn = OracleConnector(oracle_host="myhost", oracle_user="admin")
        sp = conn.fetch_security_patterns()
        assert sp.platform == "oracle"
        assert sp.rbac_enabled is True
        assert sp.encryption_at_rest is True
        assert "SOC2" in sp.compliance_certifications
        assert sp.total_findings == 2


class TestOracleFetchCostSignals:
    def _make_mock_cx(self):
        mock_cx = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            ("4",),   # cpu_count
            (500.0,), # storage_gb
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cx.connect.return_value = mock_conn
        return mock_cx

    def test_enterprise_license_detected(self):
        conn = OracleConnector(oracle_host="h", oracle_user="u", oracle_edition="enterprise")
        mock_cx = self._make_mock_cx()
        with patch.dict("sys.modules", {"cx_Oracle": mock_cx}):
            cost = conn.fetch_cost_signals()
        assert cost.has_license_cost is True
        assert cost.license_type == "enterprise"

    def test_standard_license_detected(self):
        conn = OracleConnector(oracle_host="h", oracle_user="u", oracle_edition="standard")
        mock_cx = self._make_mock_cx()
        with patch.dict("sys.modules", {"cx_Oracle": mock_cx}):
            cost = conn.fetch_cost_signals()
        assert cost.license_type == "standard"
