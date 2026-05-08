"""Tests for SynapseConnector."""

import pytest
from unittest.mock import patch, MagicMock
from src.connectors.synapse import SynapseConnector


class TestSynapseValidateCredentials:
    def test_raises_without_server(self):
        conn = SynapseConnector()
        with pytest.raises(ValueError, match="SYNAPSE_SERVER"):
            conn.validate_credentials()

    def test_raises_without_user(self):
        conn = SynapseConnector(synapse_server="myserver")
        with pytest.raises(ValueError, match="SYNAPSE_USER"):
            conn.validate_credentials()

    def test_raises_without_password_or_oauth(self):
        conn = SynapseConnector(synapse_server="myserver", synapse_user="admin")
        mock_import = MagicMock()
        with patch.dict("sys.modules", {"psycopg2": mock_import}):
            with pytest.raises(ValueError, match="SYNAPSE_PASSWORD"):
                conn.validate_credentials()

    def test_succeeds_on_valid_connection(self):
        conn = SynapseConnector(synapse_server="myserver", synapse_user="admin", synapse_password="pw")
        mock_conn = MagicMock()
        with patch("psycopg2.connect", return_value=mock_conn):
            result = conn.validate_credentials()
        assert result is True


class TestSynapseFetchSecurityPatterns:
    def test_returns_security_patterns(self):
        conn = SynapseConnector(synapse_server="s", synapse_user="u", synapse_password="pw")
        sp = conn.fetch_security_patterns()
        assert sp.platform == "synapse"
        assert sp.rbac_enabled is True
        assert sp.sso_integration is True
        assert "SOC2" in sp.compliance_certifications


class TestSynapseFetchConcurrencySignals:
    def test_returns_fixed_medium_pressure(self):
        conn = SynapseConnector(synapse_server="s", synapse_user="u", synapse_password="pw")
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (10,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch("psycopg2.connect", return_value=mock_conn):
            cs = conn.fetch_concurrency_signals()
        assert cs.platform == "synapse"
        assert cs.scaling_pressure == "medium"
