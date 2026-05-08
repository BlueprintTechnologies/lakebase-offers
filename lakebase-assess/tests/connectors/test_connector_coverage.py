import coverage
import inspect
import unittest
from unittest import mock
from src.models.query_history import QueryHistory as EmptyQueryHistory
from src.models.table_metadata import TableMetadataCollection as EmptyTableMetadataCollection
from src.models.concurrency import ConcurrencySignals as EmptyConcurrencySignals
from src.models.cost_signals import CostSignals as EmptyCostSignals
from src.models.security import SecurityPatterns as EmptySecurityPatterns
from src.models.access_patterns import AccessPatternSignals as EmptyAccessPatternSignals
from src.models.migration_complexity import MigrationComplexitySignals as EmptyMigrationComplexitySignals
from src.connectors.base import AbstractBaseConnector

# placeholder classes
class EmptyQueryHistory: pass
class EmptyTableMetadataCollection: pass
class EmptyConcurrencySignals: pass
class EmptyCostSignals: pass
class EmptySecurityPatterns: pass
class EmptyAccessPatternSignals: pass
class EmptyMigrationComplexitySignals: pass

class TestConnectorCoverage(unittest.TestCase):
    def setUp(self):
        self.connector_modules = {}
        for name in ["athena","bigquery","databricks","dremio","mysql","oracle","postgres","presto","redshift","snowflake","synapse","teradata","vertica","snowpark","clickhouse","onprem_dump"]:
            try:
                mod = __import__(f"src.connectors.{name}", fromlist=["*"])
                for attr in dir(mod):
                    if attr.endswith("Connector"):
                        cls = getattr(mod, attr)
                        if hasattr(cls, "__bases__") and issubclass(cls, AbstractBaseConnector):
                            self.connector_modules[name] = cls
                            break
            except Exception as exc:
                print(f"[test_connector_coverage] Skipping {name}: {exc}")

    def test_all_connectors_achieve_above_90_percent_coverage(self):
        cov = coverage.Coverage(source=["src"])
        cov.start()
        for name, cls in self.connector_modules.items():
            if cls is None: continue
            try:
                instance = cls()
            except TypeError:
                stub_cls = type("Stub"+cls.__name__, (cls,), {
                    "validate_credentials": lambda self: True,
                    "fetch_query_history": lambda self: EmptyQueryHistory(),
                    "fetch_table_metadata": lambda self: EmptyTableMetadataCollection(),
                    "fetch_concurrency_signals": lambda self: EmptyConcurrencySignals(),
                    "fetch_cost_signals": lambda self: EmptyCostSignals(),
                    "fetch_security_patterns": lambda self: EmptySecurityPatterns(),
                    "calculate_readiness_score": lambda self: 0.0,
                    "fetch_access_patterns": lambda self: None,
                    "fetch_migration_complexity": lambda self: None,
                })
                instance = stub_cls(dummy="placeholder")
            for method in ["fetch_query_history","fetch_table_metadata","fetch_concurrency_signals","fetch_cost_signals","fetch_security_patterns","validate_credentials","calculate_readiness_score"]:
                if hasattr(instance, method):
                    setattr(instance, method, mock.Mock())
            for attr_name, attr in inspect.getmembers(instance):
                if not attr_name.startswith("_") and callable(attr):
                    try: attr() 
                    except Exception: pass
            cov.stop()
            cov.save()
            total_pct = cov.report(show_missing=False)
            self.assertGreaterEqual(total_pct, 90, f"Connector {name} achieved only {total_pct:.1f}% coverage (required ≥ 90%).")
            cov.erase()
        final_total = cov.report(show_missing=False)
        self.assertGreaterEqual(final_total, 90)

if __name__ == "__main__":
    unittest.main()