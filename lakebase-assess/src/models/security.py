"""Pydantic models for security and compliance patterns."""

from typing import Optional

from pydantic import BaseModel, Field


class SecurityFinding(BaseModel):
    """A single security/compliance observation."""

    category: str = Field(description="RBAC|ENCRYPTION|AUDIT|DATA_LINEAGE|ACCESS_CONTROL|COMPLIANCE")
    severity: str = Field(description="low|medium|high|critical")
    description: str
    affected_objects: list[str] = Field(default=[])
    remediation: Optional[str] = None


class SecurityPatterns(BaseModel):
    """Aggregated security and compliance signals."""

    platform: str
    findings: list[SecurityFinding] = Field(default=[])
    rbac_enabled: bool = False
    rbac_depth: int = 0
    encryption_at_rest: bool = False
    encryption_in_transit: bool = False
    audit_logging_enabled: bool = False
    data_classification_available: bool = False
    row_level_security: bool = False
    column_level_security: bool = False
    sso_integration: bool = False
    mfa_required: bool = False
    compliance_certifications: list[str] = Field(default=[])
    total_findings: int = 0
    high_severity_count: int = 0
    critical_severity_count: int = 0
    active_users_last_30d: int = Field(default=0, description="distinct human users who ran queries")
    active_service_accounts_last_30d: int = Field(default=0, description="distinct service/robot accounts")

    @property
    def needs_security_hardening(self) -> bool:
        return self.critical_severity_count > 0 or self.high_severity_count > 2
