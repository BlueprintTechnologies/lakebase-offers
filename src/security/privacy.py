"""PII masking, query text filtering, and schema validation for assessment data."""

import logging
import re
from typing import Any

from src.models.assessment_payload import AssessmentPayload

logger = logging.getLogger(__name__)

# Patterns for PII detection in query text
PII_PATTERNS = [
    (r"(?i)\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),
    (r"(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]"),
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP]"),
    (r"(?i)\b\d{16}\b", "[CC]"),
    (r"(?i)(password\s*=\s*)\S+", r"\1[REDACTED]"),
    (r"(?i)(api[_-]?key\s*=\s*)\S+", r"\1[REDACTED]"),
    (r"(?i)(secret\s*=\s*)\S+", r"\1[REDACTED]"),
    (r"(?i)(token\s*=\s*)\S+", r"\1[REDACTED]"),
    (r"(?i)(auth\s*=\s*)\S+", r"\1[REDACTED]"),
    (r"(?i)\b\d{9}\b", "[PHONE]"),  # Phone-like numbers
    (r"(?i)\b\d{5}[-\s]?\d{4}\b", "[ZIP]"),  # ZIP codes
]

# Reserved SQL keywords that are safe to keep
SAFE_KEYWORDS = {
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER",
    "CROSS", "FULL", "ON", "AND", "OR", "NOT", "IN", "LIKE", "BETWEEN",
    "IS", "NULL", "ORDER", "BY", "GROUP", "HAVING", "UNION", "INTERSECT",
    "EXCEPT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "TABLE",
    "VIEW", "INDEX", "FUNCTION", "PROCEDURE", "TRIGGER", "CASE", "WHEN",
    "THEN", "ELSE", "END", "IF", "FOR", "WHILE", "LOOP", "RETURN", "BEGIN",
    "DECLARE", "SET", "DECLARE", "AS", "INTO", "VALUES", "PRIMARY", "KEY",
    "FOREIGN", "CONSTRAINT", "DEFAULT", "CHECK", "UNIQUE", "CASCADE",
}


def sanitize_payload(payload: AssessmentPayload) -> AssessmentPayload:
    """Strip all PII from an assessment payload."""
    sanitized = AssessmentPayload(
        platform=payload.platform,
        platform_display_name=payload.platform_display_name,
        query_history=_sanitize_query_history(payload.query_history),
        table_metadata=_sanitize_table_metadata(payload.table_metadata),
        concurrency_signals=payload.concurrency_signals,
        security_patterns=payload.security_patterns,
    )
    return sanitized


def _sanitize_query_history(qh) -> Any:
    """Sanitize query history records."""
    for query in qh.queries:
        # Mask PII in the fingerprint
        sanitized_text = query.query_text_fingerprint
        for pattern, replacement in PII_PATTERNS:
            sanitized_text = re.sub(pattern, replacement, sanitized_text)
        query.query_text_fingerprint = sanitized_text[:500]  # Truncate
    return qh


def _sanitize_table_metadata(tm) -> Any:
    """Sanitize table metadata for PII in names/tags."""
    for table in tm.tables:
        if table.is_sensitive:
            # Rename sensitive tables
            table.table_name = f"[REDACTED]_{table.table_name[-8:] if len(table.table_name) > 8 else table.table_name}"
            table.is_sensitive = False
    return tm


def mask_query_text(text: str) -> str:
    """Mask known PII patterns in query text."""
    result = text
    for pattern, replacement in PII_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result


def filter_query_text(text: str, max_length: int = 500) -> str:
    """Filter query text to only safe SQL keywords and structural elements.

    Replaces string literals and values with placeholders.
    """
    # Replace string literals
    result = re.sub(r"'[^']*'", "'[LITERAL]' ", text)
    result = re.sub(r'"[^"]*"', '"[LITERAL]" ', result)

    # Replace inline comments
    result = re.sub(r"--.*$", "", result, flags=re.MULTILINE)

    # Replace block comments
    result = re.sub(r"/\*.*?\*/", "[COMMENT]", result, flags=re.DOTALL)

    # Truncate
    if len(result) > max_length:
        result = result[:max_length] + "..."

    return result


def validate_schema(data: dict[str, Any], schema: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate data against a schema definition.

    Args:
        data: Dictionary of field values.
        schema: Schema dict mapping field names to types.

    Returns:
        Tuple of (is_valid, list_of_errors).
    """
    errors: list[str] = []

    # Check required fields
    required = schema.get("required", [])
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Type checks
    type_map = schema.get("types", {})
    for field, expected_type in type_map.items():
        if field in data:
            value = data[field]
            if expected_type == "str" and not isinstance(value, str):
                errors.append(f"Field '{field}' expected str, got {type(value).__name__}")
            elif expected_type == "int" and not isinstance(value, int):
                errors.append(f"Field '{field}' expected int, got {type(value).__name__}")
            elif expected_type == "float" and not isinstance(value, (int, float)):
                errors.append(f"Field '{field}' expected float, got {type(value).__name__}")
            elif expected_type == "bool" and not isinstance(value, bool):
                errors.append(f"Field '{field}' expected bool, got {type(value).__name__}")
            elif expected_type == "list" and not isinstance(value, list):
                errors.append(f"Field '{field}' expected list, got {type(value).__name__}")
            elif expected_type == "dict" and not isinstance(value, dict):
                errors.append(f"Field '{field}' expected dict, got {type(value).__name__}")

    return len(errors) == 0, errors


def is_safe_query_text(text: str) -> bool:
    """Check if query text appears safe (no PII detected)."""
    for pattern, _ in PII_PATTERNS:
        if re.search(pattern, text):
            return False
    return True


def anonymize_for_upload(payload: AssessmentPayload) -> dict[str, Any]:
    """Create an anonymized payload suitable for BPCS trend tracking.

    Only includes: platform, avg_score, priority_1_count, est_savings_pct
    All identifiers are hashed. No query text or table names are included.
    """
    scores = []
    for query in payload.query_history.queries:
        scores.append({
            "query_hash": payload.platform + "_" + query.query_id[:8],
            "raw_score": 0,  # Not included in upload
            "adjusted_score": 0,
            "priority": "Hold",  # Not included in upload
        })

    # Compute aggregate scores
    adjusted_scores = [s.get("adjusted_score", 0) for s in scores] if scores else [0]
    priority_1 = sum(1 for s in scores if s.get("priority") == "Priority_1")

    return {
        "platform": payload.platform,
        "avg_score": round(sum(adjusted_scores) / max(len(adjusted_scores), 1), 2),
        "priority_1_count": priority_1,
        "total_workloads": len(scores),
        "est_savings_pct": 0,  # Set by caller from billing calculation
        "platform_display_name": payload.platform_display_name,
    }
