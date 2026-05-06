"""Tests for PII masking, query text filtering, and schema validation."""

import pytest

from src.security.privacy import (
    PII_PATTERNS,
    sanitize_payload,
    mask_query_text,
    filter_query_text,
    validate_schema,
    is_safe_query_text,
    anonymize_for_upload,
)
from src.models.assessment_payload import AssessmentPayload
from src.models.query_history import QueryHistory, QueryRecord
from src.models.table_metadata import TableMetadataCollection


class TestPIIMasking:
    """Test PII pattern masking."""

    def test_ssn_masking(self):
        """Test SSN pattern is masked."""
        text = "SELECT * FROM users WHERE ssn = '123-45-6789'"
        masked = mask_query_text(text)
        assert "123-45-6789" not in masked
        assert "[SSN]" in masked

    def test_email_masking(self):
        """Test email pattern is masked."""
        text = "SELECT * FROM users WHERE email = 'john@example.com'"
        masked = mask_query_text(text)
        assert "john@example.com" not in masked
        assert "[EMAIL]" in masked

    def test_ip_masking(self):
        """Test IP address pattern is masked."""
        text = "SELECT * FROM logs WHERE ip = '192.168.1.1'"
        masked = mask_query_text(text)
        assert "192.168.1.1" not in masked
        assert "[IP]" in masked

    def test_password_masking(self):
        """Test password= pattern is masked."""
        text = "SELECT * FROM config WHERE password = 'secret123'"
        masked = mask_query_text(text)
        assert "[REDACTED]" in masked

    def test_api_key_masking(self):
        """Test api_key= pattern is masked."""
        text = "SELECT * FROM api_keys WHERE api_key = 'sk-12345'"
        masked = mask_query_text(text)
        assert "[REDACTED]" in masked

    def test_secret_masking(self):
        """Test secret= pattern is masked."""
        text = "INSERT INTO configs SET secret = 'mys3cr3t'"
        masked = mask_query_text(text)
        assert "[REDACTED]" in masked

    def test_no_pii_preserved(self):
        """Test that clean text is unchanged."""
        text = "SELECT * FROM analytics WHERE date > '2024-01-01' ORDER BY revenue"
        masked = mask_query_text(text)
        assert masked == text


class TestQueryFiltering:
    """Test query text filtering."""

    def test_string_literal_replacement(self):
        """Test that string literals are replaced."""
        text = "SELECT * FROM users WHERE name = 'John'"
        filtered = filter_query_text(text)
        assert "[LITERAL]" in filtered

    def test_inline_comment_removal(self):
        """Test that inline comments are removed."""
        text = "SELECT * FROM users -- this is a comment\nWHERE id = 1"
        filtered = filter_query_text(text)
        assert "--" not in filtered

    def test_block_comment_removal(self):
        """Test that block comments are removed."""
        text = "SELECT * FROM users /* sensitive data */ WHERE id = 1"
        filtered = filter_query_text(text)
        assert "[COMMENT]" in filtered

    def test_truncation(self):
        """Test that text is truncated to max_length."""
        long_text = "SELECT " + "x " * 200  # 600+ chars
        filtered = filter_query_text(long_text, max_length=100)
        assert len(filtered) <= 103  # 100 + ".." padding

    def test_safe_query_preserved(self):
        """Test that safe SQL is preserved."""
        text = "SELECT a, b, c FROM table1 JOIN table2 ON table1.id = table2.id WHERE a > 10"
        filtered = filter_query_text(text)
        assert "SELECT" in filtered
        assert "FROM" in filtered
        assert "JOIN" in filtered


