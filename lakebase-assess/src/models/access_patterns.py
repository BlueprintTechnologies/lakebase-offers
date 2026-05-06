"""Pydantic models for access pattern analysis signals."""

from typing import Optional

from pydantic import BaseModel, Field


class QueryTemporalBucket(BaseModel):
    hour_of_day: int = Field(description="0-23")
    day_of_week: int = Field(description="0=Monday")
    avg_query_count: float
    avg_exec_time_ms: float


class CacheCandidate(BaseModel):
    query_fingerprint: str = Field(description="hashed")
    execution_count: int = Field(description="in the analysis window")
    avg_exec_time_ms: float
    avg_rows_returned: float
    data_freshness_hours: float = Field(description="how often does the underlying data change?")
    estimated_cache_hit_rate: float = Field(description="fraction of executions that could be cached")
    recommended_ttl_seconds: int
    cache_type: str = Field(description="result_cache | redis | memcached")


class AccessPatternSignals(BaseModel):
    platform: str
    read_write_ratio: float = Field(description="reads / (reads + writes)")
    point_lookup_pct: float = Field(description="fraction of queries that are single-row lookups")
    full_scan_pct: float = Field(description="fraction that scan > 50% of table")
    cache_candidates: list[CacheCandidate] = Field(default=[])
    estimated_cacheable_pct: float = Field(description="fraction of all queries that are cacheable")
    temporal_buckets: list[QueryTemporalBucket] = Field(default=[])
    peak_hour_of_day: int = 0
    peak_day_of_week: int = Field(default=0, description="0=Monday")
    off_peak_query_pct: float = Field(description="queries outside business hours")
    repeated_query_pct: float = Field(description="same fingerprint > 3x in window")
    avg_data_staleness_hours: float = Field(description="how fresh does data need to be?")
    has_burst_pattern: bool = Field(description="peak > 5x average")
    burst_duration_minutes: int = 0
