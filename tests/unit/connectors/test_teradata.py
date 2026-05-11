"""Tests for TeradataConnector."""

import pytest
from unittest.mock import patch, MagicMock
from src.connectors.teradata import TeradataConnector


class TestTeradataValidateCredentials:
    def test_raises_without_host(self):
        conn = TeradataConnector()
        with pytest.raises(ValueError, match="TERADATA_HOST"):
            conn.validate_credentials()

    def test_raises_without_user(self):
        conn = TeradataConnector(teradata_host="myhost")
        with pytest.raises(ValueError, match="TERADATA_USER"):
            conn.validate_credentials()

    def test_raises_on_import_error(self):
        conn = TeradataConnector(teradata_host="myhost", teradata_user="admin")
        with patch.dict("sys.modules", {"teradata": None}):
            with pytest.raises(ImportError):
                conn.validate_credentials()


class TestTeradataFetchSecurityPatterns:
    def test_returns_security_patterns(self):
        conn = TeradataConnector(teradata_host="h", teradata_user="u")
        sp = conn.fetch_security_patterns()
        assert sp.platform == "teradata"
        assert sp.rbac_enabled is True
        assert sp.encryption_at_rest is True
        assert "SOC2" in sp.compliance_certifications
        assert sp.total_findings == 1


class TestTeradataFetchConcurrencySignals:
    def _make_session(self):
        mock_td = MagicMock()
        mock_session = MagicMock()
        mock_session.fetchone.return_value = (20,)
        mock_conn_obj = MagicMock()
        mock_conn_obj.createSession.return_value = mock_session
        mock_td.UdaExec.return_value = mock_conn_obj
        return mock_td

    def test_returns_high_scaling_pressure(self):
        conn = TeradataConnector(teradata_host="h", teradata_user="u")
        mock_td = self._make_session()
        with patch.dict("sys.modules", {"teradata": mock_td}):
            cs = conn.fetch_concurrency_signals()
        assert cs.platform == "teradata"
        assert cs.scaling_pressure == "high"
