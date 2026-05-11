"""Default billing calculator with YAML-driven platform rates and cost delta calculation."""

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from src.models.cost_signals import CostSignals

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
        cost_signals: CostSignals | None = None,
        scores: list[Any] | None = None,  # fallback only
    ) -> dict[str, Any]:
        """Calculate cost delta for a platform.

        Primary data source: CostSignals from connectors (actual usage data).
        Fallback: score-based proxy estimates.

        ESTIMATED_MONTHLY_COST =
            (COMPUTE_COST) + (STORAGE_COST) + (IO_COST) + (LICENSE_COST)
        """
        rates = self._rates.get(platform_key, self._rates.get("databricks_sql", DEFAULT_RATES["databricks_sql"]))

        if cost_signals:
            # -- real cost data (item 4: actual usage metrics) -- #
            current_cost = cost_signals.total_estimated_monthly_cost
            storage_gb = cost_signals.storage_gb_total
            bytes_scanned = cost_signals.bytes_scanned_per_month

            # Compute the Lakebase equivalent
            lakebase_compute = cost_signals.estimated_compute_cost_monthly * (1 - LAKEBASE_RATES["efficiency_gain_pct"])
            lakebase_storage = storage_gb * LAKEBASE_RATES["storage"]
            lakebase_io = (bytes_scanned / (1024 * 1024)) * 0.005 if bytes_scanned else 0.0
            lakebase_total = lakebase_compute + lakebase_storage + lakebase_io

            # Account for license savings (Lakebase doesn't need separate licenses)
            license_savings = cost_signals.estimated_license_cost_monthly if cost_signals.has_license_cost else 0.0
            lakebase_total -= license_savings

            total_queries = int(cost_signals.compute_units_per_month) if cost_signals.compute_unit_name == "query-hr (estimated)" else 0
            peak_concurrency = 0
            total_compute_hours = cost_signals.compute_units_per_month
            total_query_mb = bytes_scanned / (1024 * 1024) if bytes_scanned else 0
        else:
            # -- proxy fallback (existing behavior) -- #
            scores = scores or []
            total_compute_hours = 0.0
            total_storage_gb = 0.0
            total_query_mb = 0.0
            peak_concurrency = 0
            total_queries = 0

            for s in scores:
                if hasattr(s, "raw_score") or hasattr(s, "identifier"):
                    total_queries += 1
                    compute_proxy = s.raw_score / 10.0 if hasattr(s, "raw_score") else 0
                    total_compute_hours += max(compute_proxy, 0.1)

            for s in scores:
                if hasattr(s, "raw_score"):
                    peak_concurrency = max(peak_concurrency, int(s.raw_score / 5.0))

            if total_compute_hours == 0:
                total_compute_hours = 10.0
            if total_storage_gb == 0:
                total_storage_gb = 50.0
            if total_query_mb == 0:
                total_query_mb = 1000.0

            current_cost = total_compute_hours * rates["base_compute"] + total_storage_gb * rates["storage"] + total_query_mb * rates["io"]
            lakebase_compute = total_compute_hours * LAKEBASE_RATES["compute_dbu"]
            lakebase_storage = total_storage_gb * LAKEBASE_RATES["storage"]
            lakebase_io = total_query_mb * 0.005
            lakebase_total = lakebase_compute + lakebase_storage + lakebase_io
            license_savings = 0.0
            total_queries = total_queries
            bytes_scanned = total_query_mb * 1024 * 1024

        savings_pct = 0.0
        if current_cost > 0:
            savings_pct = ((current_cost - lakebase_total) / current_cost) * 100

        compute_hours_saved = total_compute_hours * LAKEBASE_RATES["efficiency_gain_pct"]
        cost_per_query_current = current_cost / max(total_queries, 1)
        cost_per_query_lakebase = lakebase_total / max(total_queries, 1)

        return {
            "platform": platform_display,
            "platform_key": platform_key,
            "current_estimated_monthly_cost": round(current_cost, 2),
            "projected_lakebase_cost": round(max(lakebase_total, 0), 2),
            "savings_pct": round(savings_pct, 1),
            "cost_data_source": "actual_signals" if cost_signals else "proxy_estimates",
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
