"""Tests for BigQueryConnector."""

import pytest
from unittest.mock import patch, MagicMock
from src.connectors.bigquery import BigQueryConnector


class TestBigQueryValidateCredentials:
    def test_raises_without_project(self):
        conn = BigQueryConnector()
        with pytest.raises(ValueError, match="BQ_PROJECT_ID"):
            conn.validate_credentials()

    def test_raises_on_import_error(self):
        conn = BigQueryConnector(bq_project_id="my-project")
        with patch.dict("sys.modules", {"google.oauth2": None, "google.oauth2.service_account": None}):
            with pytest.raises((ImportError, Exception)):
                conn.validate_credentials()

    def test_succeeds_with_mocked_credentials(self):
        conn = BigQueryConnector(bq_project_id="my-project")
        mock_sa_module = MagicMock()
        mock_google_auth = MagicMock()
        mock_google_auth.default.return_value = (MagicMock(), "my-project")
        mock_google = MagicMock()
        mock_google.auth = mock_google_auth
        mock_google.oauth2 = MagicMock()
        mock_google.oauth2.service_account = mock_sa_module
        with patch.dict("sys.modules", {
            "google": mock_google,
            "google.oauth2": mock_google.oauth2,
            "google.oauth2.service_account": mock_sa_module,
            "google.auth": mock_google_auth,
        }):
            result = conn.validate_credentials()
        assert result is True


class TestBigQueryClassifyQuery:
    @pytest.mark.parametrize("query,expected", [
        ("SELECT * FROM t", "SELECT"),
        ("select 1", "SELECT"),
        ("INSERT INTO t VALUES (1)", "INSERT"),
        ("UPDATE t SET x=1", "UPDATE"),
        ("DELETE FROM t", "DELETE"),
        ("CREATE TABLE t (id INT)", "DDL"),
        ("DROP TABLE t", "DDL"),
        ("ALTER TABLE t ADD COLUMN x INT", "DDL"),
        ("MERGE INTO t USING s ON t.id=s.id", "DDL"),
        ("CALL my_proc()", "OTHER"),
        ("", "OTHER"),
    ])
    def test_classify(self, query, expected):
        assert BigQueryConnector._classify_bigquery_query(query) == expected


class TestBigQueryFetchConcurrencySignals:
    def test_returns_low_pressure(self):
        conn = BigQueryConnector(bq_project_id="my-project")
        cs = conn.fetch_concurrency_signals()
        assert cs.platform == "bigquery"
        assert cs.scaling_pressure == "low"
        assert cs.avg_concurrent_queries == 0.0


class TestBigQueryFetchSecurityPatterns:
    def test_returns_security_patterns(self):
        conn = BigQueryConnector(bq_project_id="my-project")
        sp = conn.fetch_security_patterns()
        assert sp.platform == "bigquery"
        assert sp.rbac_enabled is True
        assert sp.encryption_at_rest is True
        assert "SOC2" in sp.compliance_certifications
        assert "FedRAMP" in sp.compliance_certifications
