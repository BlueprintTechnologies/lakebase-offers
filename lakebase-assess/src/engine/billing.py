"""Default billing calculator with YAML-driven platform rates and cost delta calculation."""

import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# Default rates when YAML is unavailable
DEFAULT_RATES: dict[str, dict[str, Any]] = {
    "snowflake": {
        "base_compute": 28.0,
        "compute_unit": "credit",
        "storage": 0.023,
        "storage_unit": "GB/mo",
        "io": 0.000005,
        "io_unit": "MB",
        "scaling": 0.3,
        "scaling_condition": "concurrency > 50",
    },
    "redshift": {
        "base_compute": 0.25,
        "compute_unit": "node-hr",
        "storage": 0.024,
        "storage_unit": "GB/mo",
        "io": 0.000001,
        "io_unit": "MB",
        "scaling": 0.2,
        "scaling_condition": "ra3/managed",
    },
    "bigquery": {
        "base_compute": 0.0,
        "compute_unit": "compute_free",
        "storage": 0.02,
        "storage_unit": "GB/mo",
        "io": 0.000002,
        "io_unit": "MB",
        "scaling": 0.25,
        "scaling_condition": "BI Engine",
    },
    "synapse": {
        "base_compute": 0.42,
        "compute_unit": "DWU-hr",
        "storage": 0.015,
        "storage_unit": "GB/mo",
        "io": 0.000001,
        "io_unit": "MB",
        "scaling": 0.15,
        "scaling_condition": "dedicated",
    },
    "oracle": {
        "base_compute": 0.0028,
        "compute_unit": "core-hr (amortized)",
        "storage": 0.035,
        "storage_unit": "GB/mo",
        "io": 0.0000008,
        "io_unit": "MB",
        "scaling": 0.4,
        "scaling_condition": "HA/DR",
    },
    "vertica": {
        "base_compute": 0.0028,
        "compute_unit": "core-hr (amortized)",
        "storage": 0.035,
        "storage_unit": "GB/mo",
        "io": 0.0000008,
        "io_unit": "MB",
        "scaling": 0.4,
        "scaling_condition": "HA/DR",
    },
    "teradata": {
        "base_compute": 0.0028,
        "compute_unit": "core-hr (amortized)",
        "storage": 0.035,
        "storage_unit": "GB/mo",
        "io": 0.0000008,
        "io_unit": "MB",
        "scaling": 0.4,
        "scaling_condition": "HA/DR",
    },
    "databricks_sql": {
        "base_compute": 0.072,
        "compute_unit": "DBU",
        "storage": 0.04,
        "storage_unit": "GB/mo",
        "io": 0.0,
        "io_unit": "N/A",
        "scaling": 0.0,
        "scaling_condition": "none",
    },
}

# Estimate Databricks SQL (Lakebase) rates
LAKEBASE_RATES = {
    "compute_dbu": 0.06,
    "storage": 0.04,
    "storage_unit": "GB/mo",
    "query_cost": 0.005,
    "query_cost_unit": "per_query",
    "efficiency_gain_pct": 0.3,  # Estimated 30% efficiency gain from Delta optimization
}


