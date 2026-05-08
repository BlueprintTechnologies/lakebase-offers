import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from src.connectors.base import AbstractBaseConnector
from src.models.query_history import QueryHistory
from src.models.table_metadata import TableMetadataCollection
from src.models.concurrency import ConcurrencySignals
from src.models.security import SecurityPatterns
from src.models.cost_signals import CostSignals

class TestAbstractBaseConnector:
    @pytest.fixture
    def base_connector(self):
        class ConcreteBaseConnector(AbstractBaseConnector):
            platform_name = 'test_platform'

            def validate_credentials(self) -> bool:
                return True

            def fetch_query_history(self) -> QueryHistory:
                return QueryHistory(platform='test_platform', queries=[], total_queries_fetched=0)

            def fetch_table_metadata(self) -> TableMetadataCollection:
                return TableMetadataCollection(platform='test_platform')

            def fetch_concurrency_signals(self) -> ConcurrencySignals:
                return ConcurrencySignals(platform='test_platform', snapshots=[], avg_concurrent_queries=0.0, peak_concurrent_queries=0, scaling_pressure='low')

            def fetch_security_patterns(self) -> SecurityPatterns:
                return SecurityPatterns(platform='test_platform', findings=[], rbac_enabled=True, encryption_at_rest=True, encryption_in_transit=True, audit_logging_enabled=True, compliance_certifications=[], total_findings=0, high_severity_count=0, critical_severity_count=0)

            def fetch_cost_signals(self) -> CostSignals:
                return CostSignals(platform='test_platform')

        return ConcreteBaseConnector()

    def test_ingest_all_validates_creds(self, base_connector):
        payload = base_connector.ingest_all()
        assert payload.platform == 'base'

    def test_ingest_all_calls_fetch_query_history(self, base_connector):
        payload = base_connector.ingest_all()
        assert payload.query_history is not None

    def test_ingest_all_calls_fetch_table_metadata(self, base_connector):
        payload = base_connector.ingest_all()
        assert payload.table_metadata is not None

    def test_ingest_all_includes_optional_none_signals(self, base_connector):
        payload = base_connector.ingest_all()
        assert payload.access_patterns is None
        assert payload.migration_complexity is None

    def test_fetch_access_patterns_default_none(self, base_connector):
        result = base_connector.fetch_access_patterns()
        assert result is None

    def test_fetch_migration_complexity_default_none(self, base_connector):
        result = base_connector.fetch_migration_complexity()
        assert result is None

    def test_repr(self, base_connector):
        r = repr(base_connector)
        assert 'ConcreteBaseConnector' in r or 'base' in r

    def test_hash_query_text_length(self):
        h = AbstractBaseConnector._hash_query_text("SELECT 1", length=16)
        assert len(h) == 16

    def test_hash_query_text_default_length(self):
        h = AbstractBaseConnector._hash_query_text("SELECT 1")
        assert len(h) == 64

    def test_detect_pii_email(self):
        text = "WHERE email = 'user@example.com'"
        result = AbstractBaseConnector._detect_pii_in_fingerprint(text)
        assert 'user@example.com' not in result
        assert '[EMAIL]' in result

    def test_detect_pii_ip(self):
        text = "WHERE ip = '192.168.1.1'"
        result = AbstractBaseConnector._detect_pii_in_fingerprint(text)
        assert '192.168.1.1' not in result
        assert '[IP]' in result

    def test_detect_pii_password(self):
        text = "WHERE password=secretvalue"
        result = AbstractBaseConnector._detect_pii_in_fingerprint(text)
        assert 'secretvalue' not in result
        assert '[REDACTED]' in result

    def test_detect_pii_api_key(self):
        text = "api_key=abc123xyz"
        result = AbstractBaseConnector._detect_pii_in_fingerprint(text)
        assert 'abc123xyz' not in result

    def test_safe_int_invalid_string(self):
        assert AbstractBaseConnector._safe_int('not_a_number') == 0

    def test_safe_int_float_value(self):
        assert AbstractBaseConnector._safe_int(3.7) == 3

    def test_safe_float_invalid(self):
        result = AbstractBaseConnector._safe_float('bad', default=0.0)
        assert result == 0.0

    def test_safe_float_zero(self):
        result = AbstractBaseConnector._safe_float(0)
        assert result == 0.0

    def test_is_stats_stale_none(self):
        assert AbstractBaseConnector._is_stats_stale(None) is False

    def test_is_stats_stale_recent(self):
        recent = datetime.now() - timedelta(days=5)
        assert AbstractBaseConnector._is_stats_stale(recent) is False

    def test_is_stats_stale_old(self):
        old = datetime.now() - timedelta(days=60)
        assert AbstractBaseConnector._is_stats_stale(old) is True

    def test_is_stats_stale_string_iso(self):
        old_str = (datetime.now() - timedelta(days=45)).isoformat()
        assert AbstractBaseConnector._is_stats_stale(old_str) is True

    def test_is_stats_stale_invalid_string(self):
        assert AbstractBaseConnector._is_stats_stale('not-a-date') is False

    def test_is_stats_stale_aware_datetime(self):
        from datetime import timezone
        old_aware = datetime.now(tz=timezone.utc) - timedelta(days=60)
        assert AbstractBaseConnector._is_stats_stale(old_aware) is True

    def test_connector_init_stores_kwargs(self):
        class MinimalConnector(AbstractBaseConnector):
            platform_name = 'minimal'
            def validate_credentials(self): return True
            def fetch_query_history(self): pass
            def fetch_table_metadata(self): pass
            def fetch_concurrency_signals(self): pass
            def fetch_security_patterns(self): pass
            def fetch_cost_signals(self): pass

        c = MinimalConnector(platform_name='minimal', query_history_days=30, extra_param='value')
        assert c.query_history_days == 30
        assert c._kwargs.get('extra_param') == 'value'

    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError):
            AbstractBaseConnector()
