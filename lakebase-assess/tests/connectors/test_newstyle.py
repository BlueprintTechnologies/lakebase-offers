import pytest
import inspect
from src.connectors import __all__ as all_connectors

# Dynamically import all connectors
connectors = {}
for name in all_connectors:
    # Simple mapping: OnPremDumpConnector -> onprem_dump, BigQueryConnector -> bigquery, etc.
    module_name = name.lower().replace("connector", "")
    # Handle special cases
    if name == "OnPremDumpConnector":
        module_name = "onprem_dump"
    else:
        module_name = module_name.replace("bigquery", "bigquery").replace("databricks", "databricks")
    
    module_path = f"src.connectors.{module_name}"
    try:
        connectors[name] = __import__(module_path, fromlist=["*"]).__dict__[name]
    except ModuleNotFoundError as e:
        # Try alternative naming convention
        print(f"Warning: {module_path} not found, trying alternative: {e}")
        # Handle special cases like onprem_dump
        if "onprem" in name.lower():
            module_alt = "onprem_dump"
        else:
            module_alt = name.lower().replace("connector", "")
        module_path = f"src.connectors.{module_alt}"
        connectors[name] = __import__(module_path, fromlist=["*"]).__dict__[name]

def test_all_connectors_can_be_imported():
    # Make sure each connector can be imported without error
    for name, cls in connectors.items():
        assert cls is not None, f"Failed to import {name}"

def test_connector_base_methods_exist():
    # Ensure each connector implements the required abstract methods from BaseConnector
    required_methods = [
        "validate_credentials",
        "fetch_query_history",
        "fetch_table_metadata",
        "fetch_concurrency_signals",
        "fetch_cost_signals",
        "fetch_security_patterns",
    ]
    for name, cls in connectors.items():
        for method in required_methods:
            assert hasattr(cls, method), f"{name} missing method {method}"
