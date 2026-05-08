"""Tests for TableMetadata and TableMetadataCollection models."""

import pytest
from src.models.table_metadata import TableMetadata, TableMetadataCollection, ColumnSpec


class TestColumnSpec:
    def test_basic_creation(self):
        col = ColumnSpec(name="id", data_type="INT")
        assert col.name == "id"
        assert col.data_type == "INT"
        assert col.is_nullable is True
        assert col.is_primary_key is False
        assert col.is_foreign_key is False

    def test_primary_key(self):
        col = ColumnSpec(name="id", data_type="BIGINT", is_primary_key=True, is_nullable=False)
        assert col.is_primary_key is True
        assert col.is_nullable is False

    def test_optional_stats(self):
        col = ColumnSpec(name="x", data_type="VARCHAR", distinct_count=100, null_count=5)
        assert col.distinct_count == 100
        assert col.null_count == 5


class TestTableMetadata:
    def test_basic_creation(self):
        t = TableMetadata(
            database="db", schema_name="public",
            table_name="orders", table_type="TABLE",
        )
        assert t.database == "db"
        assert t.table_name == "orders"
        assert t.table_type == "TABLE"

    def test_defaults(self):
        t = TableMetadata(
            database="db", schema_name="public",
            table_name="t", table_type="TABLE",
        )
        assert t.row_count is None
        assert t.storage_size_bytes is None
        assert t.is_partitioned is False
        assert t.is_sensitive is False
        assert t.is_stale_stats is False
        assert t.columns == []
        assert t.tags == []

    def test_with_columns(self):
        cols = [
            ColumnSpec(name="id", data_type="INT", is_primary_key=True),
            ColumnSpec(name="name", data_type="VARCHAR"),
        ]
        t = TableMetadata(
            database="db", schema_name="s", table_name="t", table_type="TABLE",
            columns=cols, column_count=2,
        )
        assert len(t.columns) == 2
        assert t.column_count == 2

    def test_sensitive_flag(self):
        t = TableMetadata(
            database="db", schema_name="s", table_name="pii_data", table_type="TABLE",
            is_sensitive=True,
        )
        assert t.is_sensitive is True

    def test_partitioned_table(self):
        t = TableMetadata(
            database="db", schema_name="s", table_name="events", table_type="TABLE",
            is_partitioned=True, partition_column="created_at",
        )
        assert t.is_partitioned is True
        assert t.partition_column == "created_at"

    def test_growth_rate_fields(self):
        t = TableMetadata(
            database="db", schema_name="s", table_name="t", table_type="TABLE",
            row_count=1000, row_count_30d_ago=800, monthly_growth_rate_pct=25.0,
            is_fast_growing=True,
        )
        assert t.monthly_growth_rate_pct == 25.0
        assert t.is_fast_growing is True


class TestTableMetadataCollection:
    def _make_table(self, name="orders", row_count=100, storage=1024,
                    sensitive=False, table_type="TABLE"):
        return TableMetadata(
            database="db", schema_name="public",
            table_name=name, table_type=table_type,
            row_count=row_count, storage_size_bytes=storage,
            is_sensitive=sensitive,
        )

    def test_empty_collection(self):
        tmc = TableMetadataCollection(platform="test")
        assert tmc.tables == []
        assert tmc.total_tables_fetched == 0

    def test_has_large_tables_true(self):
        t = self._make_table(row_count=20_000_000)
        tmc = TableMetadataCollection(platform="test", tables=[t])
        assert tmc.has_large_tables is True

    def test_has_large_tables_false(self):
        t = self._make_table(row_count=100)
        tmc = TableMetadataCollection(platform="test", tables=[t])
        assert tmc.has_large_tables is False

    def test_has_sensitive_tables_true(self):
        t = self._make_table(sensitive=True)
        tmc = TableMetadataCollection(platform="test", tables=[t])
        assert tmc.has_sensitive_tables is True

    def test_has_sensitive_tables_false(self):
        t = self._make_table(sensitive=False)
        tmc = TableMetadataCollection(platform="test", tables=[t])
        assert tmc.has_sensitive_tables is False

    def test_has_materialized_views_true(self):
        t = self._make_table(table_type="MATERIALIZED_VIEW")
        tmc = TableMetadataCollection(platform="test", tables=[t])
        assert tmc.has_materialized_views is True

    def test_has_materialized_views_false(self):
        t = self._make_table(table_type="TABLE")
        tmc = TableMetadataCollection(platform="test", tables=[t])
        assert tmc.has_materialized_views is False

    def test_database_and_schema_counts(self):
        tmc = TableMetadataCollection(
            platform="test", tables=[self._make_table()],
            database_count=3, schema_count=5,
        )
        assert tmc.database_count == 3
        assert tmc.schema_count == 5

    def test_totals(self):
        tmc = TableMetadataCollection(
            platform="test", tables=[self._make_table()],
            total_row_count=1000, total_storage_bytes=1024 * 1024,
        )
        assert tmc.total_row_count == 1000
        assert tmc.total_storage_bytes == 1024 * 1024
