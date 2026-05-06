"""Pydantic models for Databricks misuse detection signals."""

from typing import Optional

from pydantic import BaseModel, Field

# Canonical anti-pattern finding_type constants (§13)
FINDING_HIGH_FREQ_POINT_LOOKUP = "HIGH_FREQ_POINT_LOOKUP"
FINDING_AGENT_STATE_DELTA_MISUSE = "AGENT_STATE_DELTA_MISUSE"
FINDING_APP_BACKEND_ON_DELTA = "APP_BACKEND_ON_DELTA"
FINDING_FEATURE_STORE_LATENCY = "FEATURE_STORE_LATENCY"
FINDING_HIGH_CONCURRENCY_COST = "HIGH_CONCURRENCY_COST"
FINDING_CACHING_LAYER_BYPASS = "CACHING_LAYER_BYPASS"


class MisuseFinding(BaseModel):
    finding_type: str = Field(
        description=(
            "HIGH_FREQ_POINT_LOOKUP | AGENT_STATE_DELTA_MISUSE | APP_BACKEND_ON_DELTA | "
            "FEATURE_STORE_LATENCY | HIGH_CONCURRENCY_COST | CACHING_LAYER_BYPASS"
        )
    )
    severity: str = Field(description="low | medium | high")
    affected_object: str = Field(description="warehouse ID, table name, or query fingerprint")
    description: str
    evidence: str = Field(description="concrete metric that triggered this")
    recommendation: str
    estimated_monthly_savings_dbu: float = 0.0


class JobRunRecord(BaseModel):
    job_name: str
    avg_duration_seconds: float
    runs_per_day: float
    trigger_type: str = Field(description="MANUAL | SCHEDULED | FILE_ARRIVAL | CONTINUOUS")
    cluster_type: str = Field(description="EXISTING_CLUSTER | NEW_CLUSTER | SERVERLESS")
    tables_written: list[str] = Field(default=[])
    failure_rate: float = 0.0


class JobRunTimeline(BaseModel):
    platform: str = "databricks"
    jobs: list[JobRunRecord] = Field(default=[])
    always_on_cluster_jobs: int = 0
    over_provisioned_jobs: int = 0
    high_failure_rate_jobs: int = 0


class DatabricksMisuseFindings(BaseModel):
    platform: str = "databricks"
    findings: list[MisuseFinding] = Field(default=[])
    cache_candidate_queries: int = 0
    over_provisioned_warehouses: int = 0
    point_lookup_on_large_delta_count: int = 0
    total_estimated_wasted_dbu_monthly: float = 0.0
    job_timeline: Optional[JobRunTimeline] = None
