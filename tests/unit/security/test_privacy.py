"""Tests for privacy module."""

import pytest
from src.security.privacy import (
    sanitize_payload, mask_query_text, filter_query_text,
    validate_schema, is_safe_query_text, anonymize_for_upload,
)
from src.models.query_history import QueryRecord, QueryHistory
from src.models.table_metadata import TableMetadata, TableMetadataCollection
from src.models.assessment_payload import AssessmentPayload


def _make_payload(queries=None, tables=None):
    qr_list = queries or [QueryRecord(
        query_id="q1", database="db", schema_name="s",
        query_text_fingerprint="SELECT 1", query_type="SELECT",
    )]
    qh = QueryHistory(platform="test", queries=qr_list)
    tbl_list = tables or []
    tm = TableMetadataCollection(platform="test", tables=tbl_list)
    return AssessmentPayload(
        platform="test", platform_display_name="Test",
        query_history=qh, table_metadata=tm,
    )


class TestMaskQueryText:
    def test_masks_ssn(self):
        result = mask_query_text("WHERE ssn = '123-45-6789'")
        assert "123-45-6789" not in result
        assert "[SSN]" in result

    def test_masks_email(self):
        result = mask_query_text("WHERE email = 'user@example.com'")
        assert "user@example.com" not in result
        assert "[EMAIL]" in result

    def test_masks_ip(self):
        result = mask_query_text("WHERE ip = '10.0.0.1'")
        assert "10.0.0.1" not in result
        assert "[IP]" in result

    def test_masks_credit_card(self):
        result = mask_query_text("WHERE card = '4111111111111111'")
        assert "4111111111111111" not in result

    def test_masks_password(self):
        result = mask_query_text("password=mysecret123")
        assert "mysecret123" not in result
        assert "[REDACTED]" in result

    def test_masks_api_key(self):
        result = mask_query_text("api_key=abc123xyz")
        assert "abc123xyz" not in result
        assert "[REDACTED]" in result

    def test_masks_secret(self):
        result = mask_query_text("secret=topsecret")
        assert "topsecret" not in result

    def test_masks_token(self):
        result = mask_query_text("token=eyJhbGciOiJSUzI1")
        assert "eyJhbGciOiJSUzI1" not in result

    def test_clean_text_unchanged(self):
        text = "SELECT id, name FROM users ORDER BY id"
        result = mask_query_text(text)
        assert "SELECT" in result
        assert "users" in result

    def test_multiple_pii_types(self):
        text = "email=user@test.com AND ssn=123-45-6789"
        result = mask_query_text(text)
        assert "user@test.com" not in result
        assert "123-45-6789" not in result


class TestFilterQueryText:
    def test_replaces_string_literals(self):
        result = filter_query_text("WHERE name = 'Alice'")
        assert "Alice" not in result
        assert "[LITERAL]" in result

    def test_replaces_double_quoted_literals(self):
        result = filter_query_text('WHERE col = "value"')
        assert "value" not in result

    def test_removes_line_comments(self):
        result = filter_query_text("SELECT 1 -- this is a comment")
        assert "-- this is a comment" not in result

    def test_removes_block_comments(self):
        result = filter_query_text("SELECT /* secret */ 1")
        assert "secret" not in result
        assert "[COMMENT]" in result

    def test_truncates_long_text(self):
        long_text = "SELECT " + "x" * 1000
        result = filter_query_text(long_text, max_length=100)
        assert len(result) <= 103  # 100 + "..."
        assert result.endswith("...")

    def test_short_text_not_truncated(self):
        text = "SELECT 1"
        result = filter_query_text(text)
        assert "SELECT" in result
        assert not result.endswith("...")