class BillingCalculator:
    """Calculate current platform costs vs projected Lakebase costs."""

    def __init__(self, pricing_map_path: str | None = None) -> None:
        self._pricing_map: dict[str, Any] = {}
        self._rates: dict[str, dict[str, Any]] = dict(DEFAULT_RATES)

        if pricing_map_path:
            p = Path(pricing_map_path)
            if p.exists():
                with open(p) as f:
                    self._pricing_map = yaml.safe_load(f) or {}
                # Override defaults with YAML values
                if "platform_rates" in self._pricing_map:
                    for platform, rates in self._pricing_map["platform_rates"].items():
                        platform_lower = platform.lower().replace(" ", "_").replace("-", "_")
                        self._rates[platform_lower] = rates

    def calculate_cost_delta(
        self,
        platform_key: str,
        platform_display: str,
        scores: list[Any],
    ) -> dict[str, Any]:
        """Calculate cost delta for a platform based on scored workloads.

        ESTIMATED_MONTHLY_COST =
            (COMPUTE_HOURS × BASE_COMPUTE_RATE)
            + (STORAGE_GB × STORAGE_RATE_GB)
            + (QUERY_MB_SCANNED × IO_RATE_MB)
            + (PEAK_CONCURRENCY × SCALING_MULTIPLIER)
        """
        rates = self._rates.get(platform_key, self._rates.get("databricks_sql", DEFAULT_RATES["databricks_sql"]))

        # Aggregate signals from scored workloads
        total_compute_hours = 0.0
        total_storage_gb = 0.0
        total_query_mb = 0.0
        peak_concurrency = 0
        total_queries = 0
        total_rows = 0

        for s in scores:
            # Extract metrics from score results or underlying payload
            # We derive from score attributes where available
            if hasattr(s, "raw_score") or hasattr(s, "identifier"):
                # This is a WorkloadScore - we use it as a proxy
                total_queries += 1
                # Estimate compute hours from score intensity
                compute_proxy = s.raw_score / 10.0 if hasattr(s, "raw_score") else 0
                total_compute_hours += max(compute_proxy, 0.1)

        # Platform-level signals
        for s in scores:
            if hasattr(s, "raw_score"):
                peak_concurrency = max(peak_concurrency, int(s.raw_score / 5.0))

        if total_compute_hours == 0:
            total_compute_hours = 10.0  # Minimum baseline
        if total_storage_gb == 0:
            total_storage_gb = 50.0  # Minimum baseline
        if total_query_mb == 0:
            total_query_mb = 1000.0  # Minimum baseline

        # Current platform cost
        compute_cost = total_compute_hours * rates["base_compute"]
        storage_cost = total_storage_gb * rates["storage"]
        io_cost = total_query_mb * rates["io"]
        scaling_mult = rates["scaling"] if peak_concurrency > 50 else 0.0
        scaling_cost = peak_concurrency * scaling_mult

        current_cost = compute_cost + storage_cost + io_cost + scaling_cost

        # Projected Lakebase cost
        lakebase_compute = total_compute_hours * LAKEBASE_RATES["compute_dbu"]
        lakebase_storage = total_storage_gb * LAKEBASE_RATES["storage"]
        lakebase_query = total_queries * LAKEBASE_RATES["query_cost"]
        lakebase_total = lakebase_compute + lakebase_storage + lakebase_query

        savings_pct = 0.0
        if current_cost > 0:
            savings_pct = ((current_cost - lakebase_total) / current_cost) * 100

        # Efficiency metrics
        compute_hours_saved = total_compute_hours * LAKEBASE_RATES["efficiency_gain_pct"]
        cost_per_query_current = current_cost / max(total_queries, 1)
        cost_per_query_lakebase = lakebase_total / max(total_queries, 1)

        return {
            "platform": platform_display,
            "platform_key": platform_key,
            "current_estimated_monthly_cost": round(current_cost, 2),
            "projected_lakebase_cost": round(lakebase_total, 2),
            "savings_pct": round(savings_pct, 1),
            "efficiency_gain": {
                "compute_hours_saved": round(compute_hours_saved, 2),
                "cost_per_query_current": round(cost_per_query_current, 4),
                "cost_per_query_lakebase": round(cost_per_query_lakebase, 4),
                "efficiency_gain_pct": LAKEBASE_RATES["efficiency_gain_pct"] * 100,
            },
        }

    def get_rates_for_platform(self, platform: str) -> dict[str, Any]:
        """Get the rate card for a specific platform."""
        key = platform.lower().replace(" ", "_").replace("-", "_")
        return self._rates.get(key, DEFAULT_RATES.get(key, DEFAULT_RATES["databricks_sql"]))
