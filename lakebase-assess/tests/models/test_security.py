"""Tests for SecurityPatterns and SecurityFinding models."""

import pytest
from src.models.security import SecurityPatterns, SecurityFinding


class TestSecurityFinding:
    def test_basic_construction(self):
        f = SecurityFinding(
            category="RBAC",
            severity="high",
            description="No RBAC configured.",
        )
        assert f.category == "RBAC"
        assert f.severity == "high"
        assert f.description == "No RBAC configured."
        assert f.affected_objects == []
        assert f.remediation is None

    def test_full_construction(self):
        f = SecurityFinding(
            category="ENCRYPTION",
            severity="medium",
            description="Encryption may not be enabled.",
            affected_objects=["table1", "table2"],
            remediation="Enable TDE.",
        )
        assert len(f.affected_objects) == 2
        assert f.remediation == "Enable TDE."


class TestSecurityPatterns:
    def test_defaults(self):
        sp = SecurityPatterns(platform="snowflake")
        assert sp.platform == "snowflake"
        assert sp.rbac_enabled is False
        assert sp.encryption_at_rest is False
        assert sp.encryption_in_transit is False
        assert sp.audit_logging_enabled is False
        assert sp.total_findings == 0
        assert sp.high_severity_count == 0
        assert sp.critical_severity_count == 0
        assert sp.active_users_last_30d == 0
        assert sp.active_service_accounts_last_30d == 0
        assert sp.compliance_certifications == []

    def test_needs_security_hardening_with_critical(self):
        sp = SecurityPatterns(
            platform="snowflake",
            critical_severity_count=1,
        )
        assert sp.needs_security_hardening is True

    def test_needs_security_hardening_with_many_high(self):
        sp = SecurityPatterns(
            platform="snowflake",
            high_severity_count=3,
        )
        assert sp.needs_security_hardening is True

    def test_no_hardening_needed_with_two_high(self):
        sp = SecurityPatterns(
            platform="snowflake",
            high_severity_count=2,
        )
        assert sp.needs_security_hardening is False

    def test_full_construction(self):
        findings = [
            SecurityFinding(category="RBAC", severity="high", description="No roles"),
            SecurityFinding(category="ENCRYPTION", severity="medium", description="No TDE"),
        ]
        sp = SecurityPatterns(
            platform="snowflake",
            findings=findings,
            rbac_enabled=True,
            encryption_at_rest=True,
            encryption_in_transit=True,
            audit_logging_enabled=True,
            compliance_certifications=["SOC2", "HIPAA"],
            total_findings=2,
            high_severity_count=1,
            active_users_last_30d=50,
            active_service_accounts_last_30d=5,
        )
        assert len(sp.findings) == 2
        assert "SOC2" in sp.compliance_certifications
        assert sp.active_users_last_30d == 50
