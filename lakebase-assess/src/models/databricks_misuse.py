"""Pydantic models for Databricks misuse detection signals."""

from typing import Optional

from pydantic import BaseModel, Field


class MisuseFinding(BaseModel):
    finding_type: str = Field(description="Cache candidate | Table too large for point lookup | High-frequency micro-writes | Warehouse misconfigured | Small table slow scan | Cache not warming")
    severity: str = Field(description="low | medium | high")
    affected_object: str = Field(description="warehouse ID, table name, or query fingerprint")
    description: str
    evidence: str = Field(description="concrete metric that triggered this")
    recommendation: str
    estimated_monthly_savings_dbu: float = 0.0


class DatabricksMisuseFindings(BaseModel):
    platform: str = "databricks"
    findings: list[MisuseFinding] = Field(default=[])
    cache_candidate_queries: int = 0
    over_provisioned_warehouses: int = 0
    point_lookup_on_large_delta_count: int = 0
    total_estimated_wasted_dbu_monthly: float = 0.0