class TestValidateSchema:
    def test_valid_data_returns_true(self):
        data = {"name": "test", "count": 42, "active": True}
        schema = {
            "required": ["name", "count"],
            "types": {"name": "str", "count": "int", "active": "bool"},
        }
        is_valid, errors = validate_schema(data, schema)
        assert is_valid is True
        assert errors == []

    def test_missing_required_field(self):
        data = {"count": 42}
        schema = {"required": ["name", "count"]}
        is_valid, errors = validate_schema(data, schema)
        assert is_valid is False
        assert any("name" in e for e in errors)

    def test_wrong_type_str(self):
        data = {"name": 123}
        schema = {"types": {"name": "str"}}
        is_valid, errors = validate_schema(data, schema)
        assert is_valid is False

    def test_wrong_type_int(self):
        data = {"count": "not_int"}
        schema = {"types": {"count": "int"}}
        is_valid, errors = validate_schema(data, schema)
        assert is_valid is False

    def test_wrong_type_list(self):
        data = {"items": "not_a_list"}
        schema = {"types": {"items": "list"}}
        is_valid, errors = validate_schema(data, schema)
        assert is_valid is False

    def test_wrong_type_dict(self):
        data = {"meta": "not_a_dict"}
        schema = {"types": {"meta": "dict"}}
        is_valid, errors = validate_schema(data, schema)
        assert is_valid is False

    def test_float_accepts_int(self):
        data = {"score": 42}
        schema = {"types": {"score": "float"}}
        is_valid, errors = validate_schema(data, schema)
        assert is_valid is True

    def test_extra_fields_ignored(self):
        data = {"name": "test", "extra": "ignored"}
        schema = {"required": ["name"], "types": {"name": "str"}}
        is_valid, errors = validate_schema(data, schema)
        assert is_valid is True


class TestIsSafeQueryText:
    def test_clean_query_is_safe(self):
        assert is_safe_query_text("SELECT id FROM users WHERE active = 1") is True

    def test_email_not_safe(self):
        assert is_safe_query_text("WHERE email = 'user@example.com'") is False

    def test_ssn_not_safe(self):
        assert is_safe_query_text("WHERE ssn = '123-45-6789'") is False

    def test_password_not_safe(self):
        assert is_safe_query_text("password=secret") is False

    def test_empty_string_is_safe(self):
        assert is_safe_query_text("") is True


class TestSanitizePayload:
    def test_returns_assessment_payload(self):
        payload = _make_payload()
        result = sanitize_payload(payload)
        assert result.platform == "test"

    def test_pii_removed_from_query_fingerprints(self):
        qr = QueryRecord(
            query_id="q1", database="db", schema_name="s",
            query_text_fingerprint="email=user@test.com",
            query_type="SELECT",
        )
        payload = _make_payload(queries=[qr])
        result = sanitize_payload(payload)
        assert "user@test.com" not in result.query_history.queries[0].query_text_fingerprint

    def test_sensitive_table_name_redacted(self):
        t = TableMetadata(
            database="db", schema_name="s", table_name="pii_users",
            table_type="TABLE", is_sensitive=True,
        )
        payload = _make_payload(tables=[t])
        result = sanitize_payload(payload)
        assert "[REDACTED]" in result.table_metadata.tables[0].table_name

    def test_non_sensitive_table_name_unchanged(self):
        t = TableMetadata(
            database="db", schema_name="s", table_name="orders",
            table_type="TABLE", is_sensitive=False,
        )
        payload = _make_payload(tables=[t])
        result = sanitize_payload(payload)
        assert result.table_metadata.tables[0].table_name == "orders"


class TestAnonymizeForUpload:
    def test_returns_dict(self):
        payload = _make_payload()
        result = anonymize_for_upload(payload)
        assert isinstance(result, dict)

    def test_required_keys_present(self):
        payload = _make_payload()
        result = anonymize_for_upload(payload)
        assert "platform" in result
        assert "avg_score" in result
        assert "priority_1_count" in result
        assert "total_workloads" in result
        assert "est_savings_pct" in result

    def test_platform_matches(self):
        payload = _make_payload()
        result = anonymize_for_upload(payload)
        assert result["platform"] == "test"

    def test_total_workloads_matches_query_count(self):
        queries = [
            QueryRecord(query_id=f"q{i}", database="db", schema_name="s",
                        query_text_fingerprint=f"SELECT {i}", query_type="SELECT")
            for i in range(3)
        ]
        payload = _make_payload(queries=queries)
        result = anonymize_for_upload(payload)
        assert result["total_workloads"] == 3

    def test_no_raw_query_text_in_result(self):
        payload = _make_payload()
        result = anonymize_for_upload(payload)
        result_str = str(result)
        assert "query_text" not in result_str.lower()