class TestSchemaValidation:
    """Test schema validation."""

    def test_valid_data(self):
        """Test that valid data passes validation."""
        data = {"name": "test", "count": 42, "active": True, "tags": ["a", "b"], "meta": {"x": 1}}
        schema = {
            "required": ["name", "count"],
            "types": {"name": "str", "count": "int", "active": "bool", "tags": "list", "meta": "dict"},
        }
        valid, errors = validate_schema(data, schema)
        assert valid is True
        assert len(errors) == 0

    def test_missing_required_field(self):
        """Test that missing required fields produce errors."""
        data = {"name": "test"}
        schema = {"required": ["name", "count"], "types": {"name": "str", "count": "int"}}
        valid, errors = validate_schema(data, schema)
        assert valid is False
        assert any("count" in e for e in errors)

    def test_type_mismatch(self):
        """Test that type mismatches produce errors."""
        data = {"name": 123, "count": "wrong"}
        schema = {"types": {"name": "str", "count": "int"}}
        valid, errors = validate_schema(data, schema)
        assert valid is False
        assert len(errors) >= 2

    def test_empty_data(self):
        """Test empty data with no required fields."""
        data = {}
        schema = {"required": [], "types": {}}
        valid, errors = validate_schema(data, schema)
        assert valid is True
        assert len(errors) == 0


class TestSafeQueryText:
    """Test safe query text detection."""

    def test_safe_text(self):
        """Test that clean text is detected as safe."""
        text = "SELECT * FROM analytics WHERE date > '2024-01-01'"
        assert is_safe_query_text(text) is True

    def test_pii_detected(self):
        """Test that text with PII is detected as unsafe."""
        text = "SELECT * FROM users WHERE ssn = '123-45-6789'"
        assert is_safe_query_text(text) is False

    def test_email_detected(self):
        """Test that email in text is detected as unsafe."""
        text = "SELECT * FROM users WHERE email = 'test@example.com'"
        assert is_safe_query_text(text) is False


class TestAnonymizeForUpload:
    """Test anonymized payload for BPCS upload."""

    def test_anonymized_payload_structure(self):
        """Test that anonymized payload has correct fields."""
        query = QueryRecord(
            query_id="test_q_1", database="db", schema_name="s",
            query_text_fingerprint="SELECT 1", query_type="SELECT",
        )
        qh = QueryHistory(platform="test", queries=[query], total_queries_fetched=1)

        payload = AssessmentPayload(
            platform="test", platform_display_name="Test",
            query_history=qh, table_metadata=TableMetadataCollection(platform="test"),
        )

        anon = anonymize_for_upload(payload)
        assert "platform" in anon
        assert "avg_score" in anon
        assert "priority_1_count" in anon
        assert "total_workloads" in anon
        assert "platform_display_name" in anon
        # PII should not leak
        assert "SELECT 1" not in anon.get("query_hash", "")


class TestSanitizePayload:
    """Test full payload sanitization."""

    def test_sanitize_strips_pii(self):
        """Test that sanitize_payload removes PII from query text."""
        query = QueryRecord(
            query_id="q1", database="db", schema_name="s",
            query_text_fingerprint="SELECT * FROM users WHERE email = 'test@example.com' AND ssn = '123-45-6789'",
            query_type="SELECT",
        )
        qh = QueryHistory(platform="test", queries=[query])
        tm = TableMetadataCollection(platform="test")

        payload = AssessmentPayload(
            platform="test", platform_display_name="Test",
            query_history=qh, table_metadata=tm,
        )

        sanitized = sanitize_payload(payload)
        for q in sanitized.query_history.queries:
            assert "test@example.com" not in q.query_text_fingerprint
            assert "123-45-6789" not in q.query_text_fingerprint
            assert "[REDACTED]" in q.query_text_fingerprint

    def test_sanitize_truncates_long_text(self):
        """Test that PII sanitization truncates very long text."""
        long_text = "SELECT " + "x " * 300  # Well over 500 chars
        query = QueryRecord(
            query_id="q2", database="db", schema_name="s",
            query_text_fingerprint=long_text, query_type="SELECT",
        )
        qh = QueryHistory(platform="test", queries=[query])
        tm = TableMetadataCollection(platform="test")

        payload = AssessmentPayload(
            platform="test", platform_display_name="Test",
            query_history=qh, table_metadata=tm,
        )

        sanitized = sanitize_payload(payload)
        assert len(sanitized.query_history.queries[0].query_text_fingerprint) <= 500
