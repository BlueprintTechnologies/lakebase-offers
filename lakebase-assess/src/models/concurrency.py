"""Pydantic models for concurrency and performance signals."""

from typing import Optional

from pydantic import BaseModel, Field


class ConcurrencySnapshot(BaseModel):
    """A point-in-time snapshot of concurrent query activity."""

    timestamp: str
    active_sessions: int
    queued_queries: int
    avg_wait_time_ms: Optional[float] = None
    resource_utilization_cpu: Optional[float] = None  # 0.0-1.0
    resource_utilization_memory: Optional[float] = None  # 0.0-1.0


class ConcurrencySignals(BaseModel):
    """Aggregated concurrency and performance signals."""

    platform: str
    snapshots: list[ConcurrencySnapshot] = Field(default=[])
    avg_concurrent_queries: float = 0.0
    peak_concurrent_queries: int = 0
    avg_queue_time_ms: Optional[float] = None
    p95_queue_time_ms: Optional[float] = None
    p99_queue_time_ms: Optional[float] = None
    avg_cpu_utilization: Optional[float] = None
    avg_memory_utilization: Optional[float] = None
    scaling_pressure: str = Field(
        default="low",
        description="low|medium|high|critical - based on resource utilization trends",
    )
    timeout_rate: float = Field(default=0.0, description="Fraction of queries timing out")
    slow_query_rate: float = Field(default=0.0, description="Fraction of queries > 5 minutes")

    @property
    def needs_scaling(self) -> bool:
        return self.scaling_pressure in ("high", "critical")
