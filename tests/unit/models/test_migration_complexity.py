"""Tests for MigrationComplexitySignals and related models."""

import pytest
from src.models.migration_complexity import (
    UDFRecord,
    StoredProcRecord,
    BinaryColumnRecord,
    MigrationComplexitySignals,
)


class TestUDFRecord:
    def test_basic_construction(self):
        udf = UDFRecord(name="my_func", language="Python", is_portable=True)
        assert udf.name == "my_func"
        assert udf.language == "Python"
        assert udf.is_portable is True

    def test_non_portable(self):
        udf = UDFRecord(name="c_udf", language="C", is_portable=False)
        assert udf.is_portable is False


class TestStoredProcRecord:
    def test_basic_construction(self):
        sp = StoredProcRecord(
            name="process_orders",
            line_count=200,
            has_loops=True,
            has_external_calls=False,
            has_ddl=True,
            migration_path="notebook",
        )
        assert sp.name == "process_orders"
        assert sp.line_count == 200
        assert sp.has_loops is True
        assert sp.migration_path == "notebook"


class TestBinaryColumnRecord:
    def test_basic_construction(self):
        bcr = BinaryColumnRecord(
            table="files",
            column="content",
            data_type="BLOB",
            migration_path="base64_string",
        )
        assert bcr.table == "files"
        assert bcr.data_type == "BLOB"
        assert bcr.migration_path == "base64_string"


class TestMigrationComplexitySignals:
    def test_defaults(self):
        mc = MigrationComplexitySignals(platform="snowflake")
        assert mc.platform == "snowflake"
        assert mc.udf_count == 0
        assert mc.udf_records == []
        assert mc.stored_proc_count == 0
        assert mc.stored_proc_records == []
        assert mc.trigger_count == 0
        assert mc.binary_column_count == 0
        assert mc.estimated_migration_weeks == 0.0
        assert mc.has_unsupported_types is False

    def test_full_construction(self):
        udfs = [UDFRecord(name="f1", language="SQL", is_portable=True)]
        sps = [StoredProcRecord(
            name="sp1", line_count=100, has_loops=False,
            has_external_calls=False, has_ddl=False, migration_path="sql_udf",
        )]
        mc = MigrationComplexitySignals(
            platform="oracle",
            udf_count=1,
            udf_records=udfs,
            stored_proc_count=1,
            stored_proc_records=sps,
            trigger_count=3,
            binary_column_count=2,
            estimated_migration_weeks=8.0,
            has_unsupported_types=True,
        )
        assert mc.udf_count == 1
        assert len(mc.udf_records) == 1
        assert mc.stored_proc_count == 1
        assert mc.trigger_count == 3
        assert mc.has_unsupported_types is True
