"""Pydantic models for actual usage cost signals."""

from pydantic import BaseModel, Field


class CostSignals(BaseModel):
    platform: str

    # Compute
    compute_units_per_month: float = Field(description="credits (Snowflake), DWUs (Synapse), node-hrs (Redshift)")
    compute_unit_name: str = Field(description="credit | DWU-hr | node-hr | core-hr")
    compute_cost_per_unit: float = Field(description="from billing.py DEFAULT_RATES or YAML override")
    estimated_compute_cost_monthly: float = 0.0

    # Storage
    storage_gb_total: float = 0.0
    storage_cost_per_gb: float = 0.0
    estimated_storage_cost_monthly: float = 0.0

    # I/O
    bytes_scanned_per_month: float = 0.0
    io_cost_per_mb: float = 0.0
    estimated_io_cost_monthly: float = 0.0

    # Licensing (on-prem platforms only)
    has_license_cost: bool = False
    license_type: str = Field(default="unknown", description="enterprise | standard | developer | community | unknown")
    estimated_license_cost_monthly: float = Field(default=0.0, description="amortized annual license / 12")

    # Derived
    total_estimated_monthly_cost: float = 0.0
    cost_per_query: float = 0.0
    cost_per_gb_scanned: float = 0.0

    # Actuals available?
    costs_from_billing_api: bool = Field(default=False, description="True if pulled from cloud billing API vs. estimated")
