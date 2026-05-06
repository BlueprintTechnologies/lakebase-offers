"""Pydantic models for availability and SLA signals."""

from typing import Optional

from pydantic import BaseModel, Field


class AvailabilitySignals(BaseModel):
    platform: str
    incidents_last_90d: int = 0
    avg_incident_duration_minutes: float = 0.0
    sla_target_pct: float = Field(default=99.9, description="e.g., 99.9")
    sla_actual_pct: float = 0.0
    planned_maintenance_windows: int = 0
    has_dr_configured: bool = False
    rto_minutes: Optional[int] = Field(default=None, description="recovery time objective")
    rpo_minutes: Optional[int] = Field(default=None, description="recovery point objective")
